# -*- coding: utf-8 -*-
"""
Created on Mon Nov  7 12:31:36 2016

@author: erdongwei
"""

import sys
import time

from bacpypes.debugging import ModuleLogger
from bacpypes.consolelogging import ConfigArgumentParser

from bacpypes.core import run, stop

from bacpypes.pdu import Address, GlobalBroadcast
from bacpypes.apdu import ReadPropertyMultipleRequest, PropertyReference, \
    ReadAccessSpecification, ReadPropertyMultipleACK
from bacpypes.app import LocalDeviceObject, BIPSimpleApplication

from bacpypes.apdu import Error, AbortPDU, SimpleAckPDU, WhoIsRequest, IAmRequest, \
    ReadPropertyRequest, ReadPropertyACK
from bacpypes.object import get_object_class, get_datatype
from bacpypes.basetypes import ServicesSupported
from bacpypes.errors import DecodingError
from bacpypes.constructeddata import Array
from bacpypes.primitivedata import Unsigned
from bacpypes.basetypes import PropertyIdentifier

# some debugging
_debug = 0
_log = ModuleLogger(globals())

#
#   WhoIsApplication
#
global valueRead
global this_app
global deviceList

class Applications(BIPSimpleApplication):

    def __init__(self, *args):
        if _debug: Applications._debug("__init__ %r", args)
        BIPSimpleApplication.__init__(self, *args)

        # keep track of requests to line up responses
        self._request = None

    def request(self, apdu):
        global deviceList
        if _debug: Applications._debug("request %r", apdu)

        # save a copy of the request
        self._request = apdu
        self._initialTime = time.strftime("%s")
        
        if (isinstance(self._request, WhoIsRequest)):
            deviceList = []
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
                #sys.stdout.write('pduSource = ' + repr(apdu.pduSource) + '\n')
                '''sys.stdout.write('iAmDeviceIdentifier = ' + str(apdu.iAmDeviceIdentifier) + '\n')
                sys.stdout.write('maxAPDULengthAccepted = ' + str(apdu.maxAPDULengthAccepted) + '\n')
                sys.stdout.write('segmentationSupported = ' + str(apdu.segmentationSupported) + '\n')
                sys.stdout.write('vendorID = ' + str(apdu.vendorID) + '\n')
                sys.stdout.flush()'''
                deviceList.append(apdu)

        # forward it along
        BIPSimpleApplication.indication(self, apdu)
        stop()
        
    def confirmation(self, apdu):
        global valueRead
        valueRead = None
        if _debug: Applications._debug("confirmation %r", apdu)

        if isinstance(apdu, Error):
            sys.stdout.write("error: %s\n" % (apdu.errorCode,))
            sys.stdout.flush()

        elif isinstance(apdu, AbortPDU):
            apdu.debug_contents()

        elif isinstance(apdu, SimpleAckPDU):
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
            valueRead = value
        
        ### readPropertyMulti     
        elif (isinstance(self._request, ReadPropertyMultipleRequest)) and (isinstance(apdu, ReadPropertyMultipleACK)):
            valueRead = []            
            # loop through the results
            for result in apdu.listOfReadAccessResults:
                # here is the object identifier
                objectIdentifier = result.objectIdentifier
                if _debug: Applications._debug("    - objectIdentifier: %r", objectIdentifier)

                # now come the property values per object
                for element in result.listOfResults:
                    # get the property and array index
                    propertyIdentifier = element.propertyIdentifier
                    if _debug: Applications._debug("    - propertyIdentifier: %r", propertyIdentifier)
                    propertyArrayIndex = element.propertyArrayIndex
                    if _debug: Applications._debug("    - propertyArrayIndex: %r", propertyArrayIndex)

                    # here is the read result
                    readResult = element.readResult

                    #sys.stdout.write(propertyIdentifier)
                    if propertyArrayIndex is not None:
                        sys.stdout.write("[" + str(propertyArrayIndex) + "]")

                    # check for an error
                    if readResult.propertyAccessError is not None:
                        sys.stdout.write(" ! " + str(readResult.propertyAccessError) + '\n')
                        valueRead.append(None)

                    else:
                        # here is the value
                        propertyValue = readResult.propertyValue

                        # find the datatype
                        datatype = get_datatype(objectIdentifier[0], propertyIdentifier)
                        if _debug: Applications._debug("    - datatype: %r", datatype)
                        if not datatype:
                            raise TypeError("unknown datatype")

                        # special case for array parts, others are managed by cast_out
                        if issubclass(datatype, Array) and (propertyArrayIndex is not None):
                            if propertyArrayIndex == 0:
                                value = propertyValue.cast_out(Unsigned)
                            else:
                                value = propertyValue.cast_out(datatype.subtype)
                        else:
                            value = propertyValue.cast_out(datatype)
                        if _debug: Applications._debug("    - value: %r", value)

                        #sys.stdout.write(" = " + str(value) + '\n')                       
                        valueRead.append(value)
                    sys.stdout.flush()
        ### finished this reading
        stop()

def Init():
    global this_app
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
    
    this_app = Applications(this_device, args.ini.address)
        

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
        print("exception: ", error)
        
def Request_read(args):

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

def request_readMulti(args):
    if _debug: print ("read reqeust %r", args)

    try:
        i = 0
        addr = args[i]
        i += 1

        read_access_spec_list = []
        while i < len(args):
            obj_type = args[i]
            i += 1

            if obj_type.isdigit():
                obj_type = int(obj_type)
            elif not get_object_class(obj_type):
                raise ValueError("unknown object type")
            
            obj_inst = int(args[i])
            i += 1

            prop_reference_list = []
            while i < len(args):  
            ### bug here, if the name of next object is a kind of property, 
            ### then there will be a bug, for example the object notificationClass 
                prop_id = args[i]
                if prop_id not in PropertyIdentifier.enumerations:
                    break

                i += 1
                if prop_id in ('all', 'required', 'optional'):
                    pass
                else:
                    datatype = get_datatype(obj_type, prop_id)
                    if not datatype:
                        raise ValueError("invalid property for object type")

                # build a property reference
                prop_reference = PropertyReference(
                    propertyIdentifier=prop_id,
                    )

                # check for an array index
                if (i < len(args)) and args[i].isdigit():
                    prop_reference.propertyArrayIndex = int(args[i])
                    i += 1
                # add it to the list
                prop_reference_list.append(prop_reference)

            # check for at least one property
            if not prop_reference_list:
                raise ValueError("provide at least one property")

            # build a read access specification
            read_access_spec = ReadAccessSpecification(
                objectIdentifier=(obj_type, obj_inst),
                listOfPropertyReferences=prop_reference_list,
                )

            # add it to the list
            read_access_spec_list.append(read_access_spec)
        # check for at least one
        if not read_access_spec_list:
            raise RuntimeError("at least one read access specification required")

        # build the request
        request = ReadPropertyMultipleRequest(
            listOfReadAccessSpecs=read_access_spec_list,
            )
        request.pduDestination = Address(addr)
        if _debug: print("    - request: %r", request)

        # give it to the application
        return request

    except Exception as error:
        print ("exception: %r", error)
            
                
def read_prop(args):

    request = Request_read(args)
    if request == None:
        return None
    ### do the service request
    this_app.request(request)
    run()
    return valueRead
    
    
def read_multi(args):
    request = request_readMulti(args)
    if request == None:
        return None
        
    this_app.request(request)
    run()
    return valueRead
        
def whois(args):
    request = Request_whois(args)
    this_app.request(request)
    run()
    return deviceList


