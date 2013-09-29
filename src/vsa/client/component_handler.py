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


from xml.dom import minidom, Node
import enum
from vsa.client.gui.htmbtns import add_btn, del_btn, enable_btn, disable_btn, \
    refresh_btn, rescan_btn, reboot_btn, evacuate_btn,  mapto_btn, addtotgt_btn, \
    addtopool_btn, addtoraid_btn, extmon_btn, addisk_btn, addlv_btn, snap_btn, \
    promote_btn, reinit_btn, clearalarms_btn,clearalarm_btn, migrate_btn


objects = enum.Enum("SanBase", "EventFilter", "AlarmEntry", "AlarmsCls", "CacheInst", "CacheRes", "CacheMngr", "vDisk", "Extent", "PoolItem"\
                                        ,"vFCPort", "FCport", "GeneralProp", "Netif", "VolGrpItem", "VolGrpSubpool", "Provider", "SanPartition"\
                                        ,"SanRaidGrp", "SanResources", "SanTarget", "SanVolgrp", "SanVolume", "SanPath", "SanChunk"\
                                        ,"Sanplun", "ServerGroup", "TargetLun", "TargetPortal", "TmpVol", "VsaProvider")


ui_buttons =        {
                                   objects.AlarmsCls:      [clearalarms_btn, clearalarm_btn],
                                   objects.vDisk:           [add_btn,del_btn],
                                   objects.PoolItem:      [promote_btn,reinit_btn],
                                   objects.vFCPort:        [add_btn,del_btn],
                                   objects.Netif:            [extmon_btn],
                                   objects.VolGrpItem:  [add_btn],
                                   objects.Provider:       [add_btn,refresh_btn,rescan_btn,evacuate_btn,reboot_btn],
                                   objects.SanRaidGrp: [add_btn,del_btn,mapto_btn,addtotgt_btn,addtopool_btn,extmon_btn],
                                   objects.SanTarget:    [add_btn,del_btn,migrate_btn,extmon_btn],
                                   objects.SanVolgrp:    [add_btn,del_btn,addlv_btn],
                                   objects.SanVolume:  [add_btn,del_btn,mapto_btn,addtotgt_btn,snap_btn,extmon_btn],
                                   objects.SanPath:       [enable_btn,disable_btn],
                                   objects.Sanplun:       [mapto_btn,addtotgt_btn,addtoraid_btn,addtopool_btn,extmon_btn],
                                   objects.ServerGroup:     [add_btn,del_btn],
                                   objects.TargetLun:         [add_btn, del_btn]
                            }

show_columns = {
                            objects.SanBase:     ['Name','Description'],
                            objects.AlarmEntry:  ['Time','Sevirity','Obj Path','Event','Description','Occur'],
                            objects.EventFilter:   ['Class','Event','Description','Sevirity','Alarm','auto','Log','snmp','syslog','script','email'],
                            objects.vDisk:           ['Name','Pool','Req Size','Volume','Priority','AvgLoad','Paths','Target'],
                            objects.Extent:          [' ','Name','Type','Size','devfile'],
                            objects.PoolItem:      ['Slot/Role','Provider','DataState','ConnState','Size','dev','Extent'],
                            objects.FCport:         ['Role','wwnn','wwpn','Speed','Provider','HBA','vPorts','Parent'],
                            objects.Netif:            ['Name','IP','Mask','Grp','Speed','dhcp','data','mng','mtu','mac'],
                            objects.VolGrpItem:         ['Size','Free','PE','Alloc','Extent'],
                            objects.VolGrpSubpool:   ['Provider','Size','Used','Free','attr'],
                            objects.Provider:              ['Name','role','url','ifs','FCs','procs','Cache','Zone'],
                            objects.SanPartition:        [' ','Idx','Name','Device','Start','Size','Type','Mount','inLuns'],
                            objects.SanRaidGrp:        [' ','Idx','Name','Raid','Slaves','Size','Cache','Resync','Provider'],
                            objects.SanTarget:           ['Idx','Name','Server','Transport','Provider','Luns','Sessions'],
                            objects.SanVolgrp:          ['Name','Size','Used','Free','PVs','LVs','Raid','Provider','attr','Quality','Chunk'],
                            objects.SanVolume:         [' ','Name','Size','Mount','InLUNs','Snaps'],
                            objects.SanPath:              ['Req State','Device','hbtl','HBA Type','Target','Dst port','Assigned BW'],
                            objects.Sanplun:              [' ','Idx','Name','Size','Cache','Vendor','Model','paths','prt','in LUNs'],
                            objects.ServerGroup:      ['Name','OS','IPs','vWWNN','vHBAs','vDisks','Targets'],
                            objects.TargetLun:           ['Target/Lun', 'Type', 'Size', 'devfile', 'Extent']
                            }


ui_edit_table = {
                            objects.EventFilter: False,
                            objects.AlarmEntry: False
                        }


def isTableEditable(object_type):
    """
    The description of isTableEditable comes here.
    @param object_type
    @return
    """
    editable = ui_edit_table.get(object_type)
    if editable is None:
        editable = True
    return editable


def buttonsXML(btns):
    """
    @param btns - list of btns
    """
    be = minidom.Element('buttons')
    for b in btns:
        be.appendChild(b.xmlElement())
    return be


def getUIbuttons(obj):
    """
    The description of getUIbuttons comes here.
    @param obj
    @return
    """
    enum_obj = _getEnumType(obj)
    try:
        return ui_buttons[enum_obj]
    except KeyError:
        return []


def getUIbutton(obj, name):
    """
    The description of getUIbutton comes here.
    @param obj
    @param name
    @return
    """
    uibtns=getUIbuttons(obj)
    for uibtn in uibtns:
        if uibtn.name==name:
            return uibtn
    return None


def buttons_generic(obj,path):
    """
    The description of buttons_generic comes here.
    @param obj
    @param path
    @return
    """
    uibtns = getUIbuttons(obj)
    #if demo_btn not in uibtns: uibtns+=[demo_btn]
    # create xml buttons document
    x = buttonsXML(uibtns)
    return x


def get_columns(obj):
    """
    The description of get_columns comes here.
    @param obj
    @return
    """
    enum_obj = _getEnumType(obj)
    if enum_obj not in show_columns:
        # get default table columns
        enum_obj = objects.SanBase
    return show_columns[enum_obj]


def _getEnumType(obj):
    """
    The description of _getEnumType comes here.
    @param obj
    @return
    """
    if hasattr(obj, 'cclass'):
        if obj.cclass is None:
            return None
        otype = obj.cclass.__name__
    else:
        otype = obj.get_object_type()
    return getattr(objects, otype)
