"""
Project:
Date: 3/31/17 5:28 PM
Author: Demian D. Gomez
"""

from pyOptions import ReadOptions
import ConfigParser
import os

class pyGamitConfigException(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return str(self.value)

class GamitConfiguration(ReadOptions):

    def __init__(self, session_config_file):

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
            self.gamitopt['working_dir']      = None
            self.gamitopt['atx']              = None
            self.gamitopt['max_cores']        = 1
            self.gamitopt['noftp']            = 'yes'

            self.NetworkConfig = None

            self.load_session_config(session_config_file)

            ReadOptions.__init__(self, self.gamitopt['gnss_data']) # type: ReadOptions

        except:
            raise

    def load_session_config(self,session_config_file):

        try:
            # parse session config file
            config = ConfigParser.ConfigParser()
            config.readfp(open(session_config_file))

            # check that all required items are there and files exist
            self.__check_config(config, session_config_file)

            # get gamit config items from session config file
            for iconfig,val in dict(config.items('gamit')).iteritems():
                self.gamitopt[iconfig] = val

            self.NetworkConfig = dict(config.items('network'))

            self.gamitopt['gnss_data'] = config.get('Archive','gnss_data')
            self.gamitopt['max_cores'] = int(self.gamitopt['max_cores'])

            # TO-DO: check that all the required parameters are present

        except ConfigParser.NoOptionError:
            raise


    def __check_config(self, config, sess_config_file):
        try:
            item = config.get('gamit','process_defaults')
            if not os.path.isfile(item):
                raise pyGamitConfigException('process_defaults file '+item+' could not be found')
        except:
            raise

        try:
            item = config.get('gamit','sestbl')
            if not os.path.isfile(item):
                raise pyGamitConfigException('sestbl file '+item+' could not be found')
        except:
            raise

        try:
            item = config.get('gamit','atx')
            if not os.path.isfile(item):
                raise pyGamitConfigException('atx file '+item+' could not be found')
        except:
            raise

        return