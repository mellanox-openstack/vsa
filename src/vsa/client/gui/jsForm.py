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

class ht_label:
    def __init__(self, label, for_id='', must=False):
        """
        The description of __init__ comes here.
        @param label
        @param for_id
        @param must
        @return
        """
        self.label=label
        self.for_id=for_id
        self.must=must

    def html(self):
        """
        The description of html comes here.
        @return
        """
        if self.must:
            l=self.label+'<span style="color:red;">*</span>'
        else:
            l=self.label
        return '<label for="%s">%s</label>' % (self.for_id, l)

class ht_input:
    def __init__(self, name, label, must=False, text='', disabled=False, type='text', checked=False, group='', hint=''):
        """type can actually be any valid html input type.
e.g. 'text', 'checkbox'
        """
        self.name=name
        self.label=label
        self.must=must
        self.text=text
        self.type=type
        self.id=type+'-'+name
        self.disabled=disabled
        self.checked=checked
        self.group=group
        self.hint=hint

    def html(self):
        """
        The description of html comes here.
        @return
        """
        disabled=ht_input_disabled(self.disabled)
        checked=ht_input_checked(self.checked)
        if self.hint: hint=' title="%s"' % self.hint
        else: hint=''
        h="<tr%s><td>" % hint
        h+=ht_label(self.label,self.id,self.must).html()
        h+="</td><td>"
        h+='<input type="%s" id="%s" name="%s" value="%s" %s %s />' % (self.type, self.id, self.name, self.text, disabled, checked)
        h+="</td></tr>"
        return h

class ht_checkbox(ht_input):
    def __init__(self, name, label, must=False, checked=False, disabled=False, text='True', group='', hint=''):
        """
        The description of __init__ comes here.
        @param name
        @param label
        @param must
        @param checked
        @param disabled
        @param text
        @param group
        @param hint
        @return
        """
        ht_input.__init__(self, name, label, must, text, disabled, 'checkbox', checked, group, hint)

def ht_input_disabled(disabled=True):
    """
    The description of ht_input_disabled comes here.
    @param disabled
    @return
    """
    if disabled: return 'disabled="disabled"'
    return ''

def ht_option_selected(option,select):
    """
    The description of ht_option_selected comes here.
    @param option
    @param select
    @return
    """
    if option==select: return 'selected'
    return ''

def ht_radio_checked(option,select):
    """
    The description of ht_radio_checked comes here.
    @param option
    @param select
    @return
    """
    if option==select: return 'checked="checked"'
    return ''

def ht_input_checked(checked=True):
    """
    The description of ht_input_checked comes here.
    @param checked
    @return
    """
    if checked: return 'checked="checked"'
    return ''

class ht_combo:
    def __init__(self, name, label, must=False, options=[], select=None, disabled=False, group='', hint=''):
        """
        The description of __init__ comes here.
        @param name
        @param label
        @param must
        @param options
        @param select
        @param disabled
        @param group
        @param hint
        @return
        """
        self.name=name
        self.label=label
        self.must=must
        self.options=options
        self.id='select-'+name
        self.select=select
        self.disabled=disabled
        self.group=group
        self.hint=hint

    def html(self):
        """
        The description of html comes here.
        @return
        """
        disabled=ht_input_disabled(self.disabled)
        if self.hint: hint=' title="%s"' % self.hint
        else: hint=''
        h="<tr%s><td>" % hint
        h+=ht_label(self.label,self.id,self.must).html()
        h+="</td><td>"
        h+='<select id="%s" name="%s" %s>' % (self.id, self.name, disabled)
        for o in self.options:
            selected=ht_option_selected(o,self.select)
            h+='<option %s>%s</option>' % (selected, o)
        h+='</select>'
        h+="</td></tr>"
        return h

