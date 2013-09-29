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


from vsa.infra.params import ObjState, ReqState
from vsa.events.VSAEvents import SevEnum, Callist
from vsa.client.component_handler import get_columns
from vsa.model.san_container import SanContainer
from vsa.infra.params import AlarmType


class SanBase(object): # SAN Base Class
    child_obj=[]
    add_commands=[]
    set_params=[]
    #show_columns=['name','description']
    must_fields=[]
    newonly_fields=[]    # fields to allow to set on new objects only
    loadmode_fields=[]    # newonly fields to allow to set on existing objects if in load mode
    class_actions=[]
    #ui_buttons=[]

    def __init__(self,name='N/A',desc="Base San Object"):
        """
        The description of __init__ comes here.
        @param name
        @param desc
        @return
        """
        self.name=name
        sc = SanContainer.getInstance()
        self.san_interface = sc.get_san()

        self.description = desc
        self.fullpath=''
        self.parent = None
        self.exposed = True   # should it be exposed to users (may be an internal or hidden)
        self.state=ObjState.created
        self.alarmstate=SevEnum.none
        self.reqstate=ReqState.enabled
        self.error=False
        self.errstr=''
        self.handlerclass=''
        self.icon=''
        self.__dict__['_updatedattr']=[]
        self.before_update=Callist()
        self.after_update=Callist()
##        self.on_events = Callist() # Event log

    def __setattr__( self, name, val):
        """
        The description of __setattr__ comes here.
        @param name
        @param val
        @return
        """
        if hasattr(self,'before_update') and name in self.__class__.set_params: # TBD look into it
            if self.before_update(self,'before_update','value_changed',params={'name':name,'value':val})[0] : return # if callback returned true than dont update

        if not hasattr(self,'_updatedattr') : self.__dict__['_updatedattr']=[]
        if (name in self.__class__.set_params) and (name not in self._updatedattr) : self._updatedattr.append(name)
        # can do some lock here for multi-thread
        #self.__dict__[name] = val
        object.__setattr__(self, name, val)
        if hasattr(self,'after_update') and name in self.__class__.set_params:
            self.after_update(self,'after_update','value_changed',params={'name':name,'value':val})

    def get_object_type(self):
        """
        return string with object type name
        """
        return self.__class__.__name__

    def change_state(self,new,errstr='',params={},silent=False):
        """
        The description of change_state comes here.
        @param new
        @param errstr
        @param params
        @param silent
        @return
        """
        san = self.san_interface

        if str(new) not in ObjState._keys:
            self.substate = new
            new = ObjState.other

        params['oldstate'] = str(self.state)
        params['newstate'] = str(new)

        if new != self.state and str(new) in ['error','absent','degraded']:
            self.error = True
            self.errstr = errstr
            params['errstr'] = errstr
            if not self.on_error(self.state,new,params):
                san.alarms.process_event(self,AlarmType.error,params)
        else:
            self.error = False
            self.errstr = ''

        if self.state != ObjState.created and new != self.state:
            if not self.on_state_change(self.state,new,params):
                if not silent:
                    san.alarms.process_event(self,AlarmType.state_change,params)
        old = self.state
        self.state = new
        if new != old:
            self.after_state_change(old,new,errstr,params,silent)

        # returns true is state actually changed
        return (new != old)

    def on_state_change(self,old,new,params={}):
        """
        The description of on_state_change comes here.
        @param old
        @param new
        @param params
        @return
        """
        return 0

    def after_state_change(self,old,new,errstr='',params={},silent=False):
        """
        The description of after_state_change comes here.
        @param old
        @param new
        @param errstr
        @param params
        @param silent
        @return
        """
        return 0

    def on_error(self,old,new,params={}):
        """
        The description of on_error comes here.
        @param old
        @param new
        @param params
        @return
        """
        return 0

    def _flush(self):
        """
        The description of _flush comes here.
        @return
        """
        self.__dict__['_updatedattr']=[]

    def __repr__(self) :
        """
        The description of __repr__ comes here.
        @return
        """
        par=''
        if self.parent  : par=self.parent.name + '/'
        return '%s:%s%s' % (self.__class__.__name__,par,self.name)

    def __str__(self) :
        """
        The description of __str__ comes here.
        @return
        """
        return self.__repr__()

    def show(self,mode=0,level=0,ident=''):
        """
        The description of show comes here.
        @param mode
        @param level
        @param ident
        @return
        """
        return '%s%s' % (ident,self.name)

    def ui_getdetail(self,ident=''):
        """
        The description of ui_getdetail comes here.
        @param ident
        @return
        """
        out=[ident+self.fullpath,ident+self.description,ident+'State=%s  %s' % (self.state,self.errstr),ident+'Alarm State=%s' % self.alarmstate,ident+'Requested (User) State=%s' % self.reqstate]
        i=0; r=self.ui_getrow()
        for c in get_columns(self):
            out+=[ident+'%s=%s' % (c,r[i])]
            i+=1
        return '\n'.join(out)

    def ui_getrow(self):
        """
        The description of ui_getrow comes here.
        @return
        """
        out=[]
        for k in get_columns(self):
            i=k.lower()
            if i in self.__dict__ :
                if self.__dict__[i].__class__.__name__ in ['int','str','IP','list','dict','EnumValue','bool'] :
                    out+=[str(self.__dict__[i])]
                elif hasattr(self.__dict__[i],'name'):
                    out+=[self.__dict__[i].name]
                else : out+=['??']
        return out

    def update(self, flags=''):
        """
        The description of update comes here.
        @param flags
        @return
        """
        return (0,'')

    def export(self, san, path, canadd=False, exclude=[]):
        """
        The description of export comes here.
        @param san
        @param path
        @param canadd
        @param exclude
        @return
        """
        out = []
        noupdate = ''
        for i in self.set_params:
            if i not in exclude:
                g = san.getobj(self,i)
                d = san._defaults.get(self.__class__.__name__+'.'+i, '')
                isdict = getattr(self,i).__class__.__name__ == 'dict'
                if d and d == g:
                    g = None
                if g:
                    if isdict:
                        out += ['set %s/%s %s' % (path,i,g)]
                    else:
                        out += ['set %s %s=%s' % (path,i,g)]
                    noupdate = ' -n'
        if out:
            out = [l+' -n' for l in out[:-1]]+[out[-1]]
        for c in self.child_obj:
            out += self.__dict__[c].export(san,path+'/'+c)
        if (out and canadd) or getattr(self, 'alwaysadd', False):
            p = path.split('/')
            out = ['add %s %s%s' % ('/'.join(p[:-1]),p[-1],noupdate)] + out
        return out
