#!/usr/bin/env python

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


import cmd, getpass, subprocess
import string, os, sys, traceback, re
import time, socket, xmlrpclib
from vsa.infra.params import SANSRV_XMLRPC_PORT, ERR_HA_SLAVE, ERR_HA_TRANSITION
from vsa.infra.infra import safepeek, parse_cfg, confirm, tstint
from vsa.infra.config import files_dir, scripts_dir, config_db

#===============================================================================
# from params import *
# from infra import *
#===============================================================================

PRODUCT_NAME = 'VSA'
PRODUCT_VERSION = '2.1'

IntroString = "\n\
Welcome to Virtual Storage Array console!, Ver %s\n\
Type: help or help <command> for more details\n\
Type: help quick for quick step by step configuration guide\n" % PRODUCT_VERSION

lclpath = os.path.dirname(os.path.abspath(__file__)) + '/'

objlist=['disks','raids','volumes','pools','targets','fc','servers','ls','system','config','log','version','cache']
monitorlist=['block','target','server','ib','ifc','system','storage']

def sttstr(v):
    """
    The description of sttstr comes here.
    @param v
    @return
    """
    if v:
        return "**Error(%d)," % v
    else:
        return "Success,"


class CLI(cmd.Cmd):
    def __init__(self):
        """
        The description of __init__ comes here.
        @return
        """
        cmd.Cmd.__init__(self,'TAB')
        self.prompt = PRODUCT_NAME+'-root> '
        self.intro  = IntroString
        self.cfgmode=False
        self.srv=None
        self.admin=True
        self.updated=False
        self.user=os.environ.get('USER', 'service')
        self.cfgpath="/"
        self.loadmode=False
        self.lasterr=0
        self._hist = [] # history
        self.hlines=open(lclpath+'help.doc').readlines()
        self.topics={}
        last=len(self.hlines)-1
        i=0; firstline=0
        lasttop=''
        self.endhelp=0
        self.vars={}
        for l in self.hlines:
            if l.startswith('$$'):
                if i>1 and self.endhelp==0 : self.endhelp=i
                if lasttop : self.topics[lasttop]=[firstline,i-1]
                lasttop=l[2:].strip()
                firstline=i+1
            i+=1

        # Connect to SAN Server via XML RPC
        self.srv = xmlrpclib.ServerProxy('http://localhost:' + str(SANSRV_XMLRPC_PORT) + '/', allow_none=True)

    def fullpath(self,txt):
        """
        The description of fullpath comes here.
        @param txt
        @return
        """
        if txt.startswith('/'):
            return txt[1:]
        else:
            if self.cfgpath=='/':
                return txt
            else:
                return self.cfgpath[1:]+'/'+txt

    def op_complete(self,line,show=False):
        """
        The description of op_complete comes here.
        @param line
        @param show
        @return
        """
        args=line.split()
        if line.endswith(' ') : args+=['']
        if len(args)<3 :
            path=self.fullpath(args[1])
            return self.srv.complete(path,show)
        return []

    def preloop(self):
        """Initialization before prompting user for commands.
           Despite the claimeval(s in the Cmd documentaion, Cmd.preloop() is not a stub.
        """
        cmd.Cmd.preloop(self) # sets up command completion
        self._locals  = {} # Initialize execution namespace for user
        self._globals = {}

    def postloop(self):
        """Take care of any unfinished business.
           Despite the claims in the Cmd documentaion, Cmd.postloop() is not a stub.
        """
        cmd.Cmd.postloop(self)   ## Clean up command completion
        self.do_save()
        print "Exiting %s ..." % PRODUCT_NAME

    def precmd(self, line):
        """ This method is called after the line has been input but before
            it has been interpreted. If you want to modifdy the input line
            before execution (for example, variable substitution) do it here.
        """
        self.lasterr=0
        l=line.strip()
        if l not in ['','hist']:
            self._hist += [l]
        if not re.match(r'^[\w /?<>!*%#=;:,.+_-]*$',line):
            print "Error: command contains invalid characters"
            return ''
        return line

    def postcmd(self, stop, line):
        """If you want to stop the console, return something that evaluates to true.
           If you want to do some post command processing, do it here.
        """
        return stop

    def emptyline(self):
        """Do nothing on empty input line"""
        pass

    def default(self, line):
        """Called on an input line when the command prefix is not recognized.
           In that case we execute the line as Python code.
        """
        a=line.strip().split()
        c=safepeek(a)
        print c+' is not a valid CLI command !'
