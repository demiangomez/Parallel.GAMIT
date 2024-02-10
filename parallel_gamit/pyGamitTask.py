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
import numpy

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
        self.pwd_glbf     = os.path.join(remote_pwd, 'glbf')

        self.params    = params
        self.options   = params['options']
        self.orbits    = params['orbits']
        self.gamitopts = params['gamitopts']
        self.systems   = params['gamitopts']['systems']
        self.date      = params['date']
        self.success   = False
        self.stdout    = ''
        self.stderr    = ''
        self.p         = None

        self.monitor_file = os.path.join(self.pwd, 'monitor.log')

        file_write(os.path.join(self.solution_pwd, 'monitor.log'),
                   now_str() +
                   ' -> GamitTask initialized for %s: %s\n' % (self.params['DirName'],
                                                               self.date.yyyyddd()))

    def start(self, dirname, year, doy, dry_run=False):
        copy_done = False

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

            copy_done = True

            self.log('%s %i %i executing on %s systems %s' % (dirname, year, doy,
                                                              platform.node(), ', '.join(self.systems)))

            self.fetch_orbits()

            self.fetch_rinex()

            self.log('Preparing GAMIT execution')

            # create the run script
            self.create_replace_links()

            # run the script to replace the links of the tables directory
            self.execute('find ./tables ! -name "otl.grid" -type l -exec ./replace_links.sh {} +')

            results = []
            # now execute the run script
            if not dry_run:

                # do a GAMIT run for each system
                for sys in self.systems:
                    results.append(self.run_gamit(sys))

                success_results = [r for r in results if r['success']]
                if len(success_results) > 1:
                    self.combine_systems(success_results)
                elif len(success_results) == 1:
                    # just copy the system result to glbf
                    shutil.copyfile(success_results[0]['glbf'], self.pwd_glbf)
                else:
                    # a problem with all systems, declare fatal
                    self.log('No valid system solutions. Check fatals.')

                self.finish()

            self.log('return to Parallel.GAMIT')

            return results

        except Exception:

            msg = traceback.format_exc() + '\nProcessing %s date %s on node %s' \
                  % (self.params['NetName'], self.date.yyyyddd(), platform.node())

            # DDG: do not attempt to write to monitor.log or do any file operations (maybe permission problem)
            # problem might occur during copytree or rmtree or some other operation before opening monitor.log
            if copy_done:
                # if the copy was done, then it is possible to write, so log the error in monitor
                self.log('ERROR in pyGamitTask.start()\n%s' % msg)

                # the solution folder exists because it was created by GamitSession to start the processing.
                # erase it to upload the result
                if os.path.exists(self.solution_pwd):
                    shutil.rmtree(self.solution_pwd)

                # execute final error step: copy to self.solution_pwd
                shutil.copytree(self.pwd, self.solution_pwd, symlinks=True)
                # remove the remote pwd
                shutil.rmtree(self.pwd)

                # output dummy statistics to the parent for display
                results = self.run_gamit('G', dummy=True)
            else:
                results = self.run_gamit('G', dummy=True)

            results['error'] = msg

            # return useful information to the main node
            return results

    def log(self, message, no_timestamp=False):
        if not no_timestamp:
            file_append(self.monitor_file, now_str() + ' -> ' + message + '\n')
        else:
            file_append(self.monitor_file, message + '\n')

    def combine_systems(self, results):
        # create a globk.cmd file for the combination
        hfile = f'h{str(self.date.year)[2:]}{self.date.month:02}{self.date.doy:02}1200.glx'

        try:
            globk_cmd = file_open(os.path.join(self.pwd_glbf, 'globk.cmd'), 'w')
        except (OSError, IOError):
            raise Exception('could not open file globk.cmd')

        contents = f"""
 app_ptid all
 prt_opt GDLF MIDP CMDS PLST
 out_glb ../glbf/{hfile}
 descript Multi GNSS combination of global or regional solutions
 max_chii  1. 0.6
 apr_site  all 1 1 1 0 0 0
        """

        globk_cmd.write(contents)
        globk_cmd.close()

        try:
            gdl_file = file_open(os.path.join(self.pwd_glbf, 'hfiles.gdl'), 'w')
        except (OSError, IOError):
            raise Exception('could not open file hfiles.gdl')

        # create the gdl file with the glx files to merge
        contents = ''
        for sol in results:
            contents += sol['glbf'] + '\n'

        gdl_file.write(contents)
        gdl_file.close()

        self.execute('globk 0 out.prt globk.log hfiles.gdl globk.cmd > globk.out')

        # now parse the output for any problems

    def execute(self, script_name):
        self.p = subprocess.Popen(script_name, shell=False, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, cwd=self.pwd)

        self.stdout, self.stderr = self.p.communicate()

    def fetch_orbits(self):
        self.log('fetching orbits')

        try:
            Sp3 = pySp3.GetSp3Orbits(self.orbits['sp3_path'], self.date, self.orbits['sp3types'],
                                     self.pwd_igs, True)

        except pySp3.pySp3Exception:
            self.log('could not find orbits to run the process')
            raise

        if Sp3.type != 'igs':
            # rename file
            shutil.copyfile(Sp3.file_path, Sp3.file_path.replace(Sp3.type, 'igs'))

        self.log('fetching broadcast orbits')

        pyBrdc.GetBrdcOrbits(self.orbits['brdc_path'], self.date, self.pwd_brdc, no_cleanup=True)

    def fetch_rinex(self):
        for rinex in self.params['rinex']:

            self.log('fetching rinex for %s %s %s %s' % (stationID(rinex), rinex['StationAlias'],
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
                        self.log(
                            '                    -> RINEX file has been windowed: ETM detected jump on ' +
                            rinex['jump'].datetime().strftime('%Y-%m-%d %H:%M:%S') + '\n', no_timestamp=True)

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
                self.log('An error occurred while trying to copy ' +
                         rinex['source'] + ' to ' + rinex['destiny'] + ': File skipped.')

            except (pyRinex.pyRinexException, Exception) as e:
                self.log('An error occurred while trying to copy ' +
                         rinex['source'] + ': ' + str(e))

    def window_rinex(self, Rinex, window):

        # windows the data:
        # check which side of the earthquake yields more data: window before or after the earthquake
        dt = window.datetime()
        if (dt.hour + dt.minute/60.0) < 12:
            Rinex.window_data(start = dt)
        else:
            Rinex.window_data( end = dt)

    def finish(self):
        try:
            # delete everything inside the processing dir
            shutil.rmtree(self.pwd_brdc)
            shutil.rmtree(self.pwd_igs)

            # remove files in tables
            for ftype in ('*.grid', '*.dat', '*.apr'):
                for ff in glob.glob(os.path.join(self.pwd_tables, ftype)):
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

            self.log(f'ERROR in pyGamitTask.finish()\n{msg}')

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

    def translate_station_alias(self, station_alias):
        if type(station_alias) is str:
            for rinex in self.params['rinex']:
                if rinex['StationAlias'].lower() == station_alias.lower():
                    return stationID(rinex)
        elif type(station_alias) is list:
            stn_list = []
            for stn in station_alias:
                for rinex in self.params['rinex']:
                    if rinex['StationAlias'].lower() == stn.lower():
                        stn_list.append(stationID(rinex))
            return stn_list

        # if here, could not find the alias!
        raise Exception(f'Could not find station name from alias {station_alias} or input is of invalid type')

    def run_gamit(self, system, dummy=False):

        year     = self.date.yyyy()
        doy      = self.date.ddd()
        org      = self.gamitopts['org']
        expt     = self.gamitopts['expt']
        min_t    = '12'
        eop      = self.gamitopts['eop_type'],
        noftp    = self.gamitopts['noftp'], str(self.date.gpsWeekDay)
        gpswk    = self.date.wwww()
        gpswkday = str(self.date.gpsWeekDay)
        system   = system.upper()
        # the date string to print the info to monitor.log
        sdate    = '`date +"%%Y-%%m-%%d %%T"`'
        fatal    = False

        result   = {'session'             : '%s %s' % (self.date.yyyyddd(), self.params['DirName']),
                    'system'              : system,
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
                    'updated_apr'         : None,
                    'iterations'          : 0,
                    'node'                : platform.node(),
                    'execution_time'      : 0,
                    'execution_date'      : datetime.now(),
                    'glbf'                : None,
                    'missing'             : [],
                    'success'             : False,
                    'fatals'              : []}

        if dummy:
            return result

        # set the path and name for the run script
        run_file_path    = os.path.join(self.pwd, f'run_{system}.sh')
        # set the path and name for the finish script
        finish_file_path = os.path.join(self.pwd, f'finish_{system}.sh')

        try:
            run_file = file_open(run_file_path, 'w')
        except (OSError, IOError):
            raise Exception('could not open file ' + run_file_path)

        if not os.path.isdir(os.path.join(self.pwd, 'tmp')):
            os.makedirs(os.path.join(self.pwd, 'tmp'))

        if not os.path.isdir(os.path.join(self.pwd, f'gsoln/{system}')):
            os.makedirs(os.path.join(self.pwd, f'gsoln/{system}'))

        summary_path = os.path.join(self.pwd, f'{doy}{system}/sh_gamit_${doy}{system}.summary')
        lfile_path   = os.path.join(self.pwd_tables, 'lfile.')

        # once executed, check output
        # loop at least three times
        last_i  = 0
        output  = ''
        lfile   = ''
        summary = ''
        for i in range(3):
            retry  = False
            last_i = i
            # name for the GAMIT execution output file
            outfile = org + gpswk + gpswkday + system + str(i) + '.out'
            outfile_path = os.path.join(self.pwd, outfile)

            contents = f"""#!/bin/bash
            # just in case, create a temporary dir for fortran
            export TMPDIR=`pwd`/tmp
            export INSTITUTE={org}
            # log to the monitor
            echo "{sdate} run_{system}.sh" >> monitor.log
            # execute GAMIT
            sh_gamit -gnss {system} -update_l N -topt none -c -copt null {"-noftp" if noftp == "yes" else ""} -dopt c x -expt {expt} -d ${year} {doy} -minspan {min_t} -remakex Y -eop {eop} &> {outfile};
            
            # remove extraneous lfiles
            # rm ./{doy}{system}/l*[ab].*;

            # make sure to rename the gfilea to the correct gfile[0-9].doy
            # this line is inherited from Abel, not sure about how it's used. Leave just in case.
            [ -e ./igs/gfilea.* ] && mv -f ./igs/gfilea* ./*/gfile[0-9]*
            """

            run_file.write(contents)
            run_file.close()
            chmod_exec(run_file_path)

            # before executing, make a copy of the lfile
            shutil.copyfile(lfile_path, lfile_path + str(i))
            self.execute(run_file_path)

            # read the contents of the output files
            output  = ''.join(file_readlines(outfile_path))
            summary = ''.join(file_readlines(summary_path))
            lfile   = ''.join(file_readlines(lfile_path))
            lfile_i = ''.join(file_readlines(lfile_path + str(last_i)))

            # check for common problem running MAKEX, etc that usually just get fixed by rerunning
            if re.findall(r'FATAL.*FIXDRV/dcheck', output) or \
               re.findall(r'FATAL.*MAKEXP/makexp: No RINEX or X-files found', output) or \
               re.findall(r'FATAL.*MAKEX/get_rxfiles: Cannot find selected RINEX file', output) or \
               re.findall(r'FATAL.*MAKEX/openf: Error opening file:.*', output) or \
               re.findall(r'SOLVE/get_widelane: Error reading first record', output) or \
               re.findall(r'Failure in sh_preproc. STATUS 1 -- sh_gamit terminated', output):
                self.log(f'Issue found with this run (FIXDRV, MAKEXP, MAKEX, or SOLVE) trying again ({i})...')
                # skip any further tests
                continue

            # check for unreasonable geodetic height
            if re.findall(r'Geodetic height unreasonable', output):
                self.log(f'Geodetic height unreasonable in {outfile}')
                # TODO:
                # remove RINEX and station from DOY dir
                retry  = True

            # check for over constrained solutions
            if re.findall(r'over constrained', summary):
                self.log(f'Over constrained solution in sh_gamit_${doy}{system}.summary')
                # TODO:
                # two options: (1) relax over constrained sigmas or (2) remove them from processing
                # if relaxing, then replace current lfile. with previous lfile + str(i) since the
                # coordinates were changed by GAMIT (due to position change > coordinate sigma)
                retry = True

            # check for any updated coordinates
            if re.findall('Updated', lfile):
                # grep updated coordinates and print them to the monitor
                upd_stn = re.findall(r'\s(\w+)_\w+\s+(.\d+.\d+)\s+(.\d+.\d+)\s+(.\d+.\d+).*Updated.*', lfile)
                self.log(f'Found {len(upd_stn)} stations with updated coordinates in lfile. Checking deltas.')
                # monitor.write('\n'.join(re.findall(r'.*Updated.*', lfile)))

                delta = numpy.zeros(len(upd_stn))
                for si, stn in enumerate(upd_stn):
                    # find station in the previous lfile. (previous = lfile.i, before the run)
                    apr_stn = re.findall(r'\s{}_\w+\s+(.\d+.\d+)\s+(.\d+.\d+)\s+(.\d+.\d+)'.format(stn[0]),
                                         lfile_i)[0]
                    delta[si] = numpy.sqrt(numpy.square(float(stn[1]) - float(apr_stn[0])) +
                                           numpy.square(float(stn[2]) - float(apr_stn[1])) +
                                           numpy.square(float(stn[3]) - float(apr_stn[2])))

                    self.log(f'{stn[0]} update delta = {delta[si]} m', no_timestamp=True)

                    if numpy.any(delta > 0.3):
                        self.log(f'One or more stations with updated coordinates > 0.3 m.')
                        retry = True

            if not retry:
                # stop iteration if no issues found
                break
            else:
                self.log(f'Issue found in the run, trying again ({i})...')

        # save time stamp for end
        result['execution_time'] = int((datetime.now() - result['execution_date']).total_seconds() / 60.0)
        result['iterations']     = last_i

        # extract any FATALS
        if re.findall(r'.*?FATAL.*', output):
            self.log('\n'.join(re.findall(r'(.*?FATAL.*)', lfile)), no_timestamp=True)
            fatal = True
            # save the fatals as a list
            result['fatals'] = set(re.findall(r'(.*?FATAL.*)', output))

            self.log(f'Unsuccessful run for system {system}. Check fatal message.')
        else:
            # extract the run statistics and write it to the monitor
            self.log('NRMS and WL-NL ambiguity summary follows:')
            self.log('\n'.join(re.findall(r'(.*nrms.*)', summary)), no_timestamp=True)
            self.log('\n'.join(re.findall(r'(.*WL fixed.*)', summary)), no_timestamp=True)

            result['nrms'] = float(re.findall(
                r'Prefit nrms:\s+\d+.\d+[eEdD]\+\d+\s+Postfit nrms:\s+(\d+.\d+[eEdD][+-]\d+)', output)[-1])

            result['wl'] = float(re.findall(r'WL fixed\s+(\d+.\d+)', output)[0])
            result['nl'] = float(re.findall(r'NL fixed\s+(\d+.\d+)', output)[0])

            # now convert h file to GLX and place in each system folder
            try:
                finish_file = file_open(finish_file_path, 'w')
            except (OSError, IOError):
                raise Exception('could not open file ' + finish_file_path)

            contents = f"""#!/bin/bash
            # just in case, create a temporary dir for fortran
            export TMPDIR=`pwd`/tmp
            export INSTITUTE={org}
            # log to the monitor
            echo "{sdate} finish_{system}.sh" >> monitor.log
            
            cd gsoln/{system}
            # link the svnav file in tables
            ln -s ../../tables/svnav.dat .

            # create the binary h-file
            htoglb . tmp.svs -a ../../{doy}{system}/h*.{year}{doy}  >> htoglb.out
            
            # grep any missing stations to report them to monitor.log
            grep 'No data for site ' htoglb.out | sort | uniq >> ../../monitor.log
    
            # clean up
            rm HTOGLB.* tmp.svs l*  svnav.dat
            """

            finish_file.write(contents)
            finish_file.close()
            chmod_exec(finish_file_path)
            self.execute(finish_file_path)

            # retrieve no data for site x
            htoglb = ''.join(file_readlines(os.path.join(self.pwd, f'gsoln/{system}/htoglb.out')))

            result['missing'] = self.translate_station_alias(re.findall(r'No data for site (\w+)', htoglb))
            result['glbf']    = glob.glob(os.path.join(self.pwd, f'gsoln/{system}/h*.glx'))[0]
            if system == 'R':
                # for GLONASS, remove the GLX and rename the GLR to GLX
                os.remove(result['glbf'])
                shutil.move(result['glbf'][:-1] + 'r', result['glbf'])

            # finally, remove processing files after successful run
            for ftype in ('b*', 'cfmrg*', 'DPH.*', 'eq_rename.*', 'g*', 'k*', 'p*', 'rcvant.*', 'y*'):
                for ff in glob.glob(os.path.join(self.pwd, f'{doy}{system}/{ftype}')):
                    os.remove(ff)

        result['success'] = not fatal

        return result

