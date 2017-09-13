"""
Project: Parallel.GAMIT
Date: Mar-31-2017
Author: Demian D. Gomez
"""

from pyStation import Station
from pyStation import StationInstance
from pyGamitSession import GamitSession
from pyStationInfo import pyStationInfoException
from tqdm import tqdm
import numpy as np
import random
import sys
import os
import glob
import re

NET_LIMIT    = 40
MIN_CORE_NET = 10

class NetworkException(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return str(self.value)

class NetClass():

    def __init__(self, cnn, name, stations, year, doys, core=None):
        # the purpose of core is to avoid adding a station to a subnet that is already in the core

        try:
            self.Name = name.lower()
            self.Stations = []
            self.StrStns  = []

            # use the connection to the db to get the stations
            for stn in tqdm(sorted(stations.lower().split(',')), ncols=80):
                Stn = stn.strip()
                # find the station

                if '.' in Stn:
                    # NetworkCode specified, no ambiguities
                    NetworkCode = Stn.split('.')[0]
                    StationCode = Stn.split('.')[1]

                    rs = cnn.query('SELECT * FROM rinex WHERE "NetworkCode" = \'%s\' AND "StationCode" = \'%s\' AND "NetworkCode" not like \'?%%\'' % (NetworkCode, StationCode))

                    if rs.ntuples() == 1:
                        found = True
                    else:
                        tqdm.write(' -- %s -> %s: not found' % (self.Name, Stn))
                        found = False
                else:
                    rs = cnn.query('SELECT * FROM stations WHERE "StationCode" = \'%s\' AND "NetworkCode" not like \'?%%\'' % (Stn))

                    if rs.ntuples() == 1:
                        stntbl = rs.dictresult()[0]

                        NetworkCode = stntbl['NetworkCode']
                        StationCode = stntbl['StationCode']

                        found = True
                    elif rs.ntuples() == 0:
                        tqdm.write(' -- %s -> ___.%s: not found' % (self.Name, Stn))
                        found = False
                    else:
                        raise NetworkException('Station %s had no assined network, but more than one station with that name was found in the database. Disambiguate using net.stn format.'
                                               % (Stn))

                if found:
                    rs = cnn.query('SELECT * FROM rinex WHERE "NetworkCode" = \'%s\' AND "StationCode" = \'%s\' AND "ObservationYear" = %i AND "ObservationDOY" IN (%s)'
                                   % (NetworkCode, StationCode, year, ','.join([str(doy) for doy in doys])))

                    if rs.ntuples() > 0:
                        if core:
                            # if a core lists is present, and the station is in it, do not add it
                            if '%s.%s' % (NetworkCode, StationCode) in core:
                                continue

                        tqdm.write(' -- %s -> %s.%s: adding...' % (self.Name, NetworkCode, StationCode))

                        self.Stations.append(Station(cnn, NetworkCode, StationCode))
                        # make also a list of string values
                        self.StrStns.append('%s.%s' % (NetworkCode, StationCode))
                    else:
                        tqdm.write(' -- %s -> %s.%s: no data for requested time window' % (self.Name, NetworkCode,StationCode))

                sys.stdout.flush()

        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            raise

        return


class Network():

    def __init__(self, cnn, NetworkConfig, year, doys):

        try:
            self.Name = NetworkConfig['network_id'].lower()

            self.Core = NetClass(cnn, self.Name, NetworkConfig['stn_core'], year, doys)

            self.Secondary = NetClass(cnn, self.Name + '.Secondary', NetworkConfig['stn_list'], year, doys, self.Core.StrStns)

            # create a StationAlias if needed, if not, just assign StationCode
            self.AllStations = []
            for Station in self.Core.Stations + self.Secondary.Stations:
                self.CheckStationCodes(Station)
                if [Station.NetworkCode, Station.StationCode] not in [[stn['NetworkCode'], stn['StationCode']] for stn in self.AllStations]:
                    self.AllStations.append({'NetworkCode': Station.NetworkCode, 'StationCode': Station.StationCode, 'StationAlias': Station.StationAlias})

            self.total_stations = len(self.Core.Stations) + len(self.Secondary.Stations)

            sys.stdout.write('\n >> Total number of stations: %i (including core)\n\n' % (self.total_stations))

        except:
            raise

        return

    def CreateGamitSessions(self, cnn, date, GamitConfig):
        """
        analyzes the core NetClass and secondary NetClass for the processing day and makes sure that:
        1) the total station count is <= NET_LIMIT. If it's > NET_LIMIT, splits the stations into two or more subnetworks both
           containing the Core stations.
        2) If the stations were split into subnetworks, then it verifies that there are at least 10 Core stations for
           that day. If there aren't, it promotes stations from the Secondary as Core

        :return: list
        """

        # first, generate the station instances
        # instantiate the Core stations
        CoreStationInstances = []
        Core_missing_data    = []
        for stn in self.Core.Stations:
            # check that this station exists and that we have data for the day
            rs = cnn.query(
                'SELECT * FROM rinex WHERE "NetworkCode" = \'%s\' AND "StationCode" = \'%s\' AND "ObservationYear" = %s AND "ObservationDOY" = %i' % (
                stn.NetworkCode, stn.StationCode, date.yyyy(), int(date.doy)))

            if rs.ntuples() > 0:
                # do not create instance if we don't have a rinex
                try:
                    CoreStationInstances.append(StationInstance(cnn, stn, date, GamitConfig.archive_path))
                except pyStationInfoException:
                    Core_missing_data.append({'NetworkCode': stn.NetworkCode, 'StationCode': stn.StationCode, 'date': date})
            else:
                Core_missing_data.append({'NetworkCode': stn.NetworkCode, 'StationCode': stn.StationCode, 'date': date})


        # now instantiate the secondary stations
        SecondaryStationInstances = []
        Secondary_missing_data = []
        for stn in self.Secondary.Stations:
            # check that this station exists and that we have data for the day
            rs = cnn.query(
                'SELECT * FROM rinex WHERE "NetworkCode" = \'%s\' AND "StationCode" = \'%s\' AND "ObservationYear" = %s AND "ObservationDOY" = %i' % (
                    stn.NetworkCode, stn.StationCode, date.yyyy(), int(date.doy)))

            if rs.ntuples() > 0:
                # do not create instance if we don't have a rinex
                try:
                    SecondaryStationInstances.append(StationInstance(cnn, stn, date, GamitConfig.archive_path))
                except pyStationInfoException:
                    Secondary_missing_data.append({'NetworkCode': stn.NetworkCode, 'StationCode': stn.StationCode, 'date': date})
            else:
                Secondary_missing_data.append({'NetworkCode': stn.NetworkCode, 'StationCode': stn.StationCode, 'date': date})


        MissingData = Core_missing_data + Secondary_missing_data


        # now we can study the size of this potential session
        if len(SecondaryStationInstances + CoreStationInstances) <= NET_LIMIT:

            # before creating the session, does this session exist and has a glx in glbf already?
            pwd = GamitConfig.gamitopt['working_dir'].rstrip('/') + '/' + date.yyyy() + '/' + date.ddd() + '/' + self.Name

            ready, recovered_StationInstances = self.check_subnets_ready([pwd], SecondaryStationInstances + CoreStationInstances)

            if ready:
                StationInstances = recovered_StationInstances[0]
            else:
                StationInstances = SecondaryStationInstances + CoreStationInstances

            # we can join all stations into a single GamitSession
            return [GamitSession(self.Name, date, GamitConfig, StationInstances, ready)], MissingData
        else:

            # too many stations for a single GamitSession, split into subnetworks
            # determine how many subnets we need
            stn_count = len(SecondaryStationInstances + CoreStationInstances)
            subnet_count = int(np.ceil(float(float(stn_count) / float(NET_LIMIT))))

            # before creating the session, does the session exist and has a glx in glbf already?
            # if one subnet is not ready, all session will be discarded
            pwds = []
            for i in range(subnet_count):
                pwds.append(GamitConfig.gamitopt['working_dir'].rstrip('/') + '/' + date.yyyy() + '/' + date.ddd() + '/' + self.Name + '.' + GamitConfig.gamitopt['org'] + str(i).rjust(2, '0'))

            ready, recovered_StationInstances = self.check_subnets_ready(pwds, SecondaryStationInstances + CoreStationInstances)

            if ready:
                # solution is ready, SubnetInstances has all the original stations and station aliases + core stations
                SubnetInstances = recovered_StationInstances
            else:
                # check we have at least 10 stations in the core. If we don't, move some stations from Secondary to Core
                if len(CoreStationInstances) < MIN_CORE_NET:
                    add_core = random.sample(SecondaryStationInstances, MIN_CORE_NET - len(CoreStationInstances))
                    # move add_core stations from Secondary to Core
                    CoreStationInstances += add_core
                    SecondaryStationInstances = [item for item in SecondaryStationInstances if item not in add_core]

                # divide the SecondaryStationInstances into subnets
                SubnetInstances = self.partition(SecondaryStationInstances, subnet_count)

                # add the core stations to each subnet
                for Subnet in SubnetInstances:
                    Subnet += CoreStationInstances

            # return the list of GamitSessions
            return [GamitSession(self.Name + '.' + GamitConfig.gamitopt['org'] + str(i).rjust(2,'0'), date, GamitConfig, Subnet, ready) for i,Subnet in enumerate(SubnetInstances)], MissingData


    def check_subnets_ready(self, pwds, StationInstances):

        recovered_station_inst = []

        pattern = re.compile('^\d+-\d+-\d+\s\d+:\d+:\d+\s->\s\w+\s\w+\s\w+\s(\w+.\w+)\s(\w+).*$')

        ready = False

        for pwd in pwds:
            # loop through the directories of sessions/subnets
            stn_list = []
            if os.path.exists(pwd + '/glbf'):
                # look for *.glx* in case the file was compressed
                if glob.glob(pwd + '/glbf/*.glx*'):
                    # read the station list from monitor.log
                    with open(pwd + '/monitor.log', 'r') as monitor:
                        for line in monitor:
                            stn = pattern.findall(line)
                            if stn:
                                stn_list.append({'Net.Stn': stn[0][0], 'StationAlias': stn[0][1]})

                            if '-> executing GAMIT' in line:
                                # this indicated that all the stations were added and that this is not a truncated
                                # session due to an error. If this line is not present, redo the whole thing
                                ready = True
                                break

                    recovered_station_inst.append(stn_list)
                else:
                    ready = False
                    break
            else:
                ready = False
                break

        SubnetInstances = []

        if ready and recovered_station_inst:
            # if all the pwds are ready and the recovered station instances is not empty
            for subnet in recovered_station_inst:
                RStationInst = []
                # of each station dict in recovered_station_inst
                for Station in subnet:
                    # loop through the station instances that where passed by parent
                    for StationInstance in StationInstances:
                        if StationInstance.Station.NetworkCode + '.' + StationInstance.Station.StationCode == Station['Net.Stn']:
                            # change station alias if necessary to match the original StationAlias used for processing
                            # the station alias is randomly generated at the initialization of the Network object
                            # but is unique for all instances/subnets/sessions, so it's OK to change it if different
                            if StationInstance.Station.StationAlias != Station['StationAlias']:
                                StationInstance.Station.StationAlias = Station['StationAlias']

                            RStationInst.append(StationInstance)
                            break

                # create the StationInstance List
                SubnetInstances.append(RStationInst)

        elif ready and not recovered_station_inst:
            ready = False

        return ready, SubnetInstances

    def partition(self, lst, n):
        division = len(lst) / float(n)
        return [lst[int(round(division * i)): int(round(division * (i + 1)))] for i in xrange(n)]

    def CheckStationCodes(self, Station):

        for NetStn in self.AllStations:
            if NetStn['NetworkCode'] != Station.NetworkCode and NetStn['StationCode'] == Station.StationCode:
                # duplicate StationCode (different Network), produce Alias
                unique = False
                while not unique:
                    Station.GenerateStationAlias()
                    # compare again to make sure this name is unique
                    unique = self.CompareAliases(Station, [NetStnAl['StationAlias'] for NetStnAl in self.AllStations])

        return

    def CompareAliases(self, Station, AllAliasStations):

        for NetStnAl in AllAliasStations:

            # this if prevents comparing against myself, although the station is not added until after
            # the call to CompareAliases. But, just in case...
            if NetStnAl['StationCode'] != Station.StationCode and NetStnAl['NetworkCode'] != Station.NetworkCode and \
                            Station.StationAlias == NetStnAl['StationAlias']:
                # not unique!
                return False

        return True