##        if c  in objlist:
##            self.do_set(line)

    def do_hist(self, args):
        """Print a list of commands that have been entered"""
        print self._hist

    def do_EOF(self, args):
        """Exit on system end of file character"""
        return self.do_quit(args)

    def do_add(self, arg):
        """
        The description of do_add comes here.
        @param arg
        @return
        """
        if not self.cfgmode:
            print "*** add command can only be used in config menus/mode, type: config"
            return
        (e,a0,a1,a2,lv)=parse_cfg(arg,[],'ancf',{'a':'0'})
        self.lasterr=e
        if e or not arg:
            print 'Command Error !!!'
            self.do_help('add')
            return
        path=self.fullpath(a0)
        (e,txt,newpath)=self.srv.add_obj(path,a1,a2,lv,self.user)
        self.lasterr=e
        if not self.loadmode or e:
            if self.loadmode:
                print 'CMD: add '+arg
            print sttstr(e),txt
        self.updated=True
        if lv['c']:
            self.do_config(newpath)

    def complete_add(self,text,line,begin_idx,end_idx):
        """
        The description of complete_add comes here.
        @param text
        @param line
        @param begin_idx
        @param end_idx
        @return
        """
        return self.op_complete(line)

    def do_del(self, arg):
        """
        The description of do_del comes here.
        @param arg
        @return
        """
        if not self.cfgmode:
            print "*** clear command can only be used in config menus/mode, type: config"
            return
        (e,a0,a1,a2,lv)=parse_cfg(arg,[],'f')
        self.lasterr=e
        if e or not arg:
            print 'Command Error !!!'
            self.do_help('del')
            return
        path=self.fullpath(a0)
        if path.endswith('*'):
            ans = confirm('Please confirm you would like to delete multiple objects')
            if not ans or ans=='n':
                return
        (e,txt)=self.srv.del_obj(path,lv,self.user)
        self.lasterr=e
        print sttstr(e),txt
        self.updated=True

    def complete_del(self,text,line,begin_idx,end_idx):
        """
        The description of complete_del comes here.
        @param text
        @param line
        @param begin_idx
        @param end_idx
        @return
        """
        return self.op_complete(line)

    def do_config(self, arg):
        """
        The description of do_config comes here.
        @param arg
        @return
        """
        if not self.admin and not self.loadmode:
            print "*** admin privilage is requiered for configuration"
            return
        path=self.fullpath(arg)
        (e,txt)=self.srv.test_objpath(path)
        self.lasterr=e
        if e:
            print txt
            return
        self.cfgpath='/'+path
        self.prompt = PRODUCT_NAME+'-%s# ' % self.cfgpath
        self.cfgmode=True

    def complete_config(self,text,line,begin_idx,end_idx):
        """
        The description of complete_config comes here.
        @param text
        @param line
        @param begin_idx
        @param end_idx
        @return
        """
        return self.op_complete(line)

    def do_exit(self, arg):
        """
        The description of do_exit comes here.
        @param arg
        @return
        """
        if self.cfgmode:
            if self.updated:
                if arg not in ['silent','nosave']:
                    ans = confirm('save configuration')
                    if not ans:
                        return
                    if ans=='y':
                        self.do_save('')
                if arg=='silent':
                    self.do_save('')
            self.prompt = PRODUCT_NAME+'-root> '
            self.cfgpath = '/'
            self.cfgmode = False
        else:
            print 'Already exited config mode, use quit to leave'

    def do_monitor(self, arg):
        """
        The description of do_monitor comes here.
        @param arg
        @return
        """
        (e,cat,a1,a2,lv)=parse_cfg(arg,monitorlist,'igws',{'i':'1','g':'rs'})
        if e or not arg:
            if not e: e=1
            self.lasterr=e
            print 'Command Error !!!'
            self.do_help('monitor')
            return e
        if a1 : obj=a1.split(',')
        else : obj=[]

        interval = tstint(lv['i'], 1)
        if interval < 1:
            interval = 1
        maxcnt = tstint(lv['s'], 0)
        if maxcnt < 0:
            maxcnt = 0

        if cat<>'system':
            mon=self.srv.mon
            #(e,m,p)=mon.startnew(cat,name='s',objs=obj,interval=interval,oplist=lv['g'])
            try:
                (e,m,p)=mon.startnew(cat,'s',obj,interval,lv['g'])
                if e:
                    self.lasterr=e
                    mon.stop(m)
                    print "Monitor error:",m
                    return e
            except KeyboardInterrupt:
                return

            hdr=mon.get_headers(m)
            header=0; cnt=0
            try:
                while 1:
                    if header==0 : print hdr
                    time.sleep(interval)
                    mon.process_tick(m)
                    mtxt=mon.get_datatxt(m)
                    if mtxt.strip()== '' and not lv['w']:
                        print 'No data currently available for your selection'
                        mon.stop(m)
                        return 0
                    print mtxt
                    header=(header+1) % 8
                    cnt+=1
                    if cnt==maxcnt:
                        mon.stop(m)
                        return 0

            except KeyboardInterrupt:
                mon.stop(m)
                print "Stopped.."
        if cat == 'system':
            try:
                rc = subprocess.call(['vmstat', str(interval), str(maxcnt)])
            except KeyboardInterrupt:
                print "Stopped.."
        return 0

    def complete_monitor(self,text,line,begin_idx,end_idx):
        """
        The description of complete_monitor comes here.
        @param text
        @param line
        @param begin_idx
        @param end_idx
        @return
        """
        return [i for i in monitorlist if i.startswith(text)]

    def do_reboot(self, arg):
        """
        The description of do_reboot comes here.
        @param arg
        @return
        """
        (e,a0,a1,a2,lv)=parse_cfg(arg,[],'f')
        if a0=='all' : a0=''
        if not self.admin :
            print "User must be an Admin to reboot the systems"
            return
        if confirm('Are you sure you want to reboot','n')<>'n':
            (e,txt)=self.srv.reboot(self.user,a0,a1+' '+a2,lv['f'])
            print sttstr(e),txt

    def do_rescan(self, arg):
        """
        The description of do_rescan comes here.
        @param arg
        @return
        """
        (e,a0,a1,a2,lv)=parse_cfg(arg)
        (e,txt)=self.srv.rescan(a0,a1)
        self.lasterr = e
        print sttstr(e),txt

    def do_refresh(self, arg):
        """
        The description of do_refresh comes here.
        @param arg
        @return
        """
        self.srv.refresh()

