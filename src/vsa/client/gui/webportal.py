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


import os.path
import re
import traceback
from xml.dom import minidom

from twisted.internet import reactor, protocol
from twisted.python import log, failure
from twisted.web import server, resource
from twisted.web.client import getPage
from twisted.protocols.basic import LineReceiver

from vsa.infra.params import logopt, WEBPORTAL_CREDENTIALS
from vsa.infra import logger
from vsa.infra.infra import tstint, parse_cfg
from vsa.client.gui import jsTable, htmforms, htmbtns
from vsa.client.gui.htmbtns import GenFormError
from vsa.client.component_handler import buttons_generic, getUIbutton

listenport=88
staticDataLocation='/vsa_static'

lclpath= os.path.dirname(os.path.abspath(__file__))+'/'
portaldir=lclpath+'portal/'
pagesdir=portaldir+'pages/'


portal_vars = {
    'static':    staticDataLocation,
    'title':    'Virtual Storage Array (VSA)'
}

def page(fl, user=None):
    """Return parsed page from pages/"""
    fileo=None
    data=''
    re_js=re.compile("\s*@vsa-javascript:(.+\.js)")
    re_css=re.compile("\s*@css:(.+\.css)")
    str_js='<script src="%s/js/%%s" type="text/javascript"></script>' % staticDataLocation
    str_css=r'<link href="%s/css/\1" rel="stylesheet" type="text/css" />' % staticDataLocation
    str_title='Virtual Storage Array (VSA)'
    # if main.js exists include src js files else use default
    vsa_js=''
    if os.path.isfile(portaldir+'js/main.js'):
        for dirname, dirnames, filenames in os.walk(portaldir+'js/'):
            for filename in filenames:
                if filename.endswith('.js'):
                    vsa_js += str_js % filename + '\n'
    try:
        fileo = open(pagesdir+fl)
        data = fileo.read()
        data = re.sub("\[static\]", staticDataLocation+'/', data)
        data = re.sub("\[user\]", str(user), data)
        data = re.sub("\[title\]", str_title, data)
        data = re_css.sub(str_css,data)
        lines = []
        for l in data.splitlines():
            m=re_js.match(l)
            if m:
                js = m.groups()[0]
                if js == 'vsa.js' and vsa_js:
                    l = vsa_js
                else:
                    l = str_js % js
            lines += [l]
        data = '\n'.join(lines)
    except Exception, e:
        data = str(e)
    if fileo:
        fileo.close();
    return data


class NoTimeoutSession(server.Session):
    def startCheckingExpiration(self, lifetime=None):
        """
        The description of startCheckingExpiration comes here.
        @param lifetime
        @return
        """
        pass


class VSAPortal(resource.Resource):
    def __init__(self):
        """
        The description of __init__ comes here.
        @return
        """
        self.san=None
        self.srv=None
        self.isLeaf=True
        self.mon={'a':1}

    def render_GET(self, request):
        """
        The description of render_GET comes here.
        @param request
        @return
        """
        return self.render_GET_AND_POST(request)

    def render_POST(self, request):
        """
        The description of render_POST comes here.
        @param request
        @return
        """
        return self.render_GET_AND_POST(request)

    def render_GET_AND_POST(self, request):
        """
        The description of render_GET_AND_POST comes here.
        @param request
        @return
        """
        logger.weblog.info('Webportal action: %s %s' % (request.method, request.uri))
        request.path = '/' + request.path.strip('/')

        session = request.getSession()
        request.setHeader('Cache-Control', 'no-cache')

        if request.path == '/logout':
            session.user = ''
            session.expire()
            request.setResponseCode(301)
            request.setHeader('Location', 'index')
            return 'moved'
            #return LoginForm % ''
            #return "<html><head><script type=\"text/JavaScript\">top.location='/';</script></head></html>"

        if request.path=='/login':
            user = request.args.pop('user',[''])[0]
            password = request.args.pop('password',[''])[0]
            valid = False
            if user and password:
                cred = WEBPORTAL_CREDENTIALS.get(user,'')
                if cred and cred == password:
                    valid = True
            if valid:
                logger.weblog.info('User %s logged in' % user)
                session.user = user
                request.setResponseCode(301)
                request.setHeader('Location', 'index')
                return 'moved'
            logger.weblog.info('User %s failed login' % user)

