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
from vsa.infra.infra import tstint, printsz
from vsa.infra.params import ObjState, paramopts, RaidLevel, IsRunning
from vsa.model import obj2volstr, ext2path, volstr2obj
from vsa.model.san_base import SanBase


class TargetPortal(SanBase):
    def __init__(self,name):
        """
        The description of __init__ comes here.
        @param name
        @return
        """
        SanBase.__init__(self,name,'Target Portal')
        p=name.split(':')
        if p[0]=='*' : self.ip=''
        else : self.ip=IP(p[0])
        if len(p)<>2 : self.port=3260
        else : self.port=tstint(p[1],3260)
        self.provider=None
        self.pid=0
        self.initiators={}


class TargetLun(SanBase):
    set_params = ['volume', 'bstype', 'vparams'] # TBD add params 1 by 1
    #show_columns = ['Target/Lun', 'Type', 'Size', 'devfile', 'Extent']
    newonly_fields = ['bstype', 'volume']
    loadmode_fields = ['volume']
    #ui_buttons = [add_btn, del_btn]

    def __init__(self,target,lun=0,vol=None):
        """
        The description of __init__ comes here.
        @param target
        @param lun
        @param vol
        @return
        """
        SanBase.__init__(self, str(lun), 'SAN LUN')
        self.updateflag=0
        self.id=int(lun)
        self.size=0
##        self.online=True  # TBD update tgt lun when value change
        self.devfile=''
        self.volume=vol
        self.path=None
        self.bstype = self.san_interface.general.default_bstype
        self.scsisn=''
        self.scsiid=''
        self.vendor='Mellanox'
        self.stype='disk'
