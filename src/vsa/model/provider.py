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


from vsa.model import volstr2obj, obj2volstr, ext2path
from vsa.model.san_base import SanBase
from vsa.infra.params import ClusterState, ObjState, CACHECMDS
from vsa.model.vsa_collections import VSACollection, RefDict
from vsa.model.sanp_lun import Sanplun
from vsa.model.fc import FCport
from vsa.model.netif import Netif
from vsa.infra.infra import printsz
from vsa.infra import logger

class Provider(SanBase):
    child_obj=['ifs','disks','fcports']
    add_commands=['ifs'] # TBD add ,'portals'
    set_params=['url','cachedevices','evacuate','zone','flashcmd','role']
    newonly_fields=['role']
    #show_columns=['Name','role','url','ifs','FCs','procs','Cache','Zone']
    #ui_buttons=[add_btn,refresh_btn,rescan_btn,evacuate_btn,reboot_btn]

    def __init__(self,name='tgt1',url='',usr='root',pwd='123456'):
        """
        The description of __init__ comes here.
        @param name
        @param url
        @param usr
        @param pwd
        @return
        """
        SanBase.__init__(self,name,'Provider')
        self.url = url
        self.user = usr
        self.password = pwd
        self.clusterstate = ClusterState.none
        self.version = ''
        self.fullname = ''
        self.cachedevices = []
        self.cachevg = None
        self.cachesize = 0
        self.cachefree = 0
        self.zone = ''
        self.ifs = VSACollection(Netif,self,'ifs',desc='Network Interfaces',icon='VirtIfc_g.png')
        self.fcports = RefDict(FCport,self,'fcports',desc='FC Ports',icon='VirtIfc_g.png')
        self.disks = RefDict(Sanplun,self,'disks',desc='Physical Disks',icon='hard_disk.png',call=lambda self:[v for v in self.devdict.values() if isinstance(v,Sanplun)])
        self.devdict = {}
        self.tgtprocs = 1
        self.icon = ""
        self.wasabsent = False
        self.role = ''

    def ui_getrow(self):
        """
        The description of ui_getrow comes here.
        @return
        """
        return [self.name,self.clusterstate,self.url,len(self.ifs),len(self.fcports),self.tgtprocs,printsz(self.cachefree)+'/'+printsz(self.cachesize),self.zone]

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
        if old==ObjState.absent:
            self.wasabsent=True

    def add_ifs(self,name):
        """
        The description of add_ifs comes here.
        @param name
        @return
        """
        if not name:
            return None
        if self.ifs.has_key(name):
            return self.ifs[name]
        return self.ifs.add(name,Netif(name))

    def set_cachedevices(self,san,key,val='',test=0):
        """
        The description of set_cachedevices comes here.
        @param san
        @param key
        @param val
        @param test
        @return
        """
        if self.cachevg.state == ObjState.running:
            return (1,'cache is already configured')
        devobjs=[]
        sign=''
        first=True
        tmppvd=None
        if len(val) > 2 and val[0] in ['+','-']:
            sign=val[0]
            val=val[1:]
        dl = val.split(';')
        for d in dl:
            (e,t,v) = volstr2obj(d,'drhb',self,san=self.san_interface)
            if e:
                return (e,t)
            if v.locked:
                return (1,'Device %s is locked and cannot be used as cache' % v.name)
            if isinstance(v,Sanplun):
                if len(v.partitions) > 0:
                    return (1,'Device %s has partitions and cannot be used as cache' % v.name)
                if len(v.paths) > 1:
                    return (1,'Device %s has multiple paths and cannot be used as cache' % v.name)
            if v.usedinluns:
                return (1,'Device %s is used in target luns and cannot be used as cache' % v.name)
            devobjs += [v]
        if not test:
            self.cachedevices=devobjs
            self.devsign=sign
        return (0,'')

    def get_cachedevices(self,san,key):
        """
        The description of get_cachedevices comes here.
        @param san
        @param key
        @return
        """
        tmp=[]
        for d in self.cachevg.slaves():  # TBD when will add other providers, cachevg is only supported for VSApvd
            if d.extent: tmp+=[obj2volstr(d.extent)]
        return (0,';'.join(tmp))


    def evacuate(self,a='',b=''):
        """
        The description of evacuate comes here.
        @param a
        @param b
        @return
        """
        for t in self.san_interface.targets():
            if t.device and t.device is self :
                logger.eventlog.debug('evac target: %s  pvd: %s' % (t.name,str(t.device)))
                t.migrate()
        # TBDXX promote physical devs w replicated cache, maybe just w the below
        for r in self.san_interface.raids():
            if r.provider is self :
                r.promote_one(exclude=self)
                logger.eventlog.debug('promote raid: %s  new pvd: %s' % (r.name,str(r.provider)))
        return (0,'')

    def flashcmd(self,a='',b=''):
        """
        The description of flashcmd comes here.
        @param a
        @param b
        @return
        """
        act=a.split('=')
        if act[0] not in CACHECMDS : return (1,'not a valid flashcache command (use %s)' % ','.join(CACHECMDS))
        return self.act_cache(a)

    def delete(self,force=False):
        """
        The description of delete comes here.
        @param force
        @return
        """
        return (1,'cannot remove Providers')

    def update(self,flags=''):
        """
        The description of update comes here.
        @param flags
        @return
        """
        if self.state==ObjState.running and self.cachevg.state==ObjState.created and \
        'cachedevices' in self._updatedattr and self.cachedevices :
            devlist=[]
            for d in self.cachedevices :
                (e,pt)=ext2path(d,self)
                if e : return (e,'cant add Cache Pool slave %s, ' % str(d))
                devlist+=[pt]
            tmp=[d.name for d in devlist]
            print 'create cache vg on %s devs: %s' % (self.name,','.join(tmp))
            (e,r)=self.add_cachedevs(devlist)
            print e,r
            if e : return (e,r)
            self.cachedevices=[]
        return (0,'')

    def export(self,san,path,canadd=True):
        """
        The description of export comes here.
        @param san
        @param path
        @param canadd
        @return
        """
        out=[]
        for c in self.child_obj:
            if c not in self.set_params:
                out += self.__dict__[c].export(san,path+'/'+c)
##            if c not in self.set_params and not isinstance(self.__dict__[c],RefDict): out+=self.__dict__[c].export(san,path+'/'+c)
        if self.url:
            out=['add /providers %s' % (self.url)]+out
        return out

