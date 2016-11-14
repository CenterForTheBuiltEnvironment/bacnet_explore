# -*- coding: utf-8 -*-
"""
Created on Thu Nov 10 15:22:11 2016

@author: erdongwei
"""

import BACpypes_applications as BACpypesAPP
from bacpypes.object import get_datatype

def main():   
    
    BACpypesAPP.Init()
    
    args = "192.168.1.112"
    timer = 5
    devices = BACpypesAPP.whois(args, timer)
    device_list = []
    
    for devs in devices:
        args = [str(devs.pduSource), devs.iAmDeviceIdentifier[0], devs.iAmDeviceIdentifier[1], \
        'objectName', 'description', 'objectList']
        deviceinfo = BACpypesAPP.read_multi(args)
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
        objects = BACpypesAPP.read_multi(args)
        
        ### 
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
              
    device_list.append(device)
    print device_list  
    
if __name__ == "__main__":
    main()