#!/bin/env python

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


from subprocess import PIPE, Popen
import time
import re


TGTADM = 'tgtadm'
SHOW_TARGET = '%s -C {0} -m target -o show' % TGTADM
STAT_CMD = '%s -C {0} -m target -o stat --tid {1}' % TGTADM

SHOW_INSTANCES = 'ps -f --no-headers -C tgtd'
STAT_HEADER = 'ins tgt lun sid rMB/s(subm) rIO(subm) rMB/s(done) rIO(done) wMB/s(subm) wIO(subm) wMB/s(done) wIO(done) errs'
STAT_FORMAT = '%-3s %-3s %-3s %-3s %-11d %-9d %-11d %-9d %-11d %-9d %-11d %-9d %-9d'
TOTAL = '\nTotal:%-10s' % ' '

KILOBYTE=1024


def get_tgts(instance):
    tgt_ids = []
    cmd = SHOW_TARGET.format(instance)
    p = Popen(cmd.split(), stdout=PIPE)
    out, _ = p.communicate()
    for l in out.splitlines():
        if l.startswith('Target'):
            #tgt_ids.add(l.split())
            tgt_ids.append(l.split()[1][:-1])
    return tgt_ids


_instances = []
def get_instances():
    global _instances
    ins = []
    p = Popen(SHOW_INSTANCES.split(), stdout=PIPE)
    out, _ = p.communicate()
    for l in out.splitlines():
        srch = re.search(r' -(-instance|C) (\d+)', l)
        if srch and srch.group(2) not in ins:
            ins += srch.group(2)
    _instances = sorted(ins)


def print_stat_line(statline):
    print STAT_FORMAT % statline


_old_stats = {}
def get_new_stats():
    global _old_stats
    new_stats = {}
    print STAT_HEADER
    total = [0]*8
    for ins_n in _instances:
        ins = new_stats[ins_n] = {}
        for tgt_n in get_tgts(ins_n):
            stat_cmd = STAT_CMD.format(ins_n, tgt_n)
            p = Popen(stat_cmd.split(), stdout=PIPE)
            out, _ = p.communicate()
            out = out.splitlines()

            if len(out) <= 2:
                continue
            tgt = ins[tgt_n] = {}
            for l in out[2:]:
                l = l.split()
                lun_n = l[1]
                sid_n = l[2]
                lun = tgt[lun_n] = {}
                new_sid_stats = lun[sid_n] = l[3:-1]
                errs = l[-1]

                # retreiving old stats, default to 0 on all benchmarks
                old_sid_stats = _old_stats \
                                .get(ins_n, {})\
                                .get(tgt_n, {})\
                                .get(lun_n, {})\
                                .get(sid_n, [0,0,0,0,0,0,0,0])
                sid_stats_diff = [  int(new_sid_stats[i]) -
                                    int(old_sid_stats[i])
                                        for i in range(len(new_sid_stats)) ]
                for i in [0,2,4,6]:
                    sid_stats_diff[i] /= KILOBYTE*KILOBYTE
                sl = tuple(i for i in [ins_n, tgt_n, lun_n, sid_n] +
                                            sid_stats_diff + [int(errs)] )
                total = [int(total[i]) + int(sl[i+4]) for i in range(8)]
                print_stat_line(sl)
    print TOTAL + '%-11d %-9d '*4 % tuple(total)
    _old_stats = new_stats


def main():
    get_instances()
    try:
        while True:
            get_new_stats()
            time.sleep(1)
            print ''
    except KeyboardInterrupt:
        print ''
        return


if __name__ == '__main__':
    main()
