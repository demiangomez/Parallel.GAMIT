
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
    parser.add_argument('-rnx', '--load_rinex', action='store_true', help="Fix RINEX using pyRinex, create a local copy (with session number+1) and exit. Do not run PPP.")
    parser.add_argument('-ins', '--insert_sql', action='store_true', help="Produce a SQL INSERT statement for this station including OTL and coordinates.")
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
        sp3altrn = ['jpl', 'jp2', 'jpr']
        brdc_path = args.no_config_file[2]
    else:
        Config = pyOptions.ReadOptions('gnss_data.cfg') # type: pyOptions.ReadOptions
        options = Config.options
        sp3types = Config.sp3types
        sp3altrn = Config.sp3altrn
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

        try:
            with pyRinex.ReadRinex('???', stnm, rinex) as rinexinfo: # type: pyRinex.ReadRinex
                if rinexinfo.multiday:
                    print 'Provided RINEX file is a multiday file!'
                    # rinex file is a multiday file, output all the solutions
                    for rnx in rinexinfo.multiday_rnx_list:
                        execute_ppp(rnx, args, stnm, options, sp3types, sp3altrn, brdc_path)
                else:
                    execute_ppp(rinexinfo, args, stnm, options, sp3types, sp3altrn, brdc_path)

        except pyRinex.pyRinexException as e:
            print str(e)
            continue


def execute_ppp(rinexinfo, args, stnm, options, sp3types, sp3altrn, brdc_path):

    # put the correct APR coordinates in the header.
    # stninfo = pyStationInfo.StationInfo(None, allow_empty=True)
    stninfo = dict()

    brdc = pyBrdc.GetBrdcOrbits(brdc_path, rinexinfo.date, rinexinfo.rootdir)

    try:
        # inflate the chi**2 limit
        rinexinfo.purge_comments()
        rinexinfo.auto_coord(brdc=brdc, chi_limit=1000)
        rinexinfo.normalize_header(stninfo)  # empty dict: only applies the coordinate change
    except pyRinex.pyRinexException as e:
        print str(e)

    if args.load_rinex:
        rinexinfo.compress_local_copyto('./')
        print 'RINEX created in current directory.'
        return

    try:
        if args.ocean_loading or args.insert_sql:
            # get a first ppp coordinate
            ppp = pyPPP.RunPPP(rinexinfo, '', options, sp3types, sp3altrn, 0, strict=False, apply_met=False, kinematic=False, clock_interpolation=True)

            ppp.exec_ppp()

            # use it to get the OTL (when the auto_coord is very bad, PPP doesn't like the resulting OTL).
            otl = pyOTL.OceanLoading(stnm, options['grdtab'], options['otlgrid'], ppp.x, ppp.y, ppp.z)
            otl_coeff = otl.calculate_otl_coeff()

            # run again, with OTL
            ppp = pyPPP.RunPPP(rinexinfo, otl_coeff, options, sp3types, sp3altrn, 0, strict=False, apply_met=False, kinematic=False, clock_interpolation=True)
        else:
            ppp = pyPPP.RunPPP(rinexinfo, '', options, sp3types, sp3altrn, 0, strict=False, apply_met=False, kinematic=False, clock_interpolation=True)

        ppp.exec_ppp()

        if not args.insert_sql:
            print '%s %10.5f %13.4f %13.4f %13.4f %14.9f %14.9f %8.3f' % (
            stnm, rinexinfo.date.fyear, ppp.x, ppp.y, ppp.z, ppp.lat[0], ppp.lon[0], ppp.h[0])
        else:
            print 'INSERT INTO stations ("NetworkCode", "StationCode", "auto_x", "auto_y", "auto_z", "Harpos_coeff_otl", lat, lon, height) VALUES (\'???\', \'%s\', %.4f, %.4f, %.4f, \'%s\', %.8f, %.8f, %.3f)' % (stnm, ppp.x, ppp.y, ppp.z, otl_coeff, ppp.lat[0], ppp.lon[0], ppp.h[0])

    except pyPPP.pyRunPPPException as e:
        print 'Exception in PPP: ' + str(e)

    except pyRinex.pyRinexException as e:
        print 'Exception in pyRinex: ' + str(e)


if __name__ == '__main__':
    main()
