"""
Project: Parallel.GAMIT
Date: 10/28/2022
Author: Demian D. Gomez
Script to convert T0x files to RINEX
"""

import pyRinex
import pyRinexName
import argparse
import glob
import os
import pyRunWithRetry


def main():
    parser = argparse.ArgumentParser(description='Script to convert T0x files to RINEX')

    parser.add_argument('path', type=str, nargs=1, metavar='[path to dir]',
                        help="Path to directory with T0x files")

    parser.add_argument('path_out', type=str, nargs=1, metavar='[path to dir]',
                        help="Path to directory with resulting RINEX (a folder with station name will be created)")

    parser.add_argument('-stnm', '--station_name', type=str, default='dftl',
                        help="Name of the station to form that RINEX files")

    args = parser.parse_args()
    path = os.path.abspath(args.path[0])
    print('Working on %s' % path)

    # create a dictionary to save how many files there are for each date
    date_dict = {}
    stnm = args.station_name

    out = os.path.join(args.path_out[0], stnm)

    if not os.path.isdir(out):
        os.makedirs(out)

    # do a for loop and runpk00 all the files in the path folder
    for ff in glob.iglob('**/*.T0*', root_dir=path, recursive=True):

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
        tgd = os.path.join(out, file.split('.')[0]) + '.tgd'
        err = os.path.join(out, 'err.txt')

        os.system('teqc -tr d %s > %s 2> %s' % (tgd, rinex, err))

        # os.system('gfzrnx_lx -finp %s -site %s -fout %s/::RX2::' % (rinex, stnm, out))
        # os.remove(tgd)
        # os.remove(rinex)
        try:
            rnx = pyRinex.ReadRinex('???', stnm, rinex, min_time_seconds=300)

            rnx.rename(stnm + rnx.date.ddd() + '0.' + rnx.date.yyyy()[2:] + 'o')
            dir_w_year = os.path.join(os.path.join(out, f'{rnx.interval:>02.0f}' + '_SEC'),
                                      rnx.date.yyyy())

            if not os.path.isdir(dir_w_year):
                os.makedirs(dir_w_year)

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


if __name__ == '__main__':
    main()

