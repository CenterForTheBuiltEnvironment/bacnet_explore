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

### multi read with error handling
def read(args):
    s = 0
    results = None
    while((results is None) and s <= 5):
        try: 
            results = BACpypesAPP.read_multi(args)
        except Exception as error:
            print error
        sleep(5)
        s += 1
    return results

### get object list for every batch size
def getobjects(devs, sleepTime, objsCount, count):
    batchSize = 10 ### batch size for every multi read
    args = [str(devs.pduSource), devs.iAmDeviceIdentifier[0], devs.iAmDeviceIdentifier[1]]   
    batch = batchSize + count
    while(count <= objsCount):
        args.append('objectList')
        args.append(str(count))
        count += 1
        if count > batch:
            break
        
    objs = read(args)
    sleep(sleepTime)
    
    return objs, count


### read objects inforamtion in the object list
def readObjects(objs, args, sleepTime, device):  
    objcontent = []
    prop = ['units', 'objectName', 'description']
    newobj = []
    for obj in objs:
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
        newobj.append(obj)
    
    ### use multi read to get the information of all objects
    objects = read(args)
    sleep(sleepTime)
    
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

### read all the objects when the device support segmentation  
def readDevice_all(devs, sleepTime): 
    args = [str(devs.pduSource), devs.iAmDeviceIdentifier[0], devs.iAmDeviceIdentifier[1], \
            'objectName', 'description', 'objectList']

    deviceinfo = read(args)
    sleep(sleepTime)
    
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
    device = readObjects(objs, args, sleepTime, device)
    if device is None:
        print "cannot read this device now"
        return None
    return device

### read all the objects when the objects doesn't support segmentation
def readDevice_pieces(devs, sleepTime):
    args = [str(devs.pduSource), devs.iAmDeviceIdentifier[0], devs.iAmDeviceIdentifier[1], \
            'objectName', 'description', 'objectList', '0']
    deviceinfo = read(args)
    sleep(sleepTime)
    if deviceinfo is None:
        print "cannot read this device now"
        return None
    name, desc, objsCount = deviceinfo[0], deviceinfo[1], deviceinfo[2]

    device = {
    'address': str(devs.pduSource),
    'type': devs.iAmDeviceIdentifier[0],
    'inst': devs.iAmDeviceIdentifier[1],
    'name': name,
    'desc': desc,
    'objs': []
    }
    
    count = 1
    objs = []
    while(count <= objsCount):
        args = [str(devs.pduSource), devs.iAmDeviceIdentifier[0], devs.iAmDeviceIdentifier[1], 'objectList']   
        objs, count = getobjects(devs, sleepTime, objsCount, count)
        
        if objs is None:
            print "cannot read this device now"
            return None
            
        args = [str(devs.pduSource)]
        device = readObjects(objs, args, sleepTime, device)
        if device is None:
            print "cannot read this device now"
            return None
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
            if devs.segmentationSupported == 'segmentedBoth' or 'segmentedTransmit':
                device = readDevice_pieces(devs, sleepTime)
                if device is None:
                    print "Cannot get the information of ", devs
            else:
                device = readDevice_pieces(devs, sleepTime)
                if device is None:
                    print "Cannot get the information of ", devs
            device_list.append(device)
    else:    
        for arg in args:
            devices = BACpypesAPP.whois(arg)
            sleep(sleepTime)
            
            for devs in devices:
                if devs.segmentationSupported == 'segmentedBoth' or 'segmentedTransmit':
                    device = readDevice_pieces(devs, sleepTime)
                    if device is None:
                        print "Cannot get the information of ", devs
                else:
                    device = readDevice_pieces(devs, sleepTime)
                    if device is None:
                        print "Cannot get the information of ", devs
                device_list.append(device)
    print device_list
    json.dump(device_list, fout)
    fout.close()
    
if __name__ == "__main__":
    main()