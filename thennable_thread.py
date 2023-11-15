from threading import Thread, Event
import traceback, inspect
class ThreadWithReturnValue(Thread):
    end_event = Event()
    
    def end_event_decorator(end_event):
        def end_event_decorator_inner(func):
            # wrapper that wrap the function
            def wrapped(self, *args, **kwargs):
                result= func(self, *args, **kwargs)
                end_event.set()
                return result
            return wrapped
        return end_event_decorator_inner
    
    def __init__(self, group=None, target=None, name=None,
                 args=(), kwargs={}):
        super().__init__(group, target, name, args, kwargs)
        self._return = None
        
    #@end_event_decorator(end_event)
    def run(self):
        try:
            if self._target is not None:
                self._return = self._target(*self._args,
                                                    **self._kwargs)
            
            # self.state = "fullfilled", run not mean fullfilled, just leave open possible
        except Exception as e:
            
            self._error = e
        finally:
            self.end_event.set()
            
            # Avoid a refcycle if the thread is running a function with
            # an argument that has a member that points to the thread.
            del self._target, self._args, self._kwargs
    def join(self):
        Thread.join(self)
        return self._return
class ChainException(BaseException):
    pass
from typing import List, Union

def await_start_next(last_th: "ThreadWithReturnValue", next_th: "ThreadWithReturnValue"):
    if last_th is not None:
        last_th.end_event.wait()
    if last_th.error_event.is_set():
        pass
    else:
        if last_th is not None:
            next_th._args = [last_th._return] + next_th._args
        else:
            #may behave insert none here
            # nothing indicate it has no result no parent
            pass
        if next_th._started.is_set():
            pass
        else:
            next_th.start()
from threading import Lock
class thennable_thread(ThreadWithReturnValue):
    parent : "thennable_thread" = None
    children: List['thennable_thread'] = []
    
    
    
    def __init__(self, *arg, thennable = False, **kwarg):
        super().__init__(*arg, **kwarg)
        self.promise_resolved_event = Event()
        self.error_event = Event()
        self.chainnable = True
        self.auto_fullfull = True
        self.thennable = thennable
        self.mutex = Lock()
        self.state = "pending"
        self._error = None
        self.th_wait_end = None
        self.resolve_value = None
        self.reject_reason = None
    def resolve(self, value):
        if self.state == "pending":
            self.state = 'fullfilled'
            
            self.resolve_value = value
        self.promise_resolved_event.set()
    def reject(self, reason):
        if self.state == "pending":
            self.state = 'rejected'
        
        self.reject_reason = reason
        self.promise_resolved_event.set()
    def error(self, reason):
        self._error = reason
        self.error_event.set()
        for c in self.children:
            c.error(reason)

        
    #@end_event_decorator(end_event=end_event)
    def run(self):
        try:
            super().run()
            
            if self.auto_fullfull:
                self.resolve(self._return)
        except Exception as e:
            self.reject(e)
        
    
        
    def done(self, other):
        return self.then(other)
        
    def then(self, other : "function", args = None, chainnable=None, kwarg = None):
        if args is None and kwarg is None:
            args = []
        th_other = thennable_thread(target=other, args=args, kwargs=kwarg )
        if self.chainnable:
            self.children.append(th_other)
        if chainnable is None:
            th_other.chainnable = self.chainnable
        else:
            th_other.chainnable = chainnable
        if th_other.chainnable:
            th_other.parent = self
        
        def await_start_next(last_th: "thennable_thread", next_th: "thennable_thread"):
            if last_th is not None:
                last_th.end_event.wait()
            if last_th.state == 'rejected':
                last_th.promise_resolved_event.wait()
                with next_th.mutex:
                    if next_th.state == "pending":
                        next_th.reject(last_th.reject_reason)
                        next_th._error = last_th._error
                        next_th.end_event.set()
            else:   
                if last_th is not None:
                    next_th._args = [last_th._return] + next_th._args
                else:
                    #may behave insert none here
                    # nothing indicate it has no result no parent
                    pass
                if next_th._started.is_set():
                    pass
                else:
                    next_th.start()
        wsn_th = Thread(target= await_start_next, args = [self, th_other])
        wsn_th.start()
        self.wsh_th = wsn_th

        return th_other
    def catch(self, other, chainnable = None):
        args = [self._error]
        th_other = thennable_thread(target=other, args=args )
        if self.chainnable:
            self.children.append(th_other)
        if chainnable is None:
            th_other.chainnable = self.chainnable
        else:
            th_other.chainnable = chainnable
        if th_other.chainnable:
            th_other.parent = self
        
        def await_start_next(last_th: "thennable_thread", next_th: "thennable_thread"):
            if last_th is not None:
                last_th.end_event.wait()
            last_th.promise_resolved_event.wait()
            if last_th.state == 'fullfilled':
                with next_th.mutex:
                    if next_th.state == "pending":
                        next_th.resolve(last_th._return)
                        next_th._return = self._return
                        next_th.end_event.set()
                        
            else: #caught error
                next_th.reject_reason = last_th.reject_reason
                if last_th is not None:
                    next_th._args = [last_th._error] + next_th._args
                else:
                    #may behave insert none here
                    # nothing indicate it has no result no parent
                    pass
                if next_th._started.is_set():
                    pass
                else:
                    next_th.start()
        wsn_th = Thread(target= await_start_next, args = [self, th_other])
        wsn_th.start()
        self.wsh_th = wsn_th
        return th_other
    def finally_(self, other, chainnable = None):
        th_final = thennable_thread(target=other)
        
        if self.chainnable:
            self.children.append(th_final)
        if chainnable is None:
            th_final.chainnable = self.chainnable
        else:
            th_final.chainnable = chainnable
        if th_final.chainnable:
            th_final.parent = self
        def await_start_next(last_th: "thennable_thread", next_th: "thennable_thread"):
            last_th.end_event.wait()
            last_th.promise_resolved_event.wait()
            if last_th.state == 'fullfilled':
                self._return = last_th._return
            next_th.state = "fullfilled"
            next_th.start()
            next_th.end_event.wait()
        wsn_th = Thread(target= await_start_next, args = [self, th_final])
        wsn_th.start()
        return th_final

