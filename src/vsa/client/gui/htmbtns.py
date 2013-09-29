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


from enum import Enum
#===============================================================================
# from jsForm import *
# from infra import *
# from params import *
#===============================================================================

from xml.dom import minidom, Node
from vsa.infra.params import Transport, RaidLevel
from vsa.infra.infra import txt2size
from vsa.client.gui.jsForm import ht_form, ht_combo, ht_radio, ht_input, ht_checkbox
from vsa.client.gui.htmforms import ht_demo
from vsa.model import obj2volstr


BtnAction = Enum('none', 'add', 'edit', 'delete', 'confirm', 'form', 'js')
# none - selection is not important
# one - only one selection is allowed
# many - one or above selection is needed
SelectType = Enum('none', 'one', 'many')


class GenFormError(Exception):
    pass

# dummy post action
def null_post(btn, san, path, objlist, args):
    """
    The description of null_post comes here.
    @param btn
    @param san
    @param path
    @param objlist
    @param args
    @return
    """
    return (0, btn.text + ' done !')


class UIButton(object):
    def __init__(self, name, text='', act=BtnAction.confirm, icon='',
            select=SelectType.one, confirm='Are you sure ?',
            form=None, post=null_post, autosave=False, hint=''):
        """
            confirm - confirmation message
            form - callback function
        """
        self.name=name
        if not text:
            self.text = name.capitalize()
        else:
            self.text=text
        self.icon=icon
        self.act=act
        self.select=select
        self.confirm=confirm
        self.form=form
        self.post=post
        self.autosave=autosave
        self.hint=hint

    def gen_form(self,san,path,objlist):
        """
        The description of gen_form comes here.
        @param san
        @param path
        @param objlist
        @return
        """
        # called when button was clicked (in BtnAction.form)
        if not self.form:
            raise Exception(1, 'form function is missing for %s' % self.name)
        return self.form(self,san,path,objlist)

    def post_form(self,san,path,objlist,args):
        """
        The description of post_form comes here.
        @param san
        @param path
        @param objlist
        @param args
        @return
        """
        # called when "ok" button was clicked inside the form
        if self.post:
            return self.post(self,san,path,objlist,args)
        else:
            return (0,'')

    def xmlElement(self):
        """
        The description of xmlElement comes here.
        @return
        """
        elem = minidom.Element('button')
        elem.setAttribute('name',str(self.name))
        elem.setAttribute('text', str(self.text))
        elem.setAttribute('act', str(self.act))
        if self.icon:
            elem.setAttribute('icon', str(self.icon))
        if self.act == BtnAction.confirm:
            elem.setAttribute('confirm', str(self.confirm))
        if self.select:
            elem.setAttribute('select', str(self.select))
        if self.hint:
            elem.setAttribute('hint', self.hint)
        return elem


#def clickResult(result, data):
#    doc=minidom.Document()
#    res=doc.createElement('clickResult')
#    doc.appendChild(res)
#    res.setAttribute('type', result)
#    t=doc.createTextNode(data)
#    res.appendChild(t)
#    return doc

# forms (activated by bottons)
def refresh_post(btn,san,path,objlist,args):
    """
    The description of refresh_post comes here.
    @param btn
    @param san
    @param path
    @param objlist
    @param args
    @return
    """
    for obj in objlist :
        san.refresh(obj)
    return (0,'')

def rescan_post(btn,san,path,objlist,args):
    """
    The description of rescan_post comes here.
    @param btn
    @param san
    @param path
    @param objlist
    @param args
    @return
    """
    for obj in objlist :
        san.rescan(obj.name)
    return (0,'')

def reboot_post(btn,san,path,objlist,args):
    """
    The description of reboot_post comes here.
    @param btn
    @param san
    @param path
    @param objlist
    @param args
    @return
    """
    bootlcl=False
    for obj in objlist :
        if obj is san.lclprovider : bootlcl=True
        else : san.reboot(obj.name)
    # reboot the local (master) provider last, after the other providers
    if bootlcl : san.reboot(san.lclprovider.name)
    return (0,'Systems will reboot')

def evacuate_post(btn,san,path,objlist,args):
    """
    The description of evacuate_post comes here.
    @param btn
    @param san
    @param path
    @param objlist
    @param args
    @return
    """
    for obj in objlist :
        obj.evacuate()
    return (0,'DR storage objects were evacuated successfully')

# Map to function to create target based on list of storage objects
def mapto_frm(btn,san,path,objlist):
    """
    The description of mapto_frm comes here.
    @param btn
    @param san
    @param path
    @param objlist
    @return
    """
    form=ht_form(btn.name, path,'Map to server')
    form.addHidden('source','button')
    form.add(ht_combo('server','Server/Initiator',True,san.servers.keys(),'everyone') )
    form.add(ht_radio('transport','Transport',False,Transport._keys,'iscsi'))
    form.add(ht_input('tgtname','Target Name (optional)',False))
    return form.html()

