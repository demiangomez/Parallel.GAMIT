"""
Project: Parallel.GAMIT
Date: 4/3/17 6:57 PM
Author: Demian D. Gomez
"""
import os
from datetime import datetime
import shutil
import subprocess
import re
import glob
import platform
import traceback

# app
import pyRinex
import pySp3
import pyBrdc
from Utils import (file_write, file_open,
                   file_append, file_readlines,
                   chmod_exec, stationID)

def now_str():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

class GamitTask(object):

    def __init__(self, remote_pwd, params, solution_pwd):

        self.pwd          = remote_pwd
        self.solution_pwd = solution_pwd
        self.pwd_igs      = os.path.join(remote_pwd, 'igs')
        self.pwd_brdc     = os.path.join(remote_pwd, 'brdc')
        self.pwd_rinex    = os.path.join(remote_pwd, 'rinex')
        self.pwd_tables   = os.path.join(remote_pwd, 'tables')

        self.params    = params
        self.options   = params['options']
        self.orbits    = params['orbits']
        self.gamitopts = params['gamitopts']
        self.date      = params['date']
        self.success   = False
        self.stdout    = ''
        self.stderr    = ''
        self.p         = None

        file_write(os.path.join(self.solution_pwd, 'monitor.log'),
                   now_str() +
                   ' -> GamitTask initialized for %s: %s\n' % (self.params['DirName'],
                                                               self.date.yyyyddd()))

    def start(self, dirname, year, doy, dry_run=False):
        monitor_open = False

        try:
            # copy the folder created by GamitSession in the solution_pwd to the remote_pwd (pwd)
            try:
                if not os.path.exists(os.path.dirname(self.pwd)):
                    os.makedirs(os.path.dirname(self.pwd))
            except OSError:
                # racing condition having several processes trying to create the same folder
                # if OSError occurs, ignore and continue
                pass

            # if the local folder exists (due to previous incomplete processing, erase it).
            if os.path.exists(self.pwd):
                shutil.rmtree(self.pwd)

            # ready to copy the shared solution_dir to pwd
            shutil.copytree(self.solution_pwd, self.pwd, symlinks=True)

            with file_open(os.path.join(self.pwd, 'monitor.log'), 'a') as monitor:
                monitor_open = True

                def log(s):
                    monitor.write(now_str() + ' -> ' + s + '\n')

                log('%s %i %i executing on %s' % (dirname, year, doy, platform.node()))
                log('fetching orbits')

                try:
                    Sp3 = pySp3.GetSp3Orbits(self.orbits['sp3_path'], self.date, self.orbits['sp3types'],
                                             self.pwd_igs, True)  # type: pySp3.GetSp3Orbits

                except pySp3.pySp3Exception:
                    log('could not find principal orbits, fetching alternative')

                    # try alternative orbits
                    if self.options['sp3altrn']:
                        Sp3 = pySp3.GetSp3Orbits(self.orbits['sp3_path'], self.date, self.orbits['sp3altrn'],
                                                 self.pwd_igs, True)  # type: pySp3.GetSp3Orbits
                    else:
                        raise

                if Sp3.type != 'igs':
                    # rename file
                    shutil.copyfile(Sp3.file_path, Sp3.file_path.replace(Sp3.type, 'igs'))

                log('fetching broadcast orbits')

                pyBrdc.GetBrdcOrbits(self.orbits['brdc_path'], self.date, self.pwd_brdc,
                                     no_cleanup=True)  # type: pyBrdc.GetBrdcOrbits

                for rinex in self.params['rinex']:

                    log('fetching rinex for %s %s %s %s'
                        % (stationID(rinex), rinex['StationAlias'],
                           '{:10.6f} {:11.6f}'.format(rinex['lat'], rinex['lon']), 'tie' if rinex['is_tie'] else ''))

                    try:
                        with pyRinex.ReadRinex(rinex['NetworkCode'],
                                               rinex['StationCode'],
                                               rinex['source'], False) as Rinex:  # type: pyRinex.ReadRinex

                            # WARNING! some multiday RINEX were generating conflicts because the RINEX has a name, say,
                            # tuc12302.10o and the program wants to rename it as tuc12030.10o but because it's a
                            # multiday file, during __init__ it's already split and renamed as tuc12300.10o and
                            # additional folders are generated with the information for each file. Therefore, find
                            # the rinex that corresponds to the date being processed and use that one instead of the
                            # original file. These files are not allowed by pyArchiveService, but the "start point" of
                            # the database (i.e. the files already in the folders read by pyScanArchive) has such
                            # problems.

                            # figure out if this station has been affected by an earthquake
                            # if so, window the data
                            if rinex['jump'] is not None:
                                monitor.write(
                                    '                    -> RINEX file has been windowed: ETM detected jump on ' +
                                    rinex['jump'].datetime().strftime('%Y-%m-%d %H:%M:%S') + '\n')

                            if Rinex.multiday:
                                # find the rinex that corresponds to the session being processed
                                for Rnx in Rinex.multiday_rnx_list:
                                    if Rnx.date == self.date:
                                        Rnx.rename(rinex['destiny'])

                                        if rinex['jump'] is not None:
                                            self.window_rinex(Rnx, rinex['jump'])
                                        # before creating local copy, decimate file
                                        Rnx.decimate(30)
                                        Rnx.purge_comments()
                                        Rnx.compress_local_copyto(self.pwd_rinex, rinex['destiny'])
                                        break
                            else:
                                Rinex.rename(rinex['destiny'])

                                if rinex['jump'] is not None:
                                    self.window_rinex(Rinex, rinex['jump'])
                                # before creating local copy, decimate file
                                Rinex.decimate(30)
                                Rinex.purge_comments()
                                Rinex.compress_local_copyto(self.pwd_rinex, rinex['destiny'])

                    except (OSError, IOError):
                        log('An error occurred while trying to copy ' +
                            rinex['source'] + ' to ' + rinex['destiny'] + ': File skipped.')

                    except (pyRinex.pyRinexException, Exception) as e:
                        log('An error occurred while trying to copy ' +
                            rinex['source'] + ': ' + str(e))

                log('executing GAMIT')

                # create the run script
                self.create_replace_links()
                self.create_run_script()
                self.create_finish_script()

            # run the script to replace the links of the tables directory
            self.p = subprocess.Popen('find ./tables ! -name "otl.grid" -type l -exec ./replace_links.sh {} +',
                                      shell=True, stdout=subprocess.PIPE,stderr=subprocess.PIPE, cwd=self.pwd)
            _, _ = self.p.communicate()

            # now execute the run script
            if not dry_run:
                self.p = subprocess.Popen('./run.sh', shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                          cwd=self.pwd)

                self.stdout, self.stderr = self.p.communicate()

                self.p = subprocess.Popen('./finish.sh', shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                          cwd=self.pwd)

                self.stdout, self.stderr = self.p.communicate()

                # check for any fatals
                self.p = subprocess.Popen('grep -q \'FATAL\' monitor.log', shell=True, stdout=subprocess.PIPE,
                                          stderr=subprocess.PIPE, cwd=self.pwd)

                _, _ = self.p.communicate()

                self.success = (self.p.returncode != 0)

            # output statistics to the parent to display
            result = self.parse_monitor(self.success)

            file_append(os.path.join(self.pwd, 'monitor.log'),
                        now_str() + ' -> return to Parallel.GAMIT\n')

            # no matter the result of the processing, move folder to final destination
            if not dry_run:
                self.finish()

            return result

        except:

            msg = traceback.format_exc() + '\nProcessing %s date %s on node %s' \
                  % (self.params['NetName'], self.date.yyyyddd(), platform.node())

            # DDG: do not attempt to write to monitor.log or do any file operations (maybe permission problem)
            # problem might occur during copytree or rmtree or some other operation before opening monitor.log
            if monitor_open:
                file_append(os.path.join(self.pwd, 'monitor.log'),
                            now_str() +
                            ' -> ERROR in pyGamitTask.start()\n%s' % msg)

                # the solution folder exists because it was created by GamitSession to start the processing.
                # erase it to upload the result
                if os.path.exists(self.solution_pwd):
                    shutil.rmtree(self.solution_pwd)

                # execute final error step: copy to self.solution_pwd
                shutil.copytree(self.pwd, self.solution_pwd, symlinks=True)
                # remove the remote pwd
                shutil.rmtree(self.pwd)

                # output statistics to the parent to display
                result = self.parse_monitor(False)
            else:
                result = {'session'             : '%s %s' % (self.date.yyyyddd(), self.params['DirName']),
                          'Project'             : self.params['NetName'],
                          'subnet'              : self.params['subnet'],
                          'Year'                : self.date.year,
                          'DOY'                 : self.date.doy,
                          'FYear'               : self.date.fyear,
                          'wl'                  : 0,
                          'nl'                  : 0,
                          'nrms'                : 0,
                          'relaxed_constrains'  : '',
                          'max_overconstrained' : '',
                          'node'                : platform.node(),
                          'execution_time'      : 0,
                          'execution_date'      : 0,
                          'missing'             : '',
                          'success'             : False,
                          'fatals'              : []
                          }

            result['error'] = msg

            # return useful information to the main node
            return result

    def window_rinex(self, Rinex, window):

        # windows the data:
        # check which side of the earthquake yields more data: window before or after the earthquake
        dt = window.datetime()
        if (dt.hour + dt.minute/60.0) < 12:
            Rinex.window_data(start = dt)
        else:
            Rinex.window_data( end = dt)

    def parse_monitor(self, success):
        lines  = file_readlines(self.pwd + '/monitor.log')
        output = ''.join(lines)

        try:
            start_time = datetime.strptime(
                re.findall(r'run.sh \((\d+-\d+-\d+ \d+:\d+:\d+)\): Iteration depth: 1',
                           output, re.MULTILINE)[0], '%Y-%m-%d %H:%M:%S')
        except:
            start_time = datetime(2001, 1, 1, 0, 0, 0)

        try:
            if success:
                end_time = datetime.strptime(
                    re.findall(r'finish.sh \((\d+-\d+-\d+ \d+:\d+:\d+)\): Done processing h-files and generating SINEX.'
                               , output, re.MULTILINE)[0], '%Y-%m-%d %H:%M:%S')
            else:
                end_time = datetime.now()

        except:
            end_time = datetime(2001, 1, 1, 0, 0, 0)

        try:
            if not success:
                fatals = set(re.findall(r'(.*?FATAL.*)', output, re.MULTILINE))
            else:
                fatals = []
        except Exception as e:
            fatals = ['Could not retrieve FATALS: ' + str(e)]

        try:
            iterations = int(re.findall(r'run.sh \(\d+-\d+-\d+ \d+:\d+:\d+\): Iteration depth: (\d+)',
                             output, re.MULTILINE)[-1])
        except:
            iterations = 0

        try:
            nrms = float(
                re.findall(r'Prefit nrms:\s+\d+.\d+[eEdD]\+\d+\s+Postfit nrms:\s+(\d+.\d+[eEdD][+-]\d+)', output,
                           re.MULTILINE)[-1])
        except:
            # maybe GAMIT didn't finish
            nrms = 100

        try:
            updated_apr = re.findall(r' (\w+).*?Updated from', output, re.MULTILINE)[0]
            updated_apr = [upd.replace('_GPS', '').lower() for upd in updated_apr]
            upd_stn = []
            for stn in updated_apr:
                for rinex in self.params['rinex']:
                    if rinex['StationAlias'].lower() == stn.lower():
                        upd_stn += [stationID(rinex)]

            upd_stn = ','.join(upd_stn)
        except:
            # maybe GAMIT didn't finish
            upd_stn = None


        try:
            wl = float(re.findall(r'WL fixed\s+(\d+.\d+)', output, re.MULTILINE)[0])
        except:
            # maybe GAMIT didn't finish
            wl = 0

        try:
            nl = float(re.findall(r'NL fixed\s+(\d+.\d+)', output, re.MULTILINE)[0])
        except:
            # maybe GAMIT didn't finish
            nl = 0

        try:
            oc = re.findall(r'relaxing over constrained stations (\w+.*)', output, re.MULTILINE)[0]
            oc = oc.replace('|', ',').replace('_GPS', '').lower()

            oc_stn = []
            for stn in oc.split(','):
                for rinex in self.params['rinex']:
                    if rinex['StationAlias'].lower() == stn.lower():
                        oc_stn += [stationID(rinex)]

            oc_stn = ','.join(oc_stn)

        except:
            # maybe GAMIT didn't finish
            oc_stn = None

        try:
            max_overconstrained = None
            overcons = re.findall(r'GCR APTOL (\w+).{10}\s+([-]?\d+.\d+)', output, re.MULTILINE)

            if len(overcons) > 0:
                vals = [float(o[1]) for o in overcons]
                i    = vals.index(max(abs(v) for v in vals))
                stn  = overcons[i][0]

                for rinex in self.params['rinex']:
                    if rinex['StationAlias'].lower() == stn.lower():
                        # get the real station code
                        max_overconstrained = stationID(rinex)
            else:
                max_overconstrained = None

        except:
            # maybe GAMIT didn't finish
            max_overconstrained = None

        try:
            ms = re.findall(r'No data for site (\w+)',   output, re.MULTILINE)
            ds = re.findall(r'.*deleting station (\w+)', output, re.MULTILINE)
            missing_sites = []
            for stn in ms + ds:
                for rinex in self.params['rinex']:
                    if rinex['StationAlias'].lower() == stn.lower() and \
                       stationID(rinex) not in missing_sites:
                        if stn in ms:
                            missing_sites += ['(' + stationID(rinex) + ')']
                        else:
                            missing_sites += [stationID(rinex)]

        except:
            # maybe GAMIT didn't finish
            missing_sites = []

        return {'session'             : '%s %s' % (self.date.yyyyddd(), self.params['DirName']),
                'Project'             : self.params['NetName'],
                'subnet'              : self.params['subnet'],
                'Year'                : self.date.year,
                'DOY'                 : self.date.doy,
                'FYear'               : self.date.fyear,
                'wl'                  : wl,
                'nl'                  : nl,
                'nrms'                : nrms,
                'relaxed_constrains'  : oc_stn,
                'max_overconstrained' : max_overconstrained,
                'updated_apr'         : upd_stn,
                'iterations'          : iterations,
                'node'                : platform.node(),
                'execution_time'      : int((end_time - start_time).total_seconds() / 60.0),
                'execution_date'      : start_time,
                'missing'             : missing_sites,
                'success'             : success,
                'fatals'              : fatals
                }

    def finish(self):
        try:
            # delete everything inside the processing dir
            shutil.rmtree(self.pwd_brdc)
            shutil.rmtree(self.pwd_igs)

            # remove files in tables
            for ftype in ('*.grid', '*.dat', '*.apr'):
                for ff in glob.glob(os.path.join(self.pwd_tables, ftype)):
                    os.remove(ff)

            # remove processing files
            for ftype in ('b*', 'cfmrg*', 'DPH.*', 'eq_rename.*', 'g*', 'k*', 'p*', 'rcvant.*', 'y*'):
                for ff in glob.glob(os.path.join(os.path.join(self.pwd, self.date.ddd()), ftype)):
                    os.remove(ff)

            try:
                if not os.path.exists(os.path.dirname(self.solution_pwd)):
                    os.makedirs(os.path.dirname(self.solution_pwd))
            except OSError:
                # racing condition having several processes trying to create the same folder
                # if OSError occurs, ignore and continue
                pass

            # the solution folder exists because it was created by GamitSession to start the processing.
            # erase it to upload the result
            if os.path.exists(self.solution_pwd):
                shutil.rmtree(self.solution_pwd)

            # execute final step: copy to self.solution_pwd
            shutil.copytree(self.pwd, self.solution_pwd, symlinks=True)
            # remove the remote pwd
            shutil.rmtree(self.pwd)

        except:
            msg = traceback.format_exc() + '\nProcessing %s date %s on node %s' \
                  % (self.params['NetName'], self.date.yyyyddd(), platform.node())

            file_append(os.path.join(self.pwd, 'monitor.log'), 
                        now_str() +
                        ' -> ERROR in pyGamitTask.finish()\n%s' % msg)

    def create_replace_links(self):
        replace_ln_file_path = os.path.join(self.pwd, 'replace_links.sh')

        try:
            replace_ln_file = file_open(replace_ln_file_path, 'w')
        except (OSError, IOError):
            raise Exception('could not open file ' + replace_ln_file_path)

        replace_ln_file.write("""#!/bin/bash
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
        """)

        replace_ln_file.close()

        chmod_exec(replace_ln_file_path)

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
            run_file = file_open(run_file_path, 'w')
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
        NOFTP=%s;

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
        % (self.gamitopts['org'], self.gamitopts['expt'], year, doy, '12', self.gamitopts['eop_type'],
           self.gamitopts['noftp'], self.gamitopts['org'], gpsWeek_str, str(self.date.gpsWeekDay))

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

        grep -q    "FATAL.*MAKEX/openf: Error opening file:.*" $OUT_FILE;
        if [ $? -eq 0 ]; then
            grep       "FATAL.*MAKEX/openf: Error opening file:.*" $OUT_FILE;
            echo "run.sh (`date +"%Y-%m-%d %T"`): MAKEX/openf: Error opening file" >> monitor.log
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
        
        # grep over constrained sites
        grep -q "over constrained" ./$DOY/sh_gamit_${DOY}.summary;
        if [ $? -eq 0 ]; then
            # get the number of lines
            lines=`cat ./$DOY/sh_gamit_${DOY}.summary | sed -n 's/WARNING: \([0-9]*\) SITES.*$/\\1/p'`
            grep -A $lines "over constrained" ./$DOY/sh_gamit_${DOY}.summary >> monitor.log
            
            # DDG: new behavior -> remove the station with the largest over constrained coordinate
            # grep the sites and get the unique list separeted by | (to do regex grep)
            # stns=`grep "GCR APTOL" monitor.log | awk '{print $4"_GPS"}' | uniq | tr '<line break>' '|'`
            # copy the sittbl. (just in case)
            # cp tables/sittbl. tables/sittbl.${iter_ext}
            # remove those from the sittbl list: this will relax station to 100 m
            # grep -v -E "${stns:0:-1}" tables/sittbl.${iter_ext} > tables/sittbl.
            
            stns=`grep "GCR APTOL" ./$DOY/sh_gamit_${DOY}.summary | awk '{print sqrt($(NF) * $(NF)), $4}' | sort -r | head -n1 | awk '{print $2}' | tr '[:upper:]' '[:lower:]'`
            echo "run.sh (`date +"%Y-%m-%d %T"`): deleting over constrained station ${stns}" >> monitor.log
            rm rinex/${stns}*;
            rm $DOY/${stns}* ;
            
            # echo "run.sh (`date +"%Y-%m-%d %T"`): relaxing over constrained stations ${stns:0:-1}" >> monitor.log
            echo "run.sh (`date +"%Y-%m-%d %T"`): replacing lfile. from this run with lfile.${iter_ext}" >> monitor.log
            rm ./tables/lfile.
            cp ./tables/lfile.${iter_ext} ./tables/lfile.
            
            echo "run.sh (`date +"%Y-%m-%d %T"`): will try sh_gamit again ..." >> monitor.log
            
            EXE=1;
        fi

        if [ $EXE -eq 1 ]; then
            # if it will retry, save the previous output using extension .l00_i00, .l00_i01, ... etc
            # where lxx is the level of iteration and iyy is the interation in this level
            mv $OUT_FILE $OUT_FILE.${iter_ext}
            COUNTER=$((COUNTER+1));
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
        # rm ./$DOY/l*[ab].*;

        # make sure to rename the gfilea to the correct gfile[0-9].doy
        [ -e ./igs/gfilea.* ] && mv -f ./igs/gfilea* ./*/gfile[0-9]*

        # see if any of the coordinates were updated, exit if not
        # DDG: Actually, sometimes the final updated coordinate only differs by < .3 m when solve is invoked more than
        # once from within sh_gamit. Therefore, also check that the updated coordinate is > .3 m from the original APR
        # this happens because the first Updated coordinate (lxxxxa.ddd) triggers an iteration in solve (lxxxxb.ddd) 
        # with a solution that is again close to the original APR. Without this check, PG iterates 3 times unnecessarily
        
        grep Updated ./tables/lfile.;
        if [ $? -ne 0 ]; then
            echo "run.sh (`date +"%Y-%m-%d %T"`): Normal exit from run.sh" >> monitor.log
            # uncompress everything. Will be compressed later on
            gunzip ./*/*;
            exit
        else
            updated=(`grep Updated ./tables/lfile. | awk '{print $1}'`)
            
            RERUN=0
            
            for stn in ${updated[*]}
            do
                coords=`grep $stn ./tables/lfile. | awk '{print $2,$3,$4}'`
                
                # use the copy of the lfile to grep the APR coordinates
                aprs=`grep $stn ./tables/lfile.${iter_ext} | awk '{print $2,$3,$4}'`
                
                # get the distance between Updated and APR
                dist=`echo $coords $aprs | awk '{print sqrt(($1 - $4)^2 + ($2 - $5)^2 + ($3 - $6)^2)}'`
                
                if (( $(echo "$dist > 0.3" | bc -l) )); then
                    RERUN=1;
                fi
            done
            
            # if RERUN = 0, Updated coordinate was < 0.3 m
            if [ $RERUN -eq 0 ]; then
                echo "run.sh (`date +"%Y-%m-%d %T"`): Updated coordinate detected but final solution within 0.3 m of APR" >> monitor.log
                echo "run.sh (`date +"%Y-%m-%d %T"`): Normal exit from run.sh" >> monitor.log
                # uncompress everything. Will be compressed later on
                gunzip ./*/*;
                exit
            fi
        fi

        # iteration detected!
        echo "run.sh (`date +"%Y-%m-%d %T"`): Updated coordinate detected in lfile. Iterating..." >> monitor.log

        # save this level's out file for debugging
        mv $OUT_FILE $OUT_FILE.${iter_ext}

        # apr file for updated coordinates
        aprfile=${EXPT}.temp

        # recreate the apr file with updated coordinates minus the comments
        sed -e 's/Updated from l.....\.[0-9][0-9][0-9]//g' ./tables/lfile. > ./tables/${aprfile};

        # the copy of the lfile was saved BEFORE running GAMIT. Replace with the updated version
        cp ./tables/${aprfile} ./tables/lfile.

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

        chmod_exec(run_file_path)

    def create_finish_script(self):

        year = self.date.yyyy()
        doy  = self.date.ddd()

        # extract the gps week and convert to string
        gpsWeek_str = str(self.date.gpsWeek)

        # normalize gps week string
        if self.date.gpsWeek < 1000: gpsWeek_str = '0' + gpsWeek_str

        # extract the gps week and day of week
        gps_week     = self.date.gpsWeek
        gps_week_day = self.date.gpsWeekDay

        finish_file_path = os.path.join(self.pwd, 'finish.sh')

        try:
            finish_file = file_open(finish_file_path,'w')
        except (OSError, IOError):
            raise Exception('could not open file '+finish_file_path)

        contents = """#!/bin/bash
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
        htoglb . tmp.svs -a ../$DOY/h*.${YEAR}${DOY}  >> ../${FILE}.out

        # grep any missing stations to report them to monitor.log
        grep 'No data for site ' ../${FILE}.out | sort | uniq >> ../monitor.log
        
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
            contents = """
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

        contents = """
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

        contents = """
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
        chmod_exec(finish_file_path)
