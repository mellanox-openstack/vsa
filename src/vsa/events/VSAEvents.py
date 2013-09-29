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


import time
import xmlrpclib
import smtplib
from enum import Enum

SevEnum=Enum('none','info','warning','minor','major','critical')


# message category
Info = 1
Warning = 2
Minor = 3
Major = 4
Critical = 5

sev = {
    Info            : 'Info',
    Warning         : 'Warning',
    Minor           : 'Minor',
    Major           : 'Major',
    Critical        : 'Critical',
}

class Callist:
    '''Handles a list of methods and functions
    Usage:
        d = Callist()
        d += function    # Add function to end of call list
        d(*args, **kw)  # Call all functions, returns "or" + list of results
        d -= function    # Removes last matching function from list
        d -= object        # Removes all methods of object from list
    '''
    def __init__(self):
        """
        The description of __init__ comes here.
        @return
        """
        self.__callist = []

    def __add__(self, other):
        """
        The description of __add__ comes here.
        @param other
        @return
        """
        self.__callist + other.__callist
        return self

    def __iadd__(self, callback):
        """
        The description of __iadd__ comes here.
        @param callback
        @return
        """
        self.__callist.append(callback)
        return self

    def __isub__(self, callback):
        """
        The description of __isub__ comes here.
        @param callback
        @return
        """
        # If callback is a class instance,
        # remove all callbacks for that instance
        self.__callist = [ cb
            for cb in self.__callist
                if getattr(cb, 'im_self', None) != callback]

        # If callback is callable, remove the last
        # matching callback
        if callable(callback):
            for i in range(len(self.__callist)-1, -1, -1):
                if self.__callist[i] == callback:
                    del self.__callist[i]
                    return self
        return self

    def __call__(self, *args, **kw):
        """
        The description of __call__ comes here.
        @param *args
        @param **kw
        @return
        """
        r=[ callback(*args, **kw) for callback in self.__callist]
        t=0
        for i in r : t=t or i
        return t,r


class VSANotification :
    def __init__(self,name='',f=None):
        """
        The description of __init__ comes here.
        @param name
        @param f
        @return
        """
        self.name=name
        self._func=f
    def __call__(self, sender,evnt,reason='',code=0,desc='',params={}):
        """
        The description of __call__ comes here.
        @param sender
        @param evnt
        @param reason
        @param code
        @param desc
        @param params
        @return
        """
        dt=time.strftime("%d %b %Y %H:%M:%S")
        path=''
        if sender and hasattr(sender,'name') :
            path=sender.name
            if hasattr(sender,'parent') and sender.parent and hasattr(sender.parent,'name'):
                path=sender.parent.name+'.'+path
        if self._func :
            self._func(self.name,dt,sender,path,evnt,reason,code,desc,params)
        else :
            print dt+' - '+self.name,path,evnt,reason,code,desc,params

class VSANtfyXml :
    def __init__(self,name='',url='localhost:8010',f=None):
        """
        The description of __init__ comes here.
        @param name
        @param url
        @param f
        @return
        """
        self.name=name
        self.url="http://"+url
        self._func=f
    def __call__(self, sender,evnt,reason='',code=0,desc='',params={}):
        """
        The description of __call__ comes here.
        @param sender
        @param evnt
        @param reason
        @param code
        @param desc
        @param params
        @return
        """
        dt=time.strftime("%d %b %Y %H:%M:%S")
        path=''
        if sender and hasattr(sender,'name') :
            path=sender.name
            if hasattr(sender,'parent') and sender.parent and hasattr(sender.parent,'name'):
                path=sender.parent.name+'.'+path
        txt=dt+' - '+self.name,path,evnt,reason,code,desc,params
        try:
            server = xmlrpclib.ServerProxy(self.url)
        except:
            pass
        try:
            server.out(txt)
        except xmlrpclib.Fault, fault:
            print fault.faultCode
            print fault.faultString
        except :
            pass


# additional sub classes of Notification will follow

# usage example
class mycls:
    def __init__(self):
        """
        The description of __init__ comes here.
        @return
        """
        self.name='myenv'
        self._on_my_event=Callist()
    def f1(self):
        """
        The description of f1 comes here.
        @return
        """
        print 'first line'
        self._on_my_event(self,'on_change','value_changed',params={'param1':3})
        print 'secound line\n'

def test1(*args,**kwargs):
    """
    The description of test1 comes here.
    @param *args
    @param **kwargs
    @return
    """
    print 'test1 was here'


##m=mycls()
##m.f1()
##m._on_my_event+=GVNtfyEmail('ntfy',[],'my sub22')
##m.f1()
##m._on_my_event+=GVNotification('ntfy',test1)
##m.f1()



