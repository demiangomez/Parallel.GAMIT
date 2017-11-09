"""
Project: Parallel.PPP
Date: 9/13/17 6:30 PM
Author: Demian D. Gomez

This module handles the cluster nodes and checks all the necessary dependencies before sending jobs to each node
"""

import pp
import time
import Utils
import cPickle as pickle
import inspect
import types

def test_node():
    # test node: function that makes sure that all required packages and tools are present in the nodes
    import traceback
    import platform
    import os
    import sys

    # BEFORE ANYTHING! check the python version
    version = sys.version_info
    if version.major > 2 or version.minor < 7 or (version.micro < 13 and version.minor <= 7):
        return ' -- %s: Incorrect Python version: %i.%i.%i. Recommended version > 2.7.13' % (platform.node(), version.major, version.minor, version.micro)

    # start importing the modeles needed
    try:
        import pyRinex
        import dbConnection
        import pyStationInfo
        import pyArchiveStruct
        import pyPPP
        import pyBrdc
        import pyOptions
        import Utils
        import pyOTL
        import shutil
        import datetime
        import time
        import uuid
        import pySp3
        import traceback
        import numpy
        import pyPPPETM
        import pyRunWithRetry
        import pyDate

    except Exception:
        return ' -- %s: Problem found while importing modules:\n%s' % (platform.node(), traceback.format_exc())

    # continue with a test SQL connection
    # make sure that the gnss_data.cfg is present
    try:
        cnn = dbConnection.Cnn('gnss_data.cfg')

        q = cnn.query('SELECT count(*) FROM networks')

    except Exception:
        return ' -- %s: Problem found while connecting to postgres:\n%s ' % (platform.node(), traceback.format_exc())

    # make sure we can create the production folder
    try:
        test_dir = os.path.join('production/node_test')
        if not os.path.exists(test_dir):
            os.makedirs(test_dir)
    except Exception:
        return ' -- %s: Could not create production folder:\n%s ' % (platform.node(), traceback.format_exc())

    # test
    try:
        Config = pyOptions.ReadOptions('gnss_data.cfg')

        # check that all paths exist and can be reached
        if not os.path.exists(Config.archive_path):
            return ' -- %s: Could not reach archive path %s' % (platform.node(), Config.archive_path)

        if not os.path.exists(Config.repository):
            return ' -- %s: Could not reach repository path %s' % (platform.node(), Config.repository)

        # pick a test date to replace any possible parameters in the config file
        date = pyDate.Date(year=2010,doy=1)
    except Exception:
        return ' -- %s: Problem while reading config file and/or testing archive access:\n%s' % (platform.node(), traceback.format_exc())

    try:
        brdc = pyBrdc.GetBrdcOrbits(Config.brdc_path, date, test_dir)
    except Exception:
        return ' -- %s: Problem while testing the broadcast ephemeris archive (%s) access:\n%s' % (platform.node(), Config.brdc_path, traceback.format_exc())

    try:
        sp3 = pySp3.GetSp3Orbits(Config.sp3_path, date, Config.sp3types, test_dir)
    except Exception:
        return ' -- %s: Problem while testing the sp3 orbits archive (%s) access:\n%s' % (platform.node(), Config.sp3_path, traceback.format_exc())

    # check that all executables and GAMIT bins are in the path
    list_of_prgs = ['crz2rnx', 'crx2rnx', 'rnx2crx', 'rnx2crz', 'RinSum', 'teqc', 'svdiff', 'svpos', 'tform', 'sh_rx2apr', 'doy', 'RinEdit']

    for prg in list_of_prgs:
        with pyRunWithRetry.command('which ' + prg) as run:
            run.run()
            if run.stdout == '':
                return ' -- %s: Could not find path to %s' % (platform.node(), prg)

    # check grdtab and ppp from the config file
    if not os.path.isfile(Config.options['grdtab']):
        return ' -- %s: Could not find grdtab in %s' % (platform.node(), Config.options['grdtab'])

    if not os.path.isfile(Config.options['otlgrid']):
        return ' -- %s: Could not find otlgrid in %s' % (platform.node(), Config.options['otlgrid'])

    if not os.path.isfile(Config.options['ppp_exe']):
        return ' -- %s: Could not find ppp_exe in %s' % (platform.node(), Config.options['ppp_exe'])

    if not os.path.isfile(os.path.join(Config.options['ppp_path'],'gpsppp.stc')):
        return ' -- %s: Could not find gpsppp.stc in %s' % (platform.node(), Config.options['ppp_path'])

    if not os.path.isfile(os.path.join(Config.options['ppp_path'],'gpsppp.svb_gps_yrly')):
        return ' -- %s: Could not find gpsppp.svb_gps_yrly in %s' % (platform.node(), Config.options['ppp_path'])

    if not os.path.isfile(os.path.join(Config.options['ppp_path'],'gpsppp.flt')):
        return ' -- %s: Could not find gpsppp.flt in %s' % (platform.node(), Config.options['ppp_path'])

    if not os.path.isfile(os.path.join(Config.options['ppp_path'],'gpsppp.stc')):
        return ' -- %s: Could not find gpsppp.stc in %s' % (platform.node(), Config.options['ppp_path'])

    if not os.path.isfile(os.path.join(Config.options['ppp_path'],'gpsppp.met')):
        return ' -- %s: Could not find gpsppp.met in %s' % (platform.node(), Config.options['ppp_path'])

    if not os.path.isfile(Config.options['atx']):
        return ' -- %s: Could not find atx in %s' % (platform.node(), Config.options['atx'])

    return ' -- %s: Test passed!' % (platform.node())


