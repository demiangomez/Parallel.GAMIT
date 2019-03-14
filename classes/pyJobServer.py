"""
Project: Parallel.PPP
Date: 9/13/17 6:30 PM
Author: Demian D. Gomez

This module handles the cluster nodes and checks all the necessary dependencies before sending jobs to each node
"""

import time
import dispy
import dispy.httpd
from tqdm import tqdm
from functools import partial

DELAY = 5


def test_node(check_gamit_tables=None):
    # test node: function that makes sure that all required packages and tools are present in the nodes
    import traceback
    import platform
    import os
    import sys

    def check_tab_file(tabfile, date):

        if os.path.isfile(tabfile):
            # file exists, check contents
            with open(tabfile, 'r') as luntab:
                lines = luntab.readlines()
                tabdate = pyDate.Date(mjd=lines[-1].split()[0])
                if tabdate < date:
                    return ' -- %s: Last entry in %s is %s but processing %s' \
                           % (platform.node(), tabfile, tabdate.yyyyddd(), date.yyyyddd())

        else:
            return ' -- %s: Could not find file %s' % (platform.node(), tabfile)

        return []

    # BEFORE ANYTHING! check the python version
    version = sys.version_info
    if version.major > 2 or version.minor < 7 or (version.micro < 13 and version.minor <= 7):
        return ' -- %s: Incorrect Python version: %i.%i.%i. Recommended version > 2.7.13' \
               % (platform.node(), version.major, version.minor, version.micro)

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
        import pyETM
        import pyRunWithRetry
        import pyDate
        import pg

    except Exception:
        return ' -- %s: Problem found while importing modules:\n%s' % (platform.node(), traceback.format_exc())

    # continue with a test SQL connection
    # make sure that the gnss_data.cfg is present
    try:
        cnn = dbConnection.Cnn('gnss_data.cfg')

        q = cnn.query('SELECT count(*) FROM networks')

        if int(pg.version[0]) < 5:
            return ' -- %s: Incorrect PyGreSQL version!: %s' % (platform.node(), pg.version)

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
        return ' -- %s: Problem while reading config file and/or testing archive access:\n%s' \
               % (platform.node(), traceback.format_exc())

    try:
        brdc = pyBrdc.GetBrdcOrbits(Config.brdc_path, date, test_dir)
    except Exception:
        return ' -- %s: Problem while testing the broadcast ephemeris archive (%s) access:\n%s' \
               % (platform.node(), Config.brdc_path, traceback.format_exc())

    try:
        sp3 = pySp3.GetSp3Orbits(Config.sp3_path, date, Config.sp3types, test_dir)
    except Exception:
        return ' -- %s: Problem while testing the sp3 orbits archive (%s) access:\n%s' \
               % (platform.node(), Config.sp3_path, traceback.format_exc())

    # check that all executables and GAMIT bins are in the path
    list_of_prgs = ['crz2rnx', 'crx2rnx', 'rnx2crx', 'rnx2crz', 'RinSum', 'teqc', 'svdiff', 'svpos', 'tform',
                    'sh_rx2apr', 'doy', 'RinEdit', 'sed', 'compress']

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

    for frame in Config.options['frames']:
        if not os.path.isfile(frame['atx']):
            return ' -- %s: Could not find atx in %s' % (platform.node(), frame['atx'])

    if check_gamit_tables is not None:
        # check the gamit tables if not none

        date = check_gamit_tables[0]
        eop  = check_gamit_tables[1]

        gg = os.path.expanduser('~/gg')
        tables = os.path.expanduser('~/gg/tables')

        if not os.path.isdir(gg):
            return ' -- %s: Could not GAMIT installation dir (gg)' % (platform.node())

        if not os.path.isdir(tables):
            return ' -- %s: Could not GAMIT tables dir (gg)' % (platform.node())

        # luntab
        luntab = os.path.join(tables, 'luntab.' + date.yyyy() + '.J2000')

        result = check_tab_file(luntab, date)

        if result:
            return result

        # soltab
        soltab = os.path.join(tables, 'soltab.' + date.yyyy() + '.J2000')

        result = check_tab_file(soltab, date)

        if result:
            return result

        # ut
        ut = os.path.join(tables, 'ut1.' + eop)

        result = check_tab_file(ut, date)

        if result:
            return result

        # leapseconds

        # vmf1

        # pole
        pole = os.path.join(tables, 'pole.' + eop)

        result = check_tab_file(pole, date)

        if result:
            return result

        # fes_cmc consistency

    return ' -- %s: Test passed!' % (platform.node())


def setup(modules):
    """
    function to import modules in the nodes
    :return: nothing
    """
    for module in modules:
        module_obj = __import__(module)
        # create a global object containing our module
        globals()[module] = module_obj

    return 0


