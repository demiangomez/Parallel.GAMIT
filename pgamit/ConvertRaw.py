"""
Project: Parallel.GAMIT
Date: 11/28/2023
Author: Demian D. Gomez
Module to convert T0x files to RINEX
"""

import glob
import os
import re
import shutil
import tempfile

from tqdm import tqdm

# app
from pgamit import Utils
from pgamit import pyRinex
from pgamit import pyRunWithRetry
from pgamit.pyEvents import Event


class ConvertRawException(Exception):
    def __init__(self, value):
        self.value = value
        self.event = Event(Description=value, EventType='error')

    def __str__(self):
        return str(self.value)


class ConvertRaw(object):
    def __init__(self, station_code='stnm', path_to_raw=None, out_path=None,
                 atx_file=None, antenna=None, ant_serial=None):
        # logger information and setup
        self.logger = []
        self.station_code = station_code
        self.path_to_raw = path_to_raw
        self.out_path = out_path

        self.logger.append(Event(Description='Initialized ConvertRaw for station code %s with path %s '
                                             'and output path %s' % (station_code, path_to_raw, out_path)))

        if not os.path.isdir(out_path):
            os.makedirs(out_path)

        # if a single file is passed, then just work with that file. If a path, then do a search
        if os.path.isdir(path_to_raw):
            # a directory was passed
            self.file_list = list(glob.iglob('**/*.*', root_dir=path_to_raw, recursive=True))
        else:
            # single file
            self.file_list = [path_to_raw]

        self.logger.append(Event(Description='List of files to process: ' + ', '.join(self.file_list)))

        # if antenna is not none, then parse ATX and find provided antenna to replace in RINEX
        if atx_file is not None and antenna is not None:
            atx = Utils.parse_atx_antennas(atx_file)
            # figure out if we have wildcards in the antenna name
            ant = re.findall(antenna, '\n'.join(atx))
            if not ant or len(ant) > 1:
                raise ConvertRawException(
                    'Too many matches found. Use a more specific antenna name regex:\n' + '\n'.join(ant))
            else:
                self.antenna = ant[0]
                self.antenna_serial = ant_serial

                self.logger.append(Event(Description='Replacing ANT # / TYPE record with provided information:' +
                                                     (' ' + ant_serial if ant_serial is not None else '') +
                                                     ' %-16s%4s' % (ant, 'NONE')))
        else:
            self.antenna = None
            self.antenna_serial = None

    def print_events(self):
        for event in self.logger:
            tqdm.write(' -- ' + str(event))

    def process_files(self):
        result = False

        for file in self.file_list:
            # TRIMBLE CONVERSION
            if file[-3:].upper() in ('T00', 'T01', 'T02'):
                self.logger.append(Event(Description='Invoking Trimble Conversion'))
                result = self.convert_trimble(file)
            # OTHER CONVERSIONS COMING SOON
            else:
                self.logger.append(Event(Description='Raw format not supported: %s' % file[-3:].upper()))

        return result

    def merge_rinex(self):

        # go through the output folder and find all RINEX files to see if more than one file per day
        file_list = []
        for ft in ('*d.Z', '*.gz', '*d.z'):
            file_list += list(glob.iglob(ft, root_dir=self.out_path, recursive=False))

        date_dict = {}

        for file in file_list:
            abs_filename = os.path.join(self.out_path, file)

            rnx = pyRinex.ReadRinex('???', self.station_code, abs_filename, min_time_seconds=300)

            if rnx.date.yyyyddd() + f'_{rnx.interval:>02.0f}' in date_dict.keys():
                date_dict[rnx.date.yyyyddd() + f'_{rnx.interval:>02.0f}'].append(abs_filename)
            else:
                date_dict[rnx.date.yyyyddd() + f'_{rnx.interval:>02.0f}'] = [abs_filename]

        # now figure out if any dates have more than one file
        for d, files in date_dict.items():
            if len(files) > 1:

                rnx = []
                self.logger.append(Event(Description='Processing date / interval %s' % d))
                for frnx in files:
                    self.logger.append(Event(Description='Uncompressing %s' % frnx))
                    # do the same for the rest
                    rnx.append(pyRinex.ReadRinex('???', self.station_code, frnx, min_time_seconds=300))
                    os.remove(frnx)

                # use a file name that we know has been deleted already
                spliced_rnx = os.path.join(self.out_path, rnx[0].rinex)

                fs = ' '.join([rx.rinex_path for rx in rnx])

                cmd = pyRunWithRetry.RunCommand('gfzrnx_lx -finp %s -fout %s -vo %i'
                                                % (fs, spliced_rnx, 2), 300)
                _, _ = cmd.run_shell()

                rx = pyRinex.ReadRinex('???', self.station_code, spliced_rnx, min_time_seconds=300)

                # compress
                rx.compress_local_copyto(self.out_path)
                os.remove(spliced_rnx)

    def convert_trimble(self, filename):
        # create a dictionary to save how many files there are for each date

        result = True

        tmp_dir = tempfile.mkdtemp(suffix='.tmp', prefix=os.path.join(self.out_path, 'process.'))

        t0_file = os.path.join(self.path_to_raw, filename).replace(' ', '\\ ')

        self.logger.append(Event(Description='Processing file %s' % t0_file))

        # use runpkr00 to convert to tgd
        os.system('runpkr00 -g -d %s %s' % (t0_file, tmp_dir))
        # stdout, stderr = cmd.run_shell()
        self.logger.append(Event(Description='Executed runpkr00 -g -d %s %s'
                                             % (t0_file, tmp_dir)))

        file = os.path.basename(filename)

        # now TEQC
        rinex = os.path.join(tmp_dir, file[0:4]) + '0010.00o'

        # DDG: sometimes the output is DAT not TGD ???
        if os.path.exists(os.path.join(tmp_dir, file.split('.')[0]) + '.tgd'):
            tgd = os.path.join(tmp_dir, file.split('.')[0]) + '.tgd'
        else:
            tgd = os.path.join(tmp_dir, file.split('.')[0]) + '.dat'

        err = os.path.join(tmp_dir, 'err.txt')

        os.system('teqc +C2 +L5 +L8 -tr d %s > %s 2> %s' % (tgd, rinex, err))

        self.logger.append(Event(Description='Executed teqc -tr d %s > %s 2> %s' % (tgd, rinex, err)))

        try:
            rnx = pyRinex.ReadRinex('???', self.station_code, rinex, min_time_seconds=300)

            rnx.rename(self.station_code + rnx.date.ddd() + '0.' + rnx.date.yyyy()[2:] + 'o')

            if self.antenna:
                header = rnx.replace_record(rnx.header, 'ANT # / TYPE',
                                            [self.antenna_serial if self.antenna_serial is not None else rnx.antNo,
                                             '%-16s%4s' % (self.antenna, 'NONE')])
                header = rnx.insert_comment(header, 'ConvertRaw REPLACED ANT %s' % rnx.antType)
                rnx.write_rinex(header)

            # make sure the header reflects the curated information
            rnx.normalize_header()
            # write the file
            rnx.compress_local_copyto(self.out_path)

        except pyRinex.pyRinexException as e:
            self.logger.append(Event(Description=str(e), EventType='error'))
            result = False

        # cleanup
        try:
            shutil.rmtree(tmp_dir)
        except Exception as e:
            self.logger.append(Event(Description=str(e), EventType='error'))

        return result
