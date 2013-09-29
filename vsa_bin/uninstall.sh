#!/bin/bash

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd $DIR

if [ -f common ]; then
        . common
else
        echo "Can not find common file." 1>&2
        exit 1
fi

# params not available yet
print_help()
{
	cat <<EOF

Uage: $PROGNAME [options]

	-h	this help message
	-c	clean. try to uninstall any package related to vsa
			without checking the install log.
	
EOF
	exit 0
}

input_uninstall() {
	local SHORTOPTS="hc"

	clean=false
	force=false

	OPTS=$(getopt $SHORTOPTS "$@")

	if [ $? -ne 0 ]; then
		err "'$progname -h' for more information"
	fi

	: debug: $OPTS
	eval set -- "$OPTS"

	while [ $# -gt 0 ]; do
		: debug: $1
		case $1 in
		-h)
			print_help
			;;
		-f)
			force=true
			shift
			;;
		-c)
			clean=true
			shift
			;;
		--)
			shift
			break
			;;
		*)
			err "Internal Error: option processing error: $1"
			;;
		esac
	done

	do_uninstall
}

clean_un="
libtool-ltdl
openhpi-libs
libnet
heartbeat-stonith
heartbeat-pils
heartbeat
pyserial
pyOpenSSL
SOAPpy
python-pyasn1
python-crypto
python-zope-interface
python-twisted-web
python-twisted-words
python-twisted-runner
python-twisted-mail
python-twisted-news
python-twisted-conch
python-twisted-lore
python-twisted-names
python-twisted-core
python-twisted
python-fpconst
#sg3_utils-libs
#sg3_utils
drbd-utils
drbd-km-2.6.18_194.el5
pysnmp
flashcache-2.6.18-194.el5
python-TwistedSNMP
perl-Config-General
scsi-target-utils
vsacli
vsacli-ha
"
# remove commented packages
clean_un=`echo ${clean_un} | sed "s/#[^ ]* //g"`

select_uninstall_rpms() {
	local log=$installed_log

	if [ $clean = true ]; then
		echo "Choosing full cleanup."
		rpms_un="$clean_un"
	elif [ -f "$log" ]; then
		rpms_un=""
		for i in `grep "^install " $log | awk {'print $2'}`; do
			rpms_un+=" $i"
		done
	else
		echo "Install log not found, choosing default packages."
		vsa="vsacli"
		vsa_ha="vsacli-ha"
		tgt="scsi-target-utils"
		rpms_un="$vsa_ha $vsa $tgt"
	fi

	rpms_un="`trim $rpms_un`"
	rpms_lists="rpms_un"
}

do_clean() {
	echo "Cleaning.."
	local c i
	for c in 1 2 3; do
		for i in $rpms_un; do
			echo -n .
			rpm -e --quiet $i >/dev/null 2>&1
		done
	done
	echo .
	filter_un_lists
	if [ -n "$rpms_un" ]; then
		echo "Could not clean the following:"
		rpm -e $rpms_un
		return $?
	fi
	return 0
}

do_uninstall() {
	select_uninstall_rpms
	filter_un_lists

	# check there is anything to remove
	if [ -z "$rpms_un" ]; then
		fin "There are no packages to be removed."
	fi

	# stop all services
	echo -e "\nStopping services...\n"

	# heartbeat and drbd services are being stopped when uninstalling the rpm

	# vsa also stops when uninstall the rpm but we want to make sure we stop it before anything else
	if [ -f /usr/sbin/vsa ]; then
		/usr/sbin/vsa stop >/dev/null 2>&1
		sleep 1 # wait for tgtd to be killed
	fi

	if [ $clean = true ]; then
		do_clean
	else
		rpm -ev $rpms_un
	fi

	if [ "$?" != 0 ]; then
		err "Could not complete operation."
	fi
	
	rm -fr $installed_log
	fin "Uninstall complete."
}

input_uninstall $@
