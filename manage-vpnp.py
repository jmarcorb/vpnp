#!/usr/bin/python
#
# Build a Smart Raspberry Pi VPN Server + Tor Router
#
# Python App to:
# * Check IP Addresses of Raspberry PI, Router, and External Addr.
# * Update appropriate configuration files
# * Email owner if required
# * Reboot Server when necessary
# * Log all activity in manage-vpnp.log
#
# Author: Ira Finch
# Date: July 14, 2019
# Version 1.3
#
# Change Log:
# 1.3.0: Multiple changes for Raspbian Buster compatibility
# 1.2.5: Added Help Text via -h option
# 1.2.3: Better handling of errors on Retrieving External IP Address
# 1.2.2: Added MiniDelay Global to adjust discoverydelay for slow routers
# 1.2.1: Typo fix in line below from Sketch to Stretch :)
# 1.2.0: Added functionality to support Stretch release of Raspbian OS
# 1.1.0: Added '-f' parameter to Force UPnP Remapping and Reboot
# 1.0.3: Not always rebooting when Raspberry PI IP address changed
# 1.0.2: Better pattern matching on IP address updating
# 1.0.1: Complete rewrite of original Bash Script
#
# NOTE: See 'USER VARIABLES' section to customize to your installation
#       as instructed by my Amazon ebook:
#       Build a Smart Raspberry Pi VPN Server + Tor Router
#

import socket
import fcntl
import struct
import re
import os
import sys
import time
import smtplib
import miniupnpc
import netifaces
import requests
import random
from urllib2 import urlopen
from email.Utils import formatdate
from subprocess import Popen, PIPE, STDOUT

### USER VARIABLES - Review and Change as Necessary
#ExtVPNPort = 0
ExtSSHPort = 8022
ExtSSLPort = 443
# Adapter = 'eth0' # Do Not Alter - Now set automatically
UseMiniUPnP = True
UsePortMapper = False
ServerName = 'SERVERNAME'

#######################################
### GLOBAL VARIABLES - DO NOT ALTER !!!
Adapter=False
RaspPiIP = ''
RouterIP = ''
ExternalIP = ''
OldRaspPiIP = ''
OldRouterIP = ''
OldExternalIP = ''
DefRaspPiIP = '111.111.111.111'
DefRouterIP = '222.222.222.222'
DefExternalIP = '000.000.000.000'
EMailMsg = ''
FoundRouterMini = False
FoundRouterPM = False
SSHPortMapped = False
VPNPortMapped = False
SSLPortMapped = False
ForceRemap = False
Reboot = False
MiniDelay = 500
Service = {22: 'SSH', 1194: 'OpenVPN', 443: 'SSL' }
PMLibraries = [ 'org.chris.portmapper.router.sbbi.SBBIRouterFactory' ,
                'org.chris.portmapper.router.weupnp.WeUPnPRouterFactory' ]
PMLibIndex = -1
PMIndes = -1
IPv4Sites = [ 'https://api.ipify.org',
              'https://ident.me',
              'http://checkip.dyndns.org',
              'https://www.google.com/search?q=what+is+my+public+ip+address',
              'http://ipv4.icanhazip.com/' ,
              'http://bitman.org/irafinch/rpivpn/ipv4.php' ]
LogFile = "/root/manage-vpnp.log"
IPFile = "/root/manage-vpnp.txt"
PortMapper = '/root/PortMapper.jar'
ServerConf = '/etc/openvpn/server/server.conf'
OpenVPNFirewall = '/root/manage-fw.sh'
StunnelConf = '/etc/stunnel/stunnel.conf'
PKIPath = '/etc/openvpn/easy-rsa/pki/'
DefaultsTxt = PKIPath+'defaults.txt'
KeyPath = PKIPath+'private/'
CrtPath = PKIPath+'issued/'

#############################################################################
### getmac(interface) - Funcion para conseguir la MAC de la conexion eth0
def getmac(interface):

    try:
        mac = open('/sys/class/net/' + interface + '/address').readline()
    except:
        mac = "00:00:00:00:00:00"

    return mac[0:17]

##############################################################################
### reboot - Reboot the Pi NOW - silly function, but too many places to reboot
def reboot():

    os.system('/usr/bin/sudo shutdown -r now')

