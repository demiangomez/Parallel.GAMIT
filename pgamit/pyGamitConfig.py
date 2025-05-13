"""
Project:
Date: 3/31/17 5:28 PM
Author: Demian D. Gomez
"""

import configparser
import os

# app
from pgamit.pyOptions import ReadOptions
from pgamit import pyBunch
from pgamit.Utils import file_open


class pyGamitConfigException(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return str(self.value)


class GamitConfiguration(ReadOptions):

    def __init__(self, session_config_file, check_config=True):
        self.gamitopt = {'gnss_data'          : None,
                         'eop_type'           : 'usno',
                         'expt_type'          : 'baseline',
                         'systems'            : ['G', 'E', 'R'],
                         'should_iterate'     : 'yes',
                         'org'                : 'IGN',
                         'expt'               : 'expt',
                         'overconst_action'   : 'inflate',
                         'process_defaults'   : None,
                         'sestbl'             : None,
                         'solutions_dir'      : None,
                         'max_cores'          : 1,
                         'noftp'              : 'yes',
                         'sigma_floor_h'      : 0.10,
                         'sigma_floor_v'      : 0.15,
                         'gamit_remote_local' : ()}

        self.NetworkConfig = None
        
        self.load_session_config(session_config_file, check_config)
        
        ReadOptions.__init__(self, self.gamitopt['gnss_data'])  # type: ReadOptions

    def load_session_config(self, session_config_file, check_config):
        try:
            # parse session config file
            config = configparser.ConfigParser()
            with file_open(session_config_file) as f:
                config.read_file(f)

            # check that all required items are there and files exist
            if check_config:
                self.__check_config(config)

            # get gamit config items from session config file
            self.gamitopt.update(dict(config.items('gamit')))

            if type(self.gamitopt['systems']) is str:
                # only if config parameter was given
                self.gamitopt['systems'] = [item.strip() for item in self.gamitopt['systems'].strip(',').split(',')]

            self.NetworkConfig = pyBunch.Bunch().fromDict(dict(config.items('network')))

            if 'type' not in self.NetworkConfig.keys():
                raise ValueError('Network "type" must be specified in config file: use "regional" or "global"')

            if 'cluster_size' not in self.NetworkConfig.keys():
                self.NetworkConfig.cluster_size = '25'

            if 'ties' not in self.NetworkConfig.keys():
                self.NetworkConfig.ties = '4'

            if 'algorithm' not in self.NetworkConfig.keys():
                self.NetworkConfig.algorithm = 'qmeans'

            if self.NetworkConfig.algorithm.lower() not in ('qmeans', 'agglomerative'):
                raise ValueError('Invalid clustering algorithm, options are qmeans or agglomerative.')

            self.gamitopt['gnss_data'] = config.get('Archive', 'gnss_data')
            self.gamitopt['max_cores'] = int(self.gamitopt['max_cores'])

            # TO-DO: check that all the required parameters are present
            if len(self.gamitopt['expt']) != 4:
                raise ValueError('The experiment name parameter must be 4 characters long.')

        except configparser.NoOptionError:
            raise

    @staticmethod
    def __check_config(config):

        item = config.get('gamit', 'process_defaults')
        if not os.path.isfile(item):
            raise pyGamitConfigException('process_defaults file '+item+' could not be found')

        item = config.get('gamit', 'sestbl')
        if not os.path.isfile(item):
            raise pyGamitConfigException('sestbl file '+item+' could not be found')

        try:
            item = config.get('gamit', 'overconst_action')
            if item not in ('relax', 'inflate', 'delete', 'remove'):
                raise pyGamitConfigException('overconst_action accepts the following options: '
                                             'relax or inflate, and delete or remove')
        except configparser.NoOptionError:
            raise pyGamitConfigException('overconst_action not present. Option accepts the following: '
                                         'relax or inflate, and delete or remove')

        # item = config.get('gamit','atx')
        # if not os.path.isfile(item):
        #    raise pyGamitConfigException('atx file '+item+' could not be found')
