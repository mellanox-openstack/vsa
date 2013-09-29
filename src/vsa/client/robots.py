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


from IPy import IP
from vsa.infra import logger
from vsa.infra.infra import tstint
from vsa.infra.params import ObjState
from vsa.model.san_container import SanContainer


class Robots(object):
    def __init__(self):
        """
        The description of __init__ comes here.
        @return
        """
        pass

    def setobj(self, obj, key, val='', test=0, force=False):
        """
        The description of setobj comes here.
        @param obj
        @param key
        @param val
        @param test
        @param force
        @return
        """
        san = SanContainer.getInstance().get_san()
        if getattr(obj,'private',False) and san.runmode:
            return (1,'cannot change parameter for private %s' % obj.name)
        if obj.state != ObjState.created and (key in obj.newonly_fields):
            if san.runmode:
                return (1,'parameter %s can only be set on newly created objects, try again with proper settings' % (key))
            elif key not in obj.loadmode_fields:
                return (0,'set for %s was ignored, new only field' % key)

        objcls=obj.__class__.__name__
        if test==0:
            if key not in obj._updatedattr:
                obj._updatedattr+=[key]
        if hasattr(obj,'force_update') and force:
            obj.force_update = True
        if hasattr(obj,'set_'+key):
            return getattr(obj,'set_'+key)(san,key,val,test)
        ptype=getattr(obj,key).__class__.__name__
        if ptype=='int' : return getattr(self,'set_int')(obj,key,val,test)
        if ptype=='str' : return getattr(self,'set_str')(obj,key,val,test)
        if ptype=='bool' : return getattr(self,'set_bool')(obj,key,val,test)
        if ptype=='IP' : return getattr(self,'set_IP')(obj,key,val,test)
        if ptype=='list' : return getattr(self,'set_strlist')(obj,key,val,test)
        if ptype=='dict' : return getattr(self,'set_strdict')(obj,key,val,test)
        if ptype=='EnumValue' : return getattr(self,'set_enum')(obj,key,val,test)
        if ptype=='instancemethod' : return getattr(self,'set_method')(obj,key,val,test)
        if ptype=='VSACollection' : return (1,'Cannot set value for collection, specify %s instance' % key)
        er='unknown set type %s in set %s.%s' % (ptype,obj.__class__.__name__,key)
        logger.eventlog.warning(er)
        return (1,er)

    def set_int(self,obj,key,val='',test=0,minval=None,maxval=None):
        """
        The description of set_int comes here.
        @param obj
        @param key
        @param val
        @param test
        @param minval
        @param maxval
        @return
        """
        try:
            i = int(val)
        except ValueError:
            return (1,'%s is not an integer' % val)

        if minval and i < minval:
            return (1, 'Min value is %d' % minval)
        if maxval and i > maxval:
            return (1, 'Max value is %d' % maxval)

        if test: return (0,'')

        obj.__dict__[key] = i

        return (0,'')

    def set_str(self,obj,key,val='',test=0):
        """
        The description of set_str comes here.
        @param obj
        @param key
        @param val
        @param test
        @return
        """
        if test : return (0,'')
        obj.__dict__[key]=val
        return (0,'')

    def set_bool(self,obj,key,val='',test=0):
        """
        The description of set_bool comes here.
        @param obj
        @param key
        @param val
        @param test
        @return
        """
        val=val.lower()
        if val not in ['0','1','no','yes','true','false','on','off']:
            return (1,'%s is not a boolean value' % val)
        if test : return (0,'')
        if val in ['1','yes','true','on'] : obj.__dict__[key]=True
        else : obj.__dict__[key]=False
        return (0,'')

    def set_IP(self,obj,key,val='',test=0):
        """
        The description of set_IP comes here.
        @param obj
        @param key
        @param val
        @param test
        @return
        """
        parts=val.split('.')
        if len(parts)<>4 : return (1,'%s is not a valid IP address' % val)
        for i in parts :
            if not 0 <= tstint(i) <= 255 : return (1,'%s is not a valid IP address' % val)
        if test : return (0,'')
        obj.__dict__[key]=IP(val)
        return (0,'')

    def set_strlist(self,obj,key,val='',test=0):
        """
        The description of set_strlist comes here.
        @param obj
        @param key
        @param val
        @param test
        @return
        """
        if ';' in val : sep=';'
        else : sep=','
        l=val.split(sep)
        if test : return (0,'')
        obj.__dict__[key]=l
        return (0,'')

    def set_strdict(self,obj,key,val='',test=0,validopts=[]):
        """
        The description of set_strdict comes here.
        @param obj
        @param key
        @param val
        @param test
        @param validopts
        @return
        """
        if ';' in val : sep=';'
        else : sep=','
        val=val.strip()
        dic={}
        if val and val[0]=='+' :
            val=val[1:]
            for k,v in obj.__dict__[key].items() : dic[k]=v
        if val : l=val.split(sep)
        else : l=[]
        for o in l :
            sp=o.split('=')
            if len(sp) < 2:
                return (1,'%s dictionary is missing keys' %val)
            if validopts and sp[0] not in validopts:
                return (1,'%s has invalid parameter\nUse the following options: %s' % (val, ', '.join(validopts)))
            dic[sp[0]]=sp[1]
        if test : return (0,'')
        obj.__dict__[key]=dic
        return (0,'')

    def set_enum(self,obj,key,val='',test=0):
        """
        The description of set_enum comes here.
        @param obj
        @param key
        @param val
        @param test
        @return
        """
        etype = obj.__dict__[key].enumtype
        opts = etype._keys
        if val not in opts:
            return (1,'%s is not a valid option, can only use %s' % (val, ' | '.join(opts)))
        if test:
            return (0,'')
        obj.__dict__[key] = etype.__dict__[val]
        return (0,'')

    def set_method(self,obj,key,val='',test=0):
        """
        The description of set_method comes here.
        @param obj
        @param key
        @param val
        @param test
        @return
        """
        l=val.split(',')
        if test : return (0,'')
        try:
            r=getattr(obj,key)(*l)
            if r and len(r)==2 : return r
            return (0,'')
        except Exception,err:
            return (1,'Method %s.%s with params %s failed\n%s' % (obj.__class__.__name__,key,val,err))

    def getobj(self,obj,key):
        """
        The description of getobj comes here.
        @param obj
        @param key
        @return
        """
        san = SanContainer.getInstance().get_san()
        objcls = obj.__class__.__name__
        if hasattr(obj,'get_'+key):
            return getattr(obj,'get_'+key)(san,key)
        ptype = getattr(obj,key).__class__.__name__
        if ptype=='NoneType' or ptype=='instancemethod':
            return (0,None)
        val=obj.__dict__[key]
        if ptype in ['int','str','bool','IP','EnumValue']:
            return getattr(self,'get_str')(obj,key,val)
        if ptype=='list': return getattr(self,'get_strlist')(obj,key,val)
        if ptype=='dict': return getattr(self,'get_strdict')(obj,key,val)
        er='unknown get type %s in set %s.%s' % (ptype,obj.__class__.__name__,key)
        logger.eventlog.warning(er)
        return (1,er)

    def get_str(self,obj,key,val):
        """
        The description of get_str comes here.
        @param obj
        @param key
        @param val
        @return
        """
        return (0,str(val))

    def get_strlist(self,obj,key,val):
        """
        The description of get_strlist comes here.
        @param obj
        @param key
        @param val
        @return
        """
        val=map(str,val)
        return (0,';'.join(val))

    def get_strdict(self,obj,key,val):
        """
        The description of get_strdict comes here.
        @param obj
        @param key
        @param val
        @return
        """
        pr=[]
        for p in val.keys() :
            if ' ' in val[p] : val[p]='"'+val[p]+'"'
            pr+=['%s=%s'% (p,str(val[p]))]
        return (0,','.join(pr))

    def get_volume(self,obj,key,val=None):
        """
        The description of get_volume comes here.
        @param obj
        @param key
        @param val
        @return
        """
        return (1,'error, got to get_volume')



