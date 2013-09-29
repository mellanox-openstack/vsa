#!/bin/bash

check_interface_debian()
{
	local iface=$1
	local ifile="/etc/network/interfaces"
	
	if [ ! -e $ifile ]; then
		return 1
	fi
	local m=`grep -E "^iface $iface inet" $ifile |awk {'print $4'}`
	if [ -z $m ]; then
		return 1
	fi
	case "$m" in
	  'static') echo static ;;
	  'dhcp') echo dhcp ;;
	  'bootp') echo bootp ;;
	  *) return 1 ;;
	esac
	exit 0
}

check_interface_ifcfg()
{
	local iface=$1
	#local ifile="/etc/sysconfig/network-scripts/ifcfg-$iface"
	local ifile=$2

	if [ ! -e "$ifile" ]; then
		return 1
	fi

	m=`grep BOOTPROTO $ifile | sed 's/=/ /' | awk {'print $2'} | tr -d \'`
	if [[ -z "$m" || "$m" != "dhcp" ]]; then
		echo static
	elif [ "$m" == "bootp" ]; then
		echo bootp
	else
		echo dhcp
	fi
	exit 0
}


find_ifcfg()
{
	local iface=$1
	local m=$(find /etc/sysconfig/ -name ifcfg-$iface -print 2>&1 | grep -v denied | head -1)
	if [ ! -z "$m" ]; then
		echo "$m"
	fi
}

check_input()
{
	local iface=$1

        if [ -z "$iface" ]; then
                usage
        fi

	i=$(find_ifcfg $iface)
	if [ ! -z "$i" ]; then
		check_interface_ifcfg $iface $i
	fi
	check_interface_debian $iface

	# exit with code 0 all the time
	exit 0
}

usage()
{
        echo "Usage: $0 interface

eg: $0 eth0"
        exit 1
}

check_input $@
