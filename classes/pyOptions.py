"""
Project: Parallel.Archive
Date: 3/21/17 5:36 PM
Author: Demian D. Gomez

Class with all the configuration information necessary to run many of the scripts. It loads the config file (gnss_data.cfg).
"""

import configparser
import os

# app
from Utils import process_date, file_open
from pyDate import Date


class ReadOptions:
    def __init__(self, configfile):

        self.options = {'path'             : None,
                        'repository'       : None,
                        'parallel'         : False,
                        'cups'             : None,
                        'node_list'        : None,
                        'ip_address'       : None,
                        'brdc'             : None,
                        'sp3_type_1'       : None,
                        'sp3_type_2'       : None,
                        'sp3_type_3'       : None,
                        'sp3_altr_1'       : None,
                        'sp3_altr_2'       : None,
                        'sp3_altr_3'       : None,
                        'grdtab'           : None,
                        'otlgrid'          : None,
                        'otlmodel'         : 'FES2014b',
                        'ppp_path'         : None,
                        'institution'      : None,
                        'info'             : None,
                        'sp3'              : None,
                        'frames'           : None,
                        'atx'              : None,
                        'height_codes'     : None,
                        'ppp_exe'          : None,
                        'ppp_remote_local' : ()}

        config = configparser.ConfigParser()
        with file_open(configfile) as f:
            config.read_file(f)

        # get the archive config
        self.options.update(dict(config.items('archive')))

        # get the otl config
        self.options.update(dict(config.items('otl')))

        # get the ppp config
        for iconfig, val in dict(config.items('ppp')).items():
            self.options[iconfig] = os.path.expandvars(val).replace('//', '/')

        # frames and dates
        frames = [item.strip() for item in self.options['frames'].split(',')]
        atx    = [item.strip() for item in self.options['atx'].split(',')]

        self.Frames = []

        for frame, atx in zip(frames, atx):
            date = process_date(self.options[frame.lower()].split(','))
            self.Frames += [{'name' : frame,
                             'atx'  : atx,
                             'dates': (Date(year=date[0].year, doy=date[0].doy, hour=0 , minute=0,  second=0),
                                       Date(year=date[1].year, doy=date[1].doy, hour=23, minute=59, second=59))}]

        self.options['frames'] = self.Frames

        self.archive_path = self.options['path']
        self.sp3_path     = self.options['sp3']
        self.brdc_path    = self.options['brdc']
        self.repository   = self.options['repository']

        self.repository_data_in       = os.path.join(self.repository, 'data_in')
        self.repository_data_in_retry = os.path.join(self.repository, 'data_in_retry')
        self.repository_data_reject   = os.path.join(self.repository, 'data_rejected')


        self.sp3types = [self.options[k] for k in ('sp3_type_1', 'sp3_type_2', 'sp3_type_3') if self.options[k] is not None]
        # alternative sp3 types
        self.sp3altrn = [self.options[k] for k in ('sp3_altr_1', 'sp3_altr_2', 'sp3_altr_3') if self.options[k] is not None]

        self.run_parallel = (self.options['parallel'] == 'True')