def mapto_post(btn,san,path,objlist,args):
    """
    The description of mapto_post comes here.
    @param btn
    @param san
    @param path
    @param objlist
    @param args
    @return
    """
    for obj in objlist :
        if obj.locked : return (1,'Device %s is locked and cannot be used' % obj.name)
    tgt=san.add_targets(args['tgtname'][0])
    tgt.server=san.servers[args['server'][0]]
    tgt.transport=Transport.__dict__[args['transport'][0]]
    for obj in objlist :
        l=tgt.add_luns(lun=None,volume=obj)
        if not l or isinstance(l,str) : return (1,'Error adding Lun (volume %s), ' % str(obj)+str(l))
        (e,r)=l.update()
        if e : return (e,r)
    return (0,'created new storage target successfully')

def addtotgt_frm(btn,san,path,objlist):
    """
    The description of addtotgt_frm comes here.
    @param btn
    @param san
    @param path
    @param objlist
    @return
    """
    targets = san.targets.keys()
    if not targets:
        raise GenFormError('There are no targets configured')
    form=ht_form(btn.name, path,'Add to Target')
    form.addHidden('source','button')
    form.add( ht_combo('tgtname', 'Target name', True, targets) )
    form.add(ht_input('lun','First Lun Number (optional)',False))
    return form.html()

def addtotgt_post(btn,san,path,objlist,args):
    """
    The description of addtotgt_post comes here.
    @param btn
    @param san
    @param path
    @param objlist
    @param args
    @return
    """
    try:
        tgt = san.targets[args['tgtname'][0]]
    except KeyError:
        return (1, 'Missing target name')
    for obj in objlist :
        if obj.locked : return (1,'Device %s is locked and cannot be used' % obj.name)
        l=tgt.add_luns(lun=None,volume=obj)
        if not l or isinstance(l,str) : return (1,'Error adding Lun (volume %s), ' % str(obj)+str(l))
        (e,r)=l.update()
        if e : return (e,r)
    return (0,'created new storage target successfully')

# Map to function to create target based on list of storage objects
def addlv_frm(btn,san,path,objlist):
    """
    The description of addlv_frm comes here.
    @param btn
    @param san
    @param path
    @param objlist
    @return
    """
    form=ht_form(btn.name, path,'Add Logical Volume')
    form.addHidden('source','button')
    form.add(ht_input('name','Volume Name (optional)',False))
    form.add(ht_input('size','Size in MB',True))
    form.add(ht_checkbox('dr','Redundant (DR)',False))
    return form.html()

def addlv_post(btn,san,path,objlist,args):
    """
    The description of addlv_post comes here.
    @param btn
    @param san
    @param path
    @param objlist
    @param args
    @return
    """
    if len(objlist)<>1 : return (1,'Must select one pool to add volume to')
    (e,size)=txt2size(args['size'][0])
    if e : return (e,'volume size error,'+size)
    vol=objlist[0].add_volumes(args['name'][0],size=size)
    if vol :
        (e,r)=vol.update()
        if e : return (e,r)
    else : return(1,'Error, new volume was not created')
    return (0,'created new storage volume successfully')

def addtoraid_frm(btn,san,path,objlist):
    """
    The description of addtoraid_frm comes here.
    @param btn
    @param san
    @param path
    @param objlist
    @return
    """
    form=ht_form(btn.name, path,'Add Storage to Raid')
    form.addHidden('source','button')

    raids = san.raids.keys()
    groups = ['new']
    if raids:
        groups += ['existing']

    form.add(ht_radio('new', 'Raid', True, groups, 'new', bygroup=True))

    if raids:
        form.add(ht_combo('raidobj', 'Select Raid', True, raids, group='existing') )

    form.add(ht_input('name','New Raid Name',False,group='new'))
    form.add(ht_combo('raid','Raid/DR Type',True,RaidLevel._keys,'1',group='new'))
    return form.html()

def addtoraid_post(btn,san,path,objlist,args):
    """
    The description of addtoraid_post comes here.
    @param btn
    @param san
    @param path
    @param objlist
    @param args
    @return
    """
    for v in objlist :
        if v.locked : return (1,'Device %s is locked and cannot be used to form a Raid' % v.name)
    if args['new'][0]=='new' :
        if san.raids.has_key(args['name'][0]):
            return (1,"raid object %s already exists" % args['name'][0] )
        raid=san.add_raids(args['name'][0])
        raid.raid=RaidLevel.__dict__[args['raid'][0]]

    else:
        try:
            raid_name = args['raidobj'][0]
        except KeyError:
            return (1, 'Missing raid name')

        raid = san.raids[raid_name]

    raid.devices=[v for v in objlist]
    (e,r)=raid.update()
    if e : return (e,r)
    return (0,'created new storage raid successfully')

