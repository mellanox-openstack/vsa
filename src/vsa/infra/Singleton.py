# vim: tabstop=4 shiftwidth=4 softtabstop=4
#
# Copyright 2013 Mellanox Technologies, Ltd
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.


#taken from http://www.garyrobinson.net/2004/03/python_singleto.html
#

class SingletonException(Exception):
    pass


class MetaSingleton(type):
    def __new__(metaclass, strName, tupBases, dict):
        """
        The description of __new__ comes here.
        @param metaclass
        @param strName
        @param tupBases
        @param dict
        @return
        """
        if dict.has_key('__new__'):
            raise SingletonException, 'Can not override __new__ in a Singleton'
        return super(MetaSingleton,metaclass).__new__(metaclass, strName, tupBases, dict)

    def __call__(cls, *lstArgs, **dictArgs):
        """
        The description of __call__ comes here.
        @param cls
        @param *lstArgs
        @param **dictArgs
        @return
        """
        raise SingletonException, 'Singletons may only be instantiated through getInstance()'

class Singleton(object):
    __metaclass__ = MetaSingleton

    def getInstance(cls, *lstArgs):
        """
        Call this to instantiate an instance or retrieve the existing instance.
        If the singleton requires args to be instantiated, include them the first
        time you call getInstance.
        """
        if cls._isInstantiated():
            if len(lstArgs) != 0:
                raise SingletonException, 'If no supplied args, singleton must already be instantiated, or __init__ must require no args'
        else:
            if cls._getConstructionArgCountNotCountingSelf() > 0 and len(lstArgs) <= 0:
                raise SingletonException, 'If the singleton requires __init__ args, supply them on first instantiation'
            instance = cls.__new__(cls)
            instance.__init__(*lstArgs)
            cls.cInstance = instance
        return cls.cInstance
    getInstance = classmethod(getInstance)

    def _isInstantiated(cls):
        """
        The description of _isInstantiated comes here.
        @param cls
        @return
        """
        '''
        checks if the class has instance
        @returns true if the class has instance
        '''

        return ( hasattr(cls, 'cInstance') and cls == cls.cInstance.__class__ )
    _isInstantiated = classmethod(_isInstantiated)

    def _getConstructionArgCountNotCountingSelf(cls):
        """
        The description of _getConstructionArgCountNotCountingSelf comes here.
        @param cls
        @return
        """
        '''
        calculates number of arguments passed when class was instantiated
        @return: number of arguments passed when class was instantiated
        '''
        return cls.__init__.im_func.func_code.co_argcount - 1
    _getConstructionArgCountNotCountingSelf = classmethod(_getConstructionArgCountNotCountingSelf)

    def _forgetClassInstanceReferenceForTesting(cls):
        """
        This is designed for convenience in testing -- sometimes you
        want to get rid of a singleton during test code to see what
        happens when you call getInstance() under a new situation.

        To really delete the object, all external references to it
        also need to be deleted.
        """
        try:
            delattr(cls,'cInstance')
        except AttributeError:
            # run up the chain of base classes until we find the one that has the instance
            # and then delete it there
            for baseClass in cls.__bases__:
                if issubclass(baseClass, Singleton):
                    baseClass._forgetClassInstanceReferenceForTesting()
    _forgetClassInstanceReferenceForTesting = classmethod(_forgetClassInstanceReferenceForTesting)

