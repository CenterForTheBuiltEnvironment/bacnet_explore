# -*- coding: utf-8 -*-
"""
Created on Mon Nov  7 12:31:36 2016

@author: erdongwei
"""

import sys


from bacpypes.debugging import ModuleLogger
from bacpypes.consolelogging import ConfigArgumentParser

from bacpypes.core import run, stop

from bacpypes.pdu import Address, GlobalBroadcast
from bacpypes.app import LocalDeviceObject, BIPSimpleApplication

from bacpypes.apdu import Error, AbortPDU, SimpleAckPDU, WhoIsRequest, IAmRequest, \
    ReadPropertyRequest, ReadPropertyACK, WritePropertyRequest 
from bacpypes.object import get_object_class, get_datatype
from bacpypes.basetypes import ServicesSupported
from bacpypes.errors import DecodingError
from bacpypes.constructeddata import Array, Any
from bacpypes.primitivedata import Null, Atomic, Integer, Unsigned, Real

# some debugging
_debug = 1
_log = ModuleLogger(globals())

#
#   WhoIsApplication
#
global apdu_g

class Applications(BIPSimpleApplication):

    def __init__(self, *args):
        if _debug: Applications._debug("__init__ %r", args)
        BIPSimpleApplication.__init__(self, *args)

        # keep track of requests to line up responses
        self._request = None

    def request(self, apdu):
        if _debug: Applications._debug("request %r", apdu)

        # save a copy of the request
        self._request = apdu

        # forward it along
        BIPSimpleApplication.request(self, apdu)

    def indication(self, apdu):
        if _debug: Applications._debug("indication %r", apdu)

        if (isinstance(self._request, WhoIsRequest)) and (isinstance(apdu, IAmRequest)):
            device_type, device_instance = apdu.iAmDeviceIdentifier
            if device_type != 'device':
                raise DecodingError("invalid object type")

            if (self._request.deviceInstanceRangeLowLimit is not None) and \
                (device_instance < self._request.deviceInstanceRangeLowLimit):
                pass
            elif (self._request.deviceInstanceRangeHighLimit is not None) and \
                (device_instance > self._request.deviceInstanceRangeHighLimit):
                pass
            else:
                # print out the contents
                sys.stdout.write('pduSource = ' + repr(apdu.pduSource) + '\n')
                sys.stdout.write('iAmDeviceIdentifier = ' + str(apdu.iAmDeviceIdentifier) + '\n')
                sys.stdout.write('maxAPDULengthAccepted = ' + str(apdu.maxAPDULengthAccepted) + '\n')
                sys.stdout.write('segmentationSupported = ' + str(apdu.segmentationSupported) + '\n')
                sys.stdout.write('vendorID = ' + str(apdu.vendorID) + '\n')
                sys.stdout.flush()

        # forward it along
        BIPSimpleApplication.indication(self, apdu)
        stop()
        
    def confirmation(self, apdu):
        if _debug: Applications._debug("confirmation %r", apdu)

        if isinstance(apdu, Error):
            sys.stdout.write("error: %s\n" % (apdu.errorCode,))
            sys.stdout.flush()

        elif isinstance(apdu, AbortPDU):
            apdu.debug_contents()

        if isinstance(apdu, SimpleAckPDU):
            sys.stdout.write("ack\n")
            sys.stdout.flush()

        elif (isinstance(self._request, ReadPropertyRequest)) and (isinstance(apdu, ReadPropertyACK)):
            # find the datatype
            datatype = get_datatype(apdu.objectIdentifier[0], apdu.propertyIdentifier)
            if _debug: Applications._debug("    - datatype: %r", datatype)
            if not datatype:
                raise TypeError("unknown datatype")

            # special case for array parts, others are managed by cast_out
            if issubclass(datatype, Array) and (apdu.propertyArrayIndex is not None):
                if apdu.propertyArrayIndex == 0:
                    value = apdu.propertyValue.cast_out(Unsigned)
                else:
                    value = apdu.propertyValue.cast_out(datatype.subtype)
            else:
                value = apdu.propertyValue.cast_out(datatype)
            if _debug: Applications._debug("    - value: %r", value)

            sys.stdout.write(str(value) + '\n')
            sys.stdout.flush()
        stop()

def Init():
    args = ConfigArgumentParser(description=__doc__).parse_args()
    if _debug: _log.debug("initialization")
    if _debug: _log.debug("    - args: %r", args)
    
    ### create a local device
    this_device = LocalDeviceObject(
        objectName=args.ini.objectname,
        objectIdentifier=int(args.ini.objectidentifier),
        maxApduLengthAccepted=int(args.ini.maxapdulengthaccepted),
        segmentationSupported=args.ini.segmentationsupported,
        vendorIdentifier=int(args.ini.vendoridentifier),
        )
        
    pss = ServicesSupported()
    pss['whoIs'] = 1
    pss['iAm'] = 1
    pss['readProperty'] = 1
    pss['writeProperty'] = 1
    pss['readPropertyMultiple'] = 1
    pss['writePropertyMultiple'] = 1
    this_device.protocolServicesSupported = pss.value
    
    return this_device, args.ini.address
        

def Request_whois(args):
    args = args.split()

    try:
        # build a request
        request = WhoIsRequest()
        if (len(args) == 1) or (len(args) == 3):
            request.pduDestination = Address(args[0])
            del args[0]
        else:
            request.pduDestination = GlobalBroadcast()

        if len(args) == 2:
            request.deviceInstanceRangeLowLimit = int(args[0])
            request.deviceInstanceRangeHighLimit = int(args[1])

        # return the request
        return request

    except Exception as error:
        print("exception: %r", error)
        
def Request_read(args):
    args = args.split()
    if _debug: print("do_read %r", args)

    try:
        addr, obj_type, obj_inst, prop_id = args[:4]

        if obj_type.isdigit():
            obj_type = int(obj_type)
        elif not get_object_class(obj_type):
            raise ValueError("unknown object type")

        obj_inst = int(obj_inst)

        datatype = get_datatype(obj_type, prop_id)
        if not datatype:
            raise ValueError("invalid property for object type")

        # build a request
        request = ReadPropertyRequest(
            objectIdentifier=(obj_type, obj_inst),
            propertyIdentifier=prop_id,
            )
        request.pduDestination = Address(addr)

        if len(args) == 5:
            request.propertyArrayIndex = int(args[4])
        if _debug: print("    - request: %r", request)
        
        ### return the request
        return request
        
    except Exception as error:
            print("exception: %r", error)        
                
def main():
    args = "192.168.1.112 device 7012 objectList"
    request = Request_read(args)
    
    ### Initiralize the device    
    this_device, address = Init()
    
    ### create applications
    this_app = Applications(this_device, address)
    
    ### do the service request
    this_app.request(request)
    run()
    
if __name__ == "__main__":
    main()


