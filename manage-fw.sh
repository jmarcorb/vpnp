#!/bin/sh
#credits go to Ira Finch http://bitman.org/irafinch/rpivpn/scripts/ 
#if you want to learn more, please do get his book at amazon
sleep 30
Adapter=`ip -o link show | awk '{print $2,$9}' | grep 'UP'| awk -F: '{print $1}'`
if [ -z "$Adapter" ]
then
    Adapter='eth0'
fi
echo "Adapter = |$Adapter|"
/sbin/iptables -t nat -A POSTROUTING -o $Adapter -j MASQUERADE
/sbin/iptables -A FORWARD -i $Adapter -o tun0 -m state --state RELATED,ESTABLISHED -j ACCEPT
/sbin/iptables -A FORWARD -i tun0 -o $Adapter -j ACCEPT
