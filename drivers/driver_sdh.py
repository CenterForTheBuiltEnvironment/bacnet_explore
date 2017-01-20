#### run smap driver
#### sudo /home/.../bin/python /home/.../bin/twistd --logfile=/home/.../twistd.log --pidfile=/home/.../twistd.pid smap /home/.../conf/sdh_s1.ini
####

import json
import re
import operator
import sys
from email_utils import send_email

from twisted.internet import threads, defer
from twisted.python import log

from smap.driver import SmapDriver
from smap.util import periodicSequentialCall, find
from smap import actuate

import BACpypes_applications as BACpypesAPP
from bacpypes.apdu import Error, AbortPDU, AbortReason
from time import sleep
from subprocess import Popen, PIPE

def _get_class(name):
    cmps = name.split('.')
    assert len(cmps) > 1
    (mod_name, class_name) = ('.'.join(cmps[:-1]), cmps[-1])
    if mod_name in sys.modules:
        mod = sys.modules[mod_name]
    else:
        mod = __import__(mod_name, globals(), locals(), [class_name])
    return getattr(mod, class_name)


class Driver(SmapDriver):
    """Driver for polling BACnet points"""
    def setup(self, opts):
        #bacnet.Init(opts.get('iface', 'eth0'), '47900')
        BACpypesAPP.Init()    ### Initialize the local device

        with open(opts.get('db'), 'r') as fp:
            self.db = json.load(fp)
        self.rate = int(opts.get('rate', 60))
        self.devices = map(re.compile, opts.get('devices', ['.*']))
        self.points = map(re.compile, opts.get('points', ['.*']))
        self.ffilter = _get_class(opts.get('filter')) if opts.get('filter') else None
        self.pathnamer = _get_class(opts.get('pathnamer')) if opts.get('pathnamer') else None
        self.actuators = _get_class(opts.get('actuators')) if opts.get('actuators') else None
        self.unit_map = _get_class(opts.get('unit_map')) if opts.get('unit_map') else None
        self.email_list = opts.get('email_list')

        if self.actuators:
            act_names = [a['name'] for a in self.actuators]
        for (dev, obj, path) in self._iter_points():
            unit = str(obj['unit']).strip()
            if self.unit_map:
                if unit in self.unit_map:
                    unit = self.unit_map.get(unit)
            self.add_timeseries(path, unit, data_type='double')

            # Add actuators
            if self.actuators and obj['name'] in act_names:
                actuator = find(lambda a: a['name'] == obj['name'], self.actuators)
                setup = {'obj': obj, 'dev': dev}
                print obj['name'], obj['type']
                if obj['type'] in ['Analog Output', 'Analog Value']:
                    setup['range'] = actuator['range']
                    act = ContinuousActuator(**setup)
                    data_type = 'double'
                elif oobj['type'] == 'Binary Output':
                    act = BinaryActuator(**setup)
                    data_type = 'long'
                elif obj['type'] == 'Multi-State Output':
                    setup['states'] = actuator['states']
                    act = DiscreteActuator(**setup)
                    data_type = 'long'
                try:
                    #print "adding actuator:", path, unit, obj, actuator.get('range')
                    self.add_actuator(path + "_act", unit, act, data_type=data_type)
                    del act
                except NameError:
                    print "actuator not created for %s" % path


    @staticmethod
    def _matches(s, pats):
        return len(filter(None, map(lambda p: p.match(s), pats))) > 0

    def get_path(self, dev, obj):
        if self.pathnamer:
            path = str(self.pathnamer(dev['name'], obj['name']))
        else:
            path = str('/' + dev['name'] + '/' + obj['name'])
        return (dev, obj, path)

    def _iter_points(self):
        for dev in self.db:
            if self.ffilter:
                for obj in dev['objs']:
                    if self.ffilter(dev['name'], obj['name']):
                        yield self.get_path(dev, obj)
            else:
                if not self._matches(dev['name'], self.devices): continue
                for obj in dev['objs'][1:]:
                    if not self._matches(obj['name'], self.points): continue
                    yield self.get_path(dev, obj)

    def _read_points(self, args, path_tmp, devOld, batch_size):

        num_points = (len(args)-1)/3
        iteration = num_points // batch_size
        val = []
        path_result = []
        for i in range(iteration+1):
            args_batch = [args[0]]
            path_read = []
            if i == iteration:
                args_batch += args[3*i*batch_size+1:]
                path_read += path_tmp[i*batch_size:]
            else:
                args_batch += args[3*i*batch_size+1:3*(i+1)*batch_size+1]
                path_read += path_tmp[i*batch_size:(i+1)*bat]
            try:
                val_seperate = BACpypesAPP.read_multi(args)

                if isinstance(val_seperate, Error):
                    print "cannot reach the device ", devOld['name'], devOld['inst']

                    subject = "Read points error/Error"
                    msg = "cannot reach the device " + devOld['name'] + " " + str(devOld['inst']) + \
                    ". The args is: \n" + ' '.join(s for s in args) + "\nThe error is:\n"
                    send_email(self.email_list, msg+str(val_seperate.errorCode), subject)
                elif isinstance(val_seperate, AbortPDU):
                    print "cannot reach the device ", devOld['name'], devOld['inst']

                    subject = "Read points error/Abort"
                    msg = "cannot reach the device " + devOld['name'] + " " + str(devOld['inst']) + \
                    ". The args is: \n" + ' '.join(s for s in args) + \
                    "\nRequest is abortted, and the abort reason is:\n"
                    reason = AbortReason.enumerations
                    for s in reason:
                        if reason[s] == val_seperate.apduAbortRejectReason:
                            rejectReason = s
                    send_email(self.email_list, msg+rejectReason, subject)
                elif val_seperate is None:
                    print "cannot reach the device ", devOld['name'], devOld['inst']

                    subject = "Read points error/None"
                    msg = "cannot reach the device " + devOld['name'] + " " + str(devOld['inst']) + \
                    ". The args is: \n" + ' '.join(s for s in args)
                    send_email(self.email_list, msg, subject)
                else:
                    val += val_seperate
                    path_result += path_read
            except Exception as error:
                print error
                print "cannot reach the device ", devOld['name'], devOld['inst']

                subject = "Read points error"
                msg = "cannot reach the device " + devOld['name'] + " " + str(devOld['inst']) + \
                ". The args is: \n" + ' '.join(s for s in args) + "\nThe error is:\n"
                send_email(self.email_list, msg+str(error), subject)

        if len(val) == 0:
            return None
        else:
            return val, path_result

    def start(self):
        self.caller = periodicSequentialCall(self.update)
        self.caller.start(self.rate)

    @defer.inlineCallbacks
    def update(self):
        ### pull the data from bacnet devices
        devOld = None
        pathList = []
        args = []
        val = []
        path_tmp = []
        for (dev, obj, path) in self._iter_points():
            if devOld == dev:
                args.append(str(obj['type']))
                args.append(str(obj['inst']))
                args.append('presentValue')
                path_tmp.append(path)
            else:
                if devOld == None:
                    devOld = dev
                else:
                    if devOld['segment'] == 'segmentedBoth':
                        batch_size = 50
                    else:
                        batch_size = 2

                    val_tmp, path_tmp = yield threads.deferToThread(self._read_points, args, path_tmp, devOld, batch_size)
                    if val_tmp == None:
                        print "cannot reach the device ", devOld['name'], devOld['inst']
                    else:
                        val = val + val_tmp
                        pathList = pathList + path_tmp
                path_tmp = [path]
                devOld = dev
                args = [str(dev['address']), str(obj['type']), str(obj['inst']), 'presentValue']

        if devOld['segment'] == 'segmentedBoth':
            batch_size = 50
        else:
            batch_size = 2
        val_tmp, path_tmp = yield threads.deferToThread(self._read_points, args, path_tmp, devOld, batch_size)
        if val_tmp == None:
            print "cannot reach the device ", devOld['name'], devOld['inst']
        else:
            val = val + val_tmp
            pathList = pathList + path_tmp

        ### post the value to sMAP archiver
        for i in range(len(val)):
            if val[i] == None:
                print "cannot read the points: ", pathList[i]
                subject = "Read points error"
                msg = "cannot read this point, " + str(pathList[i])
                send_email(self.email_list, msg, subject)
            else:
                if val[i] == 'inactive':
                    self._add(pathList[i], 0.0)
                elif val[i] == 'activate':
                    self._add(pathList[i], 1.0)
                else:
                    self._add(pathList[i], float(val[i]))