##    def do_restart(self, arg):
##        print 'restart not supported yet',arg

    def do_set(self, arg):
        """
        The description of do_set comes here.
        @param arg
        @return
        """
        if not self.cfgmode:
            print "*** set command can only be used in config menus/mode, type: config"
            return

        (e,a0,a1,a2,lv)=parse_cfg(arg,[],'anf',{'a':'0'})
        self.lasterr=e
        if e  or not arg:
            print 'Command Error !!!'
            self.do_help('set')
            return
        path=self.fullpath(a0)
        (e,txt)=self.srv.set_obj(path,a1,lv,self.user)
        self.lasterr=e
        if not self.loadmode or e :
            if self.loadmode : print 'CMD: set '+arg
            print sttstr(e),txt
        self.updated=True

    def complete_set(self,text,line,begin_idx,end_idx):
        """
        The description of complete_set comes here.
        @param text
        @param line
        @param begin_idx
        @param end_idx
        @return
        """
        return self.op_complete(line)

    def do_exec(self, arg):
        """
        The description of do_exec comes here.
        @param arg
        @return
        """
        if not self.admin :
            print "*** admin privilage is requiered for exec"
            return
        argv=arg.strip().split()
        if len(argv)<2 :
            print 'too few parameters, type: exec <provider> <command>'
            return
        (e,txt)=self.srv.docmd(argv[0],argv[1:])
        self.lasterr=e
        print e,txt

    def complete_exec(self,text,line,begin_idx,end_idx):
        """
        The description of complete_exec comes here.
        @param text
        @param line
        @param begin_idx
        @param end_idx
        @return
        """
        return [i for i in self.op_complete('xx /providers/') if i.startswith(text)]

    def do_show(self, arg):
        """
        The description of do_show comes here.
        @param arg
        @return
        """
        (e,a0,a1,a2,lv) = parse_cfg(arg,[],
                            'arwildst',{'l':'0','r':'0','w':'120','s':' ','t':'50'})
        self.lasterr = e
        if e:
            return
        if a0 == 'config':
            self.onecmd('save > screen')
            return
        if a0 == 'log':
            tail = tstint(lv['t'],0)
            if not a1:
                a1 = 'event'
            (e,txt) = self.srv.get_log(a1,tail,a2)
            self.lasterr = e
            if not e and tail:
                print 'showing last %d lines, use -t option to change tail size\n' % tail
            print txt
            return

        path = self.fullpath(a0)
        (e,txt) = self.srv.print_obj(path,a1,lv)
        self.lasterr = e
        print txt

    def complete_show(self,text,line,begin_idx,end_idx):
        """
        The description of complete_show comes here.
        @param text
        @param line
        @param begin_idx
        @param end_idx
        @return
        """
        return self.op_complete(line,True)

    def do_update(self, arg):
        """
        The description of do_update comes here.
        @param arg
        @return
        """
        if not self.cfgmode:
            print "*** set command can only be used in config menus/mode, type: config"
            return

        (e,a0,a1,a2,lv)=parse_cfg(arg,[],'r',{'r':'0'})
        self.lasterr=e
        if e  or not arg:
            print 'Command Error !!!'
            self.do_help('update')
            self.lasterr=e
            return
        path=self.fullpath(a0)
        (e,txt)=self.srv.update_obj(path,lv,self.user)
        self.lasterr=e
        print e,txt
        self.updated=True

    def complete_update(self,text,line,begin_idx,end_idx):
        """
        The description of complete_update comes here.
        @param text
        @param line
        @param begin_idx
        @param end_idx
        @return
        """
        return self.op_complete(line)

    def do_quit(self, arg=''):
        """
        The description of do_quit comes here.
        @param arg
        @return
        """
        if not self.cfgmode or not self.updated:
            sys.exit(0)

        if arg not in ['silent','nosave']:
            ans=confirm('save configuration')
            if not ans:
                return
            if ans=='y':
                self.do_save('')
        if arg=='silent':
            self.do_save('')

