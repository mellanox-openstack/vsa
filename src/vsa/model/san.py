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


from vsa.model.san_base import SanBase
from vsa.client.gui.htmbtns import disable_btn, enable_btn
from vsa.infra.params import ObjState
#from san_resources import SanResources

class SanPath(SanBase):
    set_params=['reqstate','vparams']
    #show_columns=['Req State','Device','hbtl','HBA Type','Target','Dst port','Assigned BW']
    #ui_buttons=[enable_btn,disable_btn]

    def __init__(self,provider=None,name='',hbtl='0:0:0:0',lun=0):
        """
        The description of __init__ comes here.
        @param provider
        @param name
        @param hbtl
        @param lun
        @return
        """
        SanBase.__init__(self,name,'SAN Path')
        self.updateflag=0
        self.exttype='path'
        self.provider=provider   # source device or storage router (pointer to provider)
        self.hbatype=''      # HBA type ''=unknown, 'ata', 'scsi', 'fc', 'iscsi'
        self.devfile=''         # block device name in target/router e.g. sdb
        self.srcif=''        # source HBA port name
        self.hbtl=hbtl       # SCSI HBTL (Host:Bus:Target:Lun) of initiator/router
        self.initiator=''    # Source iSCSI iQN name or FC WWNN
        self.target=''       # destination iSCSI target or FC WWNN
        self.dstport=''      # destination iSCSI portal (IP:port) or FC WWPN
        if lun : self.lun=lun
        else : self.lun=int(hbtl.split(':')[3])
        self.sg=''
        self.direct=True
        self.assignbw=0
        self.vparams={}
        self.mpath=''        # multipath device name
        self.usedinluns=[]   # target luns using this volume
        self.lastseen=0      # time in which this path was last seen (by provider)
        self.cacheon=False
        self.cachedev=''
        self.cachedict={}

    def ui_getrow(self):
        """
        The description of ui_getrow comes here.
        @return
        """
        if self.provider : s = self.provider.name +'/'+self.devfile
        else : s=self.devfile
        return [self.reqstate,s,self.hbtl,self.hbatype,self.target,self.dstport,self.assignbw]

    def _getlocked(self):
        """
        The description of _getlocked comes here.
        @return
        """
        return self.parent.locked

    locked = property(_getlocked)

    def _getsize(self):
        """
        The description of _getsize comes here.
        @return
        """
        return self.parent.size

    size = property(_getsize)

    def _getusedby(self):
        """
        The description of _getusedby comes here.
        @return
        """
        return self.parent.usedby

    usedby = property(_getusedby)

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
        # check if all the paths have the same state, if yes change disk to that state
        allthesame = True
        for pt in self._owner():
            if pt.state != new:
                allthesame = False
                break
        if allthesame:
            self.parent.change_state(new,errstr,params,silent)
        else:
            self.parent.change_state(ObjState.degraded,errstr,params,silent)

        # check if we need to update vHBAs
        host = self.hbtl.split(':',1)[0]
        if new == ObjState.running and 'host'+host in self.provider.fcports:
            fcp = self.provider.fcports['host'+host]
            if fcp.virtual and fcp.name not in self.san_interface.newfcpaths:
                self.san_interface.newfcpaths += [fcp.name]

        return 0

    def show(self,mode=0,level=0,ident='') :
        """
        The description of show comes here.
        @param mode
        @param level
        @param ident
        @return
        """
        if self.provider : s = self.provider.name +'/'+self.devfile
        else : s=self.devfile
        return '%s %-15s %-8s %-10s %-10s %s %s' % (ident,s,str(self.state),self.hbtl,self.hbatype,self.target,self.dstport)

class SanChunk(SanBase) :
    def __init__(self,plun,vol,start=0,end=0,ctype=''):
        """
        The description of __init__ comes here.
        @param plun
        @param vol
        @param start
        @param end
        @param ctype
        @return
        """
        SanBase.__init__(self)
        self.plun=plun   # physical LUN
        self.vols=[vol]  # virtual LUNs
        self.start=start # chunk start sector
        self.end=end     # chunk end sector, 0 = all
        self.ctype=ctype # chunk type
    def show(self,mode=0,level=0,ident='') :
        """
        The description of show comes here.
        @param mode
        @param level
        @param ident
        @return
        """
        if self.plun : s = self.plun.name
        else : s=''
        return s+': '+`self.start`+' - '+`self.end`


