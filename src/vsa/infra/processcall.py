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


import subprocess
import signal
import os
import time
import traceback

from vsa.infra import logger

# set to enable tracking process_call exit time when suspecting
# that an application hangs or take too long to execute
log_pc_exit = 0

def process_call(cmd, timeout=30, shell=False, log=True, stderr=True):
    """
    The description of process_call comes here.
    @param cmd
    @param timeout
    @param shell
    @param log
    @param stderr
    @return
    """
    # if not running in shell convert str to list
    if cmd.__class__.__name__ == 'str' and not shell:
        cmd = cmd.split(' ')
    # log
    if log or log_pc_exit:
        logger.agentlog.info(str(cmd))
    # execute
    try:
        if stderr:
            err_pipe = subprocess.STDOUT
        else:
            err_pipe = subprocess.PIPE
        process = subprocess.Popen(cmd, shell=shell, stdout=subprocess.PIPE, stderr=err_pipe, close_fds=True)
    except Exception,err:
        return (1,'execute error '+str(err))
    tt = time.time()
    output = []
    outerr = []
    while process.poll() == None:
        w = os.waitpid(process.pid, os.WNOHANG)
        if w != (0,0):
            break
        time.sleep(0.01)
        if time.time() - tt >= timeout:
            break
        output += process.stdout.readlines()
        if not stderr:
            outerr += process.stderr.readlines()
    output += process.stdout.readlines()
    if not stderr:
        outerr += process.stderr.readlines()
    # Process not finished
    if process.poll() == None and w == (0,0):
        os.kill(process.pid, signal.SIGTERM)
        #python 2.6: process.kill()
        if log or log_pc_exit:
            logger.agentlog.warning('timeout waiting for process to finish')
        return (-1,'timeout waiting for process to finish')
    # Check which caught the signal
    if process.poll() == None:
        e = int(w[1])
    else:
        e = int(process.poll())
    output = ''.join(output)
    outerr = ''.join(outerr)
    if e:
        # if log==False we didn't log cmd before so we're logging it now
        if not log:
            logger.agentlog.warning(str(cmd))
        logger.agentlog.warning('err %d: %s' % (e, output))
        if outerr:
            logger.agentlog.warning('stderr log: %s' % outerr)
    else:
        if log_pc_exit:
            logger.agentlog.info('exit %d: %s' % (e, output))
        if outerr and (log or log_pc_exit):
            logger.agentlog.warning('stderr log: %s' % outerr)
    return (e, output)
