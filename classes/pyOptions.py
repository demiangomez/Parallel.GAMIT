"""
Project: Parallel.Archive
Date: 3/21/17 5:36 PM
Author: Demian D. Gomez

Class with all the configuration information necessary to run many of the scripts. It loads the config file (gnss_data.cfg).
"""

import ConfigParser
import os
from Utils import process_date
from pyDate import Date


class ReadOptions:
    def __init__(self, configfile):

        self.options = {'path': None,
                        'repository': None,
                        'parallel': False,
                        'cups': None,
                        'node_list': None,
                        'brdc': None,
                        'sp3_type_1': None,
                        'sp3_type_2': None,
                        'sp3_type_3': None,
                        'sp3_altr_1': None,
                        'sp3_altr_2': None,
                        'sp3_altr_3': None,
                        'grdtab': None,
                        'otlgrid': None,
                        'otlmodel': 'FES2014b',
                        'ppp_path': None,
                        'institution': None,
                        'info': None,
                        'sp3': None,
                        'frames': None,
                        'atx': None,
                        'height_codes': None,
                        'ppp_exe': None}

        config = ConfigParser.ConfigParser()
        config.readfp(open(configfile))

        # get the archive config
        for iconfig, val in dict(config.items('archive')).iteritems():
            self.options[iconfig] = val

        # get the otl config
        for iconfig, val in dict(config.items('otl')).iteritems():
            self.options[iconfig] = val

        # get the ppp config
        for iconfig, val in dict(config.items('ppp')).iteritems():
            self.options[iconfig] = val

        # get the sigma floor config
        # for iconfig, val in dict(config.items('sigmas')).iteritems():
        #    self.options[iconfig] = val

        # frames and dates
        frames = [item.strip() for item in self.options['frames'].split(',')]
        atx = [item.strip() for item in self.options['atx'].split(',')]

        self.Frames = []

        for frame, atx in zip(frames, atx):
            date = process_date(self.options[frame.lower()].split(','))
            self.Frames += [{'name': frame, 'atx': atx, 'dates':
                                    (Date(year=date[0].year, doy=date[0].doy, hour=0, minute=0, second=0),
                                    Date(year=date[1].year, doy=date[1].doy, hour=23, minute=59, second=59))}]

        self.options['frames'] = self.Frames

        self.archive_path = self.options['path']
        self.sp3_path     = self.options['sp3']
        self.brdc_path    = self.options['brdc']
        self.repository   = self.options['repository']

        self.repository_data_in = os.path.join(self.repository,'data_in')
        self.repository_data_in_retry = os.path.join(self.repository, 'data_in_retry')
        self.repository_data_reject = os.path.join(self.repository, 'data_rejected')

        self.sp3types = [self.options['sp3_type_1'], self.options['sp3_type_2'], self.options['sp3_type_3']]

        self.sp3types = [sp3type for sp3type in self.sp3types if sp3type is not None]

        # alternative sp3 types
        self.sp3altrn = [self.options['sp3_altr_1'], self.options['sp3_altr_2'], self.options['sp3_altr_3']]

        self.sp3altrn = [sp3alter for sp3alter in self.sp3altrn if sp3alter is not None]

        if self.options['parallel'] == 'True':
            self.run_parallel = True
        else:
            self.run_parallel = False

        if 'height_codes' not in self.options.keys():
            raise ValueError('Must specify a valid height codes file (usually in gamit/tables/hi.dat)')
        elif not os.path.isfile(self.options['height_codes']):
            raise ValueError('Could not find height codes file (usually in gamit/tables/hi.dat)')

        return
