# -*- coding: utf-8 -*-
"""
Created on Mon Nov  7 12:31:36 2016

@author: erdongwei
"""
import sys
import time
import ConfigParser

from bacpypes.debugging import bacpypes_debugging, ModuleLogger
from bacpypes.consolelogging import ConfigArgumentParser
from bacpypes.core import run, stop, deferred
from bacpypes.pdu import Address, GlobalBroadcast

from bacpypes.app import BIPSimpleApplication
from bacpypes.local.device import LocalDeviceObject

from bacpypes.apdu import ReadPropertyMultipleRequest, PropertyReference, \
    ReadAccessSpecification, ReadPropertyMultipleACK, \
    WritePropertyMultipleRequest, WriteAccessSpecification
from bacpypes.apdu import Error, AbortPDU, SimpleAckPDU, WhoIsRequest, IAmRequest, \
    ReadPropertyRequest, ReadPropertyACK, WritePropertyRequest

from bacpypes.object import get_object_class, get_datatype
from bacpypes.basetypes import ServicesSupported, PropertyIdentifier, PropertyValue
from bacpypes.errors import DecodingError
from bacpypes.constructeddata import Array, Any
from bacpypes.primitivedata import Null, Atomic, Integer, Unsigned, Real

# some debugging
_debug = 0
_log = ModuleLogger(globals())

#
#   WhoIsApplication
#
global valueRead
global this_app
global deviceList

@bacpypes_debugging
class Applications(BIPSimpleApplication):

    def __init__(self, *args):
        if _debug: Applications._debug("__init__ %r", args)
        BIPSimpleApplication.__init__(self, *args)

        # keep track of requests to line up responses
        self._request = None

    def request(self, apdu):
        global deviceList
        global valueRead
        valueRead = None
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

    def confirmation(self, apdu):
        global valueRead
        valueRead = None
        if _debug: Applications._debug("confirmation %r", apdu)

        if isinstance(apdu, Error):
            sys.stdout.write("error: %s\n" % (apdu.errorCode,))
            sys.stdout.flush()
            valueRead = apdu

        elif isinstance(apdu, AbortPDU):
            apdu.debug_contents()
            valueRead = apdu

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
                        pass
                        #sys.stdout.write("[" + str(propertyArrayIndex) + "]")

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
                            valueRead.append(None)
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

def Init(ini_filename):
    global this_app
    ### read initialization file
    opts = ConfigParser.ConfigParser()
    opts.read(ini_filename)

    objectName = opts.get('BACpypes', 'objectName')
    objectIdentifier = opts.get('BACpypes', 'objectIdentifier')
    maxApduLengthAccepted = opts.get('BACpypes', 'maxApduLengthAccepted')
    segmentationSupported = opts.get('BACpypes', 'segmentationSupported')
    vendorIdentifier = opts.get('BACpypes', 'vendorIdentifier')
    address = opts.get('BACpypes', 'address')

    if _debug: _log.debug("initialization")
    if _debug: _log.debug("    - args: %r", args)

    ### create a local device
    this_device = LocalDeviceObject(
        objectName=objectName,
        objectIdentifier=int(objectIdentifier),
        maxApduLengthAccepted=int(maxApduLengthAccepted),
        segmentationSupported=segmentationSupported,
        vendorIdentifier=int(vendorIdentifier),
        )

    # pss = ServicesSupported()
    # pss['whoIs'] = 1
    # pss['iAm'] = 1
    # pss['readProperty'] = 1
    # pss['writeProperty'] = 1
    # pss['readPropertyMultiple'] = 1
    # pss['writePropertyMultiple'] = 1
    # this_device.protocolServicesSupported = pss.value
    this_app = Applications(this_device, str(address))


def Request_whois(args):
    args = args.split()

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

    ### return the request
    return request

def Request_read(args):
    if _debug: print("build read reqeust: ", args)

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
    if _debug: print("    - request: %r" % request)

    ### return the request
    return request

def request_readMulti(args):
    if _debug: print ("build readMulti reqeust: ", args)

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
    if _debug: print("    - request: %r" % request)

    ### return the request
    return request

