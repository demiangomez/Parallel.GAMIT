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


def replace_vars(archive, date):
    return archive.replace('$year', str(date.year)) \
        .replace('$doy', str(date.doy).zfill(3)) \
        .replace('$gpsweek', str(date.gpsWeek).zfill(4)) \
        .replace('$gpswkday', str(date.gpsWeekDay))


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

        # a dictionary to keep track of how many stations support each system
        self.system_count = {'E': 0, 'G': 0, 'R': 0, 'C': 0}

        self.monitor_file = os.path.join(self.pwd, 'monitor.log')

        file_write(os.path.join(self.solution_pwd, 'monitor.log'), now_str() +
                   ' -> GamitTask initialized for %s %s local folder %s solution folder %s\n'
                   % (self.params['DirName'], self.date.yyyyddd(), self.pwd, self.solution_pwd))

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
            # DDG: do not log anything before the copytree operation because monitor.log still not in pwd
            self.log(f'{dirname} {year} {doy} executing on {platform.node()} systems ' + ', '.join(self.systems))
            self.log(f'Copied structure from {self.solution_pwd} to {self.pwd}')
            # this flag is to inform to the error handler that file operations have been made: thus, errors can
            # be written to monitor.log
            copy_done = True
            # create the run script
            self.create_replace_links()
            # run the script to replace the links of the tables directory
            self.execute('find ./tables ! -name "otl.grid" -type l -exec ./replace_links.sh {} +',
                         shell=True)
            self.log('Pre-process tasks (symlink fix) finished with no errors')

            self.fetch_orbits()

            self.fetch_rinex()

            self.log('About to execute GAMIT - system count ' +
                     ' '.join(f'{s}: {self.system_count[s]}' for s in self.systems))

            results = []
            # now execute the run script
            if not dry_run:

                # do a GAMIT run for each system
                for sys in self.systems:
                    if self.system_count[sys] > 1:
                        results.append(self.run_gamit(sys))
                    else:
                        self.log(f'Not enough observing stations for system {sys}. Skipping processing.')

                # combination in GLOBK
                success_results = [r for r in results if r['success']]
                if len(success_results) > 1:
                    self.log('Combination between systems needed.')
                    self.combine_systems(success_results)
                    self.success = True
                elif len(success_results) == 1:
                    self.log('Single system result, using as final GLX.')
                    # just copy the system result to glbf
                    shutil.copyfile(os.path.join(self.pwd, f'gsoln/' + success_results[0]['system'] + '/' +
                                                 success_results[0]['glbf']),
                                    os.path.join(self.pwd_glbf, success_results[0]['glbf']))
                    self.success = True
                else:
                    # a problem with all systems, declare fatal
                    self.log('No valid system solutions. Check fatals.')

                if self.success:
                    # combine zenith tropospheric delays
                    self.log('Merging all tropospheric estimates in a single file.')
                    self.process_tropo(success_results)

                self.finish()

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
                # ignore_dangling_symlinks=True and symlink=False to avoid errors from broken symlinks
                # that might exist in tables
                shutil.copytree(self.pwd, self.solution_pwd, symlinks=False, ignore_dangling_symlinks=True)
                # remove the remote pwd
                shutil.rmtree(self.pwd)

                # output dummy statistics to the parent for display
                results = self.run_gamit('G', dummy=True)
            else:
                results = self.run_gamit('G', dummy=True)

            results['error'] = msg

            # return useful information to the main node (return list because now there is one result per system)
            return [results]

    def log(self, message, no_timestamp=False):
        if not no_timestamp:
            file_append(self.monitor_file, now_str() + ' -> ' + message + '\n')
        else:
            file_append(self.monitor_file, message + '\n')

    def process_tropo(self, results):
        org = self.gamitopts['org']

        znd = os.path.join(self.pwd_glbf, org + self.date.wwwwd() + '.znd')

        for result in results:
            trp = os.path.join(self.pwd, 'gsoln/' + result['system'] + '/' + org + self.date.wwwwd() + '.trp')
            if os.path.isfile(trp):
                # read the content of the file
                output = file_readlines(trp)
                v = re.findall(r'(ATM_ZEN X \w+ .. \d+\s*\d*\s*\d*\s*\d*\s*\d*\s*\d*\s*[- ]?'
                               r'\d*.\d+\s*[+-]*\s*\d*.\d*\s*\d*.\d*)', ''.join(output), re.MULTILINE)
                # output all the lines into a single znd file in glbf that will be read by pyParseZTD
                for line in v:
                    file_append(znd, line + '\n')

    def combine_systems(self, results):
        # create a globk.cmd file for the combination
        expt  = self.gamitopts['expt']
        hfile = f'h{str(self.date.year)[2:]}{self.date.month:02}{self.date.doy:02}1200_{expt}.glx'

        try:
            globk_cmd = file_open(os.path.join(self.pwd_glbf, 'globk.cmd'), 'w')
        except (OSError, IOError):
            raise Exception('could not open file globk.cmd')

        contents = f"""
 app_ptid all
 prt_opt GDLF MIDP CMDS PLST
 out_glb {hfile}
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
            # DDG: down weight E and R solutions (double uncertainty, see GLOBK manual page 12)
            if sol['system'] == 'G':
                w = 1.0
            else:
                w = 4.0
            contents += '../gsoln/' + sol['system'] + '/' + sol['glbf'] + f' {w:.1f}\n'

        gdl_file.write(contents)
        gdl_file.close()

        self.execute('cd glbf; globk 0 out.prt globk.log hfiles.gdl globk.cmd > globk.out', shell=True)

        # now parse the output for any problems
        try:
            logfile = ''.join(file_readlines(os.path.join(self.pwd_glbf, 'globk.log')))
        except FileNotFoundError:
            logfile = ''
            pass
        self.log('\n'.join('\n'.join(i for i in s if i != '')
                           for s in re.findall(r'(\sFor .* Glbf .*)|(\*{2} .*)', logfile)), no_timestamp=True)

    def execute(self, script_name, shell=False):
        self.p = subprocess.Popen(script_name, shell=shell, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, cwd=self.pwd)

        self.stdout, self.stderr = self.p.communicate()

    def fetch_orbits(self):
        self.log('fetching orbits')

        try:
            Sp3 = pySp3.GetSp3Orbits(self.orbits['sp3_path'], self.date, self.orbits['sp3types'], self.pwd_igs, True)

            self.log(f'sp3 orbit found: {Sp3.sp3_filename} -> {Sp3.file_path}')

        except pySp3.pySp3Exception:
            self.log('could not find orbits to run the process')
            raise

        if Sp3.type[0:3].lower() != 'igs':
            # rename file
            filename = str(os.path.basename(Sp3.file_path))
            filename = filename.replace(filename[0:3], "igs")
            sp3_rename = os.path.join(self.pwd_igs, filename)
            self.log(f'renaming {Sp3.file_path} to {sp3_rename}')
            shutil.copyfile(Sp3.file_path, sp3_rename)

        self.log('fetching broadcast orbits')

        brdc = pyBrdc.GetBrdcOrbits(self.orbits['brdc_path'], self.date, self.pwd_brdc, no_cleanup=True)

        self.log(f'broadcast orbit found: {brdc.brdc_filename}')

        # ionex file TODO: probably define a new object to handle IONEX files in the same way as SP3s
        if not os.path.exists(os.path.join(self.pwd, 'ionex')):
            os.makedirs(os.path.join(self.pwd, 'ionex'))
        # look for the file in the ionex options
        ionex_file = f'IGS0OPSFIN_{self.date.yyyy()}{self.date.ddd()}0000_01D_02H_GIM.INX.gz'
        ionex_path = os.path.join(replace_vars(self.orbits['ionex_path'], self.date), ionex_file)
        if os.path.exists(ionex_path):
            # use short name when copying
            short_name = 'igsg%s0.%si.Z' % (self.date.ddd(), str(self.date.year)[2:4])
            shutil.copyfile(ionex_path, os.path.join(self.pwd, 'ionex/' + short_name))
            # uncompress the file
            self.execute('gunzip -f ionex/' + short_name, shell=True)
            self.log(f'Ionex file found: {ionex_path} -> {os.path.join(self.pwd, short_name)}')
        else:
            self.log(f'IONEX path {ionex_path} does not exist. This might stop GAMIT during processing if '
                     '"Apply 2nd/3rd order ionospheric terms" (Ion model) is set to GMAP.')

    def fetch_rinex(self):
        for rinex in self.params['rinex']:

            try:
                with pyRinex.ReadRinex(rinex['NetworkCode'],
                                       rinex['StationCode'],
                                       rinex['source'], False) as Rinex:  # type: pyRinex.ReadRinex

                    self.log(f'fetching rinex for {stationID(rinex)} {rinex["StationAlias"]} '
                             f'{rinex["lat"]:10.6f} {rinex["lon"]:11.6f} {Rinex.satsys:6} '
                             f'{"tie" if rinex["is_tie"] else ""}')

                    # add 1 to the system_count dictionary
                    for s in Rinex.satsys:
                        if s in self.system_count.keys():
                            self.system_count[s] += 1

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
            gpswday = self.date.gpsWeekDay
            gpsweek = self.date.wwww()
            org     = self.gamitopts['org']
            sinex   = f'{org}{gpsweek}{gpswday}.snx'

            if self.success:
                self.log(f'Successful run: Generating SINEX file {sinex} in glbf.')

                self.execute(f'glbtosnx . "" glbf/h*.glx glbf/{sinex} >> glbf/glbtosnx.out', shell=True)

                self.log('Deleting tables and RINEX files and processing dir.')
                # delete everything inside the processing dir
                shutil.rmtree(self.pwd_brdc)
                shutil.rmtree(self.pwd_igs)

                # remove files from tables files only if successful
                for ftype in ('*.??o', '*.grid', '*.dat', '*.apr', 'nbody', 'pole.*', 'ut1.*'):
                    for ff in glob.glob(os.path.join(self.pwd_tables, ftype)):
                        os.remove(ff)

                # remove files in rinex files only if successful
                for ff in glob.glob(os.path.join(self.pwd_rinex, '*')):
                    os.remove(ff)

                # remove files from processing directory
                for system in self.systems:
                    for ftype in ('*.??o', 'z*', '*.grid', '*.dat', '*.apr'):
                        for ff in glob.glob(os.path.join(self.pwd, f'{self.date.ddd()}{system}/{ftype}')):
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
            self.log(f'Copy results from {self.pwd} to {self.solution_pwd}')
            shutil.copytree(self.pwd, self.solution_pwd, symlinks=False, ignore_dangling_symlinks=True)
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
        elif type(station_alias) is list or type(station_alias) is set:
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
        eop      = self.gamitopts['eop_type']
        noftp    = self.gamitopts['noftp']
        gpswk    = self.date.wwww()
        gpswkday = str(self.date.gpsWeekDay)
        system   = system.upper()
        # the date string to print the info to monitor.log
        sdate    = '`date +"%Y-%m-%d %T"` -> '
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

        if not os.path.isdir(os.path.join(self.pwd, 'tmp')):
            os.makedirs(os.path.join(self.pwd, 'tmp'))

        if not os.path.isdir(os.path.join(self.pwd, f'gsoln/{system}')):
            os.makedirs(os.path.join(self.pwd, f'gsoln/{system}'))

        summary_path = os.path.join(self.pwd, f'{doy}{system}/sh_gamit_{doy}{system}.summary')
        lfile_path   = os.path.join(self.pwd_tables, 'lfile.')

        # once executed, check output
        # loop at least three times
        last_i  = 0
        output  = ''
        summary = ''
        for i in range(3):
            retry  = False
            last_i = i
            # name for the GAMIT execution output file
            outfile = org + gpswk + gpswkday + system + str(i) + '.out'
            outfile_path = os.path.join(self.pwd, outfile)

            try:
                run_file = file_open(run_file_path, 'w')
            except (OSError, IOError):
                raise Exception('could not open file ' + run_file_path)

            contents = f"""#!/bin/bash
            # just in case, create a temporary dir for fortran
            export TMPDIR=`pwd`/tmp
            export INSTITUTE={org}
            # log to the monitor
            echo "{sdate}run_{system}.sh" >> monitor.log
            # execute GAMIT
            sh_gamit -gnss {system} -update_l N -topt none -c -copt null {"-noftp" if noftp == "yes" else ""} -dopt c x -expt {expt} -d {year} {doy} -minspan {min_t} -remakex Y -eop {eop} &> {outfile};
            
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
            self.execute('./' + os.path.basename(run_file_path))

            # read the contents of the output files (summary may not exist)
            try:
                summary = ''.join(file_readlines(summary_path))
            except FileNotFoundError:
                summary = ''
                pass
            output  = ''.join(file_readlines(outfile_path))
            lfile   = ''.join(file_readlines(lfile_path))
            lfile_i = ''.join(file_readlines(lfile_path + str(last_i)))

            # check for common problem running MAKEX, etc that usually just get fixed by rerunning
            if re.findall(r'FATAL.*FIXDRV/dcheck', output) or \
               re.findall(r'FATAL.*MAKEXP/makexp: No RINEX or X-files found', output) or \
               re.findall(r'FATAL.*MAKEX/get_rxfiles: Cannot find selected RINEX file', output) or \
               re.findall(r'FATAL.*MAKEX/openf: Error opening file:.*', output) or \
               re.findall(r'SOLVE/get_widelane: Error reading first record', output) or \
               re.findall(r'Failure in sh_preproc. STATUS 1 -- sh_gamit terminated', output) or \
               re.findall(r'Failure in sh_setup. -- sh_gamit terminated', output) or \
               re.findall(r'sh_get_ion failed to download requested IONEX file', output) or \
               (re.findall(r'yr: Subscript out of range.', output) and not summary == ''):
                self.log(f'Issue found with this run (sh_setup, FIXDRV, MAKEXP, MAKEX, SOLVE, or sh_get_ion) '
                         f'trying again ({i})...')
                # skip any further tests
                continue

            # check for unreasonable geodetic height
            if re.findall(r'Geodetic height unreasonable', output):
                self.log(f'Geodetic height unreasonable in {outfile}')
                # find the last site that was being processed
                sites = re.findall(r'MODEL/open: Site\s(\w+)', output)
                if len(sites):
                    rinex_rm = glob.glob(os.path.join(self.pwd_rinex, sites[-1].lower() + '*'))
                    result['missing'] = result['missing'] + self.translate_station_alias([sites[-1].lower()])
                    for rnx in rinex_rm:
                        self.log(f'Removing RINEX file {rnx}')
                        os.remove(rnx)
                retry  = True

            # check for over constrained solutions
            oc_site_count = re.findall(r'WARNING: (\d+).*over constrained', summary)
            result['relaxed_constrains'] = []
            if oc_site_count:
                p = 'WARNING: \d+.*over constrained.*(?:\n.*){%s}' % oc_site_count[0]
                match_sites  = re.findall(p, summary)[0]
                # extract the sites and their over constrained parameters
                oc_sites_vals  = re.findall(r'GCR APTOL (\w+).{10}\s+(-?\d+.\d+)', match_sites)
                oc_sites_alias = set([s[0].lower() for s in oc_sites_vals])
                oc_sites_only  = self.translate_station_alias(oc_sites_alias)

                self.log(f'Over constrained solution in sh_gamit_{doy}{system}.summary')
                self.log(' ' + '\n '.join(oc_sites_only), no_timestamp=True)

                # two options: (1) relax over constrained sigmas or (2) remove them from processing
                # if relaxing, then remove from current lfile.

                if self.gamitopts['overconst_action'] == 'delete' or self.gamitopts['overconst_action'] == 'remove':
                    # get rid of the stations with issues
                    # add any stations to the missing list, since we have data but we will not have a solution
                    result['missing'] = result['missing'] + oc_sites_only
                    for site in oc_sites_alias:
                        rinex_rm = glob.glob(os.path.join(self.pwd_rinex, site + '*'))
                        for rnx in rinex_rm:
                            self.log(f'Removing RINEX file {rnx}')
                            os.remove(rnx)

                elif self.gamitopts['overconst_action'] == 'relax' or self.gamitopts['overconst_action'] == 'inflate':
                    # relax the constraints for this station
                    self.log(f'Creating sittbl. backup to sittbl.{i}')
                    shutil.copyfile(os.path.join(self.pwd_tables, 'sittbl.'),
                                    os.path.join(self.pwd_tables, f'sittbl.{i}'))
                    self.log('Relaxing constraints in sittbl.')
                    sites = '|'.join(site.upper() for site in oc_sites_alias)
                    self.execute(f'grep -v -E "{sites}" tables/sittbl.{i} > tables/sittbl.', shell=True)
                    result['relaxed_constrains'] = oc_sites_only
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
        if re.findall(r'.*?FATAL.*', output) or summary == '':
            self.log('\n'.join(re.findall(r'(.*?FATAL.*)', output)), no_timestamp=True)
            fatal = True
            # save the fatals as a list
            result['fatals'] = set(re.findall(r'(.*?FATAL.*)', output))

            self.log(f'Unsuccessful run for system {system}. Check fatal message.')
        else:
            # extract the run statistics and write it to the monitor
            self.log('NRMS and WL-NL ambiguity summary follows:')
            self.log('\n'.join(re.findall(r'(.*nrms.*)', summary)), no_timestamp=True)
            self.log('\n'.join(re.findall(r'(.*WL fixed.*)', summary)), no_timestamp=True)

            try:
                result['nrms'] = float(re.findall(
                    r'Prefit nrms:\s+\d+.\d+[eEdD]\+\d+\s+Postfit nrms:\s+(\d+.\d+[eEdD][+-]\d+)', summary)[-1])

                result['wl'] = float(re.findall(r'WL fixed\s+(\d+.\d+)', summary)[0])
                result['nl'] = float(re.findall(r'NL fixed\s+(\d+.\d+)', summary)[0])

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
                echo "{sdate}finish_{system}.sh" >> monitor.log
                
                cd gsoln/{system}
                # link the svnav file in tables
                ln -s ../../tables/svnav.dat .
    
                # create the binary h-file
                htoglb . tmp.svs -a ../../{doy}{system}/h*.{year[2:]}{doy}  >> htoglb.out
                
                # grep any missing stations to report them to monitor.log
                grep 'No data for site ' htoglb.out | sort | uniq >> ../../monitor.log
        
                # clean up
                rm HTOGLB.* tmp.svs l*  svnav.dat
                """

                finish_file.write(contents)
                finish_file.close()
                chmod_exec(finish_file_path)
                self.execute('./' + os.path.basename(finish_file_path))

                # retrieve no data for site x
                htoglb = ''.join(file_readlines(os.path.join(self.pwd, f'gsoln/{system}/htoglb.out')))

                # append any reported missing stations to the result['missing'] list that might have been reported
                # during the removal of over constrained stations
                result['missing'] = \
                    result['missing'] + \
                    self.translate_station_alias(set(re.findall(r'No data for site (\w+)', htoglb)))

                hfile = glob.glob(os.path.join(self.pwd, f'gsoln/{system}/h*.glx'))[0]
                # only write the filename, not the path
                result['glbf'] = os.path.basename(hfile)

                if system == 'R':
                    # for GLONASS, remove the GLX and rename the GLR to GLX
                    os.remove(hfile)
                    shutil.move(hfile[:-1] + 'r', hfile)

                # move the ofile for zenith delay parsing
                ofile = glob.glob(os.path.join(self.pwd, f'{doy}{system}/o*a.[0-9][0-9][0-9]*'))
                if len(ofile):
                    for of in ofile:
                        shutil.move(of, os.path.join(self.pwd, f'gsoln/{system}/{org}{gpswk}{gpswkday}.trp'))

            except IndexError:
                msg = 'Processing resulted in invalid NRMS or WL/NL ambiguity resolution. Declaring fatal.'
                self.log(msg)
                # save this generic message as the FATAL error
                result['fatals'] = [msg]
                fatal = True

            # finally, remove processing files after successful run
            for ftype in ('b*', 'cfmrg*', 'DPH.*', 'eq_rename.*', 'g*', 'k*', 'p*', 'rcvant.*', 'y*'):
                for ff in glob.glob(os.path.join(self.pwd, f'{doy}{system}/{ftype}')):
                    os.remove(ff)

        result['success'] = not fatal

        return result

