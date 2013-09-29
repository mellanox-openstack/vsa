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
from vsa.model import wwn2alias
from vsa.infra.params import Transport, ObjState
from vsa.infra import logger
from twisted.internet import reactor
from vsa.model.san_target import SanTarget
from vsa.model.vsa_collections.ref_dict import RefDict

class vFCPort(SanBase):
    set_params=['port','priority','avgload','vsan','transport']
    newonly_fields=['port','transport']
    #ui_buttons=[add_btn,del_btn]

    def __init__(self,name):
        """
        The description of __init__ comes here.
        @param name
        @return
        """
        SanBase.__init__(self,name,'Virtual HBA')
        self.vsan=0
        self.priority=0
        self.avgload=50
        self.port=''
        self.provider=None
        self.fchost=''
        self.transport=Transport.iscsi
        self.targets={}

    def find_fcport(self,pvd=None):
        """
        The description of find_fcport comes here.
        @param pvd
        @return
        """
        bw={}
        portlist=[]
        curports=[]
        curpvd=[]
        for f in self.parent.hbas.values():
            if f.provider:
                curports += [[f.provider.name,f.fchost]]
                if f.provider.name not in curpvd:
                    curpvd += [f.provider.name]
        if pvd:
            for (pk,pfc) in pvd.fcports.items():
                if [pvd.name,pk] not in curports and pfc.maxnpiv - pfc.npivinuse > 1 and \
                pfc.speed != 'unknown':
                    portlist += [[pvd.name,pk]]
        else:
            for p in self.san_interface.providers.values():
                for (k,pfc) in p.fcports.items():
                    if pfc.maxnpiv - pfc.npivinuse > 1 and pfc.speed != 'unknown' and \
                    [p.name,k] not in curports and p.name not in curpvd:
                        portlist += [[p.name,k]]
        if not portlist:
            return (1,'no available FC (NPIV) ports were found')
        for pi in portlist:
            pv = self.san_interface.providers[pi[0]].fcports[pi[1]]
            bw[pv.assignbw] = [self.san_interface.providers[pi[0]],pi[1]]
        return (0, bw[min(bw.keys())])

    def set_port(self,san,key,val='',test=0):
        """
        The description of set_port comes here.
        @param san
        @param key
        @param val
        @param test
        @return
        """
