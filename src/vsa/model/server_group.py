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
from vsa.model.san_base import SanBase
from vsa.client.gui.htmbtns import add_btn, del_btn
from vsa.model.vsa_collections import VSACollection
from vsa.model.disk import vDisk
from vsa.model.fc import vFCPort
from vsa.infra.infra import tstint, getunique
from vsa.infra.params import OsType, Transport, ObjState
from vsa.infra import logger


class ServerGroup(SanBase):  # eq UFM Logical Server
    child_obj=['vdisks','hbas']
    add_commands=['vdisks','hbas']
    set_params=['ips','user','password','ostype','wwnn']
    newonly_fields=['wwnn']
    #show_columns=['Name','OS','IPs','vWWNN','vHBAs','vDisks','Targets']
    #ui_buttons=[add_btn,del_btn]

    def __init__(self,name,defaultos='unknown', ips=[]):
        """
        The description of __init__ comes here.
        @param name
        @param defaultos
        @param ips
        @return
        """
        SanBase.__init__(self,name,'Server Group')
        self.id=0
        self.iscsiname=''
        self.wwnn=''
        self.ips=ips
        self._ipchanged=False
        self.vdisks=VSACollection(vDisk,self,'vdisks',True,desc='Virtual Disks',icon='hard_disk.png')
        self.hbas=VSACollection(vFCPort,self,'hbas',True,desc='Virtual FC HBA',icon='VirtIfc_g.png')
        self.targets={}
        self.interfaces=[]
        self.childs=[]  # TBD add "compute" collection for childs (SAP, ..)
        self.user=''
        self.password=''
        self.ostype=defaultos
        self.icon=""

    def ui_getrow(self):
        """
        The description of ui_getrow comes here.
        @return
        """
        return [self.name,self.ostype,','.join([str(i) for i in self.ips]),self.wwnn,len(self.hbas),len(self.vdisks),len(self.targets)]

    def set_ips(self,san,key,val='',test=0):
        """
        The description of set_ips comes here.
        @param san
        @param key
        @param val
        @param test
        @return
        """
        if self.name=='everyone':
            if val.lower()=='all':
                return (0,'')
            else:
                return (1,'cannot change IP address for Everyone server group')
        if ';' in val:
            sep=';'
        else:
            sep=','
        sign=0
        if len(val) > 1 and val[0] in ('+','-'):
            sign=val[0]
            val=val[1:]
        ipl=set(val.strip().split(sep))
        for v in ipl:
            parts = v.split('.')
            if len(parts) <> 4:
                return (1,'%s is not a valid IP address' % v)
            for i in parts:
                if not 0 <= tstint(i) <= 255:
                    return (1,'%s is not a valid IP address' % v)
        if not test:
            old=set(self.ips)
            new=set([IP(v) for v in ipl])
            if sign=='+': new=old.union(new)
            elif sign=='-': new=old.difference(new)
            self.ips=[IP(v) for v in new]
        self._ipchanged=True
        return (0,'')

    def add_vdisks(self,name=''):
        """
        The description of add_vdisks comes here.
        @param name
        @return
        """
        if name in self.vdisks.keys() : return None
        if not name or name=='#' : name=getunique(self.vdisks.keys(),'disk')
        vd=self.vdisks.add(name,vDisk(name)) # TBD add
        if vd and self.ostype==OsType.linux : vd.transport=Transport.iser
        return vd

    def add_hbas(self,name=''):
        """
        The description of add_hbas comes here.
        @param name
        @return
        """
        if len(self.hbas)>= self.san_interface.wwpnspernode:
            logger.eventlog.error('fail to add hba to %s, exceeded Max wwpn per node' % (self.name))
            return None
        if name in ['','#'] :
            name='%16.16X' % (int(self.wwnn,16)+len(self.hbas))
        else:
            try:
                name='%16.16X' % int(name,16)
            except Exception,err:
                logger.eventlog.error('fail to add hba to %s, %s' % (self.name,str(err)))
                return None
        if name in self.hbas.keys() : return None
        vhb=self.hbas.add(name,vFCPort(name))
        if vhb and self.ostype==OsType.linux : vhb.transport=Transport.iser
        return vhb

    def delete(self,force=False):
        """
        The description of delete comes here.
        @param force
        @return
        """
        if self.name=='everyone' : return (1,'cannot remove "everyone" group')
        if self.targets : return (1,'server %s in use by targets, remove targets, vDisks, and vHBAs first' % self.name) # TBD add targets name
        # TBD address auto-targets & vHBAs
        return (0,'')

    def show(self,mode=0,level=0,ident=''):
        """
        The description of show comes here.
        @param mode
        @param level
        @param ident
        @return
        """
        tmp = '%s%-10s  IPs: %s vWWNN: %s' % (ident,self.name,','.join([str(i) for i in self.ips]),self.wwnn)
        if level>0:
            tmp+='\n'+ident+'  Virtual FC Ports:'
            for v in self.hbas.values()  : tmp+='\n'+v.show(mode,level-1,ident+'    ')
            tmp+='\n'
        return tmp

    def export(self,san,path,canadd=True):
        """
        The description of export comes here.
        @param san
        @param path
        @param canadd
        @return
        """
        exclude=[]
        if self.name=='everyone' : canadd=False; exclude=['ips']
        return SanBase.export(self,san,path,canadd,exclude)

    def update(self,flags=''):
        """
        The description of update comes here.
        @param flags
        @return
        """
        self.state=ObjState.running
        if self._ipchanged:
            for t in self.targets.values() :
                t.update()
            self._ipchanged=False
        return (0,'')