###########################################
# Skipping login page for now. its anoying.
#        session.user='admin'
###########################################

        user = getattr(session, 'user', '')
        if not user:
            return page('login.html')
            #return LoginForm % ''

        # log args after login
        logger.weblog.info('Args: %s ' % str(request.args))

        path = request.path.strip('/')
        if not path:
            path = 'index'

        # check if requested xml
        if path.startswith('xml/'):
            request.setHeader('content-type', 'text/xml')

        str_path = path.replace('/','_')

        # find method to handle the request
        handle = getattr(self, 'render_path_%s' % str_path, None)
        if type(handle).__name__ == 'instancemethod':
            return handle(request)

        # no method found
        logger.weblog.info('Unknown requested path: %s' % request.path)
        request.setResponseCode(404)
        return '<h3>Not Found</h3>'

    def render_path_index(self, request):
        """
        The description of render_path_index comes here.
        @param request
        @return
        """
#        if request.path=='/index' or request.path=='/':
#            f=open(logdir+'event.log','r')
#            fsz=os.path.getsize(logdir+'event.log')
#            if fsz>1000 : fsz=1000
#            f.seek(-fsz,2)
#            msg='<br>'.join(f.read().strip().split('\n')[-6:-1])
#            print msg
#            f.close()
#            return HtmlPage(request,user,None,'<b>Recent Log:</b><br>'+msg).html()
        session = request.getSession()
        return page('main.html', session.user)

    def render_path_monitor(self, request):
        """
        The description of render_path_monitor comes here.
        @param request
        @return
        """
        session = request.getSession()
        path = request.args['path'][0]
        name = request.args['name'][0]
        selpath = request.args['selpath']
        data = page('monitor.html', session.user)

        params = re.sub('\'', '\"', str(request.args))
        mon_params = 'mon_params = %s;' % params

        data = re.sub("\[mon_params\]", mon_params, data)

        return data

    def render_path_tree(self, request):
        """
        The description of render_path_tree comes here.
        @param request
        @return
        """
        t=self.san.BuildTree().GetTree()['children']
        #t = jsTree.BuildDefaultTree().GetTree()['children']
        if len(t)==0: return ""
        # convert ' to " for valid json format
        d=re.sub('\'', '\"', str(t))
        return d

    def render_path_table(self, request):
        """
        The description of render_path_table comes here.
        @param request
        @return
        """
        path = request.args['path'][0]
        lst = path.strip()[1:].split('/')
        logger.weblog.debug('lst: %s' % str(lst))
        (e,obj,sub) = self.srv.get_object(lst)
        if not sub:
            lst = lst[:-1]
            path = '/' + '/'.join(lst)
            (e,obj,sub) = self.srv.get_object(lst)
        if e:
            return self.divAlert('Error in requested table path')
        if sub:
            ob = obj.__dict__[sub]
            html = jsTable.jsTable('table_%s' % lst[-1], ob, path).getHtml()
            return html
        return self.divAlert('Error table path not found')

    def render_path_form(self, request):
        """
        The description of render_path_form comes here.
        @param request
        @return
        """
        # get a form
        ftype=request.args['form-type'][0]
        fpath=request.args['form-path'][0]
        logger.weblog.debug("ftype: %s" % ftype)
        logger.weblog.debug("fpath: %s" % fpath)
        if not fpath:
            return self.divAlert("Form failure")
        # get object
        lst = fpath.strip('/ ').split('/')
        (e,obj,sub) = self.srv.get_object(lst)
        if sub:
            obj = getattr(obj,sub)
        #logger.weblog.debug('obj: %s' % str(obj))
        # create form
        f = htmforms.hfrm_generic(self.san,obj,ftype,fpath)
        if f:
            return f
        return self.divAlert("Form failure")

    def render_path_xml_form_submit(self, request):
        """
        The description of render_path_xml_form_submit comes here.
        @param request
        @return
        """
        # submit form and get result
        args = request.args
        if not args:
            return self.create_xml_response(1,'empty args').toxml()
        ftype = args.pop('form-type')[0]
        fpath = args.pop('form-path')[0]
        source = args.pop('source',[''])[0]
        logger.weblog.debug('ftype: %s fpath: %s' % (ftype, fpath))
        # get name for add
        if ftype == 'add':
            name = args.pop('name')[0]
            if not name:
                name='#'
        # pop table selected items
        objlst = self.popSelPathObjs(args)
        # concat string for set
        s=''
        for i in args:
            if args[i][0]:
                s += ',' + i + '=' + args[i][0]
        s = s.strip(',')
        logger.weblog.debug('s: %s' % s)
        # result
        if (source == 'button'):
            obj = self.getObject(fpath)
            btn = getUIbutton(obj,ftype)
            (e,data) = self.evalButtonPost(btn,fpath,objlst,args)
        else:
            fpath = fpath.strip('/ ')
            session = request.getSession()
            try:
                if ftype == 'add':
                    (e, data, newpath) = self.srv.add_obj(fpath, name, s, {'n':0}, session.user)
                    #print "newpath: "+str(newpath)
                elif ftype == 'edit':
                    (e,data) = self.srv.set_obj(fpath, s, {'n':0}, session.user)
                else:
                    (e,data) = (1,'form_submit: unknown type: %s' % ftype)
                if not e:
                    self.srv.save_configuration()
            except Exception, exc:
                (e,data) = (1, 'form_submit edit failure')
                logger.weblog.error('Webportal form_submit edit failure: %s traceback: %s' % \
                        (str(exc),  traceback.format_exc()))
        return self.create_xml_response(e, data, not e).toxml()

    def render_path_xml_buttons(self, request):
        """
        The description of render_path_xml_buttons comes here.
        @param request
        @return
        """
        # submit form and get result
        if not request.args.has_key('path'):
            return self.create_xml_response(1,'missing path').toxml()
        path = request.args.pop('path')[0]
        logger.weblog.debug('path: %s' % path)
        path = path.strip('/ ')
        # get object
        lst = path.split('/')
        #logger.weblog.debug('lst: %s' % str(lst))
        (e,obj,sub) = self.srv.get_object(lst)
        #if not sub:
        #    print "not sub: "+str(obj)
        #    lst=lst[:-1]
        #    path='/'.join(lst)
        if sub:
            obj = getattr(obj,sub)
        #logger.weblog.debug('obj: %s' % str(obj))
        if obj != None: # empty obj is fine we need its static property ui_buttons
            btnsXML = buttons_generic(obj,path)
            (e,r) = (0, btnsXML)
        else:
            (e,r) = (1, 'object not found')
        return self.create_xml_response(e,r).toxml()

    def render_path_xml_buttonClick(self, request):
        """
        The description of render_path_xml_buttonClick comes here.
        @param request
        @return
        """
        # button clicked
        if not request.args.has_key('path'):
            return self.create_xml_response(1,'missing path').toxml()
        args = request.args
        path = args.pop('path')[0]
        logger.weblog.debug("path: %s" % path)
        name = args.pop('name')[0]
        obj = self.getObject(path)
        btn = getUIbutton(obj,name)
        # pop table selected items
        objlst = self.popSelPathObjs(args)
        session = request.getSession()
        (e, data) = self.handleButtonClick(btn, path, objlst, args, session.user)
        return self.create_xml_response(e, data).toxml()

    def render_path_logs(self, request):
        """
        The description of render_path_logs comes here.
        @param request
        @return
        """
        return self.logsForm(request.args)

    def render_path_xml_getlog(self, request):
        """
        The description of render_path_xml_getlog comes here.
        @param request
        @return
        """
        return self.getlog(request.args).toxml()

    def render_path_alarms(self, request):
        """
        The description of render_path_alarms comes here.
        @param request
        @return
        """
        ob=self.getObject('alarms').current
        html=jsTable.jsTable('alarms-table', ob, '/alarms').getHtml()
        return html

    def render_path_reports(self, request):
        """
        The description of render_path_reports comes here.
        @param request
        @return
        """
        return self.reportsForm(request.args)

    def render_path_xml_getreport(self, request):
        """
        The description of render_path_xml_getreport comes here.
        @param request
        @return
        """
        return self.getreport(request.args).toxml()


    monitorlist = ['block', 'target', 'server', 'ib', 'ifc', 'system', 'storage']

    def render_path_xml_monitor(self, request):
        """
        The description of render_path_xml_monitor comes here.
        @param request
        @return
        """
        name = request.args.pop('name', [''])[0]
        cat = request.args.pop('cat', [''])[0]
        param = request.args.pop('param', [''])[0]

        if not name or not cat or cat not in self.monitorlist:
            return self.create_xml_response(1, 'missing or invalid monitor name and cat').toxml()

        # free monitor resource
        if request.args.has_key('stop'):
            if self.mon.has_key(name):
                self.srv.mon.stop(self.mon[name])
                self.mon.pop(name)
            return self.create_xml_response(0, '').toxml()

        # new monitor
        if not self.mon.has_key(name):
            interval = 10     # doesn't matter, not used in mon object
            if param:
                param = param.split(',')
            logger.weblog.debug(param)
            (e,m,p) = self.srv.mon.startnew(cat, name, param, interval, 'rs')
            if e:
                self.srv.mon.stop(m)
                return self.create_xml_response(e, 'Monitor error: '+m).toxml()
            self.mon[name] = m
        else:
            m = self.mon[name]

        self.srv.mon.process_tick(m)
        headers = self.srv.mon.get_headers(m).split()
        mtxt = self.srv.mon.get_data(m)
        data = []
        for m in mtxt:
            line = {}
            for i in range(len(headers)):
                line[ headers[i].replace('/','_') ] = m[i]
            data.append( self.dict2element('line', line) )

        return self.create_xml_response(0, data).toxml()


        #return divAlert("Not implemented")

        #if request.path=='/tree.json':
        #    return repr(staticTree)

