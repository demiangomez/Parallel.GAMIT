"""
Project: Parallel.GAMIT 
Date: 6/15/24 10:29 AM 
Author: Demian D. Gomez

Description goes here

"""

import argparse
import os
import numpy as np
from tqdm import tqdm

import dbConnection
import pyDate
import pyETM
from Utils import process_stnlist, stationID, cart2euler, get_stack_stations
from pyLeastSquares import adjust_lsq
from pyOkada import sind, cosd


def build_design(hdata, vdata):

    An, Ae = build_design_href(hdata)

    if 'v' in hdata[0].keys():
        # test to see if velocity was passed
        Lh = np.array([[d['v'][0]] for d in hdata] + [[d['v'][1]] for d in hdata])
    else:
        Lh = []

    if len(vdata) > 0:
        # stack the horizontal components for the Euler pole
        Ah = np.row_stack((An, Ae))
        # design matrix for the effect of vref on href
        Anv, Aev, _ = build_design_vref(hdata)
        A  = np.column_stack((Ah, np.row_stack((Anv, Aev))))
        # actual vref
        _, _, Auv = build_design_vref(vdata)
        Av = np.column_stack((np.zeros((Auv.shape[0], 3)), Auv))
        A = np.row_stack((A, Av))

        if 'v' in vdata[0].keys():
            # test to see if velocity was passed
            L = np.row_stack((Lh, np.array([[d['v'][2]] for d in vdata])))
        else:
            L = Lh
    else:
        A = np.row_stack((An, Ae))
        L = Lh

    return A, L


def build_design_href(data):
    slat = sind(np.array([d['lat'] for d in data]))
    slon = sind(np.array([d['lon'] for d in data]))
    clat = cosd(np.array([d['lat'] for d in data]))
    clon = cosd(np.array([d['lon'] for d in data]))

    slatslon = slat * slon
    slatclon = slat * clon

    Re = 6378137

    An = Re * 1e-9 * np.column_stack((slon, -clon, np.zeros_like(slon)))
    Ae = Re * 1e-9 * np.column_stack((-slatclon, -slatslon, clat))

    return An, Ae


def build_design_vref(data):

    lat = np.array([d['lat'] for d in data])
    lon = np.array([d['lon'] for d in data])

    An = np.column_stack((-(sind(lat) * cosd(lon)), -sind(lon), cosd(lat) * cosd(lon)))
    Ae = np.column_stack((-(sind(lat) * sind(lon)), cosd(lon), cosd(lat) * sind(lon)))
    Au = np.column_stack((cosd(lat), np.zeros_like(lat), sind(lat)))

    return An, Ae, Au


