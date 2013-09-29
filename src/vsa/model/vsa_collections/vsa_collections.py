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


from vsa.infra.infra import iif, val2str, getnextidx
from vsa.events.VSAEvents import SevEnum
from vsa.infra.params import AlarmType
from vsa.infra import logger
from vsa.model.san_container import SanContainer
from vsa.client.component_handler import get_columns
from vsa.model.vsa_collections.ref_dict import RefDict


class VSACollection(dict):
    def __init__(self, typ=object, owner = None,path='',candelete=False,altidx='',indexed=False,desc='',icon=''):
        """
        The description of __init__ comes here.
        @param typ
        @param owner
        @param path
        @param candelete
        @param altidx
        @param indexed
        @param desc
        @param icon
        @return
        """
        self.cclass=typ
        self.path=path
        self.description=iif(desc,desc,path.capitalize())
        self.can_delete=candelete
        self._owner = owner
        self.handlerclass=''
        self.fullpath=owner.fullpath+'/'+path
        self.altidx=altidx
        self.altdict={}
        self.indexed=indexed
        self.icon=icon
        self.on_add = None
        self.on_delete = None
        self.before_add = None
        self.before_delete = None

    def get_object_type(self):
        """
        return string with object type name
        """
        return self.__class__.__name__

    def rename(self, old,new):
        """
        The description of rename comes here.
        @param old
        @param new
        @return
        """
        if old==new : return
        v=self[old]
        v.name=new
        v.mykey=new
        v.fullpath=self.fullpath+'/'+new
        self[new]=v
        del self[old]

    def add(self, key, obj, firstidx=0):
        """
        The description of add comes here.
        @param key
        @param obj
        @param firstidx
        @return
        """
        if key in self.keys():
            return None
        if self.indexed:
            obj.__dict__[self.altidx] = getnextidx(self.altdict.keys(), firstidx)
        if self.before_add:
            if self.before_add(self,key,obj,'before_add'):
                return None
        self[key]=obj
        obj.mykey=key # TBD maybe use Name ..
        if self.altidx:
            self.altdict[getattr(obj,self.altidx)]=obj
        obj.parent=self._owner
        obj.fullpath=self.fullpath+'/'+key
        for ck,cv in obj.__dict__.items():
            if isinstance(cv,VSACollection) or isinstance(cv,RefDict):
                cv.fullpath = obj.fullpath+'/'+ck
        obj._owner=self
        mySan = SanContainer.getInstance().get_san()
        obj.san_interface = mySan
        if mySan and mySan.runmode:
            mySan.alarms.process_event(self,AlarmType.add,{
                        'name':key,
                        'path':self.fullpath,
                        'otype':obj.__class__.__name__,
                        'description':obj.description
                        })
        if hasattr(obj,'post_add'):
            obj.post_add()
        if self.on_add:
            self.on_add(self,key,obj,'on_add')
        return obj

    def delete(self, ch, force=False, skipdel=False):
        """
        The description of delete comes here.
        @param ch
        @param force
        @param skipdel
        @return
        """
        # TODO can skipdel be removed?
        key=ch.mykey
        if self.before_delete:
            if self.before_delete(self,key,'before_delete'):
                return (1,'delete blocked')# if callback returned true than dont delete
        if hasattr(ch,'delete') and not skipdel:
            (e,txt)=ch.delete(force)
            if e:
                logger.eventlog.debug('del error, object %s %s' % (key,txt))
                return (1,txt)
        if getattr(ch,'extent',False) and not skipdel:
            # first clean from usedby
            if ch.parent in ch.extent.usedby:
                ch.extent.usedby.remove(ch.parent)
            # try to unlock
            ch.extent.locked=False
# commented by AT
        mySan = SanContainer.getInstance().get_san()
        if mySan.runmode:
            mySan.alarms.process_event(self,AlarmType.delete,{
                            'name':key,
                            'path':self.fullpath,
                            'otype':ch.__class__.__name__,
                            'description':ch.description
                            })

        if self.altidx:
            del self.altdict[getattr(ch,self.altidx)]
        del ch
        del self[key]
        if self.on_delete:
            self.on_delete(self,key,'on_delete')
        return (0,'Item Deleted')

    def __call__(self, id=0):
        """
        The description of __call__ comes here.
        @param id
        @return
        """
        if id:
            return self.values()[id:]
        else:
            return self.values()

    def export(self,san,path,canadd=True):
        """
        The description of export comes here.
        @param san
        @param path
        @param canadd
        @return
        """
        out=[]
        for k in sorted(self.keys()) :
            cpath=path+'/'+k
            if hasattr(self[k],'export'):
                out+=self[k].export(san,cpath,self.can_delete)
        return out

    def print_tbl(self,ident='',width=120,idx='',lvl=0,sep=' ',all=False):
        """
        The description of print_tbl comes here.
        @param ident
        @param width
        @param idx
        @param lvl
        @param sep
        @param all
        @return
        """
        h = ['State'] + get_columns(self)
        rng=range(len(h))
        csize=[0]*len(h)
        ch=[]
        childs=(lvl>0)
        for i in rng : csize[i]=len(h[i])
        tbl=[h]
        if self.indexed : lst=[self.altdict[k] for k in sorted(self.altdict.keys())]
        else : lst=[self[k] for k in sorted(self.keys())]
        for o in lst :
            if not all and not o.exposed : continue # if not 'all' flag, skip hidden rows
            a='!'*(o.alarmstate<>SevEnum.none)
            r=[str(o.state)+a.ljust(1)]+[val2str(x) for x in o.ui_getrow()]
            tbl+=[r]
            for i in rng :
                if len(r[i])>csize[i] : csize[i]=len(r[i])
            if childs :
                txt=''
                for cobj in o.child_obj:
                    if (isinstance(o.__dict__[cobj],VSACollection) or isinstance(o.__dict__[cobj],RefDict)) and len(o.__dict__[cobj]()):
                        if not len(o.__dict__[cobj]()):
                            continue
                        txt+=ident+'  '+o.__dict__[cobj].description+' (%s):\n' % len(o.__dict__[cobj]())
                        txt+=o.__dict__[cobj].print_tbl(ident+'    ',width,lvl=lvl-1,sep=sep,all=all)+'\n'
                ch+=[txt]
        out=[]; x=0
        for l in tbl:
            txt=''
            for i in rng :
                if len(ident+txt)<width : txt+=l[i].center(csize[i])+sep
            out+=[ident+txt] #+iif(childs,ch.pop(0))
            if childs and x>0 and ch[x-1]: out+=[ch[x-1]]
            x+=1
        return '\n'.join(out)