# class Test(object):
#     def _decorator(foo):
#         def magic( self ) :
#             print ("start magic")
#             foo( self )
#             print ("end magic")
#         return magic
#     def haha(self):
#         self.bar()
#     @_decorator
#     def bar( self ) :
#         print ("normal call")
# class Test2(Test):
#     def buz(self):
#         super().bar()
# test = Test()
# test2 = Test2()
# test.bar()
# test2.buz()



if __name__ == "__main__":
    import time
    def e (*arg, **kwarg):
        print("e+ , prev arg = ", arg, '\n')
        raise(Exception('test for error'))
    def f (*arg):
        time.sleep(4)
        print("sleep+f, prev arg = ", arg, '\n')
        return 'ff' + str(arg)
    def g (*arg, **kwarg):
        print('g+, prev arg = ",',arg, 'prev kwarg =', kwarg, '\n')
        return str(arg) + "gg"
    def h (err):
        if err is None:
            print("h + err is none")
        else:
            raise (BaseException(str(err)))
    # thth1 = Deferred(target = f, args = ['asd', 12], kwargs = {})
    # thth2 = thth1.then(g).catch(h)
    # thth1.start()
    # Promise(thennable_thread(target=f), args = [])
    #thth2.when([f]).done(h)

    def prom_test():
        prom = when([f])
        prom.th.end_event.wait()
        print(prom.th.end_event.is_set())
        print(type(prom))
        
        prom.done(g)
    
    thth1 = thennable_thread(target = g)
    thth2 = thth1.then(g)
    thth3 = thth2.then(g)
    thth4 = thth2.then(h)
    thth5 = thth4.then(e)
    thth6 = thth5.then(g)
    thth7 = thth6.then(e)
    thth8 = thth7.catch(h)

    thth1.start()