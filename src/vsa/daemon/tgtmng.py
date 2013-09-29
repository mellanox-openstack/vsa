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


import os,re,time
from vsa.infra import logger
from vsa.infra.infra import tstint
from vsa.infra.processcall import process_call

#===============================================================================
# from processcall import *
# from infra import *
#===============================================================================

TGTPATH = '/usr/sbin/tgtadm'

mtarget = re.compile(r'^Target (\d+): (.+)')
mlun = re.compile(r'^LUN:\s(\d+)')
msize = re.compile(r'(\d+).+')

lun_params = ['product_id', 'product_rev', 'scsi_id', 'scsi_sn', 'removable', 'mode_page', 'sense_format', 'online', 'path', 'direct']

# error codes
TGTADM_NOT_FOUND = 99
TARGET_NOT_FOUND = 11
TARGET_WITH_SESSIONS = 13


class Tgt_target:
    def __init__(self,name,state=''):
        """
        The description of __init__ comes here.
        @param name
        @param state
        @return
        """
        self.name=name
        self.state=state
        self.updated=0
        self.lld='iscsi'
        self.default_param={}
        self.luns={}
        self.conn=[]
        self.acls=[]


class Tgt_lun:
    def __init__(self,num):
        """
        The description of __init__ comes here.
        @param num
        @return
        """
        self.num=num
        self.bstor=''
        self.bpath=''
        self.vendor=''
        self.scsi_id=''
        self.scsi_sn=''
        self.online='yes'
        self.removable='No'
        self.write_cache=1
        self.params={}


class Tgtadm:
    def __init__(self, pid=0):
        """
        The description of __init__ comes here.
        @param pid
        @return
        """
        self.cmd = [TGTPATH, '-C', str(pid)]
        self.pid = pid
        self.process = 0
        self.targets = {}
        self.default_lld = 'iscsi'
        self.vendor_id = 'Mellanox'
        self.default_param = {'product_rev': '1.0'}
        self.nametmp = 'P'+`pid`+'-%s'
        self.version = (1,0)
        self.get_tgtshow()

    def docmd(self, args, log=True):
        """
        The description of docmd comes here.
        @param args
        @param log
        @return
        """
        if not os.path.isfile(TGTPATH):
            return (TGTADM_NOT_FOUND, 'cant open tgtadm process')
        (e,o) = process_call(self.cmd+args, log=log)
        return (e,o)

    def get_tgtshow(self,gettid=True) :
        """
        The description of get_tgtshow comes here.
        @param gettid
        @return
        """
        target=0
        i=0
        lun=-1
        aclon=0
        accon=0
        itn=0
        targets={}
        luns={}
        connections=[]
        acls=[]
        for tg in self.targets.values() : tg.update=0
        (e,txt)=self.docmd(['--lld','iscsi','--mode','target','--op','show'],log=False)
        if e : return (e,txt)
        fl=txt.splitlines()
        while i<len(fl):
            l=fl[i].strip()
            m=mtarget.match(l)
            if m :
                target=int(m.group(1))
                targets[target]={'tid':`target`,'name':m.group(2)}
                if not self.targets.has_key(target) :
                    self.targets[target]=Tgt_target(m.group(2))
                if gettid:
                    (e,txt)=self.docmd(['--lld','iscsi','--mode','target','--op','show','--tid',str(target)],log=False)
                    if e : return (e,txt)
                    if txt.strip().startswith('Redirect') : targets[target]['redir']='yes'
                self.targets[target].luns={}
                self.targets[target].conn=[]
                self.targets[target].acls=[]
                self.targets[target].update=1
                lun=-1
                aclon=0
            elif target>0 :
                m=mlun.match(l)
                if m :
                    lun=int(m.group(1))
                    tl='%d:%d' % (target,lun)
                    luns[tl]={'tid':`target`,'lid':`lun`}
                    self.targets[target].luns[lun]=Tgt_lun(lun)
                elif aclon and not (':' in l):
                    acls+=[[target,l]]
                    self.targets[target].acls+=[l]
                else:
                    sl=l.split(':')
                    sls=[c.strip() for c in sl]
                    if sls[0]=='ACL information' : aclon=1
                    if len(sl)>1:
                        k=sls[0]
                        v=sls[1]
                        if k=='Driver' :
                            targets[target]['driver']=v
                            self.targets[target].lld=v
                        if k=='State' :
                            targets[target]['state']=v
                            self.targets[target].state=v
                        if k=='Initiator' : initiator=v
                        if "IP Address" in k :
                            connections+=[[target,itn,initiator,v]]
                            self.targets[target].conn+=[[itn,initiator,v]]
                        if lun>=0 :
                            if k=='Type' : luns[tl]['type']=v
                            if k=='SCSI ID' : luns[tl]['scsiid']=v
                            if k=='SCSI SN' : luns[tl]['scsisn']=v
                            if k=='Size' : luns[tl]['size']=msize.match(v).group(1)
                            if k=='Online' : luns[tl]['on']=v.lower()
                            if k=='Removable media' : luns[tl]['removable']=v.lower()
                            if k=='Backing store type' : luns[tl]['bstype']=v
                            if k=='Backing store path' : luns[tl]['bspath']=v
                        if k=='Initiator' : initiator=v
                        if k=='I_T nexus' : itn=v

            i+=1
        for tg in self.targets.values() :
            if not tg.update :
                print 'target %s not found ' % tg.name
                del tg
        return (0,{'targets':targets.values(),'luns':luns.values(),'connections':connections,'acls':acls,'accounts':[]})

    def create_target(self,name='',tid=0,lld='',acl=['ALL'],params={},redirect=''):
        """
        The description of create_target comes here.
        @param name
        @param tid
        @param lld
        @param acl
        @param params
        @param redirect
        @return
        """