####################################################################################
### logMessage - Write msg to logFile and optionally append to eMailMsg for emailing
def logMessage(msg,email):

    global EMailMsg

    with open(LogFile,"a") as fhandle:
        if msg == " " or msg[:5] == "#####":
            fhandle.write(msg + "\n")
        else:
            fhandle.write(time.strftime("%Y-%m-%d %H:%M:%S") + "| " + msg + "\n")

    if email: EMailMsg += msg + "\n"
    return msg

#################################################################
### Actualizar ip en servidor central.
def actualizaIPenNube():

    from time import sleep
    sleep(random.randint(1, 120)) #PRUEBAS
    #sleep(random.randint(1, 3300)) #PRODUCCION
    URL = 'https://vpnp.es/update.php'
    ns = ServerName
    #ns = ServerName
    #ma = "00:00:00:00:00:00"
    ma = getmac("eth0")
    PARAMS = {'ns':ns, 'ma':ma}
    r = requests.get(url = URL, params = PARAMS)


##################################################################
### findIPs - Find Raspberry Pi, Router, and External IP Addresses
def findIPs():

    raspPiIP = ''
    routerIP = ''
    externalIP = ''
    global Adapter

    # Get the active Network Adapter Name
    if not Adapter:
        Adapter = netifaces.gateways()['default'][netifaces.AF_INET][1]

    netifaces.ifaddresses(Adapter)
    raspPiIP  = netifaces.ifaddresses(Adapter)[netifaces.AF_INET][0]['addr']

    # Check the Raspberry Pi IP Address. If none: report error and exit
    if not re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$",raspPiIP):
        logMessage("ERROR: No Raspberry IP Address found - Rebooting",False)
        reboot()
        exit()

    ## Get Router IP Address
    with open("/proc/net/route") as fhandle:
        for line in fhandle:
            fields = line.strip().split()
            if fields[1] != '00000000' or not int(fields[3], 16) & 2:
                continue
            routerIP = socket.inet_ntoa(struct.pack("<L", int(fields[2], 16)))
    routerIP = routerIP.strip()

    # Check the Router IP address. If none: report error, try to send email, and exit
    if not re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$",routerIP):
        logMessage("ERROR: No Router IP Address found - Rebooting",True)
        reboot()
        exit()

    ## Get External IP Address
    if UseMiniUPnP:
        try:
            upnpc = miniupnpc.UPnP()
            upnpc.discoverdelay = 200
            upnpc.discover()
            upnpc.selectigd()
            externalIP = upnpc.externalipaddress()
        except:
            logMessage("WARNING: MiniUPnP uable to determine External IP Address. Trying external sites",False)
            externalIP = ""

    if externalIP == '':
        for IPIndex, IPUrl in enumerate(IPv4Sites):
            try:
                externalIP = urlopen(IPUrl).read()
                if re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$",externalIP):
                    break
            except:
                logMessage("WARNING: "+IPUrl+" is not responding",False)
                externalIP = ""
        externalIP = externalIP.strip()

    # Check the External IP address. If none: report error, try to send mail, and exit
    if not re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$",externalIP):
        logMessage("ERROR: No External IP Address found - aborting",True)
        exit()

    logMessage("New RPi IP ["+raspPiIP+"] | New Router IP ["+routerIP+"] | New External IP ["+externalIP+"]",False)

    return raspPiIP, routerIP, externalIP

##################################################################
### getOldIPs - Read the Original IP address from manage-vpnp.txt
def getOldIPs():

    try:
        fhandle = open(IPFile, 'r')
        fhandle.close()
    except IOError:
        fhandle = open(IPFile, 'w')
        fhandle.close()

    with open(IPFile,"r") as fhandle :
        oldRaspPiIP = fhandle.readline().strip() or DefRaspPiIP
        oldRouterIP = fhandle.readline().strip() or DefRouterIP
        oldExternalIP = fhandle.readline().strip() or DefExternalIP

    logMessage("Old RPi IP ["+oldRaspPiIP+"] | Old Router IP ["+oldRouterIP+"] | Old External IP ["+oldExternalIP+"]",False)

    return oldRaspPiIP, oldRouterIP, oldExternalIP


