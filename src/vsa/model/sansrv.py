#!/usr/bin/env python

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


import os
import sys
import traceback
from datetime import datetime
import re

from vsa.infra.params import ERR_TWISTED, REFRESH_PERIOD, ERR_HA_SLAVE,\
    logopt, showlist, ObjState, CACHEPFX, CACHESEP, ERR_LOADPVD_LO, ERR_LOADPVD,\
    SANSRV_XMLRPC_PORT, MANHOLE_CREDENTIALS, MANHOLE_PORT, ERR_HA_TRANSITION,\
    ERR_COMPUTE_NODE

try:
    from twisted.internet import reactor, task
    from twisted.web import xmlrpc, server
    from twisted.python import log
    from twisted.conch import manhole, manhole_ssh
    from twisted.cred import portal, checkers
except ImportError, e:
    print 'Twisted package not found or is the wrong version:',e
    sys.exit(ERR_TWISTED)


from IPy import IP
from vsa.infra import logger, config
from vsa.infra.config import config_db
from vsa.client.gui.vsaxmlrpc import VsaXmlRpc
from vsa.client.gui import webportal
from vsa.daemon.daemon import Daemon
from vsa.monitor.monitor import VSAmonitor
from vsa.model.vsapvd import VsaProvider, LoopbackException
from vsa.model import volstr2obj
from vsa.model.san_resources import SanResources
from vsa.model.vsa_collections import VSACollection, RefDict
from vsa.infra.infra import ha_rsc_status, get_vsa_role,\
    str2dict, tstint, dict2str, printsz
from vsa.model.san_container import SanContainer


lclpath = os.path.dirname(os.path.abspath(__file__))+'/'

def print_class(obj):
    """
    The description of print_class comes here.
    @param obj
    @return
    """
    out=[]
    for i in sorted(obj.__dict__.keys()) :
        if obj.__dict__[i].__class__.__name__ in ['int','str','IP','list','dict','EnumValue','bool'] :
            if i[0] <> '_': out+=['  %s=%s' %(i,str(obj.__dict__[i]))]
    return out


class session:
    def __init__(self,admin,user,sid):
        """
        The description of __init__ comes here.
        @param admin
        @param user
        @param sid
        @return
        """
        self.user=user
        self.admin=admin
        self.sid=sid


