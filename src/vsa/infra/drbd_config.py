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


import re, shutil
from vsa.infra import logger
from xml.dom.minidom import parse, parseString
from vsa.infra.processcall import process_call
#from processcall import *

#on both: drbdadm create-md resource
#on both: drbdadm up resource
#on source: drbdadm -- --overwrite-data-of-peer primary resource

drbd_resource_file='/etc/drbd.d/vsa.res'

NO_DRBD_RESOURCE_DEFINED = 3

def drbdadm(*args):
    """
    The description of drbdadm comes here.
    @param *args
    @return
    """
    cmd=["/sbin/drbdadm"]+list(args)
    print "_drbdadm: %s" % str(cmd)
    e,r=process_call(cmd)
    return e,r

def drbd_create_resource(resource):
    """To be executed on both nodes after adding a resource"""
    e,r=drbdadm("-d","create-md",resource)
    if e: return e,r
    lines=r.splitlines()
    for l in lines:
        l=l.strip().split(' ')
        if l[0].rfind("drbdmeta") >= 0:
            l.insert(1,"--force")
        e,o = process_call(l)
        if e:
            return e,o
    return e,o

def drbd_become_primary(resource):
    """To be executed on the primary node after adding a resource"""
    return drbdadm("--", "--overwrite-data-of-peer", "primary",resource)

def drbd_discard_my_data(resource):
    """to solve split brain. run on secondary node"""
    return drbdadm("--", "--discard-my-data", "connect",resource)

#re.findall('^resource ([a-z0-9]+) {.[^}]*device\s+([a-z0-9/]+).[^}]*}',b,re.I + re.M + re.S)
def drbd_resource_names():
    """Returns a list of current resource names"""
    res=[]
    e,out=drbdadm("dump")
    if e: return e,res
    for l in out.splitlines():
        if l.strip()[:8]=="resource":
            res.append(l.strip().split()[1])
    return e,res

def drbd_new_float_resource(res_name, drbd_dev, local_ip, local_port, local_dev, remote_ip, remote_port, remote_dev, protocol='C'):
    """Returns a new drbd resource block"""
    local_adr = "%s:%s" % (local_ip, local_port)
    remote_adr = "%s:%s" % (remote_ip, remote_port)
    r = """
resource %s {
    device %s;
    meta-disk internal;
    protocol %s;

    floating %s {
        disk %s;
    }

    floating %s {
        disk %s;
    }
}
""" % (res_name, drbd_dev, protocol, local_adr, local_dev, remote_adr, remote_dev)
    return r

def drbd_new_on_resource(res_name, drbd_dev, local_host, local_ip, local_port, local_dev, remote_host, remote_ip, remote_port, remote_dev, protocol='C'):
    """Returns a new drbd resource block"""
    local_adr = "%s:%s" % (local_ip, local_port)
    remote_adr = "%s:%s" % (remote_ip, remote_port)
    r = """
resource %s {
    device %s;
    meta-disk internal;
    protocol %s;

    on %s {
        disk %s;
        address %s;
    }

    on %s {
        disk %s;
        address %s;
    }
}
""" % (res_name, drbd_dev, protocol, local_host, local_dev, local_adr, remote_host, remote_dev, remote_adr)
    return r


def drbd_del_resource(resource,fail_if_not_defined=True):
    """Delete a resource from /etc/drbd.d/vsa.res"""
    data=''
    try:
        data=open(drbd_resource_file,'r').read()
    except:
        return (1,'Resource file not found')

    # fetch the resource block
    p='\s+^resource '+resource+' {(((?!^}).)*)^}\s+'
    pt = re.compile(p, re.M+re.S)
    newdata = re.sub(pt, "", data)

    # check if found
    if newdata == data:
        if fail_if_not_defined:
            return (1,'Resource name not found')
        return (0,'')

    shutil.copy(drbd_resource_file, drbd_resource_file+'.old');
    f=open(drbd_resource_file,'w')
    f.writelines(newdata)
    f.close()

    return (0,'')

def balanced_brackets(lst):
    """Input: list of {} brackets.
    Output: If brackets are balanced."""
    c=0
    for i in lst:
        if i=='{': c+=1
        if i=='}': c-=1
        if i<0: break
    if c==0: return True
    return False

def drbd_overview():
    """
    The description of drbd_overview comes here.
    @return
    """
    r = {}
    try:
        (e, out) = process_call(['/sbin/drbdadm', 'sh-status'], log=False, stderr=False)
        if e:
            return (0, r)
        out = out.strip().splitlines()
        g = {}
        for line in out:
            if not line:
                continue
            pair = line.split('=')
            key = pair[0]
            if len(pair) > 1:
                val = pair[1]
            else:
                val = ''
            if key == "_conf_res_name":
                # new res
                g['name'] = val
            elif key in ('_minor', '_cstate', '_role', '_resynced_percent', '_disk'):
                g[key[1:]] = val
            elif key == "_sh_status_process":
                # end of res
                o = process_call(['/sbin/drbdadm', 'sh-ll-dev', g['name']], log=False)
                g['dev'] = o[1].strip()
                o = process_call(['/sbin/drbdadm', 'sh-dev', g['name']], log=False)
                g['device'] = o[1].strip()
                # add drbd res
                r[g['minor']] = g
                g = {}
    except Exception, e:
        logger.agentlog.debug('drbd_overview error: %s' % str(e))
        r = {}
    return (0, r)

