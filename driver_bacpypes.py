### activate the virtual environment
activate_this = "/home/zhanwei/virt_env/virt_hvac/bin/activate_this.py"
execfile(activate_this, dict(__file__=activate_this))

import json
import re
import operator
import sys

from twisted.internet import threads, defer
from twisted.python import log

from smap.driver import SmapDriver
from smap.util import periodicSequentialCall, find
from smap import actuate
from pybacnet import bacnet

import BACpypes_applications as BACpypesAPP
from time import sleep

def _get_class(name):
    cmps = name.split('.')
    assert len(cmps) > 1
    (mod_name, class_name) = ('.'.join(cmps[:-1]), cmps[-1])
    if mod_name in sys.modules:
        mod = sys.modules[mod_name]
    else:
        mod = __import__(mod_name, globals(), locals(), [class_name])
    return getattr(mod, class_name)


class BACnetDriver(SmapDriver):
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

    def _read_points(self, args):
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

    def _read_seperate(self, args, devOld):
        batch_size = 10
        num_points = (len(args)-1)/3
        iteration = num_points // batch_size
        val = []
        for i in range(iteration+1):
            if i == iteration:
                args_batch = args[i*batch_size+1:]
            else:
                args_batch = args[i*batch_size+1:(i+1)batch_size+1]
            val_seperate = self._read_points(args_batch)
            if val_seperate == None:
                print "cannot reach the device ", devOld['name'], devOld['inst']
            else:
                val += val_seperate
        if len(val) == 0:
            return None
        else:
            return val

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
                args.append(obj['type'])
                args.append(obj['inst'])
                args.append('presentValue')
                path_tmp.append(path)
            else:
                if devOld['segment'] == 'segmentedBoth':
                    val_tmp = self._read_points(args)
                else:
                    val_tmp = self._read_seperate(args, devOld)
                if val_tmp == None:
                    print "cannot reach the device ", devOld['name'], devOld['inst']
                else:
                    val = val + val_tmp
                    pathList = pathList + path_tmp
                path_tmp = [path]
                devOld = dev
                args = [dev['address'], obj['type'], obj['inst'], 'presentValue']

        ### post the value to sMAP archiver
        for i in range(len(val)):
            if val == None:
                print "cannot read the points: ", pathList[i]
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