class SanServer(VsaXmlRpc):
    def __init__(self, san, loadpvd=True):
        """
        The description of __init__ comes here.
        @param san
        @param loadpvd
        @return
        """
        VsaXmlRpc.__init__(self, allowNone=True)
        self.san = san
        self.mon = VSAmonitor(self.san)
        self.putSubHandler('mon', self.mon)
        self.sessions = {}
        self.loadpvdErr = None

    def post_init(self, loadpvd=True):
        """
        The description of post_init comes here.
        @param loadpvd
        @return
        """
        if loadpvd:
            try:
                pvd = VsaProvider(local=True)
            except Exception, exc:
                logger.eventlog.error(
                'Local provider initialization failure: %s traceback: %s'
                            % (str(exc),  traceback.format_exc()))
                self.loadpvdErr = exc
            else:
                self.san.providers.add(pvd.name,pvd)
                pvd.load(info=False, sync=True)
                self.san.lclprovider = pvd
        logger.eventlog.info('VSA started')
        logger.auditlog.info('VSA started')

        # Initialize periodic data refresh. Make first refresh after refresh period (not immediately)
        if REFRESH_PERIOD:
            task.LoopingCall(self.refresh).start(REFRESH_PERIOD, now = False)


    def login(self,admin,user):
        """
        The description of login comes here.
        @param admin
        @param user
        @return
        """
        self.sessions[0]=session(admin,user,0)
        e=0
        c=ha_rsc_status()
        if c=='none':
            e=ERR_HA_SLAVE
        logger.auditlog.info('User %s Login, Session: %d, Code: %d' % (user,0,e))
        return (e,0,'')

    def debuglvl(self):
        """
        The description of debuglvl comes here.
        @return
        """
        return self.san.debug

    def loaded(self):
        """
        The description of loaded comes here.
        @return
        """
        self.san.after_load()

    def refresh(self):
        """
        The description of refresh comes here.
        @return
        """
        self.san.refresh()
        return (0,'')

    def rescan(self,pvd,host):
        """
        The description of rescan comes here.
        @param pvd
        @param host
        @return
        """
        if not pvd : return (1,'please specify provider name to rescan')
        if not self.san.providers.has_key(pvd) : return (1,'provider name %s does not exist' % pvd)
        return self.san.rescan(pvd,host)

    def reboot(self,user,pvd,reason='',force=''):
        """
        The description of reboot comes here.
        @param user
        @param pvd
        @param reason
        @param force
        @return
        """
        if pvd and not self.san.providers.has_key(pvd) : return (1,'provider name %s does not exist' % pvd)
        logger.auditlog.info('User %s issued reboot (pvd=%s), Reason: %s' % (user,pvd,reason))
        self.san.reboot(pvd,force)
        return (0,'')

    def docmd(self,pvd,argv):
        """
        The description of docmd comes here.
        @param pvd
        @param argv
        @return
        """
        if not self.san.providers.has_key(pvd) : return (1,'provider name %s does not exist' % pvd)
        return self.san.providers[pvd].docmd(argv)

    def complete(self,txt='',show=False):
        """
        The description of complete comes here.
        @param txt
        @param show
        @return
        """
        lst=txt.split('/')
        n=len(lst); i=0
        obj=self.san
        while i<n :
            c=lst[i]
            if obj.__class__.__name__=='VSACollection':
                childs=obj.keys()
                cstars=[x for x in childs]
            else :
                if hasattr(obj.__class__,'child_obj'): childs=[x for x in obj.__class__.child_obj]
                else: childs=[]
                cstars=[x+'/' for x in childs]
                if hasattr(obj.__class__,'set_params'):
                    for s in obj.__class__.set_params : # TBD
                        childs+=[s]
                        cstars+=[s]
            if n == 1 and show :
                return [j for j in cstars + showlist if j.startswith(c)]
            if i == n-1:
                return [j for j in cstars if j.startswith(c)]
            if c in childs:
                if obj.__class__.__name__ == 'VSACollection':
                    obj=obj[c]
                else : obj=obj.__dict__[c]
            else:
                return []
            i+=1

    def get_log(self, ltype, tail=0, pvdname=''):
        """
        The description of get_log comes here.
        @param ltype
        @param tail
        @param pvdname
        @return
        """
        if not ltype:
            ltype = 'event'
        if ltype not in logopt:
            return (1,'not a valid log option, possible logs: %s' % ','.join(logopt))
        if ltype in ('tgt', 'agent'):
            if pvdname:
                try:
                    pvd = self.san.providers[pvdname]
                except KeyError:
                    return (1,'No provider named %s' % pvdname)
                #if self.san.providers.has_key(pvdname):
                #    pvd = self.san.providers[pvdname]
                #else:
                #    return (1,'No provider named %s' % pvdname)
            else:
                pvd = self.san.lclprovider
            if not pvd:
                return (1, 'Not connected to provider')
            log = pvd.get_log(ltype)
            j = "\n"
        else:
            if ltype == 'event':
                log_file = logger.event_log_file
            elif ltype == 'audit':
                log_file = logger.audit_log_file
            elif ltype == 'webportal':
                log_file = logger.web_log_file
            print log_file
            try:
                log = open(log_file).readlines()
            except Exception,err:
                return (1,'fail to show log, %s' % str(err))
            j = ""
        log = log[-tail:]
        return (0,j.join(log).strip())

    def get_object(self,lst):
        """
        The description of get_object comes here.
        @param lst
        @return
        """
        logger.eventlog.debug("get_object:%s", lst)
        n = len(lst)
        i = 0
        obj = self.san
        if n == 1 and not lst[0]:
            return (0, obj, '')
        while i < n:
            c = lst[i]
            isDict = obj.__class__.__name__ in ['VSACollection', 'RefDict']
            if isDict:
                childs = obj.keys()
            else:
                childs = [x for x in obj.__class__.child_obj]
            if c in childs:
                if isDict:
                    obj = obj[c]
                    if i == n-1:
                        return (0, obj, '')
                else:
                    if i == n-1:
                        if obj.__dict__[c].__class__.__name__ in ['VSACollection', 'RefDict']:
                            return (0, obj, c)
                        else:
                            return (0, obj.__dict__[c], '')
                    obj = obj.__dict__[c]
            elif not isDict and c in obj.__class__.set_params and i == n-1:
                return (0, obj, c)
            else:
                return (1, None, None)
            i += 1
        return (1, None, None)

    def test_objpath(self,path):
        """
        The description of test_objpath comes here.
        @param path
        @return
        """
        if path[-1:] == '/':
            path = path[:-1]
        lst = path.strip().split('/')
        (e,obj,sub) = self.get_object(lst)
        if e:
            return (e,'illegal object path')
        else:
            return (0,obj.__class__.__name__+':'+obj.name+':'+sub)

    def add_obj(self,path,name,val='',opts={},user=''):
        """
        The description of add_obj comes here.
        @param path
        @param name
        @param val
        @param opts
        @param user
        @return
        """
        if not re.match(r'^[#A-Za-z0-9:._-]+$',name):
            if val or not ('=' in name or ',' in name or ';' in name or not name):
                return (1, 'object name can only contain [A-Za-z0-9._-]', '')
            val = name
            name = '#'
        if path[-1:] == '/':
            path = path[:-1]
        lst = path.split('/')
        (e,obj,sub) = self.get_object(lst)
        if e:
            return (e,'illegal object path','')
        if not sub or sub not in obj.__class__.add_commands :
            return (1,'can not add elements to '+path,'')
        (e,params) = str2dict(val)
        if e:
            return (e,params,'')
        logger.auditlog.info('User:%s - add %s %s %s' % (user,path,name,val))

        if sub=='providers':
            if name=='#' or not name:
                return (1,'please specify provider name or url','')
            try:
                pvd = VsaProvider('',name,role=params.get('role'),san=self.san)
                name = pvd.name
                if self.san.providers.has_key(pvd.name):
                    del pvd
                    return (1,'provider name %s already exist' % name,'')
                self.san.providers.add(pvd.name,pvd)
                if pvd.state == ObjState.absent:
                    return (1,'Provider created, but not connected/discovered !',path+'/'+name)
                pvd.load(info=False, sync=True)
                if len(self.san.providers) == 0 or name == os.uname()[1].split('.')[0]:
                    # TBD in case of NOPVD flag the ==0 condition may have issues w redirect
                    self.san.lclprovider = pvd
                return (0,'new provider name %s created' % name,path+'/'+name)
            except Exception,err:
