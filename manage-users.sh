#!/bin/sh

MOUNTDIR=/mnt/usb
if [! -d "$MOUNTDIR" ]; then
    mkdir $MOUNTDIR
    echo "USB montado en $MOUNTDIR"
fi
mount /dev/sda1 $MOUNTDIR
if [ $? -eq 0]; then
    echo "Woohoo! Mount succeeded!"
    echo "################## genkey secret ta.key #######################"
    cd /etc/openvpn/easy-rsa
    openvpn --genkey --secret pki/ta.key
    echo "############## creación de certificados ######################"
    ./easyrsa --batch --req-cn=llave1 gen-req llave1 nopass
    ./easyrsa --batch --days=7300 sign-req client llave1
    ./easyrsa --batch --req-cn=llave2 gen-req llave2 nopass
    ./easyrsa --batch --days=7300 sign-req client llave2
    ./easyrsa --batch --req-cn=llave3 gen-req llave3 nopass
    ./easyrsa --batch --days=7300 sign-req client llave3
    ./easyrsa --batch --req-cn=llave4 gen-req llave4 nopass
    ./easyrsa --batch --days=7300 sign-req client llave4
    ./easyrsa --batch --req-cn=llave5 gen-req llave5 nopass
    ./easyrsa --batch --days=7300 sign-req client llave5
    ./easyrsa --batch --req-cn=llave1 gen-req llave6 nopass
    ./easyrsa --batch --days=7300 sign-req client llave6
    ./easyrsa --batch --req-cn=llave2 gen-req llave7 nopass
    ./easyrsa --batch --days=7300 sign-req client llave7
    ./easyrsa --batch --req-cn=llave3 gen-req llave8 nopass
    ./easyrsa --batch --days=7300 sign-req client llave8
    ./easyrsa --batch --req-cn=llave4 gen-req llave9 nopass
    ./easyrsa --batch --days=7300 sign-req client llave9
    ./easyrsa --batch --req-cn=llave5 gen-req llave0 nopass
    ./easyrsa --batch --days=7300 sign-req client llave0
    #echo "############ creación de .ovpn ######################"
    cd pki
    wget https://github.com/jmarcorb/vpnp/raw/master/defaults.txt
    /root/manage-vpnp.py -m llave1
    /root/manage-vpnp.py -m llave2
    /root/manage-vpnp.py -m llave3
    /root/manage-vpnp.py -m llave4
    /root/manage-vpnp.py -m llave5
    /root/manage-vpnp.py -m llave6
    /root/manage-vpnp.py -m llave7
    /root/manage-vpnp.py -m llave8
    /root/manage-vpnp.py -m llave9
    /root/manage-vpnp.py -m llave0
    mv *.ovpn /mnt/usb/
else
  echo "Crap! Mount Failed :( "
fi

exit
