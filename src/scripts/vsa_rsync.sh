#!/bin/bash

# SET OPTIONS
CONFIG="/opt/vsa/config.db"
LOGS="/opt/vsa/files/log/audit.log /opt/vsa/files/log/event.log"
ALL="$CONFIG $LOGS"

# PARSE ARGUMENT OPTION
FILES=${!1}

REMOTE=""
LOGS_DIR="/opt/vsa/files/log/"
SHORT=`hostname -s`
REMOTE_LOG_DIR="${LOGS_DIR}${SHORT}_log/"
#######################

if [[ "$1" == "logsize" ]]; then
	s=`du -c $LOGS | tail -1 | awk {'print $1'}`
	echo $s
	exit 0
fi

if [[ "$1" == "confsize" ]]; then
        s=`du -c $CONFIG | tail -1 | awk {'print $1'}`
        echo $s
        exit 0
fi

if [[ "$1" == "allsize" ]]; then
        s=`du -c $ALL | tail -1 | awk {'print $1'}`
        echo $s
        exit 0
fi

valid_input() {
	if [[ -z "$REMOTE" ]]; then
		echo "Remote not configured"
		exit 1
	fi
	if [[ -z "$FILES" ]]; then
		echo "Files to sync not configured"
		exit 1
	fi
}

rsync_files() {
	if [[ -z "$REMOTE" || -z "$FILES" ]]; then
		echo "Failed rsync"
		return 1
	fi
	if ! cping $REMOTE ; then
		echo "Cannot connect to $REMOTE"
		return 1
	fi

	local n

	for f in $FILES ; do
		n=${f##*/}
		echo -e "rsync $n -> $REMOTE"
		if [[ "$f" =~ "$LOGS_DIR" ]]; then
			rsync -aq $f $REMOTE:${REMOTE_LOG_DIR}
		else
			rsync -aq $f $REMOTE:$f
		fi
	done
	return 0
}

cping() {
	local _ip=$1
	local _var=`ping -s 1 -c 1 $_ip > /dev/null 2>&1; echo $?`
        if [[ "$_var" != 0 ]]; then
                #echo "Ping failed to $_ip"
                return 1
        fi
	return 0
}

get_remote() {
	REMOTE=""
	if [[ ! -f /etc/ha.d/ha.cf ]]; then
		echo "Could not find /etc/ha.d/ha.cf"
		exit 1
	fi
	local _ips=`grep -o "ucast [a-z0-9]* .*" /etc/ha.d/ha.cf | awk {'print $3'}`
	for i in $_ips ; do
		if cping $i ; then
			REMOTE=$i
			return 0
		fi
	done
	echo "Could not detect remote host from /etc/ha.d/ha.cf" 
	exit 1
}

ha_is_master() {
	# check heartbeat installed
	rpm -q --quiet heartbeat || exit 1
	# heartbeat status
	local a=`(cl_status hbstatus >/dev/null && cl_status rscstatus 2>/dev/null) || echo none`
	# none == standby or ha not running
	if [[ "$a" == "none" ]]; then
		exit 1
	fi
	# all == other node is stand by
	if [[ "$a" == "all" ]]; then
		return 0
	fi
	# if we're here then heartbeat status is probably local
	# check if vsa.conf is missing
	if [[ ! -f /opt/vsa/files/conf/vsa.conf ]]; then
		exit 1
	fi
	local s=`grep "^role=" /opt/vsa/files/conf/vsa.conf | cut -d"=" -f2`
	# check if configured as master
	if [[ "$s" == "master" ]]; then
		return 0
	fi
	echo "ha check failed: cl: $a - ro: $s"
	exit 1
}

ha_is_master
get_remote
valid_input
rsync_files