##                if self.san.debug : traceback.print_exc(file=sys.stdout)
                return (1,'Cannot add provider, '+str(err),'')

        d=getattr(obj,sub)
        isnew=not d.has_key(name)
        if self.san.runmode and not isnew:
            # allow add on existing object only when its initial configuration load
            return (1,'Object name %s already exist' % name,'')

        clname=d.cclass.__name__

        for p in params.keys():
            if p not in d.cclass.set_params:
                return (1,'can not set parameter %s in object %s, try again with proper settings' % (p,clname),'')

        if isnew and not opts['n']:
            for p in d.cclass.must_fields:
                if p not in params.keys():
                    return (1,'%s parameters must be specified for new %s objects, try again with proper settings' % (','.join(params.keys()),clname),'')

        if isnew :
            newobj=getattr(obj,'add_'+sub)(name)
            if not newobj : return (1,'object was not created, may already exist','')
            if newobj.__class__.__name__=='str' : return (1,newobj,'')
        else : newobj=d[name]

        newname=newobj.name
        parlist=newobj._owner

        force_update = bool(opts.get('f',False))

        for p in params.keys():
            (e,txt)=self.san.setobj(newobj,p,params[p],test=1,force=force_update)
            if e :
                if isnew : parlist.delete(newobj,True)
                return (e,'Object not created or updated, error: '+txt,'')
        for p in params.keys():
            (e,txt)=self.san.setobj(newobj,p,params[p],force=force_update)
            if e : return (e,'Object created or updated with error: '+txt,'')

        if not opts['n'] and hasattr(newobj,'update'):
            (e,txt)=getattr(newobj,'update')(True)
            newobj._flush()
            if e : return (0,'Object created or updated with error: '+txt,path+'/'+newname)

        return (0,'new object %s created' % newname,path+'/'+newname)

    def set_obj(self,path,val,opts={},user=''):
        """
        The description of set_obj comes here.
        @param path
        @param val
        @param opts
        @param user
        @return
        """
        if path[-1:]=='/':
            path=path[:-1]
        lst=path.split('/')
        (e,obj,sub)=self.get_object(lst)
        if e:
            (e1,obj,sub)=self.get_object(lst[:-1])
            if not e1:
                # TBD add only if its a can-add collection
                (e2,txt,no)=self.add_obj('/'.join(lst[:-1]), lst[-1], '', {'n':'1'})
            if e1 or e2:
                return (e,'illegal object path')
            (e,obj,sub)=self.get_object(lst)
            if e:
                return (e,'illegal object path, failed to create new object')

        force_update = bool(opts.get('f',False))

        logger.auditlog.info('User:%s - set %s %s' % (user,path,val))
        if sub:
            (e,txt)=self.san.setobj(obj,sub,val,force=force_update) # TBD is root the only place for sub ?
            if e:
                return (e,txt)
        else:
            (e,params)=str2dict(val)
            if e:
                return (e,params)
            for p in params.keys():
                if p not in obj.__class__.set_params:
                    return (1,'can not set parameter %s in object %s ' % (p,obj.__class__.__name__))
                (e,txt)=self.san.setobj(obj,p,params[p],test=1,force=force_update)
                if e:
                    return (e,txt)
            for p in params.keys():
                (e,txt)=self.san.setobj(obj,p,params[p],force=force_update)
                if e:
                    return (e,txt)

        if not opts['n'] and hasattr(obj,'update'):
