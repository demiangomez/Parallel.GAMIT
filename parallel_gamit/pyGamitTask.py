"""
Project: Parallel.GAMIT
Date: 4/3/17 6:57 PM
Author: Demian D. Gomez
"""
import os
import datetime
import pyRinex
import pySp3
import pyBrdc
import shutil
import subprocess
import re
import glob

class GamitTask:

    def __init__(self, pwd, params, final_pwd):

        self.pwd        = pwd
        self.final_pwd  = final_pwd
        self.pwd_igs    = os.path.join(pwd, 'igs')
        self.pwd_brdc   = os.path.join(pwd, 'brdc')
        self.pwd_rinex  = os.path.join(pwd, 'rinex')
        self.pwd_tables = os.path.join(pwd, 'tables')

        self.params    = params
        self.options   = params['options']
        self.orbits    = params['orbits']
        self.gamitopts = params['gamitopts']
        self.date      = params['date']
        self.success   = False

        with open(os.path.join(pwd, 'monitor.log'), 'a') as monitor:
            monitor.write(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') + ' -> starting GAMIT job for %s: %s\n' % (self.params['NetName'], self.date.yyyyddd()))

    def start(self):

        with open(os.path.join(self.pwd,'monitor.log'), 'w') as monitor:
            monitor.write(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') + ' -> fetching orbits\n')

            try:
                Sp3 = pySp3.GetSp3Orbits(self.orbits['sp3_path'], self.date, self.orbits['sp3types'], self.pwd_igs, True)  # type: pySp3.GetSp3Orbits
            except pySp3.pySp3Exception:

                monitor.write(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') + ' -> could not find principal orbits, fetching alternative\n')

                # try alternative orbits
                if self.options['sp3altrn']:
                    Sp3 = pySp3.GetSp3Orbits(self.orbits['sp3_path'], self.date, self.orbits['sp3altrn'], self.pwd_igs, True)  # type: pySp3.GetSp3Orbits
                else:
                    raise

            if Sp3.type != 'igs':
                # rename file
                shutil.copyfile(Sp3.file_path, Sp3.file_path.replace(Sp3.type, 'igs'))

            monitor.write(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') + ' -> fetching broadcast orbits\n')

            pyBrdc.GetBrdcOrbits(self.orbits['brdc_path'], self.date, self.pwd_brdc, no_cleanup=True)  # type: pyBrdc.GetBrdcOrbits

            for rinex in self.params['rinex']:

                monitor.write(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') + ' -> fetching rinex for %s.%s %s %s\n' %(rinex['NetworkCode'],rinex['StationCode'],rinex['StationAlias'],'{:10.6f} {:11.6f}'.format(rinex['lat'], rinex['lon'])))

                try:
                    with pyRinex.ReadRinex(rinex['NetworkCode'],
                                           rinex['StationCode'],
                                           rinex['source'], False) as Rinex:  # type: pyRinex.ReadRinex

                        # WARNING! some multiday RINEX were generating conflicts because the RINEX has a name, say,
                        # tuc12302.10o and the program wants to rename it as tuc12030.10o but because it's a multiday
                        # file, during __init__ it's already split and renamed as tuc12300.10o and additional folders
                        # are generated with the information for each file. Therefore, find the rinex that corresponds
                        # to the date being processed and use that one instead of the original file
                        # These files are not allowed by pyArchiveService, but the "start point" of the database
                        # (i.e. the files already in the folders read by pyScanArchive) has such problems.

                        # figure out if this station has been affected by an earthquake
                        # if so, window the data
                        if rinex['jump'] is not None:
                            monitor.write('                    -> RINEX file has been windowed: ETM detected jump on ' + rinex['jump'].datetime().strftime('%Y-%m-%d %H:%M:%S') + '\n')

                        if Rinex.multiday:
                            # find the rinex that corresponds to the session being processed
                            for Rnx in Rinex.multiday_rnx_list:
                                if Rnx.date == self.date:
                                    Rnx.rename(rinex['destiny'])

                                    if rinex['jump'] is not None:
                                        self.window_rinex(Rnx, rinex['jump'])
                                    # before creating local copy, decimate file
                                    Rnx.decimate(30)
                                    Rnx.compress_local_copyto(self.pwd_rinex)
                                    break
                        else:
                            Rinex.rename(rinex['destiny'])

                            if rinex['jump'] is not None:
                                self.window_rinex(Rinex, rinex['jump'])
                            # before creating local copy, decimate file
                            Rinex.decimate(30)
                            Rinex.compress_local_copyto(self.pwd_rinex)

                except (OSError, IOError):
                    monitor.write(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') + ' -> An error occurred while trying to copy ' + rinex['source'] + ' to ' + rinex['destiny'] + ': File skipped.\n')
                except pyRinex.pyRinexException as e:
                    monitor.write(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') + ' -> An error occurred while trying to copy ' + rinex['source'] + ': ' + str(e) + '\n')

            monitor.write(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') + ' -> executing GAMIT\n')

            # create the run script
            self.create_replace_links()
            self.create_run_script()
            self.create_finish_script()

        # run the script to replace the links of the tables directory
        self.p = subprocess.Popen('find ./tables ! -name "otl.grid" -type l -exec ./replace_links.sh {} +', shell=True, stdout=subprocess.PIPE,stderr=subprocess.PIPE, cwd=self.pwd)
        _, _ = self.p.communicate()

        # now execute the run script
        self.p = subprocess.Popen('./run.sh', shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=self.pwd)

        self.stdout, self.stderr = self.p.communicate()

        self.p = subprocess.Popen('./finish.sh', shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=self.pwd)

        self.stdout, self.stderr = self.p.communicate()

        # check for any fatals
        self.p = subprocess.Popen('grep -q \'FATAL\' monitor.log', shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=self.pwd)
        _, _ = self.p.communicate()

        if self.p.returncode == 0:
            self.success = False
        else:
            self.success = True

        # output statistics to the parent to display
        nrms = 100
        wl = 0
        nl = 0
        if self.success:
            vals = []
            pattern1 = re.compile('^\s\w+\s\w+:\s+\d\.\d+[Ee][+-]?\d+\s+\w+\s\w+:\s+(\d\.\d+[Ee][+-]?\d+).*$')
            pattern2 = re.compile('^\s\w+\s\w+\s\w+\s\w+\s+(\d+\.\d)\%\s\w+\s\w+\s+(\d+\.\d)\%.*')
            with open(self.pwd + '/monitor.log', 'r') as monitor:
                for line in monitor:
                    nrms = pattern1.findall(line)
                    if nrms:
                        vals.append(float(nrms[0]))

                    wlnl = pattern2.findall(line)
                    if wlnl:
                        wl = float(wlnl[0][0])
                        nl = float(wlnl[0][1])

                if vals:
                    # bias free WL ambiguities
                    nrms = vals[0]
                else:
                    nrms = 100

        # no matter the result of the processing, move folder to final destination
        self.finish()

        return {'Session': '%s %s' % (self.params['NetName'], self.date.yyyyddd()), 'Success': self.success, 'NRMS': nrms, 'WL': wl, 'NL': nl}

    def window_rinex(self, Rinex, window):

        # windows the data:
        # check which side of the earthquake yields more data: window before or after the earthquake
        if (window.datetime().hour + window.datetime().minute/60.0) < 12:
            Rinex.window_data(start=window.datetime())
        else:
            Rinex.window_data(end=window.datetime())

    def finish(self):

        # delete everything inside the processing dir
        shutil.rmtree(self.pwd_brdc)
        shutil.rmtree(self.pwd_igs)

        # remove files in tables
        for ftype in ['*.grid', '*.dat', '*.apr']:
            for ff in glob.glob(os.path.join(self.pwd_tables, ftype)):
                os.remove(ff)

        # remove processing files
        for ftype in ['b*', 'cfmrg*', 'DPH.*', 'eq_rename.*', 'g*', 'k*', 'p*', 'rcvant.*', 'y*']:
            for ff in glob.glob(os.path.join(os.path.join(self.pwd, self.date.ddd()), ftype)):
                os.remove(ff)

        try:
            os.makedirs(os.path.dirname(self.final_pwd))
        except OSError:
            # racing condition having several processes trying to create the same folder
            # if OSError occurs, ignore and continue
            pass

        # execute final step: copy to self.final_pwd
        shutil.copytree(self.pwd, self.final_pwd, symlinks=True)
        shutil.rmtree(self.pwd)

        return

    def create_replace_links(self):
        replace_ln_file_path = os.path.join(self.pwd, 'replace_links.sh')

        try:
            replace_ln_file = open(replace_ln_file_path, 'w')
        except (OSError, IOError):
            raise Exception('could not open file ' + replace_ln_file_path)

        contents = """#!/bin/bash
        set -e
        for link; do
            test -h "$link" || continue

            dir=$(dirname "$link")
            reltarget=$(readlink "$link")
            case $reltarget in
                /*) abstarget=$reltarget;;
                *)  abstarget=$dir/$reltarget;;
            esac

            rm -fv "$link"
            cp -afv "$abstarget" "$link" || {
                # on failure, restore the symlink
                rm -rfv "$link"
                ln -sfv "$reltarget" "$link"
            }
        done
        """

        replace_ln_file.write(contents)
        replace_ln_file.close()

        os.system('chmod +x ' + replace_ln_file_path)

    def create_run_script(self):

        year = self.date.yyyy()
        doy  = self.date.ddd()

        # extract the gps week and convert to string
        gpsWeek_str = str(self.date.gpsWeek)

        # normalize gps week string
        if self.date.gpsWeek < 1000: gpsWeek_str = '0'+gpsWeek_str

        # set the path and name for the run script
        run_file_path = os.path.join(self.pwd,'run.sh')

        try:
            run_file = open(run_file_path,'w')
        except (OSError, IOError):
            raise Exception('could not open file '+run_file_path)

        contents = """#!/bin/bash

        # just in case, create a temporary dir for fortran
        if [ ! -d ./tmp ]; then
            mkdir ./tmp
        fi
        export TMPDIR=`pwd`/tmp

        export INSTITUTE=%s
        # set max depth for recursion
        MAX_LEVEL=3;

        # parse input
        level=$1; [ $# -eq 0 ] && level=1;

        # check that level less than max depth
        if [[ $level -gt $MAX_LEVEL ]];then
            # if so then exit
            echo "run.sh (`date +"%%Y-%%m-%%d %%T"`): MAX ITERATION DEPTH REACHED ... MUST EXIT" >> monitor.log
            exit 0;
        fi

        echo "run.sh (`date +"%%Y-%%m-%%d %%T"`): Iteration depth: $level" >> monitor.log

        # set the params
        EXPT=%s;
        YEAR=%s;
        DOY=%s;
        MIN_SPAN=%s;
        EOP=%s;
        NOFPT=%s;

        # set the name of the outfile
        OUT_FILE=%s%s%s.out

        # execution flag for sh_gamit
        EXE=1;
        COUNTER=0;

        while [ $EXE -eq 1 ]; do

        if [ $COUNTER -gt 9 ]; then
            echo "run.sh (`date +"%%Y-%%m-%%d %%T"`): Maximum number of retries (10) reached. Abnormal exit in run.sh. Check processing log." >> monitor.log
            exit 1
        fi

        # set exe to 0 so that we exit exe loop if no problems found
        EXE=0;

        # save a copy of the lfile. before running sh_gamit
        iter_ext=`printf "l%%02d_i%%02d" $level $COUNTER`
        cp ./tables/lfile. ./tables/lfile.${iter_ext}

        # do the damn thing
        if [ "$NOFTP" = "no" ]; then
            sh_gamit -update_l N -topt none -c -copt null -dopt c x -expt $EXPT -d $YEAR $DOY -minspan $MIN_SPAN -remakex Y -eop $EOP &> $OUT_FILE;
        else
            sh_gamit -update_l N -topt none -c -copt null -noftp -dopt c x -expt $EXPT -d $YEAR $DOY -minspan $MIN_SPAN -remakex Y -eop $EOP &> $OUT_FILE;
        fi
        """ \
        % (self.gamitopts['org'], self.gamitopts['expt'], year, doy,'12', self.gamitopts['eop_type'], self.gamitopts['noftp'], self.gamitopts['org'], gpsWeek_str, str(self.date.gpsWeekDay))

        # if we're in debug mode do not pipe output to file
        # if not session.options['debug']: contents += """ &> $OUT_FILE; """;

        contents += """

        grep -q "Geodetic height unreasonable"  $OUT_FILE;
        if [ $? -eq 0 ]; then
            sstn=`grep "MODEL/open: Site" $OUT_FILE  | tail -1 | cut -d ":" -f 5 | cut -d " " -f 3 |tr '[:upper:]' '[:lower:]'`;
            echo "run.sh (`date +"%Y-%m-%d %T"`): deleting station ${sstn}: unreasonable geodetic height" >> monitor.log
            rm rinex/${sstn}* ;
            rm $DOY/${sstn}* ;
            grep "MODEL/open: Site" $OUT_FILE  | tail -1
            echo "run.sh (`date +"%Y-%m-%d %T"`): will try sh_gamit again ..." >> monitor.log
            EXE=1;
        fi

        grep "FATAL.*MAKEX/lib/rstnfo: No match for" $OUT_FILE
        if [ $? -eq 0 ];then
            sstn=`grep "FATAL.*MAKEX/lib/rstnfo: No match for" $OUT_FILE | tail -1 | cut -d ":" -f5 | awk '{print $4}' | tr '[:upper:]' '[:lower:]'`
            echo "run.sh (`date +"%Y-%m-%d %T"`): deleting station ${sstn}: no station info" >> monitor.log
            rm rinex/${sstn}* ;
            rm $DOY/${sstn}* ;
            echo "run.sh (`date +"%Y-%m-%d %T"`): will try sh_gamit again ..." >> monitor.log
            EXE=1;
        fi

        grep -q "Error extracting velocities for"  $OUT_FILE;
        if [ $? -eq 0 ]; then
            sstn=`grep "Error extracting velocities for" $OUT_FILE  | head -1 | cut -d ":" -f 5 | cut -d " " -f 6 |tr '[:upper:]' '[:lower:]'`;
            echo "run.sh (`date +"%Y-%m-%d %T"`): deleting station ${sstn}: Error extracting velocities for" >> monitor.log
            rm rinex/${sstn}* ;
            rm $DOY/${sstn}* ;
            grep "Error extracting velocities for" $OUT_FILE  | tail -1
            echo "run.sh (`date +"%Y-%m-%d %T"`): will try sh_gamit again ..." >> monitor.log
            EXE=1;
        fi

        grep -q    "Bad WAVELENGTH FACT" $OUT_FILE;
        if [ $? -eq 0 ]; then
            sstn=`grep "Bad WAVELENGTH FACT" $OUT_FILE | tail -1 | cut -d ":" -f 5 | cut -d " " -f 6 | cut -c 3-6`
            echo "run.sh (`date +"%Y-%m-%d %T"`): deleting station ${sstn}: Bad WAVELENGTH FACT in rinex header" >> monitor.log
            rm rinex/${sstn}*;
            rm $DOY/${sstn}* ;
            echo "run.sh (`date +"%Y-%m-%d %T"`): will try sh_gamit again ..." >> monitor.log
            EXE=1;
        fi

        grep -q    "Error decoding swver" $OUT_FILE;
        if [ $? -eq 0 ]; then
            grep       "Error decoding swver" $OUT_FILE;
            sstn=`grep "Error decoding swver" $OUT_FILE | tail -1 | awk '{print $8}' | tr '[:upper:]' '[:lower:]'`
            echo "run.sh (`date +"%Y-%m-%d %T"`): deleting station ${sstn}: Error decoding swver" >> monitor.log
            rm rinex/${sstn}*;
            rm $DOY/${sstn}* ;
            echo "run.sh (`date +"%Y-%m-%d %T"`): will try sh_gamit again ..." >> monitor.log
            EXE=1;
        fi

        grep -q    "FATAL.*MAKEX/lib/hisub:  Antenna code.*not in hi.dat" $OUT_FILE;
        if [ $? -eq 0 ]; then
            grep       "FATAL.*MAKEX/lib/hisub:  Antenna code.*not in hi.dat" $OUT_FILE;
            sstn=`grep "FATAL.*MAKEX/lib/hisub:  Antenna code.*not in hi.dat" $OUT_FILE | tail -1 | awk '{print $9}' | cut -c2-5 | tr '[:upper:]' '[:lower:]'`
            echo "run.sh (`date +"%Y-%m-%d %T"`): deleting station ${sstn}: Antenna code not in hi.dat" >> monitor.log
            rm rinex/${sstn}*;
            rm $DOY/${sstn}* ;
            echo "run.sh (`date +"%Y-%m-%d %T"`): will try sh_gamit again ..." >> monitor.log
            EXE=1;
        fi

        grep -q    "FATAL.*FIXDRV/dcheck: Only one or no existing X-files" $OUT_FILE;
        if [ $? -eq 0 ]; then
            grep       "FATAL.*FIXDRV/dcheck: Only one or no existing X-files" $OUT_FILE;
            echo "run.sh (`date +"%Y-%m-%d %T"`): FIXDRV/dcheck: Only one or no existing X-files" >> monitor.log
            echo "run.sh (`date +"%Y-%m-%d %T"`): will try sh_gamit again ..." >> monitor.log
            EXE=1;
        fi

        grep -q    "FATAL.*MAKEXP/makexp: No RINEX or X-files found" $OUT_FILE;
        if [ $? -eq 0 ]; then
            grep       "FATAL.*MAKEXP/makexp: No RINEX or X-files found" $OUT_FILE;
            echo "run.sh (`date +"%Y-%m-%d %T"`): MAKEXP/makexp: No RINEX or X-files found" >> monitor.log
            echo "run.sh (`date +"%Y-%m-%d %T"`): will try sh_gamit again ..." >> monitor.log
            EXE=1;
        fi

        grep -q    "FATAL.*MAKEX/get_rxfiles: Cannot find selected RINEX file" $OUT_FILE;
        if [ $? -eq 0 ]; then
            grep       "FATAL.*MAKEX/get_rxfiles: Cannot find selected RINEX file" $OUT_FILE;
            echo "run.sh (`date +"%Y-%m-%d %T"`): MAKEX/get_rxfiles: Cannot find selected RINEX file" >> monitor.log
            echo "run.sh (`date +"%Y-%m-%d %T"`): will try sh_gamit again ..." >> monitor.log
            EXE=1;
        fi

        grep -q    "SOLVE/get_widelane: Error reading first record" $OUT_FILE;
        if [ $? -eq 0 ]; then
            grep       "SOLVE/get_widelane: Error reading first record" $OUT_FILE;
            echo "run.sh (`date +"%Y-%m-%d %T"`): SOLVE/get_widelane: Error reading first record of temp file" >> monitor.log
            echo "run.sh (`date +"%Y-%m-%d %T"`): will try sh_gamit again ..." >> monitor.log
            EXE=1;
        fi

        grep -q    "Failure in sh_preproc. STATUS 1 -- sh_gamit terminated" $OUT_FILE;
        if [ $? -eq 0 ]; then
            grep       "Failure in sh_preproc. STATUS 1 -- sh_gamit terminated" $OUT_FILE;
            echo "run.sh (`date +"%Y-%m-%d %T"`): Failure in sh_preproc. STATUS 1 -- sh_gamit terminated" >> monitor.log
            echo "run.sh (`date +"%Y-%m-%d %T"`): will try sh_gamit again ..." >> monitor.log
            EXE=1;
        fi

        # problems related to ill conditioned bias matrix
        grep -q  "FATAL.*SOLVE/lcloos: Inversion error in" $OUT_FILE;
        if [ $? -eq 0 ]; then

            # remove the FATAL from the message to avoid confusing finish.sh that there was an error during execution
            err="SOLVE/lcloos: Inversion error in LCNORM(2)"

            # determine which autocln.sum exists and has information in it
            if [ -s $DOY/autcln.post.sum ]; then
                autocln=autcln.post.sum

                # error occurred after the prefit, read the autcln file and remove the station with low obs

                echo "run.sh (`date +"%Y-%m-%d %T"`): $err (after prefit) Will remove the station with the lowest obs count in $autocln" >> monitor.log

                sstn=`sed -n -e '/Number of data by site/,/^$/ p' $DOY/$autocln | tail -n +3 | sed '$d' | awk '{print $3, $4}' | awk -v min=999999 '{if($2<min){min=$2; stn=$1}}END{print stn}' | tr '[:upper:]' '[:lower:]'`

                nobs=`sed -n -e '/Number of data by site/,/^$/ p' $DOY/$autocln | tail -n +3 | sed '$d' | awk '{print $3, $4}' | awk -v min=999999 '{if($2<min){min=$2; stn=$1}}END{print min}'`

                echo "run.sh (`date +"%Y-%m-%d %T"`): deleting station ${sstn} -> observation count: $nobs" >> monitor.log
                rm rinex/${sstn}*;
                rm $DOY/${sstn}* ;
                echo "run.sh (`date +"%Y-%m-%d %T"`): will try sh_gamit again ..." >> monitor.log
                EXE=1;

            else
                # the error occurred during the prefit, autocln may or may not have gotten the problem. Use the observation count in the $OUTFILE

                echo "run.sh (`date +"%Y-%m-%d %T"`): $err. (during prefit) Will analyze the MAKEX output and remove the file with more rejected observations" >> monitor.log

                max_rejected=`grep "observations rejected" $OUT_FILE | awk -F ':' '{print $5}' | awk '{print $6}' | awk -v max=0 '{if($1>max){max=$1}}END{print max}'`

                sstn=(`sed -n -e '/'$max_rejected' observations rejected/,/End processing/ p' $OUT_FILE | grep 'End' | awk -F ':' '{print $6}' | awk '{print $1'} | uniq | tr '[:upper:]' '[:lower:]'`)

                if [ -z "$sstn" ]; then
                    echo "run.sh (`date +"%Y-%m-%d %T"`): could not determine the station with low observation count. Check $OUT_FILE" >> monitor.log
                else
                    for stn in ${sstn[*]}
                    do
                        echo "run.sh (`date +"%Y-%m-%d %T"`): deleting station ${stn} -> rejected observation count: $max_rejected" >> monitor.log
                        rm rinex/${stn}*;
                        rm $DOY/${stn}* ;
                    done
                    echo "run.sh (`date +"%Y-%m-%d %T"`): will try sh_gamit again ..." >> monitor.log
                    EXE=1;
                fi
            fi

            # different search methods, deprecated
            #sstn=(`sed -n -e '/ .... valid observations/,/stop in MODEL/ p' $OUT_FILE | grep 'Site' | awk -F ':' '{print $5}' | awk '{print $2'} | uniq | tr '[:upper:]' '[:lower:]'`)
        fi

        # this case after SOLVE/lcloos because it also triggers GAMIT sh_chksolve
        grep -q "FATAL GAMIT sh_chksolve: Solve failed to complete normally" $OUT_FILE;
        if [ $? -eq 0 ] && [ $EXE -eq 0 ]; then
            echo "run.sh (`date +"%Y-%m-%d %T"`): GAMIT sh_chksolve: Solve failed to complete normally" >> monitor.log
            echo "run.sh (`date +"%Y-%m-%d %T"`): will try sh_gamit again ..." >> monitor.log
            EXE=1;
        fi

        if [ $EXE -eq 1 ]; then
            # if it will retry, save the previous output using extension .l00_i00, .l00_i01, ... etc
            # where lxx is the level of iteration and iyy is the interation in this level
            mv $OUT_FILE $OUT_FILE.${iter_ext}
            COUNTER=$((COUNTER+1));
        fi

        # grep over constrained sites
        grep -q "over constrained" ./$DOY/sh_gamit_${DOY}.summary;
        if [ $? -eq 0 ]; then
            lines=`cat ./$DOY/sh_gamit_${DOY}.summary | sed -n 's/WARNING: \([0-9]*\) SITES.*$/\\1/p'`
            grep -A $lines "over constrained" ./$DOY/sh_gamit_${DOY}.summary >> monitor.log
        fi

        # grep updated coordinates
        grep Updated ./tables/lfile.;
        if [ $? -eq 0 ]; then
            grep Updated ./tables/lfile. >> monitor.log
        fi

        done

        # clean up
        rm -rf ionex met teqc*

        # blab about failures
        grep "FATAL" *.out >> monitor.log

        """

        run_file.write(contents)

        contents = \
        """

        # remove extraneous solution files
        rm ./$DOY/l*[ab].*;

        # make sure to rename the gfilea to the correct gfile[0-9].doy
        [ -e ./igs/gfilea.* ] && mv -f ./igs/gfilea* ./*/gfile[0-9]*

        # see if any of the coordinates were updated, exit if not
        grep Updated ./tables/lfile.;
        if [ $? -ne 0 ]; then
            echo "run.sh (`date +"%Y-%m-%d %T"`): Normal exit from run.sh" >> monitor.log
            # uncompress everything. Will be compressed later on
            gunzip ./*/*;
            exit
        fi

        # iteration detected!
        echo "run.sh (`date +"%Y-%m-%d %T"`): Updated coordinate detected in lfile. Iterating..." >> monitor.log

        # save this level's out file for debugging
        mv $OUT_FILE $OUT_FILE.${iter_ext}

        # apr file for updated coordinates
        aprfile=${EXPT}.apr

        # recreate the apr file with updated coordinates minus the comments
        sed -e 's/Updated from l.....\.[0-9][0-9][0-9]//g' ./tables/lfile. > ./tables/$aprfile;

        # the copy of the lfile was saved BEFORE running GAMIT. Replace with the updated version
        cp ./tables/$aprfile ./tables/lfile.

        # copy over an updated gfile if it exists
        # cp ./*/gfile* ./tables/

        # update level
        level=$((level+1));

        # remove the 'old' solution
        [ $level -le $MAX_LEVEL ] && rm -rf ./$DOY;

        # decompress the remaining solution files
        gunzip ./*/*;

        # do another iteration
        ./run.sh $level;

        """

        run_file.write(contents)
        run_file.close()

        os.system('chmod +x '+run_file_path)

    def create_finish_script(self):

        year = self.date.yyyy()
        doy = self.date.ddd()

        # extract the gps week and convert to string
        gpsWeek_str = str(self.date.gpsWeek)

        # normalize gps week string
        if self.date.gpsWeek < 1000: gpsWeek_str = '0' + gpsWeek_str

        # extract the gps week and day of week
        gps_week = self.date.gpsWeek
        gps_week_day = self.date.gpsWeekDay

        finish_file_path = os.path.join(self.pwd, 'finish.sh')

        try:
            finish_file = open(finish_file_path,'w')
        except (OSError, IOError):
            raise Exception('could not open file '+finish_file_path)

        contents = \
        """#!/bin/bash
        export INSTITUTE=%s

        echo "finish.sh (`date +"%%Y-%%m-%%d %%T"`): Finish script started" >> monitor.log

        # set the name of the outfile
        FILE=%s%s%s
        DOY=%s
        YEAR=%s

        # move to the solution path
        if [ ! -d ./glbf ]; then
            # something went wrong! no glbf dir
            mkdir glbf
        fi

        cd glbf

        # make sure an h file exists, if not exit
        if [ ! -f ../$DOY/h*.${YEAR}${DOY} ]; then
            echo "FATAL in finish.sh (`date +"%%Y-%%m-%%d %%T"`): h-files not found in $DOY folder. Exit" >> ../monitor.log
            exit;
        fi

        # get the WL and NL ambiguity resolution and the nrms double diff statistics
        echo "finish.sh (`date +"%%Y-%%m-%%d %%T"`): NRMS and WL-NL ambiguity summary follows:" >> ../monitor.log
        grep 'nrms' ../$DOY/sh_gamit_${DOY}.summary >> ../monitor.log
        grep 'WL fixed' ../$DOY/sh_gamit_${DOY}.summary >> ../monitor.log

        # link the svnav.dat file
        ln -s ../tables/svnav.dat .

        # create the binary h-file
        htoglb . tmp.svs ../$DOY/h*.${YEAR}${DOY}  >> ../${FILE}.out

        # convert the binary h-file to sinex file
        glbtosnx . "" h*.glx ${FILE}.snx >> ../${FILE}.out

        # clean up
        rm HTOGLB.* tmp.svs l*  svnav.dat

        # move back to home
        cd ..;

        """ % (self.gamitopts['org'], self.gamitopts['org'], gpsWeek_str, str(gps_week_day), doy, year[2:4])

        # dump contents to the script file
        finish_file.write(contents)

        # this section is to calculate the orbits
        if self.gamitopts['expt_type'] == 'relax':

            # create an sp3 file from the g-file
            contents  = \
            """
            # move to the solutions directory
            cd ./solutions/*

            # make temporary directory
            mkdir tmp

            # copy the gfile to temp dir
            cp gfile* tmp/

            # move to the temp dir
            cd tmp;

            # do the damn thing
            mksp3.sh %s %s %s

            # copy the sp3 file to solution dir if exists
            [ -e *.sp3 ] && mv *.sp3 ..;

            # move out of temporary directory
            cd ..;

            # clean up
            rm -rf tmp gfile*;

            # back to home directory
            cd ../..

            """ % (year,doy,self.options['org'])

            finish_file.write(contents)

            return

        contents = \
        """
        # move to the solutions directory
        cd $DOY

        # rename o file to znd file
        if [ -f o*a.[0-9][0-9][0-9]* ]; then
            mv -f o*a.[0-9][0-9][0-9]* ../glbf/%s%s%s.znd;
        fi

        # remove a priori o file
        if [ -f o*p.[0-9][0-9][0-9]* ]; then
            rm -f o*p.[0-9][0-9][0-9]*;
        fi

        # restore home dir
        cd ..

        """ % (self.gamitopts['org'], gpsWeek_str, str(gps_week_day))

        finish_file.write(contents)

        contents = \
        """
        # move to the solutions directory
        cd $DOY

        # clean up
        # remove the grid files, rinex files, etc
        rm -rf gfile* *.grid ????????.??o

        # compress remaining files
        for file in $(ls);do gzip --force $file; done

        # return to home directory
        cd ..

        cd rinex
        rm -rf *
        cd ..
        echo "finish.sh (`date +"%Y-%m-%d %T"`): Done processing h-files and generating SINEX." >> monitor.log

        """

        finish_file.write(contents)

        # make sure to close the file
        finish_file.close()

        # add executable permissions
        os.system('chmod +x '+finish_file_path)

        return
