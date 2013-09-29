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


import time,urllib
from vsa.client.gui.pages import DefaultHeader

PageHeader2="""
<html><head><title>%s</title>
<script>
function expand(sec)
{thisSec = eval('sec' + sec);
 if (thisSec != null){
          if (thisSec.length){
               if (thisSec[0].style.display != 'none'){
                    for (var i=0;i<thisSec.length;i++) {thisSec[i].style.display = 'none'}
               }
               else{
                    for (var i=0;i<thisSec.length;i++) {thisSec[i].style.display = 'block'}
               }
          }
          else{
                         if (thisSec.style.display != 'none')     {thisSec.style.display = 'none'}
               else{thisSec.style.display = 'block'}
          }
 }
}

</script>
</head>
<body><h1>%s</h1>"""

PageHeader=DefaultHeader + "</head>"

PageFooter="</body></html>"

MsgBar="""
<table boarder="1" align=center bgcolor="#FFFFC1" width="98%%">
<tr><td>&nbsp;%s<br></td></tr></table><br>"""

#hred,hgreen,hgray=(' bgcolor="#ff0000" ',' bgcolor="lime" ','  bgcolor="#e1e1e1"')

ActionHeader="""
<script type='text/javascript'>
function SetChecked(val,frm) {
dml=document.getElementById(frm)
len = dml.elements.length;
var i=0;
for( i=0 ; i<len ; i++) {
if (dml.elements[i].name=='citems') {
dml.elements[i].checked=val;
}}}
function ConfirmAct(act){return confirm("Are you sure you want to "+act.value+" ?")}
</script>
<form id="%s" name="itemsfrm" method="POST" action="#" onSubmit="return ConfirmAct(this.actions)"><tr bgcolor="#BBBBFF">
<td align="left" COLSPAN=%d>&nbsp;Select: <a href="javascript:SetChecked(1,'%s')">All</a>,
<a href="javascript:SetChecked(0,'%s')">None</a>&nbsp;&nbsp;&nbsp; Action:
<select name="actions">
%s
</select>
&nbsp;&nbsp;&nbsp;Parameters (optional): &nbsp;<input type="text" name="params" value="">
&nbsp;&nbsp;<input type="submit" value="Go.."><td align="right"></td></tr>
"""

# Html Colors
htc_red,htc_green,htc_gray,htc_orange,htc_yellow,htc_black=('#ff0000','lime','#e1e1e1','#ffcc00','#ffff00','#000000')

# Html Objects

class HtmlPage:
    # Html Page base class
    def __init__(self,request,user,ufm=None,msg='',txt='',header='',formargs={}) :
        """
        The description of __init__ comes here.
        @param request
        @param user
        @param ufm
        @param msg
        @param txt
        @param header
        @param formargs
        @return
        """
        self.req,self.ufm,self.msg=request,ufm,msg
        self.user='Unknown'
        if user : self.user=user
        self.objs=[]
        if txt : self.objs=[txt]
        self.tree=[]
        self.title=''
        self.header=header
        self.args={}
        self.formargs=formargs
        if self.req : self.args=self.req.args
    def generate(self):
        """
        The description of generate comes here.
        @return
        """
            # stub called prior to Html text generation
        pass
    def addobj(self,obj):
        """
        The description of addobj comes here.
        @param obj
        @return
        """
            # add/append an html object to the page
        self.objs+=[obj]
        return obj
    def addraw(self,txt):
        """
        The description of addraw comes here.
        @param txt
        @return
        """
            # add/append raw Html text to the page
        self.objs+=[txt]
    def addrtxt(self,txt,color='',size=0,face=''):
        """
        The description of addrtxt comes here.
        @param txt
        @param color
        @param size
        @param face
        @return
        """
            # add/append rich text to the page
        self.objs+=[htrtext(txt,color,size,face)]
    def html(self):
        """
        The description of html comes here.
        @return
        """
            # generate and return page Html text
        self.generate()
        if self.msg : self.msg=MsgBar % self.msg
        #nav='&nbsp;'+genref('index','Home')
        #for t in self.tree:
        #    nav+=' > '+t

        #login='User: %s | %s | %s' % (self.user,genref('logout','Logout'),time.strftime('%H:%M:%S'))
        #line='<tr><td align=left>%s</td><td align=right>%s</td></tr>' % (nav,login)
        #h='<table border=0 width=95%><b>'+line+'</b></table><hr width="100%%" size="2" color="#666699"><br>'
        #h=PageHeader % (self.header,self.header) + h + self.msg
        h=PageHeader + self.msg
        if self.title : h+=genfont(self.title+'<br>',"#004080",3)

        tmp=[]
        for o in self.objs :
            if type(o) is str : tmp+=[o]
            else : tmp+=[o.html()]
        h+='\n'.join(tmp)
        return str(h + PageFooter)