##            print obj.name
            (e,txt)=getattr(obj,'update')()
            obj._flush()
            if e:
                return (e,'error in updating object : '+txt)
        return (0,'set operation was successful')

    def update_obj(self,path,opt={},user=''):
        """
        The description of update_obj comes here.
        @param path
        @param opt
        @param user
        @return
        """
        lst=path.split('/')
        if len(lst)>1 and lst[-1]=='' :
            lst=lst[:-1]; path=path[:-1]
        if lst and lst[-1].endswith('*'):
            wild=lst[-1]
            lst=lst[:-1]
        else : wild=''
        (e,obj,sub)=self.get_object(lst)
        if e: return (e,'illegal object path')
        if sub :
            IsColl=obj.__dict__[sub].__class__.__name__=='VSACollection'
            if not wild and IsColl : return(1,'must specify an object or a range to update (not a collection)')
            if not wild : return(1,'cannot update a property, only a complete objects')
            objl=[o for o in obj.__dict__[sub].values() if o.name.startswith(wild[:-1])]
            if len(objl)==0 : return (0,'No match found, zero objects were updated')
        else :
            if not (hasattr(obj,'_owner') and obj._owner.__class__.__name__=='VSACollection'):
                return (1,'not a collection')
            objl=[obj]
        logger.auditlog.info('User:%s - update %s' % (user,path))
        txt=''
        for o in objl :
            if hasattr(o,'update'):
                (e,txt)=getattr(o,'update')()
                o._flush()
                if e : return (e,txt)
            else : return (1,'object does not support update command ')
        if wild or txt=='' : txt='Update operation was successful'
        return (0,txt)

    def save_configuration(self, path='/', opt={}, to=None):
        """
        The description of save_configuration comes here.
        @param path
        @param opt
        @param to
        @return
        """
        logger.auditlog.info('User: - save configuration')
        if not to: to = config_db
        (e,lst)=self.export_obj(path,opt)
        try:
            f=open(to,'w')
            f.write('\n'.join(lst)+'\n')
            f.close()
        except Exception, exc:
            logger.auditlog.info('Error saving configuration: %s traceback: %s'
                    % (str(exc),  traceback.format_exc()))
            return (1,'error saving configuration')
        return (0,'configuration saved successfuly')

    def export_obj(self,path,opt={}):
        """
        The description of export_obj comes here.
        @param path
        @param opt
        @return
        """
        lst=path.split('/')
        if len(lst)>1 and lst[-1]=='' :
            lst=lst[:-1]; path=path[:-1]
        (e,obj,sub)=self.get_object(lst)
        if e: return (e,'illegal object path')
        if sub : obj=obj.__dict__[sub]
        if hasattr(obj,'export'):
            return (0,getattr(obj,'export')(self.san,path))
        else : return (1,'object does not support export command ')

    def print_obj(self, path, str2, opt={}):
        """
        The description of print_obj comes here.
        @param path
        @param str2
        @param opt
        @return
        """
        lst = path.split('/')
        w = tstint(opt['w'], 120)
        lvl = tstint(opt['l'], 0)
        all = opt['a']
        sep = opt['s']
        if path == 'config' :
            (e, lst) = self.export_obj(str2, opt)
            if e : return(1, "** Error, "+lst)
            return (0,'\n'.join(lst))
        if path in ['system','version','cache','fctree'] :
            out=sanshow(self.san,path,str2,lvl)
            return (0,'\n'.join(out+['']))

        if len(lst) > 1 and lst[-1] == '' :
            lst = lst[:-1]
            path = path[:-1]
        (e,obj,sub) = self.get_object(lst)
        if e:
            return (e,'illegal object path')
        print lst,str(obj),str(sub)
        if sub :
            if not hasattr(obj,sub):
                return (1,'property %s is not readable' % sub)
            if getattr(obj,sub).__class__.__name__ == 'instancemethod' :
                return (1,'property %s is not readable (Method).' % sub)
            if isinstance(obj.__dict__[sub],VSACollection) or isinstance(obj.__dict__[sub],RefDict):
                if opt['d'] :
                    out=[]
                    for subobj in obj.__dict__[sub]() : out+=[subobj.fullpath]+print_class(subobj)+['']
                    return (0,'\n'.join(out))
                else : return (0,obj.__dict__[sub].print_tbl(width=w,lvl=lvl,sep=sep,all=all))
            else :
                return (0,str(obj.__dict__[sub]))
        else :
            if obj.__class__.__name__=='dict':
                out=[k+'='+str(v) for k,v in obj.items()]
                return (0,'\n'.join(out))
        if opt['d']:
            out = print_class(obj)
        else :
            out = [obj.ui_getdetail()]
            for ch in obj.child_obj:
                if (isinstance(obj.__dict__[ch],VSACollection) or isinstance(obj.__dict__[ch],RefDict)) and len(obj.__dict__[ch]()):
                    out+=['','  '+obj.__dict__[ch].fullpath, obj.__dict__[ch].print_tbl('    ',width=w,lvl=lvl,sep=sep,all=all)]
        return (0,'\n'.join(out+['']))

    def del_obj(self,path,opt={},user=''):
        """
        The description of del_obj comes here.
        @param path
        @param opt
        @param user
        @return
        """
        lst=path.split('/')
        if len(lst) > 1 and lst[-1]=='':
            lst=lst[:-1]
            path=path[:-1]
        if lst and lst[-1].endswith('*'):
            wild=lst[-1]
            lst=lst[:-1]
        else:
            wild=''
        (e,obj,sub)=self.get_object(lst)
