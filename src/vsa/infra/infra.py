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


from os import path, popen

from vsa.infra.processcall import process_call
from vsa.infra.config import vsa_conf

_VERSION=None
def getVersion():
    """
    The description of getVersion comes here.
    @return
    """
    global _VERSION
    if _VERSION: return _VERSION
    e,o=process_call(['rpm','-q','scsi-target-utils','vsa'],log=False)
    v=o.splitlines()
    e,inf=process_call(['uname','-r'],log=False)
    version=[inf.strip()]+[i.strip() for i in v]
    _VERSION=version
    return version

def iif(test,tval,fval=''):
    """
    The description of iif comes here.
    @param test
    @param tval
    @param fval
    @return
    """
    if test : return tval
    else : return fval

def b2YN(val):
    """
    The description of b2YN comes here.
    @param val
    @return
    """
    if val : return 'Y'
    else : return 'N'

def val2str(val):
    """
    The description of val2str comes here.
    @param val
    @return
    """
    if isinstance(val,bool) : return b2YN(val)
    if isinstance(val,list) : return ','.join(val)
    return str(val)

def bulkupd(obj,dict):
    """
    The description of bulkupd comes here.
    @param obj
    @param dict
    @return
    """
    for kk in dict.keys() :
        obj.__dict__[kk]=dict[kk]

def printsz(val) :
    """
    The description of printsz comes here.
    @param val
    @return
    """
    if val==0 : return '0'
    if val<2000 : return '%dMB' % val
    else : return '%dGB' % (int(val/1024))

def txt2size(txt,size=0):
    """
    The description of txt2size comes here.
    @param txt
    @param size
    @return
    """
    if not txt : return (0,0)
    unit=txt[-1].lower()
    if unit in ['m','g','%']: num=tstint(txt[:-1])
    else : num=tstint(txt)
    if num<0 : return (1,'not a valid integer')
    if unit=='g' : num=num*1024
    if unit=='%' :
        if size : num=num*size/100
        else : return (1,'cannot use %')
    return (0,num)

def getnextidx(ls,first=0):
    """
    The description of getnextidx comes here.
    @param ls
    @param first
    @return
    """
    ls.sort()
    m=first
    for l in ls :
        if m==l : m+=1
        else : return m
    return m

def getnextspace(d,first=1):  # find the first/smallest unassigned idx number in list
    """
    The description of getnextspace comes here.
    @param d
    @param first
    @return
    """
    j=first
    for i in sorted(map(int,d)) :
        if i==j or i<j:    j=i+1
        else : break
    return j

def pdict(dic): # nice dictionary print
    """
    The description of pdict comes here.
    @param dic
    @return
    """
    for i in dic.keys() :
        print "   ",i," = ",dic[i]

def safekey(dic,key,default=''):
    """
    The description of safekey comes here.
    @param dic
    @param key
    @param default
    @return
    """
    if dic.has_key(key) : return dic[key]
    else : return default

def safepeek(ls) :
    """
    The description of safepeek comes here.
    @param ls
    @return
    """
    if len(ls)>0 : return ls[0]
    else : return ''

def tstint(i,default=-1) :
    """
    The description of tstint comes here.
    @param i
    @param default
    @return
    """
    try:
        t = int(i)
        return t
    except ValueError:
        return default

def str2dict(val):
    """
    The description of str2dict comes here.
    @param val
    @return
    """
    if not val.strip():
        return (0, {})
    l = val.strip().split(',')
    dic = {}
    for o in l:
        sp = o.split('=', 1)
        if len(sp) < 2:
            sp += ['1']
        dic[sp[0]] = sp[1]
    return (0, dic)

def dict2str(val):
    """
    The description of dict2str comes here.
    @param val
    @return
    """
    pr=[]
    for p in val.keys() :
        if ' ' in val[p] : val[p]='"'+val[p]+'"'
        pr+=['%s=%s'% (p,str(val[p]))]
    return ','.join(pr)

def getunique(lst,pfx,start=1):
    """
    The description of getunique comes here.
    @param lst
    @param pfx
    @param start
    @return
    """
    # return a unique string that starts with pfx and is not repeated in lst
    i=start
    while  pfx+str(i) in lst : i+=1
    return pfx+str(i)

def confirm(txt,defans='y'):
    """
    The description of confirm comes here.
    @param txt
    @param defans
    @return
    """
    ans='x'
    while ans.lower() not in ['y','n','','yes','no']:
        try:
            ans=raw_input('%s [%s] ?' % (txt,defans))
        except (KeyboardInterrupt, EOFError):
            print
            return ''
        if ans.lower() not in ['y','n','','yes','no']:
            print 'Please type y/n/yes/no as answer, try again'
    if ans=='' : ans=defans
    if ans.lower() in ['','y','yes'] : return 'y'
    return 'n'

def hex2chrlist(k):
    """
    The description of hex2chrlist comes here.
    @param k
    @return
    """
    return ''.join([chr(int(k[i*2:i*2+2],16)) for i in range(len(k)/2)])

def chrlist2hex(x):
    """
    The description of chrlist2hex comes here.
    @param x
    @return
    """
    return ''.join(['%02X' % i for i in [ord(c) for c in x]])

def ha_rsc_status():
    """
    The description of ha_rsc_status comes here.
    @return
    """
    if not path.isfile('/usr/bin/cl_status'):
        return None
    try:
        c = popen('/usr/bin/cl_status hbstatus >/dev/null 2>&1 && /usr/bin/cl_status rscstatus 2>/dev/null').read().strip()
        return c
    except:
        return None


# roles allowed in vsa config file
VSA_ROLES = ('standalone', 'standby', 'master', 'compute')

def get_vsa_role():
    """
    The description of get_vsa_role comes here.
    @return
    """
    role = None
    role = vsa_conf.safe_get('vsa', 'role', VSA_ROLES[0])
    if role not in VSA_ROLES:
        role = VSA_ROLES[0] #TODO: logit!
    return role

def set_vsa_role(role):
    """
    The description of set_vsa_role comes here.
    @param role
    @return
    """
    if role not in VSA_ROLES:
        return (1, 'invalid role')
    vsa_conf.safe_set('vsa', 'role', role)
    return (0,'')

def parse_cfg(arg,clist=[],optlist='',optdef={}):
    """
    The description of parse_cfg comes here.
    @param arg
    @param clist
    @param optlist
    @param optdef
    @return
    """
    a=arg.strip().split()
    opts={};

    # test if the first arg matches the allowed categories (clist), if clist is not []
    if clist and len(a)>0 and (not a[0].startswith('-')) and (a[0] not in clist) :
        print '*** Unknown category: '+a[0]
        print 'Category options are: '+','.join(clist)
        return (1,'','','',{})

    for o in optlist :
        if optdef.has_key(o) : opts[o]=optdef[o]
        else : opts[o]=''

    argsl=[]; i=0;
    while i<len(a):
        if not a[i].startswith('-') :
            argsl+=[a[i]]
            i+=1
        else : break

    for o in a[i:] :
        if not o.startswith('-') or len(o)<2 or (o[1] not in optlist):
            print '*** Illegal Option: %s , valid options are %s, and must start with a "-"' % (o,optlist)
            return (1,'','','',{})
        if len(o)==2: opts[o[1]]='1'
        else : opts[o[1]]=o[2:]
    a0=''; a1=''; a2='';
    if len(argsl)>0: a0=argsl[0]
    if len(argsl)>1: a1=argsl[1]
    if len(argsl)>2: a2=argsl[2]
    return (0,a0,a1,a2,opts)