##            while ans.lower() not in ['y','n','','yes','no']:
##                try:
##                    ans=raw_input('save configuration [y] ?')
##                except (KeyboardInterrupt, EOFError):
##                    print
##                    return
##
##                if ans.lower() not in ['y','n','','yes','no']:
##                    print 'Please type y/n/yes/no as answer, try again'
##        if arg=='silent' or ans.lower() in ['','y','yes'] : self.do_save('')
        sys.exit(0)

    def do_save(self, arg=''):
        """
        The description of do_save comes here.
        @param arg
        @return
        """
        (e,a0,a1,a2,lv) = parse_cfg(arg,[],'r',{'r':'0'})
        self.lasterr = e
        if e:
            return
        if a0==">": a2=a1 ; a1=a0; a0='/'
        if not self.cfgmode and not (a2 and a2=='screen'):
            print "*** save command can only be used in config menus/mode, type: config"
            return
        if a1 and a1<>">" :
            print "Wrong syntax, Usage: save [path] [> file-name | screen]"
            return
        if a0 and a0<>'/' and not a2 :
            print "Please specify destination file, cannot use default for partial configuration/path"
            return
        m=re.match(r'[a-z][a-z0-9._]*$',a2, re.I)
        if a2 and not m:
            print "File name can only contain [a-z0-9._] and must start with a letter"
            return

        path=self.fullpath(a0)
        (e,lst)=self.srv.export_obj(path,lv)
        self.lasterr=e
        if e :
            print "** Error, ",lst
            return
        if (a2 and a2<>'screen') or not a2 :
            sync_config = False
            if not a2 :
                a2=config_db
                sync_config = True
            else:
                a2 = os.path.join(files_dir, a2)
            save_msg = "Saving configuration"
            if arg:
                save_msg = "%s to %s" % (save_msg, os.path.basename(a2))
            print save_msg
            f=open(a2,'w')
            f.write('\n'.join(lst)+'\n')
            f.close()
            self.updated = False
            if sync_config and os.path.isfile(scripts_dir+'/vsa_rsync.sh'):
                try:
                    rc=subprocess.call([scripts_dir+'/vsa_rsync.sh','CONFIG'])
                except OSError, m:
                    print 'Error syncing configuration:',m
        else :
            print '\n'.join(lst)

    def complete_save(self,text,line,begin_idx,end_idx):
        """
        The description of complete_save comes here.
        @param text
        @param line
        @param begin_idx
        @param end_idx
        @return
        """
        return self.op_complete(line)

    def do_load(self, arg='',ignorerr=False):
        """
        The description of do_load comes here.
        @param arg
        @param ignorerr
        @return
        """
        self.loaderr=0
        if not self.admin and not self.loadmode:
            return
        if arg == '> screen':
            scr=1
        else:
            scr=0
        if not arg or arg == '> screen':
            arg = config_db
        else:
            m=re.match(r'[A-Za-z0-9.]+$',arg)
            if arg and not m:
                print 'illegal file path, file name can only contain [A-Za-z0-9.] and should be placed in %s' % files_dir
                return
            arg = os.path.join(files_dir, arg)
        try:
            f=open(arg,'r')
        except Exception,err:
            if not self.loadmode : print "** Error,",err
            self.lasterr=1
            return

        if scr :
            print f.read()
            f.close()
            return

        lines=f.readlines()
        f.close()
        lastcfg=self.cfgmode
        if not lastcfg : self.do_config('')
        for l in lines:
            if not self.loadmode : print 'do: ',l,
            try:
                if l[0]<>'#' : self.onecmd(l)
            except Exception,err:
                print "** Error,",err
                self.lasterr=1
        self.updated=False
        if not lastcfg : self.do_exit('')

    def do_help(self,arg):
        """
        The description of do_help comes here.
        @param arg
        @return
        """
        if arg and arg in self.topics.keys():
            t = self.topics[arg]
            print ''.join(self.hlines[t[0]:t[1]])
        else:
            print ''.join(self.hlines[1:self.endhelp])

    def complete_help(self,text,line,begin_idx,end_idx):
        """
        The description of complete_help comes here.
        @param text
        @param line
        @param begin_idx
        @param end_idx
        @return
        """
        sl=line.split()
        hkeys=[]
        if len(sl)<3 and not (len(sl)==2 and line[-1]==' '):
            for t in self.topics.keys() :
                t1=t.split()[0]
                if t1 not in hkeys : hkeys+=[t1]
        else:
            for t in self.topics.keys() :
                tn=t.split()
                if tn[0]==sl[1] :
                    if tn[1] not in hkeys : hkeys+=[tn[1]]
        return [i for i in hkeys if i.startswith(text)]

    def onecmd(self,arg):
        """
        The description of onecmd comes here.
        @param arg
        @return
        """
        try:
            cmd.Cmd.onecmd(self,arg.replace('%','%%') % self.vars)
        except SystemExit:
            print 'Bye..'
            sys.exit(0)
        except Exception, err:
            self.lasterr = 1
            print "** Error, ",err
            if self.srv.debuglvl():
                print '-'*60
                traceback.print_exc(file=sys.stdout)
                print '-'*60

    def do_var(self,arg) :
        """
        The description of do_var comes here.
        @param arg
        @return
        """
        if not self.admin :
            print "*** admin privilage is requiered for variables"
            return
        if not arg :
            for k,v in self.vars.items() : print '%s=%s' % (k,v)
            return
        m=re.match(r'([A-Za-z][A-Za-z0-9]*)=(.+)',arg)
        if not m :
            if arg in self.vars.keys() : print '%s=%s' % (arg,self.vars[arg])
            else : print 'not a valid var assignment'
            return
        m1=re.match(r"([A-Za-z0-9' ]+[/+-/*/%]?\s*)+$",m.group(2).strip())
        if not m1 :
            print 'illegal expression use the format <var>|number|string +|-|*|/ <var>|number|string ..'
            return
        try:
            tmp=eval(m.group(2),{},self.vars)
            print tmp
            self.vars[m.group(1)]=tmp
        except Exception,err:
            print "** Error, ",err

    def do_eval(self,arg):
        """
        The description of do_eval comes here.
        @param arg
        @return
        """
        s = self.srv.san
        print eval(arg)

    # shortcuts
    do_q = do_quit
    do_sh = do_show
    complete_sh = complete_show