##        print 'del:',e,obj,sub
        if e:
            return (e,'illegal object path')
        if sub:
            IsColl = obj.__dict__[sub].__class__.__name__=='VSACollection'
            if not wild and IsColl:
                return (1,'must specify an object or a range to delete (not a collection)')
            if not wild or not IsColl:
                return (1,'cannot delete a property, only complete objects')
            objl = [o for o in obj.__dict__[sub].values() if o.name.startswith(wild[:-1])]
            if len(objl)==0:
                return (0,'No match found, zero objects were deleted')
        else:
            if not (hasattr(obj,'_owner') and obj._owner.__class__.__name__=='VSACollection'):
                return (1,'not a collection')
            objl=[obj]
        if not objl[0]._owner.can_delete:
            return (1,'%s items can not be deleted' % objl[0].description)
        logger.auditlog.info('User:%s - del %s' % (user,path))
        txt=''
        for o in objl:
            (e,txt)=o._owner.delete(o,opt['f'])
            if e:
                return (e,txt)
        if wild or txt=='':
            txt='Delete operation was successful'
        return (0,txt)

    def get_target_portal(self, target, srcip):
        """
        The description of get_target_portal comes here.
        @param target
        @param srcip
        @return
        """
        if not self.san.targets.has_key(target):
            return (1,'target name %s not found' % target,'')
        tr = self.san.targets[target]
        if not tr.device:
            return (1,'no provider assigned to target '+target,'')
        ip = IP(srcip)
        # TBD use ip route get to address routers
        for nic in tr.device.ifs():
                if nic.state == ObjState.running and nic.data and ip in nic.subnet():
                       print nic.ip,tr.pid
                       return (0, str(nic.ip), str(3260+tr.pid))
        logger.eventlog.error('get_portal failed, no matching address for target %s on provider %s, src IP %s' % (target,tr.device.name,srcip))
        return (1,'no matching address was found','')