class ht_radio:
    def __init__(self, name, label, must=False, options=[], select=None, disabled=False, bygroup=False, hint=''):
        """
        The description of __init__ comes here.
        @param name
        @param label
        @param must
        @param options
        @param select
        @param disabled
        @param bygroup
        @param hint
        @return
        """
        self.name=name
        self.label=label
        self.must=must
        self.options=options
        self.id='radio-'+name
        self.select=select
        self.disabled=disabled
        self.bygroup=bygroup
        if self.bygroup:
            self.id='group-'+self.id
        self.hint=hint

    def html(self):
        """
        The description of html comes here.
        @return
        """
        disabled=ht_input_disabled(self.disabled)
        if self.hint: hint=' title="%s"' % self.hint
        else: hint=''
        h="<tr%s><td>" % hint
        h+=ht_label(self.label,self.id,self.must).html()
        h+="</td><td>"
        h+='<fieldset id="%s">' % self.id
        for o in self.options:
            selected=ht_radio_checked(o,self.select)
            h+='<span class="nowrap"><input type="radio" name="%s" value="%s" %s %s />%s</span> &nbsp;' % (self.name, o, selected, disabled, o)
        h+='</fieldset>'
        h+="</td></tr>"
        return h

class ht_form:
    def __init__(self,ftype,fpath,title=''):
        """
        The description of __init__ comes here.
        @param ftype
        @param fpath
        @param title
        @return
        """
        self.head='<form id="ht_form" class="conf_form" onsubmit="return false;" name="%s">' % title
        self.openTable='<table><tbody>'
        self.closeTable='</tbody></table>'
        self.items={'': []}
        self.hidden=[('form-type',ftype),('form-path',fpath)]
        if ftype=='add':
            self.add(ht_input('name','Name',text=''))

    @staticmethod
    def _newTR(col1, col2):
        """
        The description of _newTR comes here.
        @param col1
        @param col2
        @return
        """
        return "<tr><td>"+col1+"</td><td>"+col2+"</td></tr>"

    def add(self, col1, col2=None):
        """
        The description of add comes here.
        @param col1
        @param col2
        @return
        """
        if not col2: group=getattr(col1, 'group','')
        else: group=''
        if not self.items.has_key(group): self.items[group]=[]
        self.items[group].append( (col1,col2) )

    def addHidden(self, key, value):
        """
        The description of addHidden comes here.
        @param key
        @param value
        @return
        """
        if type(value)==list:
            for v in value:
                self.hidden.append( (key,v) )
        else:
            self.hidden.append( (key,value) )

    def html(self):
        """
        The description of html comes here.
        @return
        """
        h=self.head
        for k,v in self.hidden:
            h+='<input type="hidden" name="%s" value="%s" />' % (k,v)
        h+=self.openTable
        # table values
        for group in sorted(self.items):
            if group: h+='<tbody id="%s">' % ('content-'+str(group))
            for c1, c2 in self.items[group]:
                if c2:
                    h+=ht_form._newTR(c1, c2)
                else:
                    h+=c1.html()
            if group: h+='</tbody>'
        h+=self.closeTable
        h+='</form>'
        return h

#def formResult(result, data, refresh=True):
#    doc=minidom.Document()
#    fr=doc.createElement('formResult')
#    doc.appendChild(fr)
#    fr.setAttribute('type', result)
#    fr.setAttribute('refresh', str(refresh))
#    t=doc.createTextNode(data)
#    fr.appendChild(t)
#    return doc

###
def ht_demo(ftype='aaaaa', fpath='bbbbb'):
    """
    The description of ht_demo comes here.
    @param ftype
    @param fpath
    @return
    """
    f=ht_form(ftype, fpath)
    opts=['a','b','c']
    f.add( ht_radio('name','flabel',False,opts,select='a',bygroup=True) )
    f.add( ht_input("name1","label1",group='a') )
    f.add( ht_input("name11","label11",group='a') )
    f.add( ht_input("name2","label2",group='b') )
    f.add( ht_input("name3","label3",group='c') )
    f.add( ht_combo("name4","label4",options=['o1','o2','o3','o4'], select='o1') )
    return f