###########################################################################
### updateIPFile - Update the manage-vpnp.txt file if any IP addresses changed
def updateIPFile():

    if OldRaspPiIP != RaspPiIP or \
       OldExternalIP != ExternalIP or \
       OldRouterIP != RouterIP:
        with open(IPFile, 'w') as fhandle:
            fhandle.write(RaspPiIP+"\n")
            fhandle.write(RouterIP+"\n")
            fhandle.write(ExternalIP+"\n")

#####################################################################
### mapPorts - Map UPnP Port, if enabled, and Force Remapping if True
def mapPorts(force):

    global FoundRouterMini,FoundRouterPM,PMIndex,PMLibIndex
    global SSHPortMapped,VPNPortMapped,SSLPortMapped

    if force: logMessage("Forcing Remapping of UPnP Ports (if enabled)",False)
    ### Look for UPnP Router using MiniUPnP, if enabled
    if UseMiniUPnP:
        # Find the Router
        FoundRouterMini = findRouterMini()
        if FoundRouterMini:
            # Map the ports, if enabled
            if ExtSSHPort != 0: SSHPortMapped = mapPortMini(ExtSSHPort,22,'TCP',force)
            #if ExtVPNPort != 0: VPNPortMapped = mapPortMini(ExtVPNPort,1194,'UDP',force)
            if ExtSSLPort != 0: SSLPortMapped = mapPortMini(ExtSSLPort,443,'TCP',force)

    ### Look for UPnP Router using PortMapper, if enabled and if FoundRouterMini is False
    if UsePortMapper and not FoundRouterMini:
        # Find the Router
        FoundRouterPM, PMIndex, PMLibIndex = findRouterPM()
        if FoundRouterPM:
            # Map the ports, if enabled and NOT already mapped
            if ExtSSHPort != 0 and not SSHPortMapped: SSHPortMapped = mapPortPM(ExtSSHPort,22,'TCP',force)
            #if ExtVPNPort != 0 and not VPNPortMapped: VPNPortMapped = mapPortPM(ExtVPNPort,1194,'UDP',force)
            if ExtSSLPort != 0 and not SSLPortMapped: SSLPortMapped = mapPortPM(ExtSSLPort,443,'TCP',force)

    # Verify UPnP Router and Ports Mapped, where applicable
    verifyUPnP()


###################################################################
### findRouterMini - Find the UPnP Compatible Router using MiniUPnP
def findRouterMini():

    upnpc = miniupnpc.UPnP()
    upnpc.discoverdelay = MiniDelay
    try:
        num = upnpc.discover()
        upnpc.selectigd()
    except Exception, err:
        logMessage("MiniUPnPc Error: "+unicode(err),False)
        return False

    logMessage("MiniUPnPc Found Router: "+unicode(upnpc.statusinfo())+" / "+unicode(upnpc.connectiontype()),False)

    return True

##################################################################
### mapPortMini - Map Router Port using MiniUPnPc
def mapPortMini(extPort,intPort,proto,force=False):

    result = True
    msg = "MiniUPnPc: Checking "+Service[intPort]+" Mappings: "+unicode(extPort)+" -> "+unicode(intPort)+" ("+proto+") - "

    upnpc = miniupnpc.UPnP()
    upnpc.discoverdelay = MiniDelay
    num = upnpc.discover()
    upnpc.selectigd()
    portmap = upnpc.getspecificportmapping(extPort, proto)
    if portmap and (not re.search(re.escape(RaspPiIP),unicode(portmap)) or force) :
        msg += "Removing Old Mapping..."
        try:
            upnpc.deleteportmapping(extPort, proto)
            portmap = None
        except Exception, err:
            msg += "ERROR: "+unicode(err)
            result = False
    # If not mapped to the Raspberry PI IP, then remap
    if portmap is None: # or not mapped to PI
        msg += "Loading..."
        # Try to add new mapping
        try:
            result = upnpc.addportmapping(extPort, proto, RaspPiIP, intPort, 'manage-vpnp.py', '')
            msg += "Sucessfully loaded"
            result = True
        except Exception, err:
            msg += "ERROR: "+unicode(err)
            result = False
    else:
        msg += "Found!"

    logMessage(msg,not result)

    return result