##    TBD    if len(fp)>san.wwpnspernode : return (1,'only %d vports allowed per server group' % san.wwpnspernode)
##        if self.port : return (1,'cannot change HBA port on a running virtual port')
        fcp=None; pvd=None; fchost=''
        if val in san.providers.keys() :
            pvd=san.providers[val]
        elif val in san.fcports.keys() :
            fcp=san.fcports[val]
            if fcp.roles=='t' :
                return (1,'The specified FC port is not a host/initiator port, please specify a valid NPIV capable host wwpn')
            if fcp.freevports<=0 :
                return (1,'The port does not have available Virtual HBA (NPIV) resources')
            pvd=fcp.system
            fchost=fcp.scsihost
        elif san.runmode :
             # check only when not initial load
            return (1,'port value must be using a valid provider name or a valid FC host wwpn')

        # TBD add test for unknown & npiv in use for selected hostn too
        if not val or (pvd and not fcp):
            (e,pitem)=self.find_fcport(pvd)
            if e : return (e,pitem)
            [pvd,fchost]=pitem
            fcp=pvd.fcports[fchost]
            val=fcp.name

        if not test :
            self.port=val
            self.fchost=fchost
            self.provider=pvd
            if fcp : fcp.assignbw+=self.avgload
        return (0,'')

    def update(self,flags=''):
        """
        The description of update comes here.
        @param flags
        @return
        """
        delay=0.01
        if self.state==ObjState.created:
            if  not self.port:
                (e,pitem)=self.find_fcport()
                if e : return (e,pitem)
                [pvd,fchost]=pitem
                self.provider=pvd
                self.port=pvd.fcports[fchost].name
                self.fchost=fchost
                pvd.fcports[fchost].assignbw+=self.avgload
            if not self.fchost : return (0,'Warning, Must assign FC port before action is taken')
            if not self.san_interface.fcports.has_key(self.name):
                (e,txt)=self.provider.add_vport(self.fchost,self.parent.wwnn,self.name)
                if e : return (e,'failed to add vport %s:%s:%s ' % (self.fchost,self.name,self.parent.wwnn) +txt)
                if self.san_interface.fcports.has_key(self.name):
                    self.san_interface.fcports[self.name].vhba=self
                else :
                    logger.eventlog.error('FC vHBA %s was not created after add' % (self.name))
                delay=2.0
            else :
                # if current FC port is different than new allocated, write to log and change model to current (not to break traffic)
                op=self.san_interface.fcports[self.name]
                if not op.virtual :
                    return (1,'FC WWPN %s is a physical addressed, already assigned to another port' % (self.name))
                if op.vhba and not (op.vhba is self) :
                    return (1,'FC WWPN %s is already assigned to another virtual HBA' % (self.name))
                logger.eventlog.info('vHBA port %s %s already exist' % (self.parent.name,self.name))
                if op.wwnn<>self.parent.wwnn :
                    logger.eventlog.error('wrong wwnn %s with %s' % (op.wwnn,self.name))
                pvd=self.provider
                if op.system and op.system.name<>self.provider.name :
                    logger.eventlog.error('wrong provider %s with %s' % (op.system.name,self.name))
                    self.provider=op.system
                    pvd=op.system
                if op.parport and op.parport<>self.fchost :
                    logger.eventlog.error('wrong Parent HBA %s with %s' % (op.parport,self.name))
                    self.fchost=op.parport
                self.port=pvd.fcports[op.parport].name
            self.state=ObjState.running

        reactor.callLater(delay,self.update_async)
        return (0,'Updating Virtual HBA Port ...')

    def update_async(self,loadext=True):
        """
        The description of update_async comes here.
        @param loadext
        @return
        """
        if loadext:
            self.provider.load_extents()
        if not self.san_interface.fcports.has_key(self.name):
            return
        self.state=ObjState.running
        hbtl = {}
        for p in self.san_interface.disks.values():
            for pt in p.paths.values():
                if pt.provider.name == self.provider.name:
                    hbtl[pt.hbtl] = pt
        fcp = self.san_interface.fcports[self.name]
        for hbt, tgp in fcp.targets.items():
            haslun = False
            for d in hbtl.keys():
                if d.startswith(hbt.strip()+':'):
                    haslun=True
                    break
            if haslun:
                name='iqn.vsa.vhba.%s.%s.swwn-%s.twwn-%s' % (self.parent.name,self.provider.name,self.name,tgp.wwpn)
                if not self.san_interface.targets.has_key(name) :
                    logger.eventlog.debug('adding vHBA target:'+name)
                    itg=self.san_interface.targets.add(name,SanTarget(name,self.provider))
                    itg.transport=self.transport
                else : itg=self.san_interface.targets[name]
                itg.server=self.parent
                itg.auto=True
                itg.update()
                self.targets[name]=itg
                self.parent.targets[name]=itg
                curluns=[l.volume.hbtl for l in itg.luns.values() if l.id<>0]
                for d in sorted(hbtl.keys()) :
                    if d.startswith(hbt.strip()+':') and d not in curluns:
                        lun=itg.add_luns('#',hbtl[d])
                        logger.eventlog.debug('added lun %s' % d)
    #                    lun=itg.add_luns(d.split(':')[3],hbtl[d])
                        if lun : lun.update()
                        else : logger.eventlog.debug('vHBA Lun %s is null' % d)

    def delete(self,force=False):
        """
        The description of delete comes here.
        @param force
        @return
        """
        logger.eventlog.info('Delete vHBA: %s %s' % (self.name,str(force)))
        if self.state<>ObjState.created and self.provider :
            self.provider.fcports[self.fchost].assignbw-=self.avgload
            for (k,tg) in self.targets.items():
                if self.parent.targets.has_key(k):
                    del self.parent.targets[k]
                self.san_interface.targets.delete(tg,True)
            (e,txt)=self.provider.del_vport(self.fchost,self.parent.wwnn,self.name)
            if e : return (e,'failed to delete vport %s:%s:%s ' % (self.fchost,self.name,self.parent.wwnn) +txt)
            del self.san_interface.fcports[self.name]
            return (e,txt)
        delay=2.0
        reactor.callLater(delay,self.update_async)
        return (0,'')

    def show(self,mode=0,level=0,ident=''):
        """
        The description of show comes here.
        @param mode
        @param level
        @param ident
        @return
        """
        if self.provider : pv=self.provider.name
        else : pv=''
        tmp = '%s%s %s  Port: %s/%s  Bandwidth: %d' % (ident,self.name,self.state,pv,self.fchost,self.avgload)
        return tmp


class FCport(SanBase):
    child_obj=['tgports']
    add_commands=[]
    set_params=[]
    #show_columns=['Role','wwnn','wwpn','Speed','Provider','HBA','vPorts','Parent']

    def __init__(self,wwpn,wwnn='',fabric='',scsihost='',speed='',roles=''):
        """
        The description of __init__ comes here.
        @param wwpn
        @param wwnn
        @param fabric
        @param scsihost
        @param speed
        @param roles
        @return
        """
        SanBase.__init__(self,wwpn,'FC Port')
        self.roles=roles
        self.vhba=None
        self.scsihost=scsihost
        self.wwnn=wwnn
        self.wwpn=wwpn
        self.alias=wwn2alias(wwpn,wwnn)
        self.fabric=fabric
        self.speed=speed
##        self.state=ObjState.unknown
        self.system=None
        self.port_type=''
        self.vports=[]
        self.parport=''
        self.maxnpiv=0
        self.npivinuse=0
        self.targets={}
        self.tgports=RefDict(FCport,self,'tgports',desc='Discovered FC Targets',icon='VirtIfc_g.png',call=lambda self:[v for v in self.targets.values()])
        self.assignbw=0

    virtual=property(lambda self: bool(self.parport) )

    def ui_getrow(self):
        """
        The description of ui_getrow comes here.
        @return
        """
        return [self.roles.upper(),self.wwnn,self.wwpn,self.speed,getattr(self.system,'name',''),self.scsihost,"%d/%d" % (len(self.vports),self.maxnpiv),self.parport]

    def freevports(self):
        """
        The description of freevports comes here.
        @return
        """
        return self.maxnpiv-len(self.vports)

    def __repr__(self):
        """
        The description of __repr__ comes here.
        @return
        """
        return self.alias

    def delete(self,force=False):
        """
        The description of delete comes here.
        @param force
        @return
        """
        if self.parport and self.system and force :
            (e,txt)=self.system.del_vport(self.parport,self.wwnn,self.wwpn)
            return (e,txt)
        return (1,'can not delete physical FC ports')