def addtopool_frm(btn,san,path,objlist):
    """
    The description of addtopool_frm comes here.
    @param btn
    @param san
    @param path
    @param objlist
    @return
    """
    form=ht_form(btn.name, path,'Add Storage to Pool')
    form.addHidden('source','button')

    pools = san.pools.keys()
    groups = ['new']
    if pools:
        groups += ['existing']

    form.add(ht_radio('new','Pool', True, groups, 'new', bygroup=True))

    if pools:
        form.add(ht_combo('poolobj','Select Pool',True,san.pools.keys(),group='existing') )

    form.add(ht_input('name','New Pool Name (optional)',False,group='new'))
    form.add(ht_checkbox('glbl','Global Pool',False,group='new'))
    return form.html()

def addtopool_post(btn,san,path,objlist,args):
    """
    The description of addtopool_post comes here.
    @param btn
    @param san
    @param path
    @param objlist
    @param args
    @return
    """
    for v in objlist :
        if v.locked : return (1,'Device %s is locked and cannot be used to form a Pool' % v.name)
    if args['new'][0]=='new' :
        if san.pools.has_key(args['name'][0]):
            return (1,"pool object %s already exists" % args['name'][0] )
        pool=san.add_pools(args['name'][0])
        try:
            pool.glbl = args['glbl'][0] == 'True'
        except KeyError:
            pool.glbl = False

    else:
        try:
            pool_name = args['poolobj'][0]
        except KeyError:
            return (1, 'Missing pool name')

        pool = san.pools[pool_name]

    devices = [obj2volstr(v) for v in objlist]
    devstr = ','.join(devices)

    e, r = san.setobj(pool, 'devices', devstr)
    if e:
        return (e, r)

    (e,r)=pool.update()
    if e : return (e,r)
    return (0,'created new storage pool successfully')

# example for target migration, form has combo with list of providers
def migrate_frm(btn,san,path,objlist):
    """
    The description of migrate_frm comes here.
    @param btn
    @param san
    @param path
    @param objlist
    @return
    """
    form=ht_form(btn.name, path, 'Migrate Storage Target')
    form.addHidden('source','button')
    form.add( ht_combo('provider','Migrate to provider (none for Auto)',False,['']+san.providers.keys()) )
    return form.html()

def migrate_post(btn,san,path,objlist,args):
    """
    The description of migrate_post comes here.
    @param btn
    @param san
    @param path
    @param objlist
    @param args
    @return
    """
    for target in objlist :
        (e,txt)=target.migrate(args['provider'][0])
        if e : return (e,txt)
    return (0,'migrate operation successful')

def promote_post(btn,san,path,objlist,args):
    """
    The description of promote_post comes here.
    @param btn
    @param san
    @param path
    @param objlist
    @param args
    @return
    """
    for obj in objlist :
        if obj.parent.raid<>RaidLevel.dr: return (1,'can only promote DR type slave items')
        (e,txt)=obj.promote()
        if e : return (e,txt)
    return (0,'Slave item is promoted to primary')

def reinit_post(btn,san,path,objlist,args):
    """
    The description of reinit_post comes here.
    @param btn
    @param san
    @param path
    @param objlist
    @param args
    @return
    """
    for obj in objlist :
        if obj.parent.raid<>RaidLevel.dr: return (1,'can only Reinit DR type slave items')
        (e,txt)=obj.change('reinit')
        if e : return (e,txt)
    return (0,'Slave items are reinitialized')

def clearall_post(btn,san,path,objlist,args):
    """
    The description of clearall_post comes here.
    @param btn
    @param san
    @param path
    @param objlist
    @param args
    @return
    """
    san.alarms.clear_all()
    return (0,'All alarms were cleared')

def clearalarm_post(btn,san,path,objlist,args):
    """
    The description of clearalarm_post comes here.
    @param btn
    @param san
    @param path
    @param objlist
    @param args
    @return
    """
    for o in objlist:
        san.alarms.clear_alarm(o.objpath)
    return (0,'Selected alarm were cleared')

# general buttons
add_btn = UIButton('add',
            act=BtnAction.add,
            icon='ui-icon-add',
            hint='Add'
            )

del_btn = UIButton('delete',
            act=BtnAction.delete,
            select=SelectType.many,
            icon='ui-icon-delete',
            hint='Delete selected items'
            )

enable_btn = UIButton('enable',
            hint='enable'
            )

disable_btn = UIButton('disable',
            hint='disable'
            )

