#!/bin/sh

MOUNTDIR=/mnt/usb
DEVICE=$(ls /dev/sd?1)
if [ $DEVICE ]; then
    mount "$DEVICE" "$MOUNTDIR"
    if [ $? -eq 0 ]; then
       echo "¡Yuhuu! ¡USB montado!"
       if [ test -f /mnt/usb/renueva-certificados.txt ]; then
            #revocar viejos y crear nuevos 
            cd /etc/openvpn/easy-rsa
            ./easyrsa --batch revoke llave1
            ./easyrsa --batch revoke llave2
            ./easyrsa --batch revoke llave3
            ./easyrsa --batch revoke llave4
            ./easyrsa --batch revoke llave5
            echo "Antiguos certificados revocados (1-5)"
            #crear nuevos
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

            #echo "############ creación de .ovpn ######################"
            cd pki
            /root/manage-vpnp.py -m llave1
            /root/manage-vpnp.py -m llave2
            /root/manage-vpnp.py -m llave3
            /root/manage-vpnp.py -m llave4
            /root/manage-vpnp.py -m llave5
            echo "Certificados recreados (1-5). Reiniciando openvpn"
            service openvpn-server@server restart
            cd /mnt/
       fi
    fi
    #copiar viejos al usb
    cd /etc/openvpn/easy-rsa/pki
    cp *.ovpn /mnt/usb/
    sync
    echo "Certificados copiados al USB"
else
  echo "Crap! Mount Failed :( "
fi

exit
