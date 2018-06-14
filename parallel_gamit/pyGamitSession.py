"""
Project: Parallel.GAMIT
Date: 4/3/17 6:57 PM
Author: Demian D. Gomez
"""

import os
from shutil import copyfile
from shutil import rmtree
import pyGamitConfig
import snxParse

class GamitSessionException(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)

class GamitSession():

    def __init__(self, Name, date, GamitConfig, StationInstances, ready=False):
        """

        :param date: pyDate.Date
        :param GamitConfig: pyGamitConfig.GamitConfiguration
        :param NetIndex: index of station list in GamitConfig.Network.GetStationList()
        """
        self.NetName          = Name
        self.date             = date
        self.GamitOpts        = GamitConfig.gamitopt # type: pyGamitConfig.GamitConfiguration().gamitopt
        self.Config           = GamitConfig          # type: pyGamitConfig.GamitConfiguration
        self.StationInstances = StationInstances # type: list

        # to store the polyhedron read from the final SINEX
        self.polyhedron       = None
        self.VarianceFactor   = None

        # gamit task will be filled with the GamitTask object
        self.GamitTask        = None  # type: pyGamitTask.GamitTask
        self.ready            = ready

        # a list to report missing data for this session
        self.missing_data = []

        # create working dirs for this session
        self.solution_pwd = self.GamitOpts['solutions_dir'].rstrip('/') + '/' + date.yyyy() + '/' + date.ddd() + '/' + self.NetName

        self.remote_pwd = 'production/gamit/' + date.yyyy() + '/' + date.ddd() + '/' + self.NetName

        if not os.path.exists(self.solution_pwd):
            os.makedirs(self.solution_pwd)

        self.pwd_igs    = os.path.join(self.solution_pwd, 'igs')
        self.pwd_brdc   = os.path.join(self.solution_pwd, 'brdc')
        self.pwd_rinex  = os.path.join(self.solution_pwd, 'rinex')
        self.pwd_tables = os.path.join(self.solution_pwd, 'tables')
        self.pwd_glbf   = os.path.join(self.solution_pwd, 'glbf')
        self.pwd_proc   = os.path.join(self.solution_pwd, date.ddd())

        if not ready:
            # only create folders, etc if it was determined the solution isn't ready
            if not os.path.exists(self.pwd_igs):
                os.makedirs(self.pwd_igs)

            if not os.path.exists(self.pwd_brdc):
                os.makedirs(self.pwd_brdc)

            if not os.path.exists(self.pwd_rinex):
                os.makedirs(self.pwd_rinex)
            else:
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

        return

    def initialize(self):

        try:

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

            orbit_params = {'sp3_path'  : self.Config.sp3_path,
                            'sp3types'  : self.Config.sp3types,
                            'sp3altrn'  : self.Config.sp3altrn,
                            'brdc_path' : self.Config.brdc_path}

            self.params  = {'solution_pwd': self.solution_pwd,
                            'remote_pwd'  : self.remote_pwd,
                            'NetName'     : self.NetName,
                            'rinex'       : rinex_list,
                            'date'        : self.date,
                            'options'     : self.Config.options,
                            'orbits'      : orbit_params,
                            'gamitopts'   : self.GamitOpts}
        except Exception:
            raise

        return

    def create_otl_list(self):

        if os.path.isfile(os.path.join(self.pwd_tables, 'otl.list')):
            os.remove(os.path.join(self.pwd_tables, 'otl.list'))

        with open(os.path.join(self.pwd_tables, 'otl.list'), 'w') as otl_list:
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
                otl = stn.Station.otl_H.split('\n')
                # remove BLQ header
                otl = otl[29:]
                # need to change the station record for GAMIT to take it
                otl[0] = '  %s' % stn.Station.StationAlias.upper()
                if stn.Station.lon < 0:
                    lon = 360+stn.Station.lon
                else:
                    lon = stn.Station.lon
                otl[3] = '$$ %s                                 RADI TANG lon/lat:%10.4f%10.4f' % (stn.Station.StationAlias.upper(), lon, stn.Station.lat)
                otl = '\n'.join(otl)

                otl_list.write(otl)

            # write BLQ format termination
            otl_list.write("$$ END TABLE\n")

    def create_station_info(self):

        # delete any current station.info files
        if os.path.isfile(os.path.join(self.pwd_tables, 'station.info')):
            os.remove(os.path.join(self.pwd_tables, 'station.info'))

        with open(os.path.join(self.pwd_tables, 'station.info'), 'w') as stninfo_file:
            stninfo_file.write('*SITE  Station Name      Session Start      Session Stop       Ant Ht   HtCod  Ant N    Ant E    Receiver Type         Vers                  SwVer  Receiver SN           Antenna Type     Dome   Antenna SN          \n')

            for stn in self.StationInstances:
                # stninfo_file.write(stn.StationInfo.return_stninfo() + '\n')
                stninfo_file.write(stn.GetStationInformation() + '\n')

    def create_apr_sittbl_file(self):

        if os.path.isfile(os.path.join(self.pwd_tables, 'lfile.')):
            os.remove(os.path.join(self.pwd_tables, 'lfile.'))

        if os.path.isfile(os.path.join(self.pwd_tables, 'sittbl.')):
            os.remove(os.path.join(self.pwd_tables, 'sittbl.'))

        with open(os.path.join(self.pwd_tables, 'lfile.'), 'w') as lfile:
            with open(os.path.join(self.pwd_tables, 'sittbl.'), 'w') as sittbl:
                with open(os.path.join(self.pwd_tables, 'debug.log'), 'w') as debug:

                    sittbl.write('SITE              FIX    --COORD.CONSTR.--  \n')
                    sittbl.write('      << default for regional sites >>\n')
                    sittbl.write('ALL               NNN    100.  100.   100. \n')

                    for stn in self.StationInstances:
                        lfile.write(stn.GetApr() + '\n')
                        sittbl.write(stn.GetSittbl() + '\n')
                        debug.write(stn.DebugCoord() + '\n')

        return

    def copy_sestbl_procdef_atx(self):
        # copy process.defaults and sestbl.
        copyfile(self.GamitOpts['process_defaults'], os.path.join(self.pwd_tables, 'process.defaults'))
        copyfile(self.GamitOpts['atx'], os.path.join(self.pwd_tables, 'antmod.dat'))

        # change the scratch directory in the sestbl. file
        #copyfile(self.GamitOpts['sestbl'], os.path.join(self.pwd_tables, 'sestbl.'))

        with open(os.path.join(self.pwd_tables, 'sestbl.'), 'w') as sestbl:
            with open(self.GamitOpts['sestbl']) as orig_sestbl:
                for line in orig_sestbl:
                    if 'Scratch directory' in line:
                        # empty means local directory! LA RE PU...
                        sestbl.write('Scratch directory = \n')
                    else:
                        sestbl.write(line)

        return

    def link_tables(self):

        try:
            link_tables = open('link_tables.sh', 'w')
        except (OSError, IOError):
            raise GamitSessionException('Could not create script file link_tables.sh')

        # link the apr file as the lfile.
        contents = \
            """#!/bin/bash
            # set up links
            cd %s;
            sh_links.tables -frame J2000 -year %s -eop %s -topt none &> sh_links.out;
            # ln -s %s.apr lfile.
            cd ..;
            """ % (self.pwd_tables, self.date.yyyy(), self.GamitOpts['eop_type'], self.GamitOpts['expt'])

        link_tables.write(contents)
        link_tables.close()

        os.system('chmod +x link_tables.sh')
        os.system('./link_tables.sh')

        return

    def get_rinex_filenames(self):
        lst = []
        for stn in self.StationInstances:
            lst.append(stn.GetRinexFilename())

        return lst

    def create_sitedef(self):

        sitedefFile = os.path.join(self.pwd_tables, 'sites.defaults')
        try:
            with open(sitedefFile,'w') as sitedef:
                sitedef.write(' all_sites %s xstinfo\n' % (self.GamitOpts['expt']))

                for StationInstance in self.StationInstances:
                    sitedef.write(" %s_GPS  %s localrx\n" % (StationInstance.Station.StationAlias.upper(), self.GamitOpts['expt']))

        except Exception as e:
            raise GamitSessionException(e)
        except:
            raise

    def parse_sinex(self):

        for sinex in os.listdir(self.pwd_glbf):
            if sinex.endswith('.snx'):
                snx = snxParse.snxFileParser(os.path.join(self.pwd_glbf, sinex))
                snx.parse()
                self.polyhedron = snx.stationDict
                self.VarianceFactor = snx.varianceFactor

        if self.polyhedron:
            # remame any aliases and change keys to net.stn
            for StationInstance in self.StationInstances:
                # replace the key
                try:
                    self.polyhedron[StationInstance.Station.NetworkCode + '.' + StationInstance.Station.StationCode] = self.polyhedron.pop(StationInstance.Station.StationAlias.upper())
                except KeyError:
                    # maybe the station didn't have a solution
                    pass
        return self.polyhedron, self.VarianceFactor