###################################################################
### findRouterPM - Find the UPnP Compatible Router using PortMapper
def findRouterPM():

    msg = ''
    for libIndex, lib in enumerate(PMLibraries):
        for index in range(0,9):
            result = Popen(['/usr/bin/java', '-jar', PortMapper, '-s', '-i',unicode(index), '-u',lib], stdout=PIPE, stderr=STDOUT).communicate()[0]
            if re.search('INFO.*def loc http://'+re.escape(RouterIP),result,re.I):
                FoundRouterPM = True
                msg  = "PortMapper Found Router:\n"
                msg += "\t\t           ID = "+unicode(index)+"\n"
                msg += "\t\t         Name ="+re.search('INFO.*friendlyName.*=(.*)',result,re.I).group(1)+"\n"
                msg += "\t\t         Make ="+re.search('INFO.*manufacturer.*=(.*)',result,re.I).group(1)+"\n"
                msg += "\t\t        Model ="+re.search('INFO.*modelName.*=(.*)',result,re.I).group(1)+"\n"
                msg += "\t\t         Desc ="+re.search('INFO.*modelDescription.*=(.*)',result,re.I).group(1)+"\n"
                msg += "\t\t       Number ="+re.search('INFO.*modelNumber.*=(.*)',result,re.I).group(1)+"\n"
                msg += "\t\t       Serial ="+re.search('INFO.*serialNumber.*=(.*)',result,re.I).group(1)+"\n"
                msg += "\t\t     Firmware ="+re.search('INFO.*vendorFirmware.*=(.*)',result,re.I).group(1)+"\n"
                logMessage(msg,False)
                return True, index, libIndex

    logMessage("PortMapper Error: Could not match Router IP to PortMapper Index",False)
    return False, -1, -1

###################################################################
### mapPortPM - Map Router Port using PortMapper
def mapPortPM(extPort,intPort,proto,force=False):

    ret = True
    msg = "PortMapper: Checking "+Service[intPort]+" Mappings: "+unicode(extPort)+" -> "+unicode(intPort)+" ("+proto+") - "
    result = Popen(['/usr/bin/java', '-jar', PortMapper, '-i', unicode(PMIndex), '-u', PMLibraries[PMLibIndex], '-l'], \
                   stdout=PIPE, stderr=STDOUT).communicate()[0]
    if not re.search(proto+' :'+unicode(extPort)+' .*'+re.escape(RaspPiIP),result,re.I) or force :
        msg += "Not Found, Loading..."
        # Delete old mapping, if exists
        result = Popen(['/usr/bin/java', '-jar', PortMapper, '-i', unicode(PMIndex), '-u', PMLibraries[PMLibIndex], '-d', unicode(extPort), proto], \
                       stdout=PIPE, stderr=STDOUT).communicate()[0]
        # Try to add new mapping
        result = Popen(['/usr/bin/java', '-jar', PortMapper, '-i', unicode(PMIndex), '-u', PMLibraries[PMLibIndex], '-a', unicode(RaspPiIP), unicode(intPort), unicode(extPort), proto], \
                       stdout=PIPE, stderr=STDOUT).communicate()[0]
        if re.search(proto+' :'+unicode(extPort)+' .*'+re.escape(RaspPiIP)+':'+unicode(intPort),result,re.I):
            msg += "Sucessfully loaded"
            ret = True
        else:
            msg += "ERROR: Could not load!!!"
            ret = False
    else:
        msg += "Found!"
        ret = True

    logMessage(msg,not ret)

    return ret


##########################################################################
### verifyUPnP - Verify UPnP Router and Ports Mapped, where applicable
def verifyUPnP():

    global EMailMsg

    msg = ''
    if UseMiniUPnP or UsePortMapper:
        if not FoundRouterMini and not FoundRouterPM:
            msg += "ERROR: Could Not Find UPnP Router!\n"
        else:
            if ExtSSHPort != 0 and not SSHPortMapped:
                msg += "ERROR: Could Not Map SSH Port!\n"
            #if ExtVPNPort != 0 and not VPNPortMapped:
                #msg += "ERROR: Could Not Map OpenVPN Port!\n"
            if ExtSSLPort != 0 and not SSLPortMapped:
                msg += "ERROR: Could Not Map SSL Port!\n"

    EMailMsg += msg

##########################################################################
### updateFile - Replace the 'Old' or 'Org' with the 'New' in Filename
def updateFile(fileName, old, new, org):

    try:
        with open(fileName, 'r+') as fhandle:
            content = fhandle.read()
            fhandle.seek(0)
            fhandle.truncate()
            content = content.replace(org, new)
            fhandle.write(content.replace(old, new))
            logMessage("  Updated "+fileName,False)
    except IOError:
        logMessage("  Unable to update "+fileName+" !!!",True)

