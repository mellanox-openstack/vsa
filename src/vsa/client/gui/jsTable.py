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


from vsa import infra
#===============================================================================
# from  import RefDict
#===============================================================================
from vsa.infra.infra import val2str
from vsa.model.vsa_collections import RefDict
from vsa.client import component_handler

class jsTable:
    def __init__(self, id, ob, tablepath=''):
        """
        The description of __init__ comes here.
        @param id
        @param ob
        @param tablepath
        @return
        """
        self.id = id
        self.ob = ob
        self.tablepath = tablepath

    def getHtml(self):
        """
        The description of getHtml comes here.
        @return
        """
        return self._createTable(self.ob)

    def _createTable(self,ob):
        head = """
            <span id="tablepath_%s" class="hide">%s</span>
            <table cellpadding="0" cellspacing="0" border="0" class="display" id="%s">
            """
        # table headers
        head = head % (self.tablepath.split('/')[-1], self.tablepath, self.id)
        thead ="<thead><tr>"

        # checkbox & status
        cols=getattr(ob, 'cols', None)
        if not cols:
            cols = component_handler.get_columns(ob)

        istable=getattr(ob,'table',None)

        if not istable: thead+='<th class="checkbox no_sort"><input type="checkbox" name="checkall" value="" /></th>'

        if getattr(ob,'cclass',None)!=None:
            simpleTable = not component_handler.isTableEditable(ob.cclass.__name__)
        else: simpleTable=True

        if not istable and not simpleTable:
            #thead+='<th class="editbox no_sort"></th>'
            thead+='<th class="status">State</th>'

        # table cols
        #cols=getattr(ob, 'cols', None)
        #if not cols: cols=ob.cclass.show_columns

        # table headers
        for i in cols:
            thead+="<th>"+i+"</th>"
        thead+="</tr></thead>"

        # table body
        tbody="<tbody>"
        colsCount = len(cols)
        evenOrOdd=1

        # table rows
        if isinstance(ob,RefDict):
            lst=ob()
        else:
            lst=[ob[k] for k in sorted(ob.keys())]

        for v in lst:
            evenOrOdd^=1
            if getattr(v, 'exposed', True):
                tr=jsTable._newTR(evenOrOdd, ob, v, colsCount, istable, simpleTable)
                tbody+=tr

        # close body
        tbody+="</tbody>"
        # close table
        foot="""</table>"""
        return head+thead+tbody+foot

    @staticmethod
    def _newTR(odd, ob, v, colsCount, table=False, simple=False):
        """
        The description of _newTR comes here.
        @param odd
        @param ob
        @param v
        @param colsCount
        @param table
        @param simple
        @return
        """
        # open row
        if odd: tr = '<tr class="odd">'
        else:   tr = '<tr class="even">'

        # default cols
        if not table:
            # checkbox
            td = '<td class="center"><input type="checkbox" name="selpath" value="%s"/></td>' % str(v.fullpath)
            tr += td
            if not simple:
                # edit
                td = '<td class="center"><div id="edit" class="ui-icon ui-icon-edit-target pointer">' \
                '<span id="fullpath" class="hide">%s</span></div></td>' % str(v.fullpath)

        # status col
        if not simple and not table:
            td = '<td class="status"><span class="ui-icon left ui-icon-%s" '\
                        'title="%s"></span>%s</td>' % ( str(v.state), v.errstr, str(v.state) )
            tr += td

        # data cols
        c=1
        if table:
            for d in v:
                td = "<td>"+ val2str(d)+"</td>"
                tr += td
                c += 1
        else:
            for d in ob.cclass.ui_getrow(v):
                td = "<td>"+ val2str(d)+"</td>"
                tr += td
                c += 1

        # complete empty cols
        while c <= colsCount:
            tr += "<td></td>"
            c += 1
        # close row
        tr += "</tr>"
        return tr

import random

class testVal:
    def __init__(self, name, luns):
        """
        The description of __init__ comes here.
        @param name
        @param luns
        @return
        """
        self.name = name
        self.luns = luns
        self.status = random.choice(['statusok', 'statusfail'])
    def getData(self):
        """
        The description of getData comes here.
        @return
        """
        return [self.htmlStatus(), self.name, self.luns, 'everyone', 'vsa1', 'iscsi', 0, 1]
    def htmlStatus(self):
        """
        The description of htmlStatus comes here.
        @return
        """
        inner = '<div class="hideme center">' + self.status + '</div>'
        return '<div class="' + self.status + '" title="' + self.status + '">' + inner + '</div>'

class testOb:
    def __init__(self):
        """
        The description of __init__ comes here.
        @return
        """
        self.values=[]
        self.x=''

    @staticmethod
    def getColumns():
        """
        The description of getColumns comes here.
        @return
        """
        return ['Name', 'Luns', 'Server', 'Provider', 'Transport', 'Pid', 'Sessions']

    def add(self, v):
        """
        The description of add comes here.
        @param v
        @return
        """
        self.values.append(v)

    def getValues(self):
        """
        The description of getValues comes here.
        @return
        """
        return self.values

def getTestTable():
    """
    The description of getTestTable comes here.
    @return
    """
    o=testOb()
    for i in range(1,10):
        v=testVal('tgt'+str(i),i)
        o.add(v)
    return jsTable('table1',o).getHtml()
