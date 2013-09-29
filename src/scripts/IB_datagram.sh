#!/bin/bash

usage() {
	echo "Change IB interface to datagram mode."
	echo "Usage: $0 (iface|all)"
	echo "Example:	IB_datagram.sh ib0"
	echo "		IB_datagram.sh all"
}

function GetNetworkScriptDir() {
	if [ -e /etc/SuSE-release ]; then
		netscriptdir="/etc/sysconfig/network"
		return 0
	elif [ -e /etc/redhat-release ]; then
		netscriptdir="/etc/sysconfig/network-scripts"
		return 0
	fi
	netscriptdir="/tmp"
	return 1
}


# Change IB interface to datagram
# $1 interface (eg, ib0)
function IB_datagram() {

	GetNetworkScriptDir
	if [ $? == 1 ]; then
		echo "Unknown location of network script dir"
		return 1
	fi


	local iface=$1
	local mode=`cat /sys/class/net/$iface/mode`
	local mtu=`cat /sys/class/net/$iface/mtu`
	local netscript=$netscriptdir/ifcfg-$iface

	if [ $mode = "datagram" -a $mtu = 2044 ]; then
		return 0
	fi

	if [ ! -e $netscript ]; then
		echo "Network script not found"
		return 1
	fi

	ifdown $iface

	echo datagram > /sys/class/net/$iface/mode
#       echo 2044 > /sys/class/net/$iface/mtu
	ip link set dev $iface mtu 2044

        sed -i "s/MTU=.*/MTU=2044/g" $netscript

	# rhel IB stack
	sed -i "s/CONNECTED_MODE=.*/CONNECTED_MODE=no/g" $netscript

	# OFED stack
	if [ -e /etc/infiniband/openib.conf ]; then
		sed -i "s/SET_IPOIB_CM=.*/SET_IPOIB_CM=no/g" /etc/infiniband/openib.conf
	fi

	ifup $iface

        local mode=`cat /sys/class/net/$iface/mode`
        local mtu=`cat /sys/class/net/$iface/mtu`

        if [ $mode = "datagram" ] && [ $mtu = 2044 ]; then
		return 0
	fi

	return 1
}

iface=$1
if [ -z "$iface" ] || [ "$iface" = "-h" ]; then
	usage
	exit 0
elif [ "$iface" = "all" ]; then
	i=`ip link|grep ib[0-9] | cut -d: -f2`
	for f in $i; do
		IB_datagram $f
		r=$?
		if [ $r != 0 ]; then
			exit $r
		fi
	done
else
	IB_datagram $iface
	exit $?
fi