##        self.get_tgtshow(False)
        self.default_param=params.copy()
        if tid==0 :
            logger.agentlog.error('Target ID must not be 0')
            return (1,'Target ID must not be 0')
        if name=='' : name= 'Target%d' % tid
        #newname = self.nametmp % name
        if name in [self.targets[i].name for i in self.targets.keys()] :
            txt='Target name %s may already exist' % name
            logger.agentlog.error(txt)
        if not lld : lld=self.default_lld
        (e,txt)=self.docmd(['--lld',lld,'--mode','target','--op','new','--tid=%d' % tid,'-T',name])
        if e :
            return (e,txt)

        self.targets[tid]=Tgt_target(name)
        self.targets[tid].default_param=self.default_param
        if 'vendor' not in self.targets[tid].default_param.keys() :
            self.targets[tid].default_param['vendor_id']=self.vendor_id

        if redirect :
            ctrl='--op update --mode target --tid=%d --name RedirectCallback --value %s' % (tid,redirect)
            (e,txt)=self.docmd(ctrl.split())
            if e :
                return (e,txt)

        vendor=self.targets[tid].default_param['vendor_id']
        # TBD change Controller LUN (0) , etc'
        ctrl="--lld %s --mode logicalunit --op update --tid=%d --lun 0 --params scsi_id=1234,vendor_id=%s,product_rev=1,scsi_sn=1234,product_id=vsa"  % (lld,tid,vendor)
        (e,txt)=self.docmd(ctrl.split())
        if e :
            return (e,txt)

        for ac in acl :
            (e,txt1)=self.docmd(['--lld',lld,'--mode','target','--op','bind','--tid=%d' % tid,'-I',str(ac)])
            if e : return (e,txt1)
        return (0,tid)

    def update_target(self,tid=0,acl=[],params={}):
        """
        The description of update_target comes here.
        @param tid
        @param acl
        @param params
        @return
        """
##        self.get_tgtshow(False)
        lld=self.targets[tid].lld
        if params:
            self.default_param=params.copy()
            self.targets[tid].default_param=self.default_param
            if 'vendor' not in self.targets[tid].default_param.keys() :
                self.targets[tid].default_param['vendor_id']=self.vendor_id

        oldacls=self.targets[tid].acls
        acl=[str(a) for a in acl]
        newacl=[a for a in acl if a not in oldacls] # ACLs to add
        delacl=[a for a in oldacls if a not in acl] # ACLs to delete

        for ac in newacl :
            (e,txt)=self.docmd(['--lld',lld,'--mode','target','--op','bind','--tid=%d' % tid,'-I',ac])
            if e : return (e,txt)

        for ac in delacl :
            (e,txt)=self.docmd(['--lld',lld,'--mode','target','--op','unbind','--tid=%d' % tid,'-I',ac])
            if e : return (e,txt)

        return (0,tid)

    def del_target(self, tid, force=False):
        """
        The description of del_target comes here.
        @param tid
        @param force
        @return
        """
        self.get_tgtshow(False)
        if not self.targets.has_key(tid):
            if force:
                return (0,'')
            er = 'Cant find target id %d' % tid
            logger.agentlog.error('Del-target: '+er)
            return (TARGET_NOT_FOUND, er)

        lld = self.targets[tid].lld

        if force:
            for ac in self.targets[tid].acls:
                (e,txt) = self.docmd(['--lld',lld,'--mode','target','--op','unbind','--tid=%d' % tid,'-I',ac])
                if e:
                    return (e,txt)

        if self.targets[tid].conn and force:
            for conn in self.targets[tid].conn:
                (e,txt) = self.docmd(['--lld',lld,'--mode','conn','--op','delete','--tid=%d' % tid,'--sid',conn[0],'--cid','0'])
                if e:
                    return (e,txt)
        elif self.targets[tid].conn:
            return (TARGET_WITH_SESSIONS, 'cannot delete target with live sessions, can use force option')

        for lid in self.targets[tid].luns.keys():
            if lid <> 0:
                (e,txt) = self.del_lun(tid,lid,force)

        # delete target with 3 attemps
        for i in range(3):
            (e,txt) = self.docmd(['--lld',lld,'--mode','target','--op','delete','--tid=%d' % tid])
            if not e:
                break
            time.sleep(1)
        if e:
            return (e,txt)

        del self.targets[tid]
        return (0,txt)

    def add_lun(self,tid,lid=0,bspath='',bstype='rdwr',params={}) :
        """
        The description of add_lun comes here.
        @param tid
        @param lid
        @param bspath
        @param bstype
        @param params
        @return
        """
