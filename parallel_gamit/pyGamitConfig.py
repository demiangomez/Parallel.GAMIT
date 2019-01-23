"""
Project:
Date: 3/31/17 5:28 PM
Author: Demian D. Gomez
"""

from pyOptions import ReadOptions
import ConfigParser
import os
import pyBunch


class pyGamitConfigException(Exception):

    def __init__(self, value):
        self.value = value

    def __str__(self):
        return str(self.value)


class GamitConfiguration(ReadOptions):

    def __init__(self, session_config_file, check_config=True):

        try:
            self.gamitopt = dict()

            self.gamitopt['gnss_data']        = None
            self.gamitopt['eop_type']         = 'usno'
            self.gamitopt['expt_type']        = 'baseline'
            self.gamitopt['should_iterate']   = 'yes'
            self.gamitopt['org']              = 'IGN'
            self.gamitopt['expt']             = 'expt'
            self.gamitopt['process_defaults'] = None
            self.gamitopt['sestbl']           = None
            self.gamitopt['solutions_dir']    = None
            self.gamitopt['max_cores']        = 1
            self.gamitopt['noftp']            = 'yes'
            self.gamitopt['sigma_floor_h']    = 0.10
            self.gamitopt['sigma_floor_v']    = 0.15

            self.NetworkConfig = None

            self.load_session_config(session_config_file, check_config)

            ReadOptions.__init__(self, self.gamitopt['gnss_data'])  # type: ReadOptions

        except Exception:
            raise

    def load_session_config(self, session_config_file, check_config):

        try:
            # parse session config file
            config = ConfigParser.ConfigParser()
            config.readfp(open(session_config_file))

            # check that all required items are there and files exist
            if check_config:
                self.__check_config(config)

            # get gamit config items from session config file
            for iconfig, val in dict(config.items('gamit')).iteritems():
                self.gamitopt[iconfig] = val

            self.NetworkConfig = pyBunch.Bunch().fromDict(dict(config.items('network')))

            if 'type' not in self.NetworkConfig.keys():
                raise ValueError('Network "type" must be specified in config file: use "regional" or "global"')

            self.gamitopt['gnss_data'] = config.get('Archive', 'gnss_data')
            self.gamitopt['max_cores'] = int(self.gamitopt['max_cores'])

            # TO-DO: check that all the required parameters are present
            if len(self.gamitopt['expt']) != 4:
                raise ValueError('The experiment name parameter must be 4 characters long.')

        except ConfigParser.NoOptionError:
            raise

    @staticmethod
    def __check_config(config):

        item = config.get('gamit', 'process_defaults')
        if not os.path.isfile(item):
            raise pyGamitConfigException('process_defaults file '+item+' could not be found')

        item = config.get('gamit', 'sestbl')
        if not os.path.isfile(item):
            raise pyGamitConfigException('sestbl file '+item+' could not be found')

        # item = config.get('gamit','atx')
        # if not os.path.isfile(item):
        #    raise pyGamitConfigException('atx file '+item+' could not be found')