def drbd_pvd_dict(pvd_host, pvd_ip, pvd_port, pvd_dev):
    """
    The description of drbd_pvd_dict comes here.
    @param pvd_host
    @param pvd_ip
    @param pvd_port
    @param pvd_dev
    @return
    """
    return {"host": pvd_host, "ip": pvd_ip, "port": pvd_port, "disk": pvd_dev}

def drbd_res_dict(drbd_dev, local_host, local_ip, local_port, local_dev, remote_host, remote_ip, remote_port, remote_dev, protocol='C'):
    """
    The description of drbd_res_dict comes here.
    @param drbd_dev
    @param local_host
    @param local_ip
    @param local_port
    @param local_dev
    @param remote_host
    @param remote_ip
    @param remote_port
    @param remote_dev
    @param protocol
    @return
    """
    return {"device": drbd_dev, "protocol": protocol,
           "pvd1": drbd_pvd_dict(local_host, local_ip, local_port, local_dev),
           "pvd2": drbd_pvd_dict(remote_host, remote_ip, remote_port, remote_dev)}

def drbd_res_exists(res):
    """returns True if resource exists or on error"""
    logger.eventlog.debug('checking if drbd res %s exists' % str(res) )
    e,r = drbd_resource_names()
    if e==NO_DRBD_RESOURCE_DEFINED : e=0
    if e: logger.eventlog.debug("resource error")
    if e or r.__contains__(res): return True
    return False

# TODO not complete
def _drbd_get_resource(res=None):
    """Get drbd_res_dict from res name"""
    r={}
    #a=subprocess.Popen(["drbdadm","dump-xml"],stdout=subprocess.PIPE)
    #o=a.stdout.read()
    dom = parseString("")
    for resource in dom.getElementsByTagName("resource"):
        name=resource.getAttribute("name")
        if res and res!=name: continue
        d={}
        d['protocol']=str(resource.getAttribute("protocol"))
        d['device']=str(resource.getElementsByTagName("device")[0].childNodes[0].data)
        i=1
        for host in resource.getElementsByTagName("host"):
            hostname=str(host.getAttribute("name"))
            dev=str(host.getElementsByTagName("device")[0].childNodes[0].data)
            adr=host.getElementsByTagName("address")[0]
            port=str(adr.getAttribute("port"))
            ip=str(adr.childNodes[0].data)
            i+=1
            d['pvd%d'%i]=drbd_pvd_dict(hostname, ip, port, dev)
        if res: break
        r[name]=d
    return r

# TODO not complete
def _drbd_resource_conflict(drbd_res):
    """check if the resource can conflict"""
    ress=_drbd_get_resource()
    for res in ress:
        d=ress[res]
        if d['device']==drbd_res['device']: return True
        #
    return False

def _drbd_init(res, primary=False):
    """
    The description of _drbd_init comes here.
    @param res
    @param primary
    @return
    """
    (e,r) = drbd_create_resource(res)
    print "_drbd_init: %s %s" % ( str(e), str(r) )
    if e: return (e,r)
    (e,r) = drbd_up(res)
    if e: return (e,r)
    if primary: (e,r) = drbd_become_primary(res)
    return (e,r)

def drbd_add(res, drbd_dict, primary=False, loadonly=False):
    """
    if loadonly is True the resource is not initialized.
    """
    logger.eventlog.debug( "drbd_add: res:%s loadonly=%s" % ( res, str(loadonly) ))
    d=drbd_dict
    if drbd_res_exists(res):
        if loadonly: return (0, '')
        else: return (1,"Resource name already exists")
    r = drbd_new_on_resource(res, d["device"],
            d["pvd1"]["host"], d["pvd1"]["ip"], d["pvd1"]["port"], d["pvd1"]["disk"],
            d["pvd2"]["host"], d["pvd2"]["ip"], d["pvd2"]["port"], d["pvd2"]["disk"],
            d["protocol"])
    f=open(drbd_resource_file,'a');
    f.write(r)
    f.close()
    if loadonly:
        e,r = drbd_up(res)
        logger.eventlog.debug('drbd_add load: %s - primary: %s' % ( str(e), str(primary) ))
        if e or not primary: return e,r
        logger.eventlog.debug('promoting')
        return drbd_promote(res)
    return _drbd_init(res, primary)

def drbd_remove(res):
    """
    The description of drbd_remove comes here.
    @param res
    @return
    """
    e,r=drbd_down(res)
    if e==NO_DRBD_RESOURCE_DEFINED: e=0
    if e: return e,r
    return drbd_del_resource(res, fail_if_not_defined=False)

def drbd_replace(res, drbd_dict):
    """
    The description of drbd_replace comes here.
    @param res
    @param drbd_dict
    @return
    """
    pass
# use adjust
#    r=drbd_remove(res)
#    if r[0]!=0:
#        return r
#    return drbd_add(res, drbd_dict)

def drbd_up(res):
    """
    The description of drbd_up comes here.
    @param res
    @return
    """
    return drbdadm("up",res)

def drbd_down(res):
    """
    The description of drbd_down comes here.
    @param res
    @return
    """
    return drbdadm("down",res)

def drbd_reinit(res):
    """
    The description of drbd_reinit comes here.
    @param res
    @return
    """
    e,r=drbdadm("down",res)
    if e: return e,r
    return drbdadm("up",res)

def drbd_promote(res):
    """
    The description of drbd_promote comes here.
    @param res
    @return
    """
    return drbdadm("primary",res)

def drbd_demote(res):
    """
    The description of drbd_demote comes here.
    @param res
    @return
    """
    return drbdadm("secondary",res)