class BACnetActuator(actuate.SmapActuator):
    def __init__(self, **opts):
        self.dev = opts['dev']
        self.obj = opts['obj']
        self.priority = 15

    def get_state(self, request):
        args = [self.dev['address'], self.obj['type'], self.obj['inst'], 'presentValue']
        return BACpypesAPP.read_prop(args)

    def set_state(self, request, state):
        if 'priority' in request.args:
            self.priority = int(request.args['priority'][0])

        if 'clear' in request.args:
            self.clear()
        else:
            args = [self.dev['address'], self.obj['type'], self.obj['instance'], \
                        presentValue, str(state), '-', self.priority]
            BACpypesAPP.write_prop(args)
        return self.get_state(None)

    def clear(self):
        args = [self.dev['address'], self.obj['type'], self.obj['instance'], \
                    presentValue, 'null', '-', self.priority]
        return BACpypesAPP.write_prop(args)

class ContinuousActuator(BACnetActuator, actuate.ContinuousActuator):
    def __init__(self, **opts):
        actuate.ContinuousActuator.__init__(self, opts['range'])
        BACnetActuator.__init__(self, **opts)

class BinaryActuator(BACnetActuator, actuate.BinaryActuator):
    def __init__(self, **opts):
        actuate.BinaryActuator.__init__(self)
        BACnetActuator.__init__(self, **opts)

class DiscreteActuator(BACnetActuator, actuate.NStateActuator):
    def __init__(self, **opts):
        actuate.NStateActuator.__init__(self, opts['states'])
        BACnetActuator.__init__(self, **opts)