def sanshow(san,objcls='',obj='',level=1,mode=0):
    """
    The description of sanshow comes here.
    @param san
    @param objcls
    @param obj
    @param level
    @param mode
    @return
    """
    out=[]
    if objcls=='version' :
        out+=['','Version Info','==============']
        for pvd in san.providers.values():
            out+=['Provider %s State: %s  URL: %s' % (pvd.fullname,pvd.state,pvd.url)]
            out+=['  Ver: '+','.join(pvd.version)]
        return out

    if objcls=='cache' :
        for pvd in san.providers.values():
            for vol in pvd.cachevg.volumes.keys() :
                (e,r)=pvd.get_cache_stt(CACHEPFX+vol)
                if e : return ['Cache stat error:',r]
                volname=vol.replace(CACHESEP,':')
                (e,t,v) = volstr2obj(volname, pvdin=pvd,
                                chklock=False, chkstate=False,
                                san=SanContainer.getInstance().get_san() )
                if e : volobj='?'
                else : volobj=str(v)
                if not obj or (obj in volname) or (obj in volobj) :
                    out+=['','%s (%s): ' % (volname,volobj)+dict2str(r)]

    if objcls =='system' :
        u=os.uname()
        out+=['','System Info (local)','===================']
        out+=[str(datetime.now())]
        out+=['Host: '+u[1]]
        for pvd in san.providers.values():
            out+=['Provider %s  State: %s/%s  Procs: %d  URL: %s' % (pvd.fullname,pvd.state,pvd.clusterstate,pvd.tgtprocs,pvd.url)]
            out+=['  interfaces:']
            for ifc in pvd.ifs.values() :
                out+=[ifc.show(mode,level,'    ')]

    if objcls =='fctree' :
        out+=['','FC Ports/Nodes Info','====================']
        hbtl={}
        for p in san.disks.values(): # TBD error, need per provider
            for pt in p.paths.values() :
                hbtl[pt.hbtl]=pt
        for p in san.providers.values() :
            for host in p.fcports.keys() :
                fcp=p.fcports[host]
                if fcp.maxnpiv : vp=" vports: %d/%d" % (len(fcp.vports),fcp.maxnpiv)
                elif fcp.parport : vp=" Parent: %s" % fcp.parport
                else : vp=''
                out+=["%s:%s wwpn: %s wwnn: %s  state: %s speed: %s" % \
                  (p.name,host,fcp.wwpn,fcp.wwnn,fcp.state,fcp.speed)+vp]
                if level>0:
                    if fcp.targets : out+=["  Identified Targets:"]
                    for hbt in fcp.targets.keys():
                        tgp=fcp.targets[hbt]
                        out+=["    %s wwpn: %s wwnn: %s  state: %s" % \
                          (hbt,tgp.wwpn,tgp.wwnn,tgp.state)]
                        if level>1:
                            out+=["      Identified Luns/Paths:"]
                            for d in sorted(hbtl.keys()) :
                                if d.startswith(hbt.strip()) :
                                    pt=hbtl[d]
                                    out+=['       %-8s %-8s %-8s Vendor: %-10s %-10s  Size: %10s' % \
                                      (pt.hbtl,pt.devfile,pt.state,pt.parent.vendor,pt.parent.model,printsz(pt.parent.size))]
                    out+=['']
    return out


