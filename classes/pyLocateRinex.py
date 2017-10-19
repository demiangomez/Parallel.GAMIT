
import pyRinex
import argparse
import pyPPP
import pyOptions
import pyOTL
import pyBrdc
import glob
import os
import pyStationInfo

def main():

    parser = argparse.ArgumentParser(description='Simple PPP python wrapper. Calculate a coordinate for a RINEX file. Output one line per file with stnm epoch x y z lat lon h')
    parser.add_argument('files', type=str, nargs='+', help="List of files, directories or wildcards to process. If directories are given, searches for .Z files. Individual files or wildcards can be either .Z or ??o. Eg: pyLocationRinex.py ./igm10010.10d.Z ./igm1002a.10o ./cs*.Z ./rinex2process/")
    parser.add_argument('-otl', '--ocean_loading', action='store_true', help="Apply ocean loading coefficients (obtained from grdtab).")
    parser.add_argument('-nocfg', '--no_config_file', type=str, nargs=3, metavar=('sp3_directory','sp3_types', 'brdc_directory'),
                        help='Do not attempt to open gnss_data.cfg. Append [sp3_directory], [sp3_types] and [brdc_directory] '
                            'to access the precise and broadcast orbit files. Use the keywords $year, $doy, $month, $day, $gpsweek, $gpswkday '
                            'to dynamically replace with the appropriate values (based on the date in the RINEX file). '
                            'Grdtab and otl_grid should have the standard names if -otl is invoked and ppp should be in the PATH (with executable name = ppp).')

    args = parser.parse_args()

    options = {}
    if args.no_config_file is not None:
        options['ppp_path'] = ''
        options['ppp_exe'] = 'ppp'
        options['grdtab'] = 'grdtab'
        options['otlgrid'] = 'otl.grid'
        options['sp3'] = args.no_config_file[0]
        sp3types = args.no_config_file[1].split(',')
        brdc_path = args.no_config_file[2]
    else:
        Config = pyOptions.ReadOptions('gnss_data.cfg') # type: pyOptions.ReadOptions
        options = Config.options
        sp3types = Config.sp3types
        brdc_path = Config.brdc_path

    rinex = []
    for xfile in args.files:
        if os.path.isdir(xfile):
            # add all d.Z files in folder
            rinex = rinex + glob.glob(os.path.join(xfile, '*d.Z'))
        elif os.path.isfile(xfile):
            # a single file
            rinex = rinex + [xfile]
        else:
            # a wildcard: expand
            rinex = rinex + glob.glob(xfile)

    for rinex in rinex:
        # read the station name from the file
        stnm = rinex.split('/')[-1][0:4]
        rinexinfo = pyRinex.ReadRinex('???', stnm, rinex)  # type: pyRinex.ReadRinex

        # put the correct APR coordinates in the header.
        stninfo = pyStationInfo.StationInfo(None, allow_empty=True)
        stninfo.AntennaCode = rinexinfo.antType
        stninfo.ReceiverCode = rinexinfo.recType
        stninfo.AntennaEast = 0
        stninfo.AntennaNorth = 0
        stninfo.AntennaHeight = rinexinfo.antOffset
        stninfo.RadomeCode = rinexinfo.antDome
        stninfo.AntennaSerial = rinexinfo.antNo
        stninfo.ReceiverSerial = rinexinfo.recNo

        # inflate the chi**2 limit
        _, _, out = rinexinfo.auto_coord(brdc=pyBrdc.GetBrdcOrbits(brdc_path, rinexinfo.date, rinexinfo.rootdir), chi_limit=10)

        if out is not None:
            # warn the user that the chi**2 of the result is too high!
            print out

        rinexinfo.normalize_header(stninfo)

        if args.ocean_loading:

            otl = pyOTL.OceanLoading(stnm, options['grdtab'], options['otlgrid'], rinexinfo.x, rinexinfo.y, rinexinfo.z)
            otl_coeff = otl.calculate_otl_coeff()

            ppp = pyPPP.RunPPP(rinexinfo, otl_coeff, options, sp3types, [], 0, False, False, False)
        else:
            ppp = pyPPP.RunPPP(rinexinfo, '', options, sp3types, [], 0, False, False, False)

        ppp.exec_ppp()

        print '%s %10.5f %13.4f %13.4f %13.4f %14.9f %14.9f %8.3f' % (stnm, rinexinfo.date.fyear, ppp.x, ppp.y, ppp.z, ppp.lat[0], ppp.lon[0], ppp.h[0])

if __name__ == '__main__':
    main()