class htrtext:
    # Html rich text obgect
    def __init__(self,txt,color='',size=0,face=''):
        """
        The description of __init__ comes here.
        @param txt
        @param color
        @param size
        @param face
        @return
        """
        self.txt = txt
        self.color = color
        self.size = size
        self.face = face

    def html(self):
        """
        The description of html comes here.
        @return
        """
        tmp=self.color and (' color="%s"' % self.color)+self.size and (' size="%d"' % self.size) + \
          self.face and (' face="%s"' % self.face)
        if tmp : return '<font %s>%s</font>' % (tmp,self.txt)
        return self.txt

class htsplit:
    # Html multi column object container, with configurable widths
    def __init__(self,cols,widths=None,attribs=''):
        """
        The description of __init__ comes here.
        @param cols
        @param widths
        @param attribs
        @return
        """
        self.cols,self.widths,self.attribs=cols,widths,attribs
    def html(self):
        """
        The description of html comes here.
        @return
        """
        tmp='<table boarder=0 %s><tr valign=TOP>' % self.attribs
        if not self.widths : self.widths=['']*len(self.cols)
        for i in range(len(self.cols)) :
            wd=''
            if self.widths[i] : wd=' width="%s"' % self.widths[i]
            tmp+='<td%s>%s</td>' % (wd,self.cols[i])
        return tmp+'</tr></table>'


class htable:
    # Html Table object
    def __init__(self,title,cols,border=1,cellsp=0,chk=1,hdrclr='#A4A4FF',align='left',expand=0,style='',rules='none'):
        """
        The description of __init__ comes here.
        @param title
        @param cols
        @param border
        @param cellsp
        @param chk
        @param hdrclr
        @param align
        @param expand
        @param style
        @param rules
        @return
        """
        self.name='tbl1'
        self.title=title
        self.cols=cols
        self.expand=expand
        self.rules=rules
        self.colalign=['']*(len(cols)+1)
        self.border=border
        self.style=style
        self.cellspacing=cellsp
        self.hdrclr=hdrclr
        self.tglclr=['','#edfefe']
        self.tglrows=1
        self.check=chk
        self.chkname='citems'
        self.rows=[]
        self.addrow(cols,' align="%s"' % (align),'h',self.hdrclr)
        self.actlist={}
        #return self
    def addrow(self,data,attrib='',hdr='d',clr=''):
        """
        The description of addrow comes here.
        @param data
        @param attrib
        @param hdr
        @param clr
        @return
        """
        clr=clr or self.tglclr[len(self.rows) % len(self.tglclr)]
        r=htrow(self,data,hdr,clr,attrib)
        self.rows+=[r]
        return r
    def html(self):
        """
        The description of html comes here.
        @return
        """
        moreopt='BORDERCOLOR="%s" RULES="%s" width=95%% %s' % (self.hdrclr,self.rules,self.style)
        if self.expand :
            moreopt+=' id="sec%d" style="display:block"' % (self.expand)
            self.title=genref('javascript:expand(%d)' % self.expand,'[+] ')+self.title
        tmp='<table border="%d" cellspacing="%d"  cellpadding="2"%s>' % (self.border,self.cellspacing,moreopt)
        if self.title : tmp='<br><font color="#1A0770"><b>%s</b><br></font>' % self.title+tmp
        if self.check :
            act=''
            for k in self.actlist.keys() : act+=' <option value="%s">%s</option>\n' % (k,self.actlist[k])
            tmp+=ActionHeader % (self.name,len(self.cols),self.name,self.name,act)
        #tmp+='<tr bgcolor="#BBBBFF"><th align="left" COLSPAN=%d>&nbsp;Select: All,None&nbsp; Action:</th></tr>' % (len(self.cols)+1)
        for r in self.rows : tmp+=r.html()
        if self.check : tmp+='</form>'
        return tmp+'</table>'

class htrow:
    # Html Table Row object
    def __init__(self,par,data,hdr,clr,attrib):
        """
        The description of __init__ comes here.
        @param par
        @param data
        @param hdr
        @param clr
        @param attrib
        @return
        """
        self.parent=par
        if par.check : data=['']+data
        self.data=data
        self.hdr=hdr
        self.color=clr
        self.rowattrib=attrib
        self.attrib=['']*len(data)
        self.chkname='citems'
        self.chkval=''
        #return self

    def html(self):
        """
        The description of html comes here.
        @return
        """
        tmp='<tr%s>' % genhdr(self.color,self.rowattrib)
        if self.chkval : self.data[0]='<input type="checkbox" name="%s" value="%s">' % (self.chkname,self.chkval)
        for c in range(len(self.data)) :
            if self.hdr=='d' and self.parent.colalign[c] :
                self.attrib[c]+=' align='+self.parent.colalign[c]
            tmp+='<t%s %s>%s</t%s>' % (self.hdr,self.attrib[c],self.data[c] or '&nbsp;',self.hdr)
        return tmp+'<tr>'

