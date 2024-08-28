"""
Project: Parallel.GAMIT
Date: 11/28/2023
Author: Demian D. Gomez
Module to convert T0x files to RINEX
"""

import pyRunWithRetry
import glob
import pyRinex
import os
import Utils
import re


def convert_trimble(path, stnm, out_path, plain_path=False, antenna=None):
    # create a dictionary to save how many files there are for each date
    date_dict = {}

    if plain_path:
        out = out_path
    else:
        out = os.path.join(out_path, stnm)

    if not os.path.isdir(out):
        os.makedirs(out)

    # if a single file is passed, then just work with that file. If a path, then do a search
    if os.path.isdir(path):
        flist = glob.iglob('**/*.T0*', root_dir=path, recursive=True)
    else:
        flist = [path]

    # if antenna is not none, then parse ATX and find provided antenna to replace in RINEX
    if antenna is not None:
        atx = Utils.parse_atx_antennas(antenna[0])
        # figure out if we have wildcards in the antenna name
        ant = re.findall(antenna[1], '\n'.join(atx))
        if not ant or len(ant) > 1:
            raise Exception('Too many matches found. Use a more specific antenna name regex:\n' + '\n'.join(ant))
        else:
            ant = ant[0]
            if len(antenna) > 2:
                ant_sn = antenna[2]
            else:
                ant_sn = None
            print(' -- Replacing ANT # / TYPE record with provided information:' +
                  (' ' + ant_sn if ant_sn is not None else '') + ' %-16s%4s' % (ant, 'NONE'))
    else:
        ant = None
        ant_sn = None

    # do a for loop and runpk00 all the files in the path folder
    for ff in flist:
        t0_file = os.path.join(path, ff).replace(' ', '\\ ')

        print(' >> Found %s' % t0_file)

        # use runpkr00 to convert to tgd
        cmd = pyRunWithRetry.RunCommand('runpkr00 -g -d %s %s' % (t0_file, out), 10)
        cmd.run_shell()

        file = os.path.basename(ff)
        stnm = stnm.lower()
        print('runpkr00 -g -d %s %s' % (t0_file, out))
        # now TEQC
        rinex = os.path.join(out, file[0:4]) + '0010.00o'
        # DDG: sometimes the output is DAT not TGD ???
        if os.path.exists(os.path.join(out, file.split('.')[0]) + '.tgd'):
            tgd = os.path.join(out, file.split('.')[0]) + '.tgd'
        else:
            tgd = os.path.join(out, file.split('.')[0]) + '.dat'
        err = os.path.join(out, 'err.txt')

        os.system('teqc -tr d %s > %s 2> %s' % (tgd, rinex, err))

        # os.system('gfzrnx_lx -finp %s -site %s -fout %s/::RX2::' % (rinex, stnm, out))
        # os.remove(tgd)
        # os.remove(rinex)
        try:
            rnx = pyRinex.ReadRinex('???', stnm, rinex, min_time_seconds=300)

            rnx.rename(stnm + rnx.date.ddd() + '0.' + rnx.date.yyyy()[2:] + 'o')
            if plain_path:
                dir_w_year = out
            else:
                dir_w_year = os.path.join(os.path.join(out, f'{rnx.interval:>02.0f}' + '_SEC'), rnx.date.yyyy())

            if not os.path.isdir(dir_w_year):
                os.makedirs(dir_w_year)

            if ant:
                header = rnx.replace_record(rnx.header, 'ANT # / TYPE',
                                            [ant_sn if ant_sn is not None else rnx.antNo,
                                             '%-16s%4s' % (ant, 'NONE')])
                header = rnx.insert_comment(header, 'TrimbleT0x REPLACED ANT %s' % rnx.antType)
                rnx.write_rinex(header)

            # make sure the header reflects the curated information
            rnx.normalize_header()
            # write the file
            dest_file = rnx.compress_local_copyto(dir_w_year)

            if rnx.date.yyyyddd() + f'_{rnx.interval:>02.0f}' in date_dict.keys():
                date_dict[rnx.date.yyyyddd() + f'_{rnx.interval:>02.0f}'].append(dest_file)
            else:
                date_dict[rnx.date.yyyyddd() + f'_{rnx.interval:>02.0f}'] = [dest_file]

            print(' -- Done processing %s interval %02.0f completion %.2f for date %s'
                  % (rnx.rinex, rnx.interval, rnx.completion, str(rnx.date)))
            os.remove(rinex)
        except pyRinex.pyRinexException as e:
            print(str(e))
        try:
            os.remove(tgd)
        except Exception as e:
            print(str(e))

    # now figure out if any dates have more than one file
    for d, files in date_dict.items():
        if len(files) > 1:

            rnx = []
            print('Processing %s' % d)
            for frnx in files:
                print(' -- Uncompressing %s' % frnx)
                # do the same for the rest
                rnx.append(pyRinex.ReadRinex('???', stnm, frnx, min_time_seconds=300))
                os.remove(frnx)

            # determine the destiny folder
            dir_w_year = os.path.join(os.path.join(out, f'{rnx[0].interval:>02.0f}' + '_SEC'),
                                      rnx[0].date.yyyy())

            if not os.path.isdir(dir_w_year):
                os.makedirs(dir_w_year)

            spliced_rnx = os.path.join(dir_w_year, rnx[0].rinex)

            fs = ' '.join([rx.rinex_path for rx in rnx])

            cmd = pyRunWithRetry.RunCommand('gfzrnx_lx -finp %s -fout %s -vo %i'
                                            % (fs, spliced_rnx, 2), 300)
            pout, perr = cmd.run_shell()
            # print(err)
            # print(out)

            rx = pyRinex.ReadRinex('???', stnm, spliced_rnx, min_time_seconds=300)

            # compress
            rx.compress_local_copyto(dir_w_year)
            os.remove(spliced_rnx)
            del rx
            # delete temporary folders
            del rnx
