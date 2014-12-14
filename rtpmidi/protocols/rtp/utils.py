class  Singleton (object):
    instances = {}
    def __new__(cls, *args, **kargs):
        if Singleton.instances.get(cls) is None:
            Singleton.instances[cls] = object.__new__(cls, *args, **kargs)
        return Singleton.instances[cls]

class TestSingleton(Singleton):
    def __init__(self, argr):
        self.test = 10
        self.arg = argr

    def tt(self):
        self.o = 69

"""
class Singleton:
       class __OnlyOne:
              def __init__(self):
                     pass


       instance = {}
       def __init__(self):
              if not self.__class__ in Singleton.instance:
                     Singleton.instance[self.__class__] = Singleton.__OnlyOne()
                     #return True
              else :
                     print 'warning : trying to recreate a singleton'
                     #return False


       def __getattr__(self, name):
              return getattr(self.instance[self.__class__], name)


       def __setattr__(self, name, value):
              return setattr(self.instance[self.__class__], name, value)



singletons = {}
class Singleton(object):
       def __new__(cls, *args, **kwargs):
        if cls in singletons:
               return singletons[cls]
        self = object.__new__(cls)
        cls.__init__(self, *args, **kwargs)
        singletons[cls] = self
        return self


class Singleton(object):
    _ref = None

    def __new__(cls, *args, **kw):
        if cls._ref is None:
            cls._ref = super(Singleton, cls).__new__(cls, *args, **kw)

        return cls._ref

def pitch_cmp(x, y):
    if x[0][1] > y[0][1]:
        return 1
    elif x[0][1] > y[0][1]:
        return 0
    else:
        return -1

"""



if __name__ == "__main__":
    e = TestSingleton(42)
    e.tt()
    a = TestSingleton(44)

    print e.arg
    print e.o
    print a.o