# Html generator helpers

def genhtmlist(dic,cols=2,fsize='2',fcolor="#0000FF"):
    """
    The description of genhtmlist comes here.
    @param dic
    @param cols
    @param fsize
    @param fcolor
    @return
    """
    tmp='<font size="%s" face="Arial" color="%s">' % (fsize,fcolor)
    tmp+='<table bgcolor="#F8F8F8" border=0 cellspacing="2"  cellpadding="3" width="95%%"><tr>'
    i=0
    for k in dic.keys():
        i+=1
        tmp+='<td align=left><b>&nbsp;%s:</b></td><td align=left>%s</td><td>&nbsp;</td>' % (k,dic[k])
        if i % cols==0 : tmp+='</tr><tr>'
    return tmp[:-5]+'</table></font>'

def genhdr(clr,attr=''):
    """
    The description of genhdr comes here.
    @param clr
    @param attr
    @return
    """
    if clr : clr=' bgcolor="%s"' % clr
    if clr and attr: clr=clr+' '
    return clr+attr

def genref(link,data):
    """
    The description of genref comes here.
    @param link
    @param data
    @param data
    @return
    """
    return '<a href="%s">%s</a>' % (link,data)


def genfont(txt,color='',size=0,face=''):
    """
    The description of genfont comes here.
    @param txt
    @param color
    @param size
    @param face
    @return
    """
    tmp=(color and (' color="%s"' % color))+(size and (' size="%d"' % size))+(face and (' face="%s"' % face))
    return '<font %s>%s</font>' % (tmp,txt)

def gensplit(cols,widths=None,attribs='') :
    """
    The description of gensplit comes here.
    @param cols
    @param widths
    @param attribs
    @return
    """
    tmp='<table boarder=0 %s><tr valign=TOP>' % attribs
    if not widths : widths=['']*len(cols)
    for i in range(len(cols)) :
        wd=''
        if widths[i] : wd=' width="%s"' % widths[i]
        tmp+='<td%s>%s</td>' % (wd,cols[i])
        print widths
    return tmp+'</tr></table>'

def genopts(name,dict,select=''):
    """
    The description of genopts comes here.
    @param name
    @param dict
    @param select
    @return
    """
    txt='<select name="%s">' % name
    for k in dict.keys():
        sl=''
        if k==select : sl='selected '
        txt+='<option %svalue="%s">%s</option>' % (sl,k,dict[k])
    return txt+'</select>\n'

def htag(txt,tag,**args):
    """
    The description of htag comes here.
    @param txt
    @param tag
    @param **args
    @return
    """
    tmp=''
    for a in args.keys() : tmp+=(' %s=%s' % (a,args[a]))
    return '<%s%s>%s</%s>' % (tag,tmp,txt,tag)

def args2dic(txt):
    """
    The description of args2dic comes here.
    @param txt
    @return
    """
    if not txt : return {}
    tmp=txt.split('&')
    dict={}
    for t in tmp :
        pair=t.split('=')
        if len(pair)==1 : pair+=['']
        dict[pair[0]]=urllib.unquote_plus(pair[1])
    return dict

def dic2args(dic):
    """
    The description of dic2args comes here.
    @param dic
    @return
    """
    list=[]
    for k in dic.keys():
        if dic[k]=='':
            list+=[k]
        else : list+=[k+'='+urllib.quote_plus(dic[k])]
    return '&'.join(list)

def replacearg(urlargs,arg,newval):
    """
    The description of replacearg comes here.
    @param urlargs
    @param arg
    @param newval
    @return
    """
    dic=args2dic(urlargs)
    dic[arg]=newval
    return dic2args(dic)

def replaceargd(dic,arg,newval):
    """
    The description of replaceargd comes here.
    @param dic
    @param arg
    @param newval
    @return
    """
    d={}
    for k in dic.keys() : d[k]=dic[k]
    d[arg]=newval
    return dic2args(d)

def get_default(dic,key,default):
    """
    The description of get_default comes here.
    @param dic
    @param key
    @param default
    @return
    """
    if dic.has_key(key):
        if type(default)==int : # make sure we return the right type
            return int(dic[key])
        else : return dic[key]
    else : return default
