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


from vsa.infra.infra import dict2str
from vsa.client.gui.jsForm import ht_form, ht_combo, ht_input, ht_radio, ht_checkbox

MAXinRadio=3

FieldNameDefs={'reqstate':'Requested State','vparams':'SCSI vParams','readahead':'Read-ahead',
'iosched':'IO Scheduler','ip':'IP','bcast':'Broadcast','cachedevices':'Cache Devices',
'behind':'Write-behind','glbl':'Global Pool','avgload':'Avarage Load','ips':'IP Addresses',
'ostype':'OS Type','iscsiopt':'iSCSI Options'}

def hfrm_generic(san,obj,ftype, fpath):
    """
    The description of hfrm_generic comes here.
    @param san
    @param obj
    @param ftype
    @param fpath
    @return
    """
    form=ht_form(ftype, fpath)
    if ftype=='add' :
        myobj=obj.cclass('')
    else :
        myobj=obj

    must=myobj.must_fields
    flds=myobj.set_params
    newonly=myobj.newonly_fields
    for fld in flds :
        fldtype=getattr(myobj,fld).__class__.__name__
        cname=myobj.__class__.__name__
        if fld=='loadonly' : continue
        if fld=='devices' and cname in ['SanRaidGrp','SanVolgrp'] : continue
        ismust = fld in myobj.must_fields
        isnewonly = fld in fld in myobj.newonly_fields
        disabled = ftype<>'add' and isnewonly
        flabel=fld.capitalize()
        if FieldNameDefs.has_key(fld):
            flabel=FieldNameDefs[fld]
        if hasattr(myobj,'get_'+fld) :
            if fld=='provider':
                opts=san.providers.keys()
                if ftype=='add' : pvd=''
                else : pvd=getattr(myobj,'get_'+fld,'')(san,fld)[1]
                form.add(ht_combo(fld,flabel,ismust,opts,pvd,disabled))
            elif fld=='server':
                opts=san.servers.keys()
                if ftype=='add' : tmp=''
                else : tmp=getattr(myobj,'get_'+fld,'')(san,fld)[1]
                form.add(ht_combo(fld,flabel,ismust,opts,tmp,disabled))
            elif fld=='pool':
                opts=san.pools.keys()
                if ftype=='add' : tmp=''
                else : tmp=getattr(myobj,'get_'+fld,'')(san,fld)[1]
                form.add(ht_combo(fld,flabel,ismust,opts,tmp,disabled))
            else :
                if ftype=='add' : text=''
                else : text=getattr(myobj,'get_'+fld,'')(san,fld)[1]
                form.add(ht_input(fld,flabel,ismust,text,disabled))
        elif fldtype=='EnumValue':
            if fld=='reqstate' : flabel='Requested State'
            opts=getattr(myobj,fld,'').enumtype._keys
            if len(opts)<=MAXinRadio:
                form.add(ht_radio(fld,flabel,ismust,opts,str(getattr(myobj,fld,'')),disabled))
            else:
                form.add(ht_combo(fld,flabel,ismust,opts,str(getattr(myobj,fld,'')),disabled))
        elif fldtype=='bool':
            form.add(ht_checkbox(fld,flabel,ismust,getattr(myobj,fld,True),disabled))
        elif fldtype=='dict':
            form.add(ht_input(fld,flabel,ismust,dict2str(getattr(myobj,fld,None)),disabled))
        elif fldtype=='list':
            newstr=map(str,getattr(myobj,fld,[]))
            form.add(ht_input(fld,flabel,ismust,';'.join(newstr),disabled))
        elif fldtype<>'instancemethod' and fldtype<>'NoneType':
            form.add(ht_input(fld,flabel,ismust,str(getattr(myobj,fld,'')),disabled))
    if ftype=='add' : del myobj
    return form.html()


def ht_demo(ftype, fpath):
    """
    The description of ht_demo comes here.
    @param ftype
    @param fpath
    @return
    """
    f=ht_form()
    f.addHidden('form-type',ftype)
    f.addHidden('form-path',fpath)
    f.add( ht_input("name1","label1") )
    f.add( ht_input("name2","label2") )
    f.add( ht_input("name3","label3") )
    f.add( ht_combo("name4","label4",options=['o1','o2','o3','o4']) )
    return f.html()