refresh_btn = UIButton('refresh',
            act=BtnAction.none,
            select=SelectType.many,
            post=refresh_post,
            hint='Reload/refresh provider resources',
            icon='ui-icon-refresh'
            )

# provider buttons
rescan_btn = UIButton('rescan',
            act=BtnAction.none,
            post=rescan_post,
            select=SelectType.many,
            hint='Rescan SCSI buses/devices',
            icon='ui-icon-rescan'
            )

reboot_btn = UIButton('reboot',
            act=BtnAction.confirm,
            confirm='System will reboot, Are you sure ?',
            post=reboot_post,
            select=SelectType.many,
            hint='Reboot selected providers',
            icon='ui-icon-reboot'
            )

evacuate_btn = UIButton('evacuate',
            act=BtnAction.confirm,
            confirm='System will evacuate storage to alternative providers, Are you sure ?',
            post=evacuate_post,
            hint='Migrate repliaced storage resources/targets to alternate providers',
            icon='ui-icon-evacuate'
            )

# extent buttons
mapto_btn = UIButton('mapto',
            'Map to client',
            select=SelectType.many,
            act=BtnAction.form,
            form=mapto_frm,
            post=mapto_post,
            hint='Map storage resources to a server/initiator (create a target)',
            icon='ui-icon-maptoclnt'
            )

addtotgt_btn = UIButton('addtotgt',
            'Add to target',
            select=SelectType.many,
            act=BtnAction.form,
            form=addtotgt_frm,
            post=addtotgt_post,
            hint='Add storage resources to an existing target (add LUNs)',
            icon='ui-icon-addtotarget'
            )

addtopool_btn = UIButton('addtopool',
            'Add to pool',
            select=SelectType.many,
            act=BtnAction.form,
            form=addtopool_frm,
            post=addtopool_post,
            hint='Add storage resources to a storage Pool (as PVs)',
            icon='ui-icon-addtopool'
            )

addtoraid_btn = UIButton('addtoraid',
            'Add to raid',
            select=SelectType.many,
            act=BtnAction.form,
            form=addtoraid_frm,
            post=addtoraid_post,
            hint='Add storage resources to a storage Raid/DR',
            icon='ui-icon-addtoraid'
            )

extmon_btn = UIButton('extmon',
            'Monitor',
            act=BtnAction.js,
            select=SelectType.many,
            icon='ui-icon-monitor',
            hint='Show live statistics'
            )

addisk_btn = UIButton('addisk',
            'Add disk',
            icon='ui-icon-add-disk',
            hint='Add a disk'
            )

addlv_btn = UIButton('addlv',
            'Add Volume',
            select=SelectType.one,
            act=BtnAction.form,
            form=addlv_frm,
            post=addlv_post,
            hint='Create a new storage volume from selected pool',
            icon='ui-icon-add-vol'
            )

snap_btn = UIButton('snapshot',
            hint='Take a snapshot'
            )

promote_btn = UIButton('promote',
            select=SelectType.one,
            act=BtnAction.confirm,
            confirm='Promote DR instance to primary role ?',
            post=promote_post,
            hint='Make selected slave the DR group master/primary'
            )

reinit_btn = UIButton('reinit',
            select=SelectType.one,
            act=BtnAction.confirm,
            confirm='Reinitialize DR instance ?',
            post=reinit_post,
            hint='Reset slave properties (cycle down,up)'
            )

# alarms buttons
clearalarms_btn = UIButton('clearall',
            'Clear all',
            act=BtnAction.confirm,
            select=SelectType.none,
            confirm='All alarms will be removed, Are you sure ?',
            post=clearall_post,
            hint='Clear all alarms'
            )

clearalarm_btn = UIButton('clearalarm',
            'Clear',
            act=BtnAction.confirm,
            select=SelectType.many,
            confirm='Clear selected alarms ?',
            post=clearalarm_post,
            hint='Clear selected alarms'
            )

# target buttons
# forms (generated after button was clicked)
migrate_btn = UIButton('migrate',
            act=BtnAction.form,
            form=migrate_frm,
            post=migrate_post,
            hint='Migrate target to a different provider',
            icon='ui-icon-migrate'
            )


# demo button

def demo_frm(btn,san,path,objlist):
    """
    The description of demo_frm comes here.
    @param btn
    @param san
    @param path
    @param objlist
    @return
    """
    f=ht_demo()
    return f.html()

def demo_post(btn,san,path,objlist,args):
    """
    The description of demo_post comes here.
    @param btn
    @param san
    @param path
    @param objlist
    @param args
    @return
    """
    return 0,'done'

demo_btn=UIButton('demo','Demo button',act=BtnAction.form,form=demo_frm,post=demo_post)

