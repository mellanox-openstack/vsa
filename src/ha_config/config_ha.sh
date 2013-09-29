#!/bin/sh

BASENAME=`basename $0`
DIRNAME=`dirname $0`
#HAFILES=./hafiles
HAFILES=.
TEMPLATE_HA_CF=${HAFILES}/ha.cf.template
TEMPLATE_HARESOURCES=${HAFILES}/haresources.template
#TEMPLATE_DRBD=drbd.conf.template
#TEMPLATE_DRBD_SETUP=drbd_setup.template
#VSA_MNT="/opt/vsa/files/"
#VSA_MNT="/mnt/res_fio"
RESTORE=0

# Check we are root
if [[ $EUID -ne 0 ]]; then
    echo "This script must be run as root" 1>&2
    exit 1
fi

# include common_ha file
cd $DIRNAME
if [ -e ./common_ha ]; then
	. ./common_ha
	#mkdir -p /opt/ufm/log/
	echo -e "`date`: HA INSTALLATION\n\n" > $HA_LOGFILE
else
	echo "ERROR: File ./common_ha does not exists" | tee -a $HA_LOGFILE
	exit 1
fi
cd - > /dev/null 2>&1

# get options
get_opts $*

# validate parameters
start_script

# disaply warning
display_warning

# install ha rpms
#install_rpms

# check prerequisites rpms
check_rpms

# print info
#(( $VERBOSE )) && print_info

# check if templates file exists
check_templates

# create config files
create_config

# generate authkey
${HAFILES}/GenAuthkey.sh

stop_heartbeat

check_heartbeat_port

# copy config files to servers
copy_config

# setup drbd
#setup_drbd

# install ufm on slave
#install_ufm_on_slave

# clean generated files
clean_config

start_heartbeat

echo "== END =="