def main():
    parser = argparse.ArgumentParser(description='Script to fix plate given a set of stations. Program outputs '
                                                 'Euler vector parameters and optionally produces timee series in such '
                                                 'plate-fixed frame.')

    parser.add_argument('stack_name', type=str, nargs=1, metavar='{stack name}',
                        help="Stack name to work with. The Euler pole will be calculated so as to fix the velocities "
                             "of the selected sites in this stack.")

    parser.add_argument('-include', '--include_stations', nargs='+', type=str, metavar='{net.stnm}',
                        help="Specify which stations to use for Euler pole computation.")

    parser.add_argument('-vref', '--vertical_ref', nargs='+', metavar=('station', '[mm/yr]]'), default=[],
                        help="Transform/align to a given vertical reference frame using the provided station list "
                             "and velocities, given as [net.stnm] [vu], where vu is the vertical velocity in mm/yr.")

    parser.add_argument('-plot', '--plot_etms', action='store_true', default=False,
                        help="Plot the fixed-plate ETMs after computation is done.")

    parser.add_argument('-dir', '--directory', type=str, metavar='{dir name}',
                        help="Directory to save the resulting PNG files. If not specified, assumed to be the "
                             "production directory.")

    parser.add_argument('-save', '--save_stack', type=str, metavar='{new stack name}',
                        help="Save the time series in the plate-fixed frame as new stack. "
                             "Switch requires a stack name to use. WARNING! If stack exists it will be overwritten.")

    args = parser.parse_args()

    cnn = dbConnection.Cnn("gnss_data.cfg")

    # stations to use
    if args.include_stations:
        include_stn = process_stnlist(cnn, args.include_stations,
                                      summary_title='User selected list of stations to include:')
    else:
        include_stn = []

    # create folder for plots
    if args.directory:
        if not os.path.exists(args.directory):
            os.mkdir(args.directory)
    else:
        if not os.path.exists('production'):
            os.mkdir('production')
        args.directory = 'production'

    # vertical reference frame transformation
    if len(args.vertical_ref):
        vref = process_stnlist(cnn, args.include_stations, summary_title='Stations for VREF:')
    else:
        vref = []

    if args.save_stack:
        save_stack = args.save_stack.lower()
    else:
        save_stack = None

    stack = args.stack_name[0]
    hdata = []

    for stn in tqdm(include_stn, ncols=80, disable=None):
        tqdm.write(' >> Processing HREF station ' + stationID(stn))
        station = stn['StationCode']
        network = stn['NetworkCode']

        rs = cnn.query_float(f'SELECT etms.*, stations.lat, stations.lon FROM etms '
                             f'INNER JOIN stations '
                             f'USING ("NetworkCode", "StationCode") '
                             f'WHERE ("NetworkCode", "StationCode", "stack", "object") = '
                             f'(\'{network}\', \'{station}\', \'{stack}\', \'polynomial\')', as_dict=True)

        if len(rs):
            params = np.array(rs[0]['params'])
            hdata.append({'NetworkCode': stn['NetworkCode'],
                          'StationCode': stn['StationCode'],
                          'lat': rs[0]['lat'],
                          'lon': rs[0]['lon'],
                          'v'  : params.reshape((3, params.shape[0] // 3))[:, 1]})

    # now gather the data for the VREF, if any
    vdata = []
    if len(vref):
        for stn in tqdm(vref, ncols=80, disable=None):
            tqdm.write(' >> Processing VREF station ' + stationID(stn))
            station = stn['StationCode']
            network = stn['NetworkCode']

            rs = cnn.query_float(f'SELECT etms.*, stations.lat, stations.lon FROM etms '
                                 f'INNER JOIN stations '
                                 f'USING ("NetworkCode", "StationCode") '
                                 f'WHERE ("NetworkCode", "StationCode", "stack", "object") = '
                                 f'(\'{network}\', \'{station}\', \'{stack}\', \'polynomial\')', as_dict=True)

            if len(rs):
                params = np.array(rs[0]['params'])
                vdata.append({'NetworkCode': stn['NetworkCode'],
                              'StationCode': stn['StationCode'],
                              'lat': rs[0]['lat'],
                              'lon': rs[0]['lon'],
                              'v': params.reshape((3, params.shape[0] // 3))[:, 1]})
                vdata[-1]['v'][2] = vdata[-1]['v'][2] - float(stn['parameters'][0]) / 1000.

    A, L = build_design(hdata, vdata)

    C, sigma, index, v, factor, _, cov = adjust_lsq(A, L)

    # summery of the Euler pole calculation
    iNE = index[0:len(hdata)*2].reshape((2, len(hdata)))
    rNE = v[0:len(hdata)*2].reshape((2, len(hdata)))
    fNE = (A @ C)[0:len(hdata)*2].reshape((2, len(hdata)))
    tqdm.write('HREF residuals')
    tqdm.write('Station  NE-Used Vn [mm/yr] Ve [mm/yr] Rn [mm/yr] Re [mm/yr]')
    for i, stn in enumerate(hdata):
        tqdm.write('%s %-3s %-3s %8.3f %8.3f %8.3f %8.3f' % (stationID(stn), 'OK' if iNE[0, i] else 'NOK',
                                                             'OK' if iNE[1, i] else 'NOK',
                                                             fNE[0, i] * 1000., fNE[1, i] * 1000.,
                                                             rNE[0, i] * 1000., rNE[1, i]  * 1000.))
    tqdm.write('----------------------------------------------------')
    tqdm.write('RMS of residuals                   %8.3f %8.3f' %
               (np.sqrt(np.sum(np.square(rNE[0, :] * 1000.)) / len(hdata)),
                np.sqrt(np.sum(np.square(rNE[1, :] * 1000.)) / len(hdata))))

    # summery of VREF calculation
    if len(vref):
        iNE = index[len(hdata) * 2:]
        rNE = v[len(hdata) * 2:]
        fNE = (A @ C)[len(hdata) * 2:]
        tqdm.write('\nVREF residuals')
        tqdm.write('Station  Vu-Used Vu [mm/yr] Ru [mm/yr]')
        for i, stn in enumerate(vdata):
            tqdm.write('%s %-4s %8.3f %8.3f' % (stationID(stn), 'OK' if iNE[i, 0] else 'NOK',
                                                fNE[i, 0] * 1000., rNE[i, 0] * 1000.))
        tqdm.write('-----------------------------------')
        tqdm.write('RMS of residuals       %8.3f' % (np.sqrt(np.sum(np.square(rNE[:, 0] * 1000.)) / len(vdata))))

    lat, lon, rot = cart2euler(C[0, 0], C[1, 0], C[2, 0])
    # to convert to mas/yr
    k = 1e-9 * 180/np.pi * 3600 * 1000

    # Euler vector covariance to lla
    mT_ = np.sqrt(np.sum(C ** 2))
    mXY = np.sqrt(C[0, 0] ** 2 + C[1, 0] ** 2)
    pXZ = C[0, 0] * C[2, 0]
    pYZ = C[1, 0] * C[2, 0]

    G = np.array([[C[0, 0] / mT_,     C[1, 0] / mT_,       C[1, 0] / mT_],
                  [-1/mT_**2*pXZ/mXY, -1/mT_**2*pYZ/mXY, 1/mT_**2*mXY],
                  [-C[1, 0]/(mXY**2), C[0, 0]/(mXY**2),    0]])

    cov_lla = G @ cov[0:3, 0:3] @ G.transpose()

    tqdm.write('')
    tqdm.write(' -- Total obs.: %i' % index.shape[0])
    tqdm.write(' -- Obs. ok   : %i' % index[index].shape[0])
    tqdm.write(' -- Obs. nok  : %i' % index[~index].shape[0])
    tqdm.write(' -- wrms      : %.3f mm/yr' % (factor[0, 0] * 1000.))
    tqdm.write(' ==== EULER POLE SUMMARY ====')
    tqdm.write(' -- XYZ (mas/yr mas/yr mas/yr) : %8.4f \xB1 %.3f %9.4f \xB1 %.3f %7.4f \xB1 %.3f'
               % (C[0, 0]*k, sigma[0, 0]*k, C[1, 0]*k, sigma[0, 1]*k, C[2, 0]*k, sigma[0, 2]*k))
    tqdm.write(' -- llr (deg deg deg/Myr)      : %8.4f \xB1 %.3f %9.4f \xB1 %.3f %7.4f \xB1 %.3f'
               % (lat, np.rad2deg(np.sqrt(cov_lla[1, 1])),
                  lon, np.rad2deg(np.sqrt(cov_lla[2, 2])),
                  rot, np.rad2deg(np.sqrt(cov_lla[0, 0])) * 1e-9 * 1e6))

    if args.plot_etms:
        for stn in tqdm(hdata, ncols=80, disable=None):
            A, _ = build_design([stn], [stn] if len(vref) > 0 else [])
            v = np.zeros((3, 1))
            v[0:3 if len(vref) > 0 else 2] = A @ C
            model = pyETM.Model(pyETM.Model.VEL, velocity=v, fit=True)
            etm = pyETM.GamitETM(cnn, stn['NetworkCode'], stn['StationCode'], stack_name=stack, models=[model],
                                 plot_remove_jumps=True)

            xfile = os.path.join(args.directory, '%s.%s_%s' % (etm.NetworkCode, etm.StationCode, 'plate-fixed'))
            etm.plot(xfile + '.png', plot_missing=False)

    if save_stack:
        stations = get_stack_stations(cnn, args.stack_name[0])

        # delete the entire stack to produce the new one
        cnn.query(f'DELETE FROM stacks WHERE name = \'{save_stack}\'')

        pbar = tqdm(total=0, ncols=80, disable=None)

        for i, stn in enumerate(stations):
            StationCode = stn['StationCode']
            NetworkCode = stn['NetworkCode']

            A, _ = build_design([stn], [stn] if len(vref) > 0 else [])
            v = np.zeros((3, 1))
            v[0:3 if len(vref) > 0 else 2] = A @ C
            model = pyETM.Model(pyETM.Model.VEL, velocity=v, fit=True)
            try:
                etm = pyETM.GamitETM(cnn, stn['NetworkCode'], stn['StationCode'], stack_name=stack, models=[model],
                                     plot_remove_jumps=True)

                tqdm.write(' -- Saving station %s to stack %s (%i/%i)'
                           % (stationID(stn), save_stack, i + 1, len(stations)))
                pbar.total = len(etm.soln.date)
                pbar.reset()

                for x, y, z, d in zip(etm.L[0], etm.L[1], etm.L[2], etm.soln.date):
                    cnn.insert('stacks', Project=etm.soln.project,
                               NetworkCode=NetworkCode,
                               StationCode=StationCode,
                               X=float(x),
                               Y=float(y),
                               Z=float(z),
                               sigmax=0.00,
                               sigmay=0.00,
                               sigmaz=0.00,
                               FYear=float(d.fyear),
                               Year=int(d.year),
                               DOY=int(d.doy),
                               name=save_stack)
                    pbar.update()
                pbar.refresh()

                # replace stack name so that figures show the new stack name
                etm.soln.stack_name = save_stack

                if args.plot_etms:
                    xfile = os.path.join(args.directory, '%s.%s_%s' % (etm.NetworkCode, etm.StationCode, 'plate-fixed'))
                    etm.plot(xfile + '.png', plot_missing=False)

            except pyETM.pyETMException as e:
                tqdm.write(str(e))

        pbar.close()


if __name__ == '__main__':
    main()