def getManholeFactory(namespace, **passwords):
    """
    SSH Factory for Manhole
    """
    realm = manhole_ssh.TerminalRealm( )
    def getManhole(_):
        """
        The description of getManhole comes here.
        @param _
        @return
        """
        return manhole.ColoredManhole(namespace)
    realm.chainedProtocolFactory.protocolFactory = getManhole
    p = portal.Portal(realm)
    p.registerChecker(checkers.InMemoryUsernamePasswordDatabaseDontUse(**passwords))
    f = manhole_ssh.ConchFactory(p)
    return f


class VsaSrvDaemon(Daemon):

    def pre_start(self):
        """
        The description of pre_start comes here.
        @return
        """
        check_for_role()

        # Initialize SAN Server resource for XML RPC and VSA content
        self.san = SanResources()
        SanContainer.getInstance().set_san(self.san)
        self.san_srv = SanServer(self.san)
        self.san_srv.post_init(loadpvd=True)

        if self.san_srv.loadpvdErr:
            if isinstance(self.san_srv.loadpvdErr, LoopbackException):
                return ERR_LOADPVD_LO
            return ERR_LOADPVD

        ports = []

        # Listen for XML RPC calls on SAN Server resource
        ports.append(
            reactor.listenTCP(SANSRV_XMLRPC_PORT,
                server.Site(self.san_srv,
                    logPath = logger.srvxmlrpc_log_file)
            ))

        self.vsapor = webportal.VSAPortal()
        self.vsapor.san = self.san
        self.vsapor.srv = self.san_srv

        server_site = server.Site(self.vsapor)
        server_site.sessionFactory = webportal.NoTimeoutSession

        # Listen for http portal
        ports.append(reactor.listenTCP(webportal.listenport, server_site))

        # Open SSH manhole
        ports.append(reactor.listenTCP(MANHOLE_PORT, getManholeFactory(globals(), **MANHOLE_CREDENTIALS)))

        # After reactor shutdown, stop listening on all opened ports
        for port in ports:
            reactor.addSystemEventTrigger('after', 'shutdown', port.stopListening)

        return 0

    def run(self):
        """
        The description of run comes here.
        @return
        """
        log.startLogging(sys.stdout)
        logger.eventlog.info('SAN Server started')
        # Run reactor mainloop
        reactor.run()
        logger.eventlog.info('SAN Server stopped')


def check_for_role():
    """
    The description of check_for_role comes here.
    @return
    """
    # Check for role
    e = 0
    role = get_vsa_role()
    transition = os.getenv('VSA_HA_TRANSITION', False)

    if ha_rsc_status() == 'none':
        e = ERR_HA_SLAVE
    elif ha_rsc_status() == 'transition' and not transition:
        e = ERR_HA_TRANSITION
    elif role == 'compute':
        e = ERR_COMPUTE_NODE

    if e == ERR_HA_SLAVE:
        print '\n*** This node is a Standby node ***\n'
    elif e == ERR_HA_TRANSITION:
        print '\n*** This node is in transition ***\n'

    if e:
        sys.exit(e)


def main():
    """
    SAN Server Main
    """
    global daemon
    if len(sys.argv) == 2:
        vsasrvlog = os.path.join(config.log_dir, 'vsasrv.console.log')
        daemon = VsaSrvDaemon(pidfile='/var/run/vsasrv.pid', stdout=vsasrvlog, stderr=vsasrvlog)
        if 'start' == sys.argv[1]:
            daemon.start()
        elif 'stop' == sys.argv[1]:
            daemon.stop()
        elif 'restart' == sys.argv[1]:
            daemon.restart()
        elif 'status' == sys.argv[1]:
            if daemon.status():
                sys.exit(0)
            else:
                sys.exit(1)
        else:
            print 'Unknown command'
            sys.exit(2)
        sys.exit(0)
    else:
        print 'usage: %s start|stop|restart|status' % sys.argv[0]
        sys.exit(2)




if __name__ == '__main__':
    main()