def main():
    """
    The description of main comes here.
    @return
    """
    addpvd=True
    if '--nopvd' in sys.argv:
        addpvd=False
        sys.argv.remove('--nopvd')

    # Initialize CLI object (connects to XMLRPC server)
    cli = CLI()
    srv = cli.srv

    if '--user' in sys.argv:
        cli.admin=False
        sys.argv.remove('--user')

    # Login to SAN Server, check connection at this point
    try:
        (stt,sid,mip)=srv.login(cli.admin,cli.user)
    except socket.error as e:
        print  "SAN Server connection error: %s" % str(e)
        sys.exit(1)

    if stt==ERR_HA_SLAVE:
        print '\n*** This node is a Standby node, please login to the master node ***\n'
        sys.exit(stt)
    if stt==ERR_HA_TRANSITION:
            print '\n*** This node is in transition ***\n'
            sys.exit(stt)

    load=False
    if '--load' in sys.argv:
        load=True
        cli.loadmode=True
        cli.do_load('',True)
        cli.loadmode=False
        srv.loaded()
        sys.argv.remove('--load')
        cli.do_quit('')
    if len(sys.argv) > 1 :
        cli.do_config('') # TBD remove
        cli.onecmd(' '.join(sys.argv[1:]))
        sys.exit(cli.lasterr)
    else:
##        if cli.admin : cli.do_config('') # TBD remove
        try:
            if load :
                cli.loadmode=True
                cli.do_load('',True)
                cli.loadmode=False
            srv.loaded()
            cli.cmdloop()
        except KeyboardInterrupt:
            print "Stopped.."
            cli.do_quit('')
        except socket.error, e:
            print "SAN Server connection error: %s" % str(e)
            sys.exit(1)

if __name__ == '__main__':
    main()