#        if request.path=='/work':
#            return "work page"
            #return WorkPage

#        if request.path=='/logs':
#            return HtmlPage(request,user,None,'',logtemp).html()
#
#        if request.path=='/scripts':
#            return HtmlPage(request,user,None,'',runtemp).html()
#
#        if request.path=='/viewlog':
#            fl=request.args['file'][0]
#            if fldir.has_key(fl):
#                return HtmlPage(request,user,None,'',"<pre>"+open(fldir[fl],'r').read()+"</pre>").html()
#            else:
#                return '<h3>Illegal log</h3>'

        # redirect images to static data location
#        if request.path[:8]=="/images/":
#            request.setResponseCode(301)
#                    request.setHeader("Location", staticDataLocation+request.path)
#            return "moved"

        ###

    def logsForm(self, args):
        """
        description
        @param args
        @return
        """
        a="""<form id="logs-form" onsubmit="showlog('log-div'); return false;">"""
        # logtype
        id="select-logtype"
        lbl="Log type:"
        name="logtype"
        a+="""<label for="%s">%s</label>&nbsp;<select class="logs-select" style="width: 120px" id="%s" name="%s">""" % ( id,lbl,id,name )
        for i in logopt:
            a+="<option>%s</option>" % str(i)
        a+="</select>"+"&nbsp;"*5
        # pvd
        id="select-pvd"
        lbl="Provider:"
        name="pvd"
        a+="""<label for="%s">%s</label>&nbsp;<select class="logs-select" style="width: 120px" id="%s" name="%s">""" % ( id,lbl,id,name )
        for pvd in ['']+self.san.providers.keys():
            a+="<option>%s</option>" % str(pvd)
        a+="</select>"+"&nbsp;"*5
        # lines
        id="input-lines"
        lbl="Lines:"
        name="lines"
        a+="""<label for="%s">%s</label>&nbsp;<input type="text" class="logs-input numeric-only" style="width: 50px" id="%s" name="%s" value="50" />""" % ( id,lbl,id,name )
        a+="&nbsp;"*5
        # filter
        id="input-filter"
        lbl="Filter:"
        name="filter"
        a+="""<label for="%s">%s</label>&nbsp;<input type="text" class="logs-input" style="width: 100px" id="%s" name="%s" value="" />""" % ( id,lbl,id,name )
        a+="&nbsp;"*5

        # end form
        a+="""<input type="submit" id="showlog-button" value="Submit" /></form>"""
        a+="""<br/><div id="log-div" class="dump"></div>"""
        return a

    def getlog(self, args):
        """
        The description of getlog comes here.
        @param args
        @return
        """
        tail = tstint(args.pop('lines',[0])[0],50)
        logtype = args.pop('logtype',['event'])[0]
        filter = args.pop('filter',[''])[0].strip()
        pvd = args.pop('pvd',[''])[0]
        (e, data) = self.srv.get_log(logtype,tail,pvd)
        if not e:
            if filter:
                l = ['Filter: '+filter]
                for line in data.splitlines():
                    if filter in line:
                        l += [line]
                data = '<br>'.join(l)
            else:
                data = '<br>'.join( data.splitlines() )
        return self.create_xml_response(e, data)

    reports_lst = [
            'system', 'version', 'cache', 'config', 'fctree', 'providers',
            'fcports', 'disks', 'pools', 'servers', 'targets'
        ]
    reports_opts = {
            'a': '',
            'd': '',
            's': ' ',
            'l': 0,
            't': 50,
            'w': 120
        }

    def reportsForm(self, args):
        """
        description
        @param
        """
        a = """<form id="reports-form" onsubmit="showreport('report-div'); return false;">"""
        # report
        id = "input-report"
        lbl = "Report:"
        name = "report"
        a += """<label for="%s">%s</label>&nbsp;
<input type="text" class="logs-input numeric-only"
style="width: 150px" id="%s" name="%s" value="" />""" % \
            ( id,lbl,id,name )
        a += "&nbsp;"*5
        # hidden autocomplete values
        id = "combobox-reports"
        a += """<select id="%s" style="display: none;">""" % id
        for i in sorted(self.reports_lst):
            a += '<option value="%s">%s</option>' % (i,i)
        a += '</select>'
        a += "&nbsp;"*5
        # fieldset radios
        id = "fieldset-level"
        name = "level"
        lbl = "Detail level:"
        a += '<label for="%s">%s</label>&nbsp; \
            <fieldset id="%s" style="margin-right: 10px; display: inline;">' % \
            (id,lbl,id)
        for i in range(3):
            if i==0:
                selected = 'checked'
            else:
                selected=''
            a += '<span class="nowrap"><input type="radio" name="%s" value="%s" %s />%s</span> &nbsp;' % \
                (name,i,selected,i)
        a += '</fieldset>'
        a += "&nbsp;"*5
        # end form
        a += """<input type="submit" id="showreport-button" value="Submit" /></form>"""
        a += """<br/><div id="report-div" class="dump"></div>"""
        return a

    def getreport(self, args):
        """
        The description of getreport comes here.
        @param args
        @return
        """
        opts = dict(self.reports_opts)
        report = args.pop('report',[''])[0].strip()
        (e,a0,a1,a2,opts) = parse_cfg(report, [], 'arwildst',
                {'l':'0','r':'0','w':'150','s':' ','t':'50'})
        if e:
            (e,data) = (1,'Error, cannot parse report command')
        else:
            level = tstint(args.pop('level',[0])[0],0)
            if level > 0:
                opts['l'] = level
            (e,data) = self.srv.print_obj(a0,a1,opts)
            data = '<br>'.join(data.splitlines())
        return self.create_xml_response(e, data)

    def create_xml_response(self, rc, out, refresh=True):
        """
        The description of create_xml_response comes here.
        @param rc
        @param out
        @param refresh
        @return
        """
        doc = minidom.Document()
        res = doc.createElement('response')
        doc.appendChild(res)

        # add attributes
        res.setAttribute('rc', str(rc))
        res.setAttribute( 'refresh', str(int(bool(refresh))) )

        # convert out to minidom.Element if not already so
        if isinstance(out, str):
            out = doc.createTextNode(out)
        elif isinstance(out, list):
            for o in out:
                res.appendChild( o )
            out = None

        if out:
            res.appendChild(out)

        return doc

    def dict2element(self, name, dic):
        """
        The description of dict2element comes here.
        @param name
        @param dic
        @return
        """
        elm = minidom.Element(name)
        for k in dic.keys():
            v = dic[k]
            elm.setAttribute(k, str(v))
        return elm

    def getObject(self, path):
        """
        The description of getObject comes here.
        @param path
        @return
        """
        lst=path.strip('/ ').split('/')
        (e,obj,sub) = self.srv.get_object(lst)
        if sub: obj = getattr(obj,sub)
        return obj

    def popSelPathObjs(self, args):
        """
        The description of popSelPathObjs comes here.
        @param args
        @return
        """
        return self.pathToObj(args.pop('selpath',''))

    def pathToObj(self, pathlst):
        """
        The description of pathToObj comes here.
        @param pathlst
        @return
        """
        objlst=[]
        for p in pathlst:
            if p:
                obj=self.getObject(p)
                if obj: objlst.append(obj)
        return objlst

    def handleButtonClick(self, btn, path, objlst, args, user):
        """
        The description of handleButtonClick comes here.
        @param btn
        @param path
        @param objlst
        @param args
        @param user
        @return
        """
        #logger.weblog.debug("click objlst: %s" % str(objlst))
        RC_FORM = 2
        if btn:
            if btn.act == htmbtns.BtnAction.confirm:
                # we get here after user confirmation
                (e, data) = self.evalButtonPost(btn,path,objlst,args)
            elif btn.act == htmbtns.BtnAction.form:
                try:
                    (e, data) = (RC_FORM, btn.gen_form(self.san,path,objlst))
                except GenFormError, err:
                    (e, data) = (1, str(err))
            elif btn.act == htmbtns.BtnAction.none:
                (e, data) = self.evalButtonPost(btn,path,objlst,args)
            elif btn.act == htmbtns.BtnAction.delete:
                (e, data) = self.postButtonDelete(btn,path,objlst,args, user)
            else:
                (e, data) = (1, 'Error: button action is not defined')
        else:
            (e, data) = (1, 'Error: button object not found')
        return (e, data)

    def evalButtonPost(self, btn, path, objlst, args):
        """
        The description of evalButtonPost comes here.
        @param btn
        @param path
        @param objlst
        @param args
        @return
        """
        #logger.weblog.debug("eval objlst: %s" % str(objlst))
        try:
            (e, data) = btn.post_form(self.san, path, objlst, args)
            if not e and btn.autosave:
                self.srv.save_configuration()
        except Exception, exc:
            (e, data) = (1, 'evalButtonPost failure')
            logger.weblog.error('Webportal evalButtonPost failure: %s traceback: %s' % \
                    (str(exc),  traceback.format_exc()))
        return (e, data)

    def postButtonDelete(self, btn, path, objlst, args, user):
        """
        The description of postButtonDelete comes here.
        @param btn
        @param path
        @param objlst
        @param args
        @param user
        @return
        """
        try:
            for obj in objlst:
                p = obj.fullpath.strip('/ ')
                (e, data) = self.srv.del_obj(p, {'f': 0}, user)
                if e:
                    break
            if not e:
                self.srv.save_configuration()
        except Exception, exc:
            (e, data) = (1, 'post delete failure')
            logger.weblog.error('Webportal post delete failure: %s traceback: %s' % \
                    (str(exc),  traceback.format_exc()))
        return (e, data)

    def divAlert(self, msg):
        """
        @param msg
        @return
        """
        m="""<div class="ui-widget">
<div class="ui-state-error ui-corner-all" style="padding: 0pt 0.7em;"><p>
    <span class="ui-icon ui-icon-alert" style="float: left; margin-right: 0.3em;"></span>
    <strong>Alert:</strong> %s
</p></div></div>""" % msg
        return m

## end of class VSAPortal


#def main():
#    pass # TBD VSA server code

##from twisted.cred import portal, checkers
##from twisted.conch import manhole, manhole_ssh
##
##def getManholeFactory(namespace, **passwords):
##    realm = manhole_ssh.TerminalRealm( )
##    def getManhole(_): return manhole.ColoredManhole(namespace)
##    realm.chainedProtocolFactory.protocolFactory = getManhole
##    p = portal.Portal(realm)
##    p.registerChecker(
##        checkers.InMemoryUsernamePasswordDatabaseDontUse(**passwords))
##    f = manhole_ssh.ConchFactory(p)
##    return f

#if __name__ == '__main__':
#    print 'Starting ..'
#    reactor.callWhenRunning(main)
#    reactor.listenTCP(listenport, server.Site(VSAPortal()))
#    print 'Listening on port %d ..' % listenport
###    reactor.listenTCP(2222, getManholeFactory(globals( ), root='123456'))
#    reactor.run()
