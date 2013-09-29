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


from vsa.events.VSAEvents import SevEnum
from vsa.model.san_base import SanBase
from vsa.client.gui.htmbtns import clearalarm_btn, clearalarms_btn
from vsa.model.vsa_collections import VSACollection
from vsa.events.snmptrap import SnmpTrap
import os
import csv
from datetime import datetime
from vsa.infra import logger
from vsa.infra.processcall import process_call
from vsa.infra.config import alarms_config, alarms_scripts_dir


class EventFilter(SanBase):
    #show_columns=['Class','Event','Description','Sevirity','Alarm','auto','Log','snmp','syslog','script','email']
    #ui_table_state=False

    def __init__(self,cname,ename='general'):
        """
        The description of __init__ comes here.
        @param cname
        @param ename
        @return
        """
        SanBase.__init__(self,cname,'Event Filter')
        self.cname=cname
        self.eventname=ename
        self.id='0'
        self.description=''
        self.textfmt=''
        self.alarm=False
        self.autoclear=False
        self.sevirity=SevEnum.info
        self.log=False
        self.snmp=False
        self.syslog=False
        self.script=False
        self.scriptname=''
        self.webcall=False
        self.weburl=''
        self.email=False
        self.emailacc=None

    def ui_getrow(self):
        """
        The description of ui_getrow comes here.
        @return
        """
        return [self.cname,self.eventname,self.description,str(self.sevirity),self.alarm,self.autoclear,self.log,self.snmp,self.syslog,self.script,self.scriptname,self.email]

class AlarmEntry(SanBase):
    #show_columns=['Time','Sevirity','Obj Path','Event','Description','Occur']
    #ui_table_state=False

    def __init__(self,fltr,instance,event,time,sevirity,text=''):
        """
        The description of __init__ comes here.
        @param fltr
        @param instance
        @param event
        @param time
        @param sevirity
        @param text
        @return
        """
        SanBase.__init__(self,'alarm','Alarm Entry')
        self.fltr=fltr
        self.obj=instance
        self.objpath=''
        if instance : self.objpath=instance.fullpath
        self.fullpath=self.objpath
        self.event=event
        self.firsttime=time
        self.lasttime=None
        self.sevirity=sevirity
        self.text=text
        self.occur=1

    def ui_getrow(self):
        """
        The description of ui_getrow comes here.
        @return
        """
        return [str(self.firsttime),str(self.sevirity),self.objpath,str(self.event),self.text,self.occur]


class AlarmsCls(SanBase):
    child_obj=['filters','current']
    set_params=['clear_all']
    #ui_buttons=[clearalarms_btn, clearalarm_btn]

    def __init__(self):
        """
        The description of __init__ comes here.
        @return
        """
        SanBase.__init__(self,'Alarms','Alarms')
        self.fullpath='/alarms'
        self.filters=VSACollection(EventFilter,self,'filters')
        self.current=VSACollection(AlarmEntry,self,'current')
        self._read_filters()
        self.snmptrap = SnmpTrap()
        self.scriptdir = alarms_scripts_dir

    def _read_filters(self):
        """
        The description of _read_filters comes here.
        @return
        """
        f = None # initial definition if failure
        try:
            f = open(alarms_config, 'r')
            rd=csv.DictReader(f)
            for l in rd:
                e=EventFilter(l['cname'],l['eventname'])
                e.id=l['id']
                e.description=l['description']
                e.textfmt=l['textfmt']
                e.scriptname=l['scriptname']
                e.sevirity=SevEnum.__dict__[l['sevirity']]
                for fld in ['alarm','autoclear','log','snmp','syslog','script','scriptname','webcall','email']:
                    if l[fld]=='1':
                        e.__dict__[fld]=True
                self.filters[l['cname']+'.'+l['eventname']]=e
            f.close()
        except:
                if f:
                    f.close()
        return

    def process_event(self,obj,event,params={},time=None):
        """
        The description of process_event comes here.
        @param obj
        @param event
        @param params
        @param time
        @return
        """
        eventname = str(event)
        if obj.handlerclass:
            cname = obj.handlerclass
        else:
            cname = obj.__class__.__name__
        eventtype = cname+'.'+eventname
        if not self.filters.has_key(eventtype):
            if self.filters.has_key('SanBase.'+eventname):
                eventtype = 'SanBase.'+eventname
            else:
                return (1,'no such alarm type: '+eventtype)
        f = self.filters[eventtype]
        path = obj.fullpath
        if not time:
            time = datetime.now()
        params['objpath'] = path
        txt = path+': '+f.textfmt % params
        if f.log:
            if str(f.sevirity) in ['minor','major','critical']:
                logger.eventlog.error(txt)
            else:
                logger.eventlog.info(txt)
        if f.alarm:
            key=path+'.'+eventname
            if self.current.has_key(key):
                a=self.current[key]
                a.lasttime=time
                a.occur+=1
                a.text=txt
            else:
                self.current[path+'.'+eventname] = AlarmEntry(f,obj,eventname,time,f.sevirity,txt)
            if f.sevirity.index > obj.alarmstate.index:
                obj.alarmstate=f.sevirity
        if f.snmp:
            self.snmptrap.send(source=path, event_id=event.index, severity=f.sevirity.index, text=txt, managers=self.san_interface.general.snmpmanagers)
        if f.script:
            script = self.scriptdir + f.scriptname
            if os.path.exists(script) and os.access(script, os.X_OK):
                (e, o) = process_call([script, path, eventname, str(f.sevirity)], log=False)
                if e: logger.eventlog.error('Failed to execute script %s: error: %s' % (script, o))
            else:
                logger.eventlog.error('Script %s does not exist or is not executable' % script)
        return (0,'')

    def clear_all(self,starts='',b=''):
        """
        The description of clear_all comes here.
        @param starts
        @param b
        @return
        """
        for k,a in self.current.items():
            if not starts or k.startswith(starts):
                a.obj.alarmstate=SevEnum.none
                del a
                del self.current[k]

    def clear_alarm(self,name):
        """
        The description of clear_alarm comes here.
        @param name
        @return
        """
        a=self.current[name]
        a.obj.alarmstate=SevEnum.none
        del a
        del self.current[name]
