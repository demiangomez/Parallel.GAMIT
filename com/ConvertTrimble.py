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
                        help="Path to directory with resulting RINEX")

    args = parser.parse_args()
    print('Working on %s' % args.path[0])

    # create a dictionary to save how many files there are for each date
    date_dict = {}
    stnm = 'dftl'

    # do a for loop and runpk00 all the files in the path folder
    for ff in glob.glob(os.path.join(args.path[0],  '*.T0*')):
        # print(ff)
        # use runpkr00 to convert to tgd
        cmd = pyRunWithRetry.RunCommand('runpkr00 -g -d %s %s' % (ff, args.path_out[0]), 10)
        cmd.run_shell()

        file = os.path.basename(ff)
        stnm = file[0:4].lower()

        # now TEQC
        rinex = os.path.join(args.path_out[0], file[0:4]) + '0010.00o'
        tgd = os.path.join(args.path_out[0], file.split('.')[0]) + '.tgd'
        err = os.path.join(args.path_out[0], 'err.txt')

        os.system('teqc -tr d %s > %s 2> %s' % (tgd, rinex, err))

        # os.system('gfzrnx_lx -finp %s -site %s -fout %s/::RX2::' % (rinex, stnm, args.path_out[0]))
        # os.remove(tgd)
        # os.remove(rinex)
        try:
            rnx = pyRinex.ReadRinex('???', stnm, rinex, min_time_seconds=300)

            rnx.rename(file[0:4].lower() + rnx.date.ddd() + '0.' + rnx.date.yyyy()[2:] + 'o')
            dir_w_year = os.path.join(os.path.join(args.path_out[0], f'{rnx.interval:>02.0f}' + '_SEC'),
                                      rnx.date.yyyy())

            if not os.path.isdir(dir_w_year):
                os.makedirs(dir_w_year)

            dest_file = rnx.compress_local_copyto(dir_w_year)

            if rnx.date.yyyyddd() + f'_{rnx.interval:>02.0f}' in date_dict.keys():
                date_dict[rnx.date.yyyyddd() + f'_{rnx.interval:>02.0f}'].append(dest_file)
            else:
                date_dict[rnx.date.yyyyddd() + f'_{rnx.interval:>02.0f}'] = [dest_file]

            print(' >> Done processing %s interval %02.0f completion %.2f' % (rnx.rinex, rnx.interval, rnx.completion))
            os.remove(rinex)
        except pyRinex.pyRinexException as e:
            print(str(e))
        try:
            os.remove(tgd)
        except Exception as e:
            print(str(e))
    print(date_dict)
    # now figure out if any dates have more than one file
    for d, files in date_dict.items():
        if len(files) > 1:
            print('Processing %s' % d)
            # more than one file, splice
            # read the first file
            rnx = pyRinex.ReadRinex('???', stnm, files[0], min_time_seconds=300)
            # delete file
            os.remove(files[0])
            for frnx in files[1:]:
                # do the same for the rest
                rnx = rnx + pyRinex.ReadRinex('???', stnm, frnx, min_time_seconds=300)
                os.remove(frnx)

            # determine the destiny folder
            dir_w_year = os.path.join(os.path.join(args.path_out[0], rnx.date.yyyy()),
                                      f'{rnx.interval:>02.0f}' + '_SEC')
            # compress
            rnx.compress_local_copyto(dir_w_year)


if __name__ == '__main__':
    main()