def request_write(args):
    if _debug: ("build write request: %r" % args)

    addr, obj_type, obj_inst, prop_id = args[:4]
    if obj_type.isdigit():
        obj_type = int(obj_type)
    obj_inst = int(obj_inst)
    value = args[4]

    indx = None
    if len(args) >= 6:
        if args[5] != "-":
            indx = int(args[5])
    if _debug: print("    - indx: %r" % indx)

    priority = None
    if len(args) >= 7:
        priority = int(args[6])
    if _debug: print("    - priority: %r" % priority)

    # get the datatype
    datatype = get_datatype(obj_type, prop_id)
    if _debug: print("    - datatype: %r" % datatype)

    # change atomic values into something encodeable, null is a special case
    if (value == 'null'):
        value = Null()
    elif issubclass(datatype, Atomic):
        if datatype is Integer:
            value = int(value)
        elif datatype is Real:
            value = float(value)
        elif datatype is Unsigned:
            value = int(value)
        value = datatype(value)
    elif issubclass(datatype, Array) and (indx is not None):
        if indx == 0:
            value = Integer(value)
        elif issubclass(datatype.subtype, Atomic):
            value = datatype.subtype(value)
        elif not isinstance(value, datatype.subtype):
            raise TypeError("invalid result datatype, expecting %s" % (datatype.subtype.__name__,))
    elif not isinstance(value, datatype):
        raise TypeError("invalid result datatype, expecting %s" % (datatype.__name__,))
    if _debug: print("    - encodeable value: %r %s" % value, type(value))

    # build a request
    request = WritePropertyRequest(
        objectIdentifier=(obj_type, obj_inst),
        propertyIdentifier=prop_id
        )
    request.pduDestination = Address(addr)

    # save the value
    request.propertyValue = Any()
    try:
        request.propertyValue.cast_in(value)
    except Exception as error:
        print("WriteProperty cast error: %r" % error)

    # optional array index
    if indx is not None:
        request.propertyArrayIndex = indx

    # optional priority
    if priority is not None:
        request.priority = priority

    if _debug: print ("    - request: %r" % request)

    ### return the request
    return request

def request_writeMulti(args):
    if _debug: print ("build write request: %r" % args)

    i = 0
    addr = args[i]
    i += 1

    write_access_spec_list = []
    while i < len(args):
        obj_type = args[i]
        i += 1

        if obj_type.isdigit():
            obj_type = int(obj_type)

        obj_inst = args[i]
        i += 1
        obj_inst = int(obj_inst)


        prop_value_list = []
        while i < len(args):
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

            value = args[i]
            i += 1

            # check for an array index
            indx = None
            if (i < len(args)) and args[i].isdigit():
                indx = int(args[i])
                i += 1
            elif args[i] == '-':
                i += 1

            # check for an priority
            priority = None
            if (i < len(args)) and args[i].isdigit():
                priority = int(args[i])
                i += 1

            # change atomic values into something encodeable, null is a special case
            if (value == 'null'):
                value = Null()
            elif issubclass(datatype, Atomic):
                if datatype is Integer:
                    value = int(value)
                elif datatype is Real:
                    value = float(value)
                elif datatype is Unsigned:
                    value = int(value)
                value = datatype(value)
            elif issubclass(datatype, Array) and (indx is not None):
                if indx == 0:
                    value = Integer(value)
                elif issubclass(datatype.subtype, Atomic):
                    value = datatype.subtype(value)
                elif not isinstance(value, datatype.subtype):
                    raise TypeError("invalid result datatype, expecting %s" % (datatype.subtype.__name__,))
            elif not isinstance(value, datatype):
                raise TypeError("invalid result datatype, expecting %s" % (datatype.__name__,))
            if _debug: print("    - encodeable value: %r %s" % value, type(value))

            # build a property value
            prop_value = PropertyValue(
                propertyIdentifier=prop_id,
                )
            prop_value.value = Any()
            try:
                prop_value.value.cast_in(value)
            except Exception as error:
                print("WriteProperty cast error: %r" % error)

            # optional array index
            if indx is not None:
                prop_value.propertyArrayIndex = indx
            # optional priority
            if indx is not None:
                prop_value.priority = priority

            # add it to the list
            prop_value_list.append(prop_value)

        # check for at least one property
        if not prop_value_list:
            raise ValueError("provide at least one property")

        # build a read access specification
        write_access_spec = WriteAccessSpecification(
            objectIdentifier=(obj_type, obj_inst),
            listOfProperties=prop_value_list,
            )

        # add it to the list
        write_access_spec_list.append(write_access_spec)
    # check for at least one
    if not write_access_spec_list:
        raise RuntimeError("at least one read access specification required")

    # build the request
    request = WritePropertyMultipleRequest(
        listOfWriteAccessSpecs=write_access_spec_list,
        )
    request.pduDestination = Address(addr)
    if _debug: print("    - request: %r" % request)

    ### return the request
    return request


def write_prop(args):
    request = request_write(args)

    deferred(this_app.request, request)
    run()

def write_multi(args):
    request = request_writeMulti(args)
    ### do the service request
    deferred(this_app.request, request)
    run()

def read_prop(args):
    request = Request_read(args)

    deferred(this_app.request, request)
    run()
    return valueRead


def read_multi(args):
    request = request_readMulti(args)

    deferred(this_app.request, request)
    run()
    return valueRead

def whois(args, timer=5):
    request = Request_whois(args)

    deferred(this_app.request, request)
    run()
    return deviceList
