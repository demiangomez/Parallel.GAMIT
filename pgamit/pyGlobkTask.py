"""
Project: Parallel.GAMIT
Date: Dic-03-2016
Author: Demian D. Gomez
"""
import os
import glob
import subprocess
import shutil

# app
from pgamit import snxParse
from pgamit.Utils import file_open, chmod_exec, stationID


class GlobkException(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)


class Globk(object):

    def __init__(self, pwd_comb, date, Sessions, net_type='regional'):
        self.polyhedron     = None
        self.VarianceFactor = None
        self.date           = date
        self.eop            = Sessions[0].GamitOpts['eop_type']
        self.org            = Sessions[0].GamitOpts['org']
        self.expt           = Sessions[0].GamitOpts['expt']
        self.pwd_comb       = pwd_comb
        self.Sessions       = Sessions  # type: list
        self.h_files        = []
        self.stdout         = None
        self.stderr         = None
        self.p              = None
        self.polyhedron     = None
        self.variance       = None
        self.net_type       = net_type

    def linktables(self, year, eop_type):
        script_path = os.path.join(self.pwd_comb, 'link_tables.sh')
        try:
            link_tables = file_open(script_path, 'w')
        except:
            raise GlobkException('could not open file link_tables.sh')

        # link the apr file as the lfile.
        with link_tables:
            contents = \
                """#!/bin/bash
                # set up links
                sh_links.tables -frame J2000 -year %s -eop %s -topt none &> sh_links.out;
                # link the bulletin A
                ln -s ~/gg/tables/pmu.usno .
                """ % (year, eop_type)

            link_tables.write(contents)

        chmod_exec(script_path)

    def execute(self, parse_sinex=True):

        # if multiple session, run globk first, then returned parsed sinex
        # if single session, then self.pwd_comb points to the folder where the sinex files is
        if len(self.Sessions) > 1:
            # need to run globk
            # try to create the folder
            if os.path.exists(self.pwd_comb):
                # if exists, delete and recreate
                shutil.rmtree(self.pwd_comb)
            os.makedirs(self.pwd_comb)

            for s in self.Sessions:
                for glx in glob.glob(os.path.join(s.pwd_glbf, 'h*.glx')):
                    # save the files that have to be copied, the copy process is done on each node
                    h_file = 'h' + s.DirName + self.date.yyyy() + self.date.ddd() + '_' + self.expt + '.glx'
                    shutil.copyfile(glx, os.path.join(self.pwd_comb, h_file))

            self.linktables(self.date.yyyy(), self.eop)
            self.create_combination_script(self.date, self.org)

            # multiple sessions execute globk
            self.p = subprocess.Popen('./globk.sh', shell=False, stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE, cwd=self.pwd_comb)

            self.stdout, self.stderr = self.p.communicate()

        return self.parse_sinex() if parse_sinex else None

    def create_combination_script(self, date, org):

        # extract the gps week and convert to string
        gpsWeek_str = date.wwww()

        # set the path and name for the run script
        run_file_path = os.path.join(self.pwd_comb, 'globk.sh')

        try:
            run_file = file_open(run_file_path, 'w')
        except:
            raise GlobkException('could not open file '+run_file_path)

        with run_file:
            contents = \
            r"""#!/bin/bash

            export INSTITUTE=%s

            # data product file names
            OUT_FILE=%s%s%s;
            
            # mk solutions directory for prt files etc
            [ ! -d tables ] && mkdir tables

            cd tables
            ../link_tables.sh

            # create global directory listing for globk
            for file in $(find .. -name "*.glx" -print);do echo $file;done | grep    "\/n0\/"  > globk.gdl
            for file in $(find .. -name "*.glx" -print);do echo $file;done | grep -v "\/n0\/" >> globk.gdl

            # create the globk cmd file
            echo " app_ptid all"                                                          > globk.cmd
            echo " prt_opt GDLF MIDP CMDS"                                               >> globk.cmd
            echo " out_glb ../file.GLX"                                                  >> globk.cmd
            echo " in_pmu pmu.usno"                                                      >> globk.cmd
            echo " descript Daily combination of global and regional solutions"          >> globk.cmd
            """ % (org, org, gpsWeek_str, str(date.gpsWeekDay))

            if self.net_type == 'global':
                contents += \
                """
                echo "# activated for global network merge"                                  >> globk.cmd
                echo " apr_wob    10 10  10 10 "                                             >> globk.cmd
                echo " apr_ut1    10 10        "                                             >> globk.cmd
                echo " apr_svs all 0.05 0.05 0.05 0.005 0.005 0.005 0.01 0.01 0.00 0.01 FR"  >> globk.cmd
                """
            contents += \
            r"""
            echo " max_chii  1. 0.6"                                                     >> globk.cmd
            echo " apr_neu  all 1 1 1 0 0 0"                                             >> globk.cmd
            echo "#apr_atm  all 1 1 1"                                                   >> globk.cmd

            # create the sinex header file
            echo "+FILE/REFERENCE                               " >  head.snx
            echo " DESCRIPTION   Instituto Geografico Nacional  " >> head.snx
            echo " OUTPUT        Solucion GPS combinada         " >> head.snx
            echo " CONTACT       dgomez@ign.gob.ar              " >> head.snx
            echo " SOFTWARE      glbtosnx Version               " >> head.snx
            echo " HARDWARE      .                              " >> head.snx
            echo " INPUT         Archivos binarios Globk        " >> head.snx
            echo "-FILE/REFERENCE                               " >> head.snx

            # run globk
            globk 0 ../file.prt ../globk.log globk.gdl globk.cmd 2>&1 > ../globk.out

            # convert the GLX file into sinex
            glbtosnx . ./head.snx ../file.GLX ../${OUT_FILE}.snx 2>&1 > ../glbtosnx.out

            # restore original directory
            cd ..;

            # figure out where the parameters start in the prt file
            LINE=`grep -n "PARAMETER ESTIMATES" file.prt | cut -d ":" -f1`

            # reduce line by one to make a little cleaner
            let LINE--;

            # print prt header
            sed -n 1,${LINE}p file.prt > ${OUT_FILE}.out

            # append the log file
            cat globk.log >> ${OUT_FILE}.out

            # create the fsnx file which contains only the solution estimate
            lineNumber=`grep --binary-file=text -m 1 -n "\-SOLUTION/ESTIMATE" ${OUT_FILE}.snx | cut -d : -f 1`

            # extract the solution estimate
            head -$lineNumber ${OUT_FILE}.snx > ${OUT_FILE}.fsnx;

            # move the H file to a meaningful name
            mv file.GLX ${OUT_FILE}.GLX

            # clear out log files
            rm -rf tables
            rm -f file*
            rm -f globk*
            rm -f glb*
            rm -f *.sh

            # compress sinex file
            # gzip --force *.snx
            gzip --force *.fsnx
            gzip --force *.out
            gzip --force *.glx
            gzip --force *.GLX

            """

            run_file.write(contents)
            # all done

        # add executable permissions
        chmod_exec(run_file_path)

    def parse_sinex(self):

        for sinex in os.listdir(self.pwd_comb):
            if sinex.endswith('.snx'):
                snx = snxParse.snxFileParser(os.path.join(self.pwd_comb, sinex))
                snx.parse()
                self.polyhedron     = snx.stationDict
                self.VarianceFactor = snx.varianceFactor

        if self.polyhedron:
            # rename the dict keys to net.stn format (and replace any aliases)
            for GamitSession in self.Sessions:
                for stn in GamitSession.StationInstances:
                    # replace the key
                    try:
                        self.polyhedron[stationID(stn)] = self.polyhedron.pop(stn.StationAlias.upper())
                    except KeyError:
                        # maybe the station didn't have a solution
                        pass

        return self.polyhedron, self.VarianceFactor