##        self.get_tgtshow(False)
        lld=self.targets[tid].lld
        if lid==0:
            logger.agentlog.error('LUN ID must not be 0')
            return (1,'LUN ID must not be 0')

        if bstype != 'rdwr':
            bs = ['--bstype=%s' % bstype]
        else:
            bs = []

        if not self.targets[tid].luns.has_key(lid):
            if bstype not in ['null', 'th_null'] and not os.path.exists(bspath):
                return (1,'bspath %s not found' % bspath)
            (e,txt) = self.docmd(['--lld',lld,'--mode','logicalunit','--op','new','--tid=%d' % tid,'--lun',`lid`,'-b',bspath]+bs)
            if e:
                return (e,txt)

        (e,txt) = self.update_lunparam(tid,lid,params)
        if e:
            return (e,txt)
        return (0,lid)

    def update_lunparam(self,tid,lid=0,origparams={}) :
        """
        The description of update_lunparam comes here.
        @param tid
        @param lid
        @param origparams
        @return
        """
##        self.get_tgtshow(False)
        params=origparams.copy()
        lld=self.targets[tid].lld
        for p in self.targets[tid].default_param.keys() :
            if p not in params.keys() : params[p]=self.targets[tid].default_param[p]
        if 'write-cache' in params.keys() :
            if params['write-cache']=='off' :
                params['mode_page']='8:0:18:0x10:0:0xff:0xff:0:0:0xff:0xff:0xff:0xff:0x80:0x14:0:0:0:0:0:0'
            if params['write-cache'] not in ['on','off'] :
                logger.agentlog.error('illegal write-cache flag %s use on/off' % params['write-cache'])
            del params['write-cache']

        if not params:
            return (0,'no params')
        pr=[]
        for p in params.keys():
            pv=str(params[p]).strip()
            if ' ' in pv:
                pv = '"%s"' % pv
            itm = '%s=%s' % (p,pv)
            if p == 'online':    # online param must be first
                pr.insert(0, itm)
            else:
                pr += [itm]
        if pr:
            pr = ['--params'] + [','.join(pr)]

        (e,txt)=self.docmd(['--lld',lld,'--mode','logicalunit','--op','update','--tid=%d' % tid,'--lun',`lid`]+pr)
        return (e,txt)

    def del_lun(self, tid, lid, force=False):
        """
        The description of del_lun comes here.
        @param tid
        @param lid
        @param force
        @return
        """
        txt = ''
        self.get_tgtshow(False)

        if not self.targets.has_key(tid):
            if force:
                return (0,txt)
            logger.agentlog.error('target number %s not found on del lun' % tid)
            return (TARGET_NOT_FOUND, 'target number %s not found on del lun' % tid)

        if self.targets[tid].conn and not force:
            return (TARGET_WITH_SESSIONS, 'cannot delete lun from a target with live sessions, can use force option')

        lld = self.targets[tid].lld

        if self.targets[tid].luns.has_key(lid):
            (e,txt) = self.docmd(['--lld',lld,'--mode','logicalunit','--op','delete','--tid=%d' % tid,'--lun',`lid`])
            if e:
                return (e,txt)
            del self.targets[tid].luns[lid]
        return (0,txt)

    def get_tgopt(self,tid) :
        """
        The description of get_tgopt comes here.
        @param tid
        @return
        """
        if not self.targets.has_key(tid) : logger.agentlog.info('target id %s not found in get_tgtopt' % tid)
##        lld=self.targets[tid].lld
        (e,txt)=self.docmd(['--mode','target','--op','show','--tid',str(tid)],log=False)
        if e : return (e,txt)
        fl=txt.splitlines()
        iscsiopt={}
        for l in fl:
            [k,v]=l.split('=')
            iscsiopt[k]=v
        return (0,iscsiopt)

    def set_tgopt(self,tid,iscsiopt) :
        """
        The description of set_tgopt comes here.
        @param tid
        @param iscsiopt
        @return
        """
        lld=self.targets[tid].lld
        for ok,ov in iscsiopt.items():
            (e,txt)=self.docmd(['--lld',lld,'--mode','target','--op','update','--tid',str(tid),'--name',ok,'--value',ov])
            if e : return (e,txt)
        return (0,txt)

    def get_tgstats(self,tid,pid) :
        """
        The description of get_tgstats comes here.
        @param tid
        @param pid
        @return
        """
        # -m target -o stat --tid 1
        # -m sys -o stat
        if tid==-1 : cmd=['--mode','sys','--op','stat']
        else: cmd=['--mode','target','--op','stat','--tid',str(tid)]
        (e,txt)=self.docmd(cmd)
        if e : return (e,0,txt)
        fl=txt.splitlines()
        stats=[]
        for l in fl[1:]:
            cols=l.split()
            if len(cols)>10 and tstint(cols[0])>=0 and cols[1]<>'0':
                stats+=[[pid]+cols]
        return (0,time.time(),stats)