class JobServer:

    def check_cluster(self, status, node, job):

        if status == dispy.DispyNode.Initialized:
            print ' -- Checking node %s (%i CPUs)...' % (node.name, node.avail_cpus)
            # test node to make sure everything works
            self.cluster.send_file('gnss_data.cfg', node)

            j = self.cluster.submit_node(node, self.check_gamit_tables)

            self.cluster.wait()

            self.result.append(j())

            self.nodes.append(node)

    def __init__(self, Config, check_gamit_tables=None, run_parallel=True):
        """
        initialize the jobserver
        :param Config: pyOptions.ReadOptions instance
        :param check_gamit_tables: check or not the tables in GAMIT
        :param run_parallel: override the configuration in gnss_data.cfg
        """
        self.check_gamit_tables = check_gamit_tables

        self.nodes = []
        self.result = []
        self.jobs = []
        self.run_parallel = Config.run_parallel if run_parallel else False
        self.verbose = False
        self.close = False

        # vars to store the http_server and the progress bar (if needed)
        self.progress_bar = None
        self.http_server = None
        self.callback = None
        self.function = None
        self.modules = []

        print " ==== Starting JobServer(dispy) ===="

        # check that the run_parallel option is activated
        if self.run_parallel:
            if Config.options['node_list'] is None:
                # no explicit list, find all
                servers = ['*']
            else:
                # use the provided explicit list of nodes
                if Config.options['node_list'].strip() == '':
                    servers = ['*']
                else:
                    servers = filter(None, list(Config.options['node_list'].split(',')))

            # initialize the cluster
            self.cluster = dispy.JobCluster(test_node, servers, recover_file='pg.dat', pulse_interval=60,
                                            cluster_status=self.check_cluster)
            # discover the available nodes
            self.cluster.discover_nodes(servers)

            # wait for all nodes
            time.sleep(DELAY)

            stop = False

            for r in self.result:
                if 'Test passed!' not in r:
                    print r
                    stop = True

            if stop:
                print ' >> Errors were encountered during initialization. Check messages.'
                # terminate execution if problems were found
                self.cluster.close()
                exit()

            self.cluster.close()
        else:
            print ' >> Parallel processing deactivated by user'
            r = test_node(check_gamit_tables)
            if 'Test passed!' not in r:
                print r
                print ' >> Errors were encountered during initialization. Check messages.'
                exit()

    def create_cluster(self, function, dependencies=(), callback=None, progress_bar=None, verbose=False, modules=()):

        self.nodes = []
        self.jobs = []
        self.callback = callback
        self.function = function
        self.verbose = verbose
        self.close = True

        if self.run_parallel:
            self.cluster = dispy.JobCluster(function, self.nodes, list(dependencies), callback, self.cluster_status,
                                            pulse_interval=60, setup=partial(setup, modules),
                                            loglevel=dispy.logger.CRITICAL)

            self.http_server = dispy.httpd.DispyHTTPServer(self.cluster, poll_sec=2)

            # wait for all nodes to be created
            time.sleep(DELAY)

        self.progress_bar = progress_bar

    def submit(self, *args):
        """
        function to submit jobs to dispy. If run_parallel == False, the jobs are executed
        :param args:
        :return:
        """
        if self.run_parallel:
            self.jobs.append(self.cluster.submit(*args))
        else:
            # if no parallel was invoked, execute the procedure manually
            if self.callback is not None:
                job = dispy.DispyJob(args, ())
                try:
                    job.result = self.function(*args)
                    if self.progress_bar is not None:
                        self.progress_bar.update()
                except Exception as e:
                    job.exception = e
                self.callback(job)
            else:
                self.function(*args)

    def wait(self):
        """
        wrapped function to wait for cluster execution
        :return: none
        """
        if self.run_parallel:
            tqdm.write(' -- Waiting for jobs to finish...')
            try:
                self.cluster.wait()
                # let the process trigger cluster_status before letting the calling proc close the progress bar
                time.sleep(DELAY)
            except KeyboardInterrupt:
                for job in self.jobs:
                    if job.status in (dispy.DispyJob.Running, dispy.DispyJob.Created):
                        self.cluster.cancel(job)
                self.cluster.shutdown()

    def close_cluster(self):
        if self.run_parallel and self.close:
            tqdm.write('')
            self.http_server.shutdown()
            self.cleanup()

    def cluster_status(self, status, node, job):

        # update the status in the http_server
        self.http_server.cluster_status(self.http_server._clusters[self.cluster.name], status, node, job)

        if status == dispy.DispyNode.Initialized:
            tqdm.write(' -- Node %s initialized with %i CPUs' % (node.name, node.avail_cpus))
            # test node to make sure everything works
            self.cluster.send_file('gnss_data.cfg', node)
            self.nodes.append(node)
            return

        if job is not None:
            if status == dispy.DispyJob.Finished and self.verbose:
                tqdm.write(' -- Job %i finished successfully' % job.id)

            elif status == dispy.DispyJob.Abandoned:
                # always print abandoned jobs
                tqdm.write(' -- Job %i was reported as abandoned -> resubmitting' % job.id)

            elif status == dispy.DispyJob.Created and self.verbose:
                tqdm.write(' -- Job %i has been created' % job.id)

            elif status == dispy.DispyJob.Terminated and self.verbose:
                tqdm.write(' -- Job %i has been terminated' % job.id)

            if status in (dispy.DispyJob.Finished, dispy.DispyJob.Terminated) and self.progress_bar is not None:
                self.progress_bar.update()

    def cleanup(self):
        if self.run_parallel and self.close:
            self.cluster.print_status()
            self.cluster.close()
            self.close = False

    def __del__(self):
        self.cleanup()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()

    def __enter__(self):
        return self