class JobServer:
    def __init__(self, Config):

        self.__sfuncHM = {}
        self.__sourcesHM = {}
        self.__pickle_proto = 2

        self.process_callback = False
        self.jobs = 0

        # test the local node
        print " ==== Starting JobServer(pp) ===="
        print " >> Checking requirements at the local node..."
        result = test_node()
        print result

        if not 'Test passed!' in result:
            print ' >> The local node did not pass all the required tests. Check messages.'
            exit()

        # check that the run_parallel option is activated
        if Config.run_parallel:
            if Config.options['node_list'] is None:
                # no explicit list, find all
                ppservers = ('*',)
            else:
                # use the provided explicit list of nodes
                ppservers = tuple(Config.options['node_list'].split(','))

            # limit execution on the local machine to 'cpus'
            if Config.options['cpus'] is None:
                self.job_server = pp.Server(ncpus=Utils.get_processor_count(), ppservers=ppservers) # type: pp.Server
            else:
                self.job_server = pp.Server(ncpus=int(Config.options['cpus']), ppservers=ppservers) # type: pp.Server

            # sleep to allow the nodes to respond to the TCP request
            time.sleep(2)

            print " >> Checking requirements at the remote nodes..."

            # pickle the test_node function and (empty) arguments
            f = self.__dumpsfunc((test_node,), tuple())
            sargs = pickle.dumps(tuple(), self.__pickle_proto)

            stop = False
            for node in self.job_server.autopp_list.keys():
                node_ip_port = node.split(':')

                # open a worker for this node
                rworker = pp._RWorker(node_ip_port[0], int(node_ip_port[1]), pp.Server.default_secret, self.job_server, "EXEC", True, 10)

                try:
                    rworker.csend(f)
                    rworker.send(sargs)
                    result = rworker.receive()
                    result, sout = pickle.loads(result)

                    if not 'Test passed!' in result:
                        stop = True
                    # print the messages
                    print result

                except Exception as e:
                    print ' >> Error during rworker test: ' + str(e)

                rworker.close()

            if stop:
                print ' >> Errors where encountered during the job server initialization. Check messages.'
                # terminate execution if problems were found
                exit()
            else:
                print " >> Parallel Python started with the following nodes:"
                nodes = self.job_server.get_active_nodes()
                print " -- IP/Name               CPUs"
                for node in nodes:
                    print "    %-21s %i" % (node, nodes[node])
                print ""
        else:
            self.job_server = None

    def SubmitJob(self, funcs, args, depfuncs, modules, callback_list, callback_obj, callback_func_name):

        self.jobs += 1
        callback_list.append(callback_obj)

        self.job_server.submit(funcs,args,depfuncs,modules,getattr(callback_list[-1], callback_func_name))

        if self.jobs >= 300:
            self.jobs = 0
            self.job_server.wait()
            self.process_callback = True


    def __dumpsfunc(self, funcs, modules):
        """Serializes functions and modules"""
        hashs = hash(funcs + modules)
        if hashs not in self.__sfuncHM:
            sources = [self.__get_source(func) for func in funcs]
            self.__sfuncHM[hashs] = pickle.dumps(
                    (funcs[0].func_name, sources, modules),
                    self.__pickle_proto)
        return self.__sfuncHM[hashs]

    def __get_source(self, func):
        """Fetches source of the function"""
        hashf = hash(func)
        if hashf not in self.__sourcesHM:
            #get lines of the source and adjust indent
            sourcelines = inspect.getsourcelines(func)[0]
            #remove indentation from the first line
            sourcelines[0] = sourcelines[0].lstrip()
            self.__sourcesHM[hashf] = "".join(sourcelines)
        return self.__sourcesHM[hashf]

    def __find_modules(self, prefix, dict):
        """recursively finds all the modules in dict"""
        modules = []
        for name, object in dict.items():
            if isinstance(object, types.ModuleType) \
                    and name not in ("__builtins__", "pp"):
                if object.__name__ == prefix+name or prefix == "":
                    modules.append(object.__name__)
                    modules.extend(self.__find_modules(
                            object.__name__+".", object.__dict__))
        return modules