#        self.devobj=None
        self.devstr=''
        self.devtype=''
        self.tmppvd=None
        self.vparams={}
        self.icon=""
        self.__force_update=False

    def _get_devfile(self):
        """
        The description of _get_devfile comes here.
        @return
        """
        return getattr(self.parent.device,'name','')+':'+self.devfile

    def ui_getrow(self):
        """
        The description of ui_getrow comes here.
        @return
        """
        return [self.parent.name+'/'+str(self.id),self.stype,printsz(self.size),self._get_devfile(),str(self.volume)]

    def __get_force_update(self):
        """
        The description of __get_force_update comes here.
        @return
        """
        return self.__force_update

    def __set_force_update(self, v):
        """
        The description of __set_force_update comes here.
        @param v
        @return
        """
        self.__force_update = v

    force_update = property(__get_force_update, __set_force_update)

    def set_volume(self,san,key,val='',test=0):
        """
        The description of set_volume comes here.
        @param san
        @param key
        @param val
        @param test
        @return
        """
        self.tmppvd = None
        # not checking if locked on load mode incase initiator created pool/raid/etc
        # that locks the device
        _chklock = self.san_interface.runmode and not self.force_update
        self.force_update = False
        (e,t,v) = volstr2obj(val,pvdin=self.parent.device,chklock=_chklock,chkstate=self.san_interface.runmode, san=self.san_interface)
        if e:
            return (e,t)
        if test:
            return (0,'')
        # a TargetLun.volume can point to Sanplun instead of SanPath incase vsasrv restarts
        # and tgtd luns were running
        if self.state!=ObjState.created:
            if not self.volume:
                return (0,'ignored')
            if not (self.volume.__class__.__name__=='Sanplun' and \
            t=='h' and v.name in self.volume.paths):
                return (0,'ignored')
        self.devtype = t
        if t in 'ntf':
            self.devstr = v[0]
            self.volume = None
            if not self.parent.device:
                self.tmppvd = v[1]
        else:
            self.volume=v
        return (0,'')

    def get_volume(self,san,key):
        """
        The description of get_volume comes here.
        @param san
        @param key
        @return
        """
        return (0,obj2volstr(self.volume,self.devstr,self.parent.device))

    def set_vparams(self,san,key,val='',test=0):
        """
        The description of set_vparams comes here.
        @param san
        @param key
        @param val
        @param test
        @return
        """
        return san.robots.set_strdict(self,key,val,test,paramopts)

    def update_devfile(self):
        """
        The description of update_devfile comes here.
        @return
        """
        if self.parent and self.devfile and self.id > 0:
            params = {
                'online': 0,
                'path': self.devfile
                }
            e,res = self.parent.device.update_lun(self.parent,self.id,self.path,self.bstype,params)
            return (e,res)
        return (0,'')

    def update(self,flags='',refresh=1):
        """
        The description of update comes here.
        @param flags
        @param refresh
        @return
        """
        if self.id<>0 and self.state==ObjState.created and not (self.volume or self.devstr):
            return (1,'must specify volume object when creating a Lun')
        if self.id==0:
            return (1,'Lun 0 cannot be modified')

        if self.volume:
            (e,pt)=ext2path(self.volume,self.parent.device)
            if e:
                return (e,pt)
            if self.volume.exttype=='raid' and self.volume.raid==RaidLevel.dr:
                if len(self.parent.luns) > 2:
                    return (1,'can only have one LUN per target when using DR Raid type (cluster mirror)')
                self.volume.promote_one(checkluns=False)
                self.parent.canmigrate=True
            # TBDXX promote one for physical devs w cache
            if not self.parent.device:
                self.parent.device=pt.provider
            elif self.parent.device!=pt.provider:
                self.volume=None
                return (1,'Lun volume does not reside in the same target provider (%s)' % self.parent.device.name)
            if self.parent.state==ObjState.created:
                self.parent.update(nest=True)

        elif self.devstr and not self.parent.device:
            self.parent.device=self.tmppvd
            self.parent.update(nest=True)

        elif self.devstr and self.tmppvd and not (self.tmppvd is self.parent.device):
            self.devstr=''
            return (1,'Lun volume does not reside in the same target provider (%s)' % self.parent.device.name)

        if self.parent.state==ObjState.created:
            print 'Parent Target is still not running'
            return (0,'Parent Target is still not running')

        if self.parent.device :
            if self.parent.device.state != ObjState.running :
                logger.eventlog.error('LUN update error, Provider %s cannot be configured, not running (State=%s)' % (self.parent.device.name,str(self.parent.device.state)))
                return (1,'Provider %s cannot be configured, not running (State=%s)' % (self.parent.device.name,str(self.parent.device.state)))
            if not self.volume:
                bspath=self.devstr
            else:
                if not IsRunning(self.volume):
                    logger.eventlog.error('Volume %s in LUN %s:%d is not operational (State=%s)' % (self.volume.name,self.parent.name,self.id,str(self.volume.state)))
                    return (1,'Volume is not operational (State=%s), select another volume or check its status' % str(self.volume.state))
                bspath=pt
                # TODO self.path won't always be the path configured for already running lun
                # because pt is from ext2path and if lun is running path isn't changing
                self.path=pt
            params={}
            if self.volume and self.volume.__class__.__name__ in ['Sanplun','SanPath'] and self.volume.direct:
                if self.volume.__class__.__name__ == 'SanPath':
                    pvl=self.volume.parent
                else:
                    pvl=self.volume
                if pvl.serial : params['scsi_sn']=pvl.serial[-32:]
                if pvl.serial : params['scsi_id']=pvl.serial[-24:]
                if pvl.vendor : params['vendor_id']=pvl.vendor
                if pvl.model  : params['product_id']=pvl.model
                if pvl.revision : params['product_rev']=pvl.revision

            if self.volume and self.volume.vparams:
                for p,v in self.volume.vparams.items():
                    params[p]=v

            if self.parent.vparams:
                for p,v in self.parent.vparams.items():
                    params[p]=v

            if self.vparams:
                for p,v in self.vparams.items():
                    params[p]=v

            if self.state == ObjState.created:
                if self.id > 0:
                    # TBD in case of physical choose path from list for volume
                    e,res = self.parent.device.add_lun(self.parent,self.id,bspath,self.bstype,params)
                    if e:
                        return (1, "Error adding lun: %s" % res)
            else:
                e,res = self.parent.device.update_lun(self.parent,self.id,bspath,self.bstype,params)
                if e:
                    return (1, "Error updating lun: %s" % res)
        else:
##            self._flush()
            return (0,'Target not configured, need to specify device/provider')
        return (0,'')

    def delete(self,force=False):
        """
        The description of delete comes here.
        @param force
        @return
        """
        if self.id==0 : return (1,'cannot remove LUN 0')
        if self.state==ObjState.created : return (0,'')
        e,r=self.parent.device.del_lun(self.parent,self.id,force)
        if e: return (1,r)
        if self.volume and self in self.volume.usedinluns :
            self.volume.usedinluns.remove(self)
            print 'removed from used in LUN list for %s' % str(self.volume)
        # TBD gracefull delete, disconnect clients / offline, ..
        return (0,'')

    def show(self,mode=0,level=0,ident=''):
        """
        The description of show comes here.
        @param mode
        @param level
        @param ident
        @return
        """
        tmp = '%sLUN%-2d: %-10s %-20s  %s' % (ident,self.id,self.stype,self.devfile,printsz(self.size))

        if level>0 and self.volume:
            tmp+='\n'+ident+'  Device:'
            tmp+='\n'+self.volume.show(mode,level-1,ident+'    ')
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
        if self.id==0:
            return []
        return SanBase.export(self,san,path,canadd)
