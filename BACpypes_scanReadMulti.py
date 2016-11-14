# -*- coding: utf-8 -*-
"""
Created on Thu Nov 10 15:22:11 2016

@author: erdongwei
"""

import BACpypes_applications as BACpypesAPP
from bacpypes.object import get_datatype
import ConfigParser
from time import sleep
import json

def readDevice(devs, sleepTime):
    args = [str(devs.pduSource), devs.iAmDeviceIdentifier[0], devs.iAmDeviceIdentifier[1], \
            'objectName', 'description', 'objectList']
    count = 0
    deviceinfo = None
    while((deviceinfo is None) and count <= 5):
        try: 
            deviceinfo = BACpypesAPP.read_multi(args)
            sleep(sleepTime)
        except Exception as error:
            print error
            sleep(5)
            count += 1
    if deviceinfo is None:
        print "cannot read this device now"
        return None
    name, desc, objs = deviceinfo[0], deviceinfo[1], deviceinfo[2]

    device = {
    'address': str(devs.pduSource),
    'type': devs.iAmDeviceIdentifier[0],
    'inst': devs.iAmDeviceIdentifier[1],
    'name': name,
    'desc': desc,
    'objs': []
    }
    args = [str(devs.pduSource)]
    objcontent = []
    prop = ['units', 'objectName', 'description']
    count = 0
    newobj = []
    
    for obj in objs:
        if count >= 5:
            break
        ### pass notificationsClass because there is a property name is 'notificationsClass',
        ### it will cause errors
        if obj[0] == 'notificationClass':
            continue
        args.append(obj[0])
        args.append(obj[1])
        for j in range(len(prop)):
            datatype = get_datatype(obj[0], prop[j])
            if datatype:
                objcontent.append(1)
                args.append(prop[j])
            else:
                objcontent.append(0)
        count += 1
        newobj.append(obj)
    ### use multi read to get the information of all objects
    count = 0
    objects = None
    while((objects is None) and count <= 5):
        try: 
            objects = BACpypesAPP.read_multi(args)
            sleep(sleepTime)
        except Exception as error:
            print error
            sleep(5)
            count += 1
    if objects is None:
        print "cannot get the objects"
        return None
    ### add object information to device 
    n = 0
    for i in range(len(newobj)):
        curObject = []
        for k in range(3):
            if objcontent[3*i+k] == 1:
                curObject.append(objects[n])
                n += 1
            else:
                curObject.append(None)
        device['objs'].append({
          'type': objs[i][0],
          'inst': objs[i][1],
          'unit': curObject[0],
          'name': curObject[1],
          'desc': curObject[2]
          })
    return device


def main():   
    
    BACpypesAPP.Init()
    
    config = ConfigParser.ConfigParser()
    config.read('BACpypes_scan.ini')
    
    args = config.get('scan_information', 'IP_Address')
    args = args.split()
    sleepTime = config.get('scan_information', 'sleepTime')
    sleepTime = int(sleepTime)
    
    filename = config.get('scan_information', 'filename') 
    fout = open(filename, 'wb')
    
    device_list = []
    
    if len(args) == 0:
        devices = BACpypesAPP.whois(args)
        sleep(sleepTime)
        
        for devs in devices:
            device = readDevice(devs, sleepTime)
            device_list.append(device)
            if device is None:
                print "Cannot get the information of ", devs
    else:    
        for arg in args:
            devices = BACpypesAPP.whois(arg)
            sleep(sleepTime)
            
            for devs in devices:
                device = readDevice(devs, sleepTime)
                device_list.append(device)
                if device is None:
                    print "Cannot get the information of ", devs
    print device_list
    json.dump(device_list, fout)
    fout.close()
    
if __name__ == "__main__":
    main()