##########################################################################
### updatePIConfig - Update Config files using the Raspberry PI IP Address
def updatePIConfig():

    global Reboot

    msg = "Checking if RPi IP Changed to update config files: "
    if OldRaspPiIP != RaspPiIP:
        Reboot = True
        msg += "Yes ["+RaspPiIP+"]"
        logMessage(msg,False)
        # Upgate server.config file
        #updateFile(ServerConf,OldRaspPiIP,RaspPiIP,DefRaspPiIP)
        # update manage-fw.sh
        updateFile(OpenVPNFirewall,OldRaspPiIP,RaspPiIP,DefRaspPiIP)
        # update stunnel.conf - if exists
        #if os.path.isfile(StunnelConf):
            #updateFile(StunnelConf,OldRaspPiIP,RaspPiIP,DefRaspPiIP)
    else:
        msg += "No"
        logMessage(msg,False)

#####################################################################
### updateRtrConfig - Update Config files using the Router IP Address
def updateRtrConfig():

    global Reboot

    msg = "Checking if Router IP Changed to update config files: "
    if OldRouterIP != RouterIP:
        Reboot = True
        msg += "Yes ["+RouterIP+"]"
        logMessage(msg,False)
        # Update server.config file
        #updateFile(ServerConf,OldRouterIP,RouterIP,DefRouterIP)
    else:
        msg += "No"
        logMessage(msg,False)

#######################################################################
### updateExtConfig - Update Config files using the External IP Address
def updateExtConfig():

    msg = "Checking if External IP Changed to update config files: "
    if OldExternalIP != ExternalIP:
        msg += "Yes ["+ExternalIP+"]"
        logMessage(msg,False)
        # Upgate Defaults.txt file
        #if os.path.isfile(DefaultsTxt):
            #updateFile(DefaultsTxt,OldExternalIP,ExternalIP,DefExternalIP)
        URL = 'https://vpnp.es/getip.php'
        ns = ServerName
        PARAMS = {'ns':ns}
        r = requests.get(url = URL, params = PARAMS)
        if r != ExternalIP:
            msg += "Actualizo IP del servidor casero en vpnp.es. Antigua: "+ r.text +" Nueva: "+ExternalIP
            actualizaIPenNube()
            logMessage(msg,False)
        else:
            msg += "No actualizo en vpnp.es"
            logMessage(msg,False)

#######################################################################
### makeOVPNclient - Create the OpenVPN Client File with the given Name
def makeOVPNclient(fileName):

    if not fileName:
        print logMessage("No OpenVPN Client Filename specified. Aborting",False)
        exit()
    if not os.path.isfile(DefaultsTxt):
        print logMessage(DefaultsTxt+" file missing. Aborting",False)
        exit()
    if not os.path.isfile(CrtPath+fileName+'.crt'):
        print logMessage(CrtPath+fileName+".crt file missing. Aborting",False)
        exit()
    if not os.path.isfile(KeyPath+fileName+'.key'):
        print logMessage(KeyPath+fileName+".key file missing. Aborting",False)
        exit()
    if not os.path.isfile(PKIPath+'ca.crt'):
        print logMessage(PKIPath+"ca.crt file missing. Aborting",False)
        exit()
    if not os.path.isfile(PKIPath+'ta.key'):
        print logMessage(PKIPath+"ta.key file missing. Aborting",False)
        exit()
    # We have all the necessary files. Now make the client .ovpn file
    try:
        with open(PKIPath+fileName+'.ovpn','w') as fhandle:
            # First is the defaults.txt file
            with open(DefaultsTxt) as ifile:
                fhandle.write(ifile.read())
            # Ponemos el nombre del servidor en el fichero ovpn para que lo encuentre el SSLdroid
            fhandle.write('##VPNPSERVER##-'+ServerName)
            # Next is ca.crt
            fhandle.write('\n<ca>\n')
            with open(PKIPath+'ca.crt') as ifile:
                fhandle.write(ifile.read())
            fhandle.write('</ca>\n')
            # Next is fileName.crt
            fhandle.write('<cert>\n')
            with open(CrtPath+fileName+'.crt') as ifile:
                fhandle.write(re.search('(-----BEGIN CERTIFICATE-----.*-----END CERTIFICATE-----)',ifile.read(),re.M | re.DOTALL ).group(1))
            fhandle.write('\n</cert>\n')
            # Next is the fileName.key
            fhandle.write('<key>\n')
            with open(KeyPath+fileName+'.key') as ifile:
                fhandle.write(ifile.read())
            fhandle.write('</key>\n')
            # Next is the ta.key
            fhandle.write('<tls-auth>\n')
            with open(PKIPath+'ta.key') as ifile:
                fhandle.write(ifile.read())
            fhandle.write('</tls-auth>\n')
            # And we are Done!
            print logMessage(PKIPath+fileName+".ovpn file Successfully Created.",False)
    except Exception, err:
        print logMessage("Error Creating "+PkiPath+fileName+".ovpn: "+unicode(err),False)

###################################################################
### parseArgs - Get any Arguments from the command line and act
def parseArgs():

    global EMailMsg,ForceRemap

    if len(sys.argv) > 1:
        if sys.argv[1] == '-e':
            logMessage("Forzando actualización",False)
            updateExtConfig()
        elif sys.argv[1] == '-r':
            logMessage("Rebooting System NOW!",False)
            reboot()
        elif sys.argv[1] == '-f':
            logMessage("Forcing UPnP Port Remapping and System Reboot",False)
            ForceRemap = True
            return
        elif sys.argv[1] == '-v':
            logMessage("Restarting OpenVPN Service",False)
            os.system('/usr/bin/sudo service openvpn restart')
        elif sys.argv[1] == '-s':
            logMessage("Restarting SSL Service",False)
            os.system('/usr/bin/sudo /etc/init.d/stunnel4 restart')
        elif sys.argv[1] == '-t':
            logMessage("Restarting Tor Service",False)
            os.system('/usr/bin/sudo service tor restart')
        elif sys.argv[1] == '-c':
            logMessage("Cleaning FileSystem",False)
            os.system('/usr/bin/sudo apt-get clean')
        elif sys.argv[1] == '-m':
            logMessage("Making .ovpn Client file",False)
            makeOVPNclient(sys.argv[2])
        elif sys.argv[1] == '-h':
            print "manage-vpnp.py: Raspbery Pi OpenVPN Server Script: (c) 2014-2018 Ira Finch"
            print "Go to http://bitman.org/irafinch/rpivpn/ for more information"
            print "Usage: ./manage-vpnp.py [option]"
            print "  -c\tclean filesystem"
            print "  -e\tsend test email message"
            print "  -f\tforce UPnP port remapping and system reboot"
            print "  -m\tmake .ovpn client files"
            print "  -r\treboot system immediately"
            print "  -s\trestart SSL service"
            print "  -t\trestart Tor service"
            print "  -v\trestart OpenVPN service"
            print "  -h\tdisplay this help text"
            print " "
        else:
            print logMessage("Unknown Argument: "+sys.argv[1]+": use './manage-vpnp.py -h' for help",False)
        # Always just EXIT if we have ANY Args - valid or not
        exit()


###################################################################
### finishUp - We are Done! End the Logging and Reboot if necessary
def finishUp():

    logMessage("SUCCESS: manage-vpnp.py completed successfully",False)
    if Reboot or ForceRemap:
        logMessage("Rebooting",False)
        reboot()


#####################################################################
### MAIN ROUTINE
#####################################################################

logMessage(" ",False)
logMessage("###########################################################",False)
logMessage("START",False)


# Check for Arguments and act on them accordingly
parseArgs()

# Get the previously retrieved IP Addresses
OldRaspPiIP, OldRouterIP, OldExternalIP = getOldIPs()

# Get the Current IP Addresses
RaspPiIP, RouterIP, ExternalIP = findIPs()

# Map & Verify UPnP Ports - if applicable
mapPorts(ForceRemap)

# Update Config files using the Raspberry Pi IP Address
updatePIConfig()

# Update Config files using the Router IP Address
updateRtrConfig()

# Update Config files using the External IP Address
updateExtConfig()

# Create & Send email if any changes or errors
#createEmailMsg()

# Update the manage-vpnp.txt file if any IP addresses changed
updateIPFile()

# We are Done! End the Logging and Reboot if necessary
finishUp()
