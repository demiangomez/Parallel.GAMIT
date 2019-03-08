"""
Project: Parallel.GAMIT
Date: Dic-03-2016
Author: Demian D. Gomez
"""
import os
from shutil import copyfile
import glob
import subprocess
import snxParse


class GlobkException(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)


class Globk(object):

    def __init__(self, pwd_comb, date, Sessions):

        self.polyhedron     = None
        self.VarianceFactor = None
        self.date           = date
        self.pwd_comb       = pwd_comb
        self.Sessions       = Sessions  # type: list
        self.stdout = None
        self.stderr = None
        self.p = None

        # try to create the folder
        if not os.path.exists(pwd_comb):
            os.makedirs(pwd_comb)

        # see if there is any FATAL in the sessions to be combined
        for GamitSession in Sessions:

            for file in glob.glob(os.path.join(GamitSession.pwd_glbf, 'h*.glx')):
                copyfile(file, os.path.join(pwd_comb, 'h' + GamitSession.DirName + date.yyyy() + date.ddd() +
                                            '_' + GamitSession.GamitOpts['expt'] + '.glx'))

        self.linktables(date.yyyy(), Sessions[0].GamitOpts['eop_type'])
        self.create_combination_script(date, Sessions[0].GamitOpts['org'])

    def linktables(self, year, eop_type):

        try:
            link_tables = open(os.path.join(self.pwd_comb, 'link_tables.sh'),'w')
        except Exception:
            raise GlobkException('could not open file link_tables.sh')

        # link the apr file as the lfile.
        contents = \
        """#!/bin/bash
        # set up links
        sh_links.tables -frame J2000 -year %s -eop %s -topt none &> sh_links.out;
        # link the bulletin A
        ln -s ~/gg/tables/pmu.usno .
        """ % (year, eop_type)

        link_tables.write(contents)
        link_tables.close()

        os.system('chmod +x '+os.path.join(self.pwd_comb, 'link_tables.sh'))

        return

    def execute(self):

        # loop through the folders and execute the script
        self.p = subprocess.Popen('./globk.sh', shell=False, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, cwd=self.pwd_comb)

        self.stdout, self.stderr = self.p.communicate()

    def create_combination_script(self, date, org):

        # extract the gps week and convert to string
        gpsWeek_str = str(date.gpsWeek)

        # normalize gps week string
        if date.gpsWeek < 1000: gpsWeek_str = '0'+gpsWeek_str

        # set the path and name for the run script
        run_file_path = os.path.join(self.pwd_comb, 'globk.sh')

        try:
            run_file = open(run_file_path,'w')
        except Exception:
            raise GlobkException('could not open file '+run_file_path)

        contents = \
        """#!/bin/bash

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
        echo "# activate for global network merge"                                   >> globk.cmd
        echo "# apr_wob    10 10  10 10 "                                            >> globk.cmd
        echo "# apr_ut1    10 10        "                                            >> globk.cmd
        echo " max_chii  1. 0.6"                                                     >> globk.cmd
        echo "# apr_svs all 0.05 0.05 0.05 0.005 0.005 0.005 0.01 0.01 0.00 0.01 FR" >> globk.cmd
        echo " apr_site  all 1 1 1 0 0 0"                                            >> globk.cmd
        echo " apr_atm   all 1 1 1"                                                  >> globk.cmd

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

        """ % (org, org, gpsWeek_str, str(date.gpsWeekDay))

        run_file.write(contents)

        # all done
        run_file.close()

        # add executable permissions
        os.system('chmod +x '+run_file_path)

        return

    def parse_sinex(self):

        for sinex in os.listdir(self.pwd_comb):
            if sinex.endswith('.snx'):
                snx = snxParse.snxFileParser(os.path.join(self.pwd_comb, sinex))
                snx.parse()
                self.polyhedron = snx.stationDict
                self.VarianceFactor = snx.varianceFactor

        if self.polyhedron:
            # rename the dict keys to net.stn format (and replace any aliases)
            for GamitSession in self.Sessions:
                for StationInstance in GamitSession.StationInstances:
                    # replace the key
                    try:
                        self.polyhedron[StationInstance.NetworkCode + '.' +
                                        StationInstance.StationCode] = \
                            self.polyhedron.pop(StationInstance.StationAlias.upper())
                    except KeyError:
                        # maybe the station didn't have a solution
                        pass

        return self.polyhedron, self.VarianceFactor
