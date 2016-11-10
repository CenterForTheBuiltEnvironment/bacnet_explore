# -*- coding: utf-8 -*-
"""
Created on Wed Nov  9 14:48:08 2016

@author: erdongwei
"""
import BACpypes_applications as BACpypesAPP
import json

def main():

    fout = open("deviceList", 'wb')    
    
    BACpypesAPP.Init()
    
    args = "192.168.1.112"
    timer = 5
    devices = BACpypesAPP.whois(args, timer)
    device_list = []
    for devs in devices:
        args = [str(devs.pduSource), devs.iAmDeviceIdentifier[0], devs.iAmDeviceIdentifier[1], 'objectName']
        name = BACpypesAPP.read_prop(args)
        args = [str(devs.pduSource), devs.iAmDeviceIdentifier[0], devs.iAmDeviceIdentifier[1], 'description']
        desc = BACpypesAPP.read_prop(args)
        print desc
        device = {
        'address': str(devs.pduSource),
        'type': devs.iAmDeviceIdentifier[0],
        'inst': devs.iAmDeviceIdentifier[1],
        'name': name,
        'desc': desc,
        'objs': []
        }
        args = [str(devs.pduSource), devs.iAmDeviceIdentifier[0], devs.iAmDeviceIdentifier[1], 'objectList']
        objs = BACpypesAPP.read_prop(args)
        for obj in objs:
            args = [str(devs.pduSource), obj[0], obj[1], 'units']
            unit = BACpypesAPP.read_prop(args)
            args = [str(devs.pduSource), obj[0], obj[1], 'description']
            desc = BACpypesAPP.read_prop(args)
            args = [str(devs.pduSource), obj[0], obj[1], 'objectName']
            name = BACpypesAPP.read_prop(args)
            device['objs'].append({
              'type': obj[0],
              'inst': obj[1],
              'name': name,
              'desc': desc,
              'unit': unit
              })
              
    device_list.append(device)
    print device_list  
    json.dump(device_list, fout)
    fout.close() 

    
if __name__ == "__main__":
    main()