"""
Project: Parallel.GAMIT
Date: 4/3/17 6:57 PM
Author: Demian D. Gomez
"""

import os
from shutil import copyfile, rmtree

# deps
import simplekml
from tqdm import tqdm

# app
import pyRinexName
from pyStation import StationInstance
from Utils import determine_frame, file_open, stationID, chmod_exec
import pyGamitConfig
import snxParse


class GamitSessionException(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)


class GamitSession(object):

    def __init__(self, cnn, archive, name, org, subnet, date, GamitConfig, stations, ties=(), centroid=()):
        """
        The GAMIT session object creates all the directory structure and configuration files according to the parameters
        set in GamitConfig. Two stations list are passed and merged to create the session
        :param cnn: connection to database object
        :param archive: archive object to find rinex files in archive structure
        :param name: name of the project/network
        :param org: name of the organization
        :param subnet: subnet number (may be None, in which case the directory name will not show ORGXX
        :param date: date that is being processed
        :param GamitConfig: configuration to run gamit
        :param stations: list of stations to be processed
        :param ties: tie stations as obtained by pyNetwork
        """
        self.NetName = name
        self.org     = org
        self.subnet  = subnet

        if subnet is not None:
            self.DirName = '%s.%s%02i' % (self.NetName, self.org, self.subnet)
        else:
            self.DirName = self.NetName

        self.date           = date
        self.GamitOpts      = GamitConfig.gamitopt  # type: pyGamitConfig.GamitConfiguration().gamitopt
        self.Config         = GamitConfig           # type: pyGamitConfig.GamitConfiguration
        self.frame          = None
        self.params         = None
        # to store the polyhedron read from the final SINEX
        self.polyhedron     = None
        self.VarianceFactor = None
        # gamit task will be filled with the GamitTask object
        self.GamitTask      = None

        self.solution_base = self.GamitOpts['solutions_dir'].rstrip('/')

        # tie station dictionary (to build KMLs, do not change)
        self.tie_dict = [{'name'  : stationID(stn),
                          'coords': [(stn.lon, stn.lat)]}
                         for stn in ties]

        # station dictionary (to build KMLs, do not change)
        self.stations_dict = [{'name'   : stationID(stn),
                               'coords' : [(stn.lon, stn.lat)]}
                              for stn in stations]

        # make StationInstances
        station_instances = []
        for stn in stations:
            try:
                station_instances += [StationInstance(cnn, archive, stn, date, GamitConfig)]
            except pyRinexName.RinexNameException:
                tqdm.write(' -- WARNING (station instance): station %s on day %s appears to have a badly formed RINEX '
                           'filename. Please check the archive and make sure all filenames follow the RINEX 2/3 '
                           'convention. Station has been excluded from the GAMIT session.'
                           % (stationID(stn), date.yyyyddd()))

        # do the same with ties
        for stn in ties:
            try:
                station_instances += [StationInstance(cnn, archive, stn, date, GamitConfig, is_tie=True)]
            except pyRinexName.RinexNameException:
                tqdm.write(' -- WARNING (tie instance): station %s on day %s appears to have a badly formed RINEX '
                           'filename. Please check the archive and make sure all filenames follow the RINEX 2/3 '
                           'convention. Station has been excluded from the GAMIT session.'
                           % (stationID(stn), date.yyyyddd()))

        self.StationInstances = station_instances

        # create working dirs for this session
        last_path = '/%s/%s/%s' % (date.yyyy(), date.ddd(), self.DirName)
        self.solution_pwd = self.solution_base + last_path
        # the remote pwd is the directory where the processing will be performed
        self.remote_pwd   = 'production/gamit' + last_path

        row_key = {'Year'    : date.year,
                   'DOY'     : date.doy,
                   'Project' : self.NetName,
                   'subnet'  : 0 if subnet is None else subnet}

        try:
            # attempt to retrieve the session from the database. If error is raised, then the session has to be
            # reprocessed
            cnn.get('gamit_stats', row_key.copy())
            self.ready = True
        except:
            self.ready = False

            try:
                # since ready == False, then try to delete record in subnets
                cnn.delete('gamit_subnets', row_key.copy())
            except:
                pass

        # a list to report missing data for this session
        self.missing_data = []

        if not os.path.exists(self.solution_pwd):
            # if the path does not exist, create it!
            os.makedirs(self.solution_pwd)
            # force ready = False, no matter what the database says
            self.ready = False
            try:
                cnn.delete('gamit_stats',   row_key.copy())
                cnn.delete('gamit_subnets', row_key.copy())
            except:
                pass

        elif os.path.exists(self.solution_pwd) and not self.ready:
            # if the solution directory exists but the session is not ready, kill the directory
            rmtree(self.solution_pwd)

        if not self.ready:
            # insert the subnet in the database
            cnn.insert('gamit_subnets', {**row_key,
                                         'stations' : '{%s}' % ','.join(stationID(s)   for s in stations + list(ties)),
                                         'alias'    : '{%s}' % ','.join(s.StationAlias for s in stations + list(ties)),
                                         'ties'     : '{%s}' % ','.join(s['name']      for s in self.tie_dict),
                                         'centroid' : '{%s}' % ','.join('%.1f' % c     for c in centroid)})

        self.pwd_igs    = os.path.join(self.solution_pwd, 'igs')
        self.pwd_brdc   = os.path.join(self.solution_pwd, 'brdc')
        self.pwd_rinex  = os.path.join(self.solution_pwd, 'rinex')
        self.pwd_tables = os.path.join(self.solution_pwd, 'tables')
        self.pwd_glbf   = os.path.join(self.solution_pwd, 'glbf')
        self.pwd_proc   = os.path.join(self.solution_pwd, date.ddd())

        if not self.ready:
            # only create folders, etc if it was determined the solution isn't ready
            if not os.path.exists(self.pwd_igs):
                os.makedirs(self.pwd_igs)

            if not os.path.exists(self.pwd_brdc):
                os.makedirs(self.pwd_brdc)

            if os.path.exists(self.pwd_rinex):
                # delete any possible rinex files from a truncated session
                rmtree(self.pwd_rinex)
            os.makedirs(self.pwd_rinex)

            if not os.path.exists(self.pwd_tables):
                os.makedirs(self.pwd_tables)

            # check that the processing directory doesn't exist.
            # if it does, remove (it has already been determined that the solution is not ready
            if os.path.exists(self.pwd_glbf):
                rmtree(self.pwd_glbf)

            if os.path.exists(self.pwd_proc):
                rmtree(self.pwd_proc)

            self.generate_kml()

    def initialize(self):
        if not self.ready:
            # create the station.info
            self.create_station_info()

            self.create_apr_sittbl_file()

            self.copy_sestbl_procdef_atx()

            self.link_tables()

            self.create_sitedef()

            self.create_otl_list()

        # ready to copy the RINEX files
        rinex_list = self.get_rinex_filenames()

        self.params = {'solution_pwd': self.solution_pwd,
                       'remote_pwd'  : self.remote_pwd,
                       'NetName'     : self.NetName,
                       'DirName'     : self.DirName,
                       'subnet'      : self.subnet if self.subnet is not None else 0,
                       'rinex'       : rinex_list,
                       'date'        : self.date,
                       'options'     : self.Config.options,
                       'gamitopts'   : self.GamitOpts,
                       'orbits'      : {'sp3_path'  : self.Config.sp3_path,
                                        'sp3types'  : self.Config.sp3types,
                                        'sp3altrn'  : (),
                                        'brdc_path' : self.Config.brdc_path,
                                        'ionex_path': self.Config.ionex_path
                                        }
                       }

    def create_otl_list(self):

        otl_path = os.path.join(self.pwd_tables, 'otl.list')
        if os.path.isfile(otl_path):
            os.remove(otl_path)

        with file_open(otl_path, 'w') as otl_list:
            otl_list.write('%s   8-character GAMIT ID read by grdtab (M -> CM)\n' % (self.Config.options['otlmodel']))
            otl_list.write("""$$ Ocean loading displacement
$$
$$ Calculated on holt using olfg/olmpp of H.-G. Scherneck
$$
$$ COLUMN ORDER:  M2  S2  N2  K2  K1  O1  P1  Q1  MF  MM SSA
$$
$$ ROW ORDER:
$$ AMPLITUDES (m)
$$   RADIAL
$$   TANGENTL    EW
$$   TANGENTL    NS
$$ PHASES (degrees)
$$   RADIAL
$$   TANGENTL    EW
$$   TANGENTL    NS
$$
$$ Displacement is defined positive in upwards, South and West direction.
$$ The phase lag is relative to Greenwich and lags positive. The
$$ Gutenberg-Bullen Greens function is used. In the ocean tide model the
$$ deficit of tidal water mass has been corrected by subtracting a uniform
$$ layer of water with a certain phase lag globally.
$$
$$ Complete <model name> : No interpolation of ocean model was necessary
$$ <model name>_PP       : Ocean model has been interpolated near the station
$$                         (PP = Post-Processing)
$$
$$ CMC:  YES  (corr.tide centre of mass)
$$
$$ Ocean tide model: %s
$$
$$ END HEADER
$$\n""" % (self.Config.options['otlmodel']))

            for stn in self.StationInstances:
                otl = stn.otl_H.split('\n')
                # remove BLQ header
                otl = otl[29:]
                # need to change the station record for GAMIT to take it
                otl[0] = '  %s' % stn.StationAlias.upper()
                if stn.lon < 0:
                    lon = 360+stn.lon
                else:
                    lon = stn.lon
                otl[3] = '$$ %s                                 RADI TANG lon/lat:%10.4f%10.4f' \
                         % (stn.StationAlias.upper(), lon, stn.lat)

                otl_list.write('\n'.join(otl))

            # write BLQ format termination
            otl_list.write("$$ END TABLE\n")

    def create_station_info(self):

        # delete any current station.info files
        station_path = os.path.join(self.pwd_tables, 'station.info')
        if os.path.isfile(station_path):
            os.remove(station_path)

        with file_open(station_path, 'w') as stninfo_file:
            stninfo_file.write('*SITE  Station Name      Session Start      Session Stop       Ant Ht   HtCod  '
                               'Ant N    Ant E    Receiver Type         Vers                  SwVer  '
                               'Receiver SN           Antenna Type     Dome   Antenna SN          \n')

            for stn in self.StationInstances:
                # stninfo_file.write(stn.StationInfo.return_stninfo() + '\n')
                stninfo_file.write(stn.GetStationInformation() + '\n')

    def create_apr_sittbl_file(self):
        lfile_path  = os.path.join(self.pwd_tables, 'lfile.')
        sittbl_path = os.path.join(self.pwd_tables, 'sittbl.')
        log_path    = os.path.join(self.pwd_tables, 'debug.log')

        for f in (lfile_path, sittbl_path):
            if os.path.isfile(f):
                os.remove(f)

        with file_open(lfile_path, 'w') as lfile:
            with file_open(sittbl_path, 'w') as sittbl:
                with file_open(log_path, 'w') as debug:

                    sittbl.write('SITE              FIX    --COORD.CONSTR.--  \n')
                    sittbl.write('      << default for regional sites >>\n')
                    sittbl.write('ALL               NNN    100.  100.   100. \n')

                    for stn in self.StationInstances:
                        lfile .write(stn.GetApr()     + '\n')
                        sittbl.write(stn.GetSittbl()  + '\n')
                        debug .write(stn.DebugCoord() + '\n')

    def copy_sestbl_procdef_atx(self):

        self.frame, atx = determine_frame(self.Config.options['frames'], self.date)

        # copy process.defaults and sestbl.
        copyfile(self.GamitOpts['process_defaults'],
                 os.path.join(self.pwd_tables, 'process.defaults'))
        # copyfile(self.GamitOpts['atx'], os.path.join(self.pwd_tables, 'antmod.dat'))
        copyfile(atx, os.path.join(self.pwd_tables, 'antmod.dat'))

        # change the scratch directory in the sestbl. file
        with file_open(os.path.join(self.pwd_tables, 'sestbl.'), 'w') as sestbl:
            with file_open(self.GamitOpts['sestbl']) as orig_sestbl:
                for line in orig_sestbl:
                    if 'Scratch directory' in line:
                        # empty means local directory! LA RE PU...
                        sestbl.write('Scratch directory = \n')
                    else:
                        sestbl.write(line)

    def link_tables(self):
        script_path = 'link_tables.sh'
        try:
            link_tables = file_open(script_path, 'w')
        except (OSError, IOError):
            raise GamitSessionException('Could not create script file link_tables.sh')

        # link the apr file as the lfile.
        contents = \
            """#!/bin/bash
            # set up links
            cd %s;
            sh_links.tables -frame J2000 -year %s -eop %s -topt none &> sh_links.out;
            # kill the earthquake rename file
            rm eq_rename
            # create an empty rename file
            echo "" > eq_rename
            cd ..;
            """ % (self.pwd_tables, self.date.yyyy(), self.GamitOpts['eop_type'])

        link_tables.write(contents)
        link_tables.close()

        chmod_exec(script_path)
        os.system('./'+script_path)

    def get_rinex_filenames(self):
        return [stn.GetRinexFilename() for stn in self.StationInstances]

    def create_sitedef(self):

        sitedefFile = os.path.join(self.pwd_tables, 'sites.defaults')
        try:
            with file_open(sitedefFile, 'w') as sitedef:
                sitedef.write(' all_sites %s xstinfo\n' % (self.GamitOpts['expt']))

                for StationInstance in self.StationInstances:
                    sitedef.write(" %s_GPS  %s localrx\n" % (StationInstance.StationAlias.upper(),
                                                             self.GamitOpts['expt']))

        except Exception as e:
            raise GamitSessionException(e)

    def parse_sinex(self):

        for sinex in os.listdir(self.pwd_glbf):
            if sinex.endswith('.snx'):
                snx = snxParse.snxFileParser(os.path.join(self.pwd_glbf, sinex))
                snx.parse()
                self.polyhedron     = snx.stationDict
                self.VarianceFactor = snx.varianceFactor

        if self.polyhedron:
            # remame any aliases and change keys to net.stn
            for stn in self.StationInstances:
                # replace the key
                try:
                    self.polyhedron[stationID(stn)] = self.polyhedron.pop(stn.StationAlias.upper())
                except KeyError:
                    # maybe the station didn't have a solution
                    pass
        return self.polyhedron, self.VarianceFactor

    def generate_kml(self):

        # save this session as a kml
        kml = simplekml.Kml()

        ICON_SQUARE = 'http://maps.google.com/mapfiles/kml/shapes/placemark_square.png'

        # define styles
        styles_stn = simplekml.StyleMap()
        styles_stn.normalstyle.iconstyle.icon.href    = ICON_SQUARE
        styles_stn.normalstyle.iconstyle.color        = 'ff00ff00'
        styles_stn.normalstyle.iconstyle.scale        = 4
        styles_stn.normalstyle.labelstyle.scale       = 0
        styles_stn.highlightstyle.iconstyle.icon.href = ICON_SQUARE
        styles_stn.highlightstyle.iconstyle.color     = 'ff00ff00'
        styles_stn.highlightstyle.iconstyle.scale     = 5
        styles_stn.highlightstyle.labelstyle.scale    = 2

        styles_tie = simplekml.StyleMap()
        styles_tie.normalstyle.iconstyle.icon.href    = ICON_SQUARE
        styles_tie.normalstyle.iconstyle.color        = 'ff0000ff'
        styles_tie.normalstyle.iconstyle.scale        = 4
        styles_tie.normalstyle.labelstyle.scale       = 0
        styles_tie.highlightstyle.iconstyle.icon.href = ICON_SQUARE
        styles_tie.highlightstyle.iconstyle.color     = 'ff0000ff'
        styles_tie.highlightstyle.iconstyle.scale     = 5
        styles_tie.highlightstyle.labelstyle.scale    = 3

        folder_net = kml.newfolder(name=self.DirName)

        for stn in self.stations_dict + self.tie_dict:
            pt = folder_net.newpoint(**stn)
            if stn in self.tie_dict:
                pt.stylemap = styles_tie
            else:
                pt.stylemap = styles_stn

        kml.savekmz(os.path.join(self.solution_pwd, self.DirName) + '.kmz')
