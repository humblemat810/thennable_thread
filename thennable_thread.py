from threading import Thread, Event
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
    @end_event_decorator(end_event)
    def run(self):
        try:
            if self._target is not None:
                self._return = self._target(*self._args,
                                                    **self._kwargs)
        finally:
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

class thennable_thread(ThreadWithReturnValue):
    parent : "thennable_thread" = None
    children: List['thennable_thread'] = []
    
    error_event = Event()
    
    def __init__(self, *arg, thennable = False, **kwarg):
        super().__init__(*arg, **kwarg)
        self.chainnable = True
        self.thennable = thennable
        self.state = "pending"
        self._error = None

    def resolve(self, value):
        self.state = 'fullfilled'
        self._return = value
    def reject(self, reason):
        self.state = 'rejected'
        try:
            raise(ChainException(reason))
        except ChainException as e:
            pass
        self.error(e)
    def error(self, reason):
        self._error = reason
        self.error_event.set()
        for c in self.children:
            c.error(reason)
    #@end_event_decorator(end_event=end_event)
    def run(self):
        try:
            super().run()
        except Exception as e:
            self.error(e)
    
    
        
    def done(self, other):
        return self.then(other)
        
    def then(self, other, args = None, chainnable=None, kwarg = None):
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
        
        def await_start_next(last_th, next_th):
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
        wsn_th = Thread(target= await_start_next, args = [self, th_other])
        wsn_th.start()
        return th_other
    def catch(self, other):
        self.then(other, self._error)
        return self
    def finally_(self, other):
        self.then(other)
        return self

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
    def f (*arg):
        time.sleep(4)
        print("f", arg)
        return 'ff' + str(arg)
    def g (*arg, **kwarg):
        print('g',arg, kwarg)
        return str(arg) + "gg"
    def h (err):
        if err is None:
            pass
        else:
            raise (BaseException(str(err)))
    # thth1 = Deferred(target = f, args = ['asd', 12], kwargs = {})
    # thth2 = thth1.then(g).catch(h)
    # thth1.start()
    # Promise(thennable_thread(target=f), args = [])
    #thth2.when([f]).done(h)
    prom = when([f])
    prom.th.end_event.wait()
    print(prom.th.end_event.is_set())
    print(type(prom))
    
    prom.done(g)
    