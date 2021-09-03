#!/usr/bin/env python
"""
Project: Parallel.Archive
Date: 02/16/2017
Author: Demian D. Gomez
"""

import argparse
from io import BytesIO
import base64
import os
import json

# deps
from tqdm import tqdm
import numpy as np
import matplotlib
if not os.environ.get('DISPLAY', None):
    matplotlib.use('Agg')

import matplotlib.pyplot as plt
from mpl_toolkits.basemap import Basemap
import simplekml
from scipy.interpolate import griddata
import json

# app
import dbConnection
import Utils
import pyETM
from Utils import stationID, file_write

def plot_station_param(NetworkCode, StationCode, parameter_name, unit, pn, pe):

    fig = plt.figure(figsize=(5, 5))

    fig.suptitle('Station %s for %s.%s' % (parameter_name, NetworkCode, StationCode))
    plt.plot(0, 0, 'ok')
    plt.xlim([-30, 30])
    plt.ylim([-30, 30])
    plt.quiver(0, 0, np.multiply(pe, 1000), np.multiply(pn, 1000), scale=1, scale_units='x', zorder=3)
    plt.grid(True)
    plt.xlabel('[%s]' % unit)
    plt.ylabel('[%s]' % unit)

    figfile = BytesIO()
    fig.savefig(figfile, format='png')
    # plt.show()
    figfile.seek(0)  # rewind to beginning of file

    figdata_png = base64.b64encode(figfile.getvalue())

    plt.close()

    return figdata_png


def generate_kmz(kmz, stations, discarded):

    tqdm.write(' >> Generating KML (see production directory)...')

    kml = simplekml.Kml()
    folder1 = kml.newfolder(name='velocity')
    folder2 = kml.newfolder(name='discarded')

    # define styles
    styles_ok  = simplekml.StyleMap()
    styles_nok = simplekml.StyleMap()
    for (s, icon_color, label_scale) in ((styles_ok.normalstyle,     'ff00ff00', 0), 
                                         (styles_ok.highlightstyle,  'ff00ff00', 3),
                                         (styles_nok.normalstyle,    'ff0000ff', 0),
                                         (styles_nok.highlightstyle, 'ff0000ff', 3)):
        s.iconstyle.icon.href = 'http://maps.google.com/mapfiles/kml/shapes/placemark_square.png'
        s.iconstyle.color     = icon_color
        s.labelstyle.scale    = label_scale

    for stn in tqdm(stations, ncols=160, disable=None, desc=' -- Included station list'):
        stn_id = stationID(stn)
        plot   = plot_station_param(stn['NetworkCode'], stn['StationCode'],
                                    'velocity', 'mm/yr', stn['vn'], stn['ve'])

        pt = folder1.newpoint(name=stn_id, coords=[(stn['lon'], stn['lat'])])
        pt.stylemap = styles_ok

        pt.description = """<strong>NE vel: %5.2f %5.2f [mm/yr]</strong><br><br>
        <table width="880" cellpadding="0" cellspacing="0">
        <tr>
        <td align="center" valign="top">
        <strong>Parameters:</strong><br>
        <img src="data:image/png;base64, %s" alt="Observation information" height="300" width="300"/><br>
        <strong>Trajectory model:</strong><br>
        <img src="data:image/png;base64, %s" alt="Observation information" height="750" width="1100"/>
        </p>
        </tr>
        </td>
        </table>
        """ % (stn['vn']*1000, stn['ve']*1000, plot, stn['etm'])

        ls = folder1.newlinestring(name=stn_id)

        ls.coords = [(stn['lon'], stn['lat']),
                     (stn['lon'] + stn['ve'] * 1 / 0.025,
                      stn['lat'] + stn['vn'] * 1  /0.025 * np.cos(stn['lat']*np.pi/180))]
        ls.style.linestyle.width = 3
        ls.style.linestyle.color = 'ff0000ff'

    for stn in tqdm(discarded, ncols=160, disable=None, desc=' -- Excluded station list'):
        stn_id = stationID(stn)
        plot   = plot_station_param(stn['NetworkCode'], stn['StationCode'], 
                                    'velocity', 'mm/yr', stn['vn'], stn['ve'])

        pt = folder2.newpoint(name=stn_id, coords=[(stn['lon'], stn['lat'])])
        pt.stylemap = styles_nok

        pt.description = """<strong>NE vel: %5.2f %5.2f [mm/yr]</strong><br><br>
        <table width="880" cellpadding="0" cellspacing="0">
        <tr>
        <td align="center" valign="top">
        <strong>Parameters:</strong><br>
        <img src="data:image/png;base64, %s" alt="Observation information" height="300" width="300"/><br>
        <strong>Trajectory model:</strong><br>
        <img src="data:image/png;base64, %s" alt="Observation information" height="750" width="1100"/>
        </p>
        </tr>
        </td>
        </table>
        """ % (stn['vn']*1000, stn['ve']*1000, plot, stn['etm'])

        ls = folder2.newlinestring(name=stn_id)

        ls.coords = [(stn['lon'], stn['lat']),
                     (stn['lon'] + stn['ve'] * 1 / 0.025,
                      stn['lat'] + stn['vn'] * 1 / 0.025*np.cos(stn['lat']*np.pi/180))]
        ls.style.linestyle.width = 3
        ls.style.linestyle.color = 'ff0000ff'

    if not os.path.exists('production'):
        os.makedirs('production')

    tqdm.write(' >> Saving kmz...')
    kml.savekmz(kmz)


def process_interseismic(cnn, stnlist, force_stnlist, stack, sigma_cutoff, vel_cutoff, lat_lim, filename, kmz):
    # start by checking that the stations in the list have a linear start (no post-seismic)
    # and more than 2 years of data until the first earthquake or non-linear behavior

    tqdm.write(' >> Analyzing suitability of station list to participate in interseismic trajectory model...')
    tqdm.write(' -- velocity cutoff: %.2f mm/yr; output filename: %s' % (vel_cutoff, filename))

    use_station = []
    discarded   = []
    velocities  = []
    min_lon     =  9999
    max_lon     = -9999
    min_lat     =  9999
    max_lat     = -9999

    for stn in tqdm(stnlist, ncols=160, disable=None):
        try:
            stn_id = stationID(stn)

            etm = pyETM.GamitETM(cnn, stn['NetworkCode'], stn['StationCode'], stack_name=stack)

            use = True
            if stn in force_stnlist:
                tqdm.write(' -- %s was forced to be included in the list' % stn_id)
            else:
                # only check everything is station not included in the force list
                # check that station is within latitude range
                if etm.gamit_soln.lat[0] < lat_lim[0] or \
                   etm.gamit_soln.lat[0] > lat_lim[1]:
                    tqdm.write(' -- %s excluded because it is outside of the latitude limit' % stn_id)
                    use = False

                # check that station has at least 2 years of data
                if etm.gamit_soln.date[-1].fyear - etm.gamit_soln.date[0].fyear < 2 and use:
                    tqdm.write(' -- %s rejected due having less than two years of observations %s -> %s'
                               % (stn_id,
                                  etm.gamit_soln.date[0].yyyyddd(),
                                  etm.gamit_soln.date[-1].yyyyddd()))
                    use = False

                # other checks
                if etm.A is not None:
                    if len(etm.Jumps.table) > 0 and use:
                        j = next((j
                                  for j in etm.Jumps.table
                                  if j.p.jump_type == pyETM.CO_SEISMIC_JUMP_DECAY and j.fit and \
                                  j.magnitude >= 7 and j.date.fyear < etm.gamit_soln.date[0].fyear + 1.5
                                  ), None)
                        if j:
                            tqdm.write(' -- %s has a Mw %.1f in %s and data starts in %s'
                                       % (stn_id,
                                          j.magnitude, j.date.yyyyddd(), etm.gamit_soln.date[0].yyyyddd()))
                            use = False
                            
                        else:
                            has_eq_jumps = any(True
                                               for j in etm.Jumps.table
                                               if j.p.jump_type == pyETM.CO_SEISMIC_DECAY and j.fit)
                            if has_eq_jumps:
                                tqdm.write(' -- %s has one or more earthquakes before data started in %s'
                                           % (stn_id, etm.gamit_soln.date[0].yyyyddd()))
                                use = False

                    if (etm.factor[0] * 1000 > sigma_cutoff or \
                        etm.factor[1] * 1000 > sigma_cutoff) and use:
                        tqdm.write(' -- %s rejected due to large wrms %5.2f %5.2f %5.2f'
                                   % (stn_id,
                                      etm.factor[0] * 1000, etm.factor[1] * 1000, etm.factor[2] * 1000))
                        use = False

                    norm = np.sqrt(np.sum(np.square(etm.Linear.p.params[0:2, 1]*1000)))
                    if norm > vel_cutoff and use:
                        tqdm.write(' -- %s rejected due to large NEU velocity: %5.2f %5.2f %5.2f NE norm %5.2f'
                                   % (stn_id,
                                      etm.Linear.p.params[0, 1] * 1000,
                                      etm.Linear.p.params[1, 1] * 1000,
                                      etm.Linear.p.params[2, 1] * 1000,
                                      norm))
                        use = False
                elif use:
                    tqdm.write(' -- %s too few solutions to calculate ETM' % stn_id)
                    use = False

            def getvel():
                return {'NetworkCode' : etm.NetworkCode,
                        'StationCode' : etm.StationCode,
                        'lat'         : etm.gamit_soln.lat[0],
                        'lon'         : etm.gamit_soln.lon[0],
                        'vn'          : etm.Linear.p.params[0, 1],
                        've'          : etm.Linear.p.params[1, 1],
                        'etm'         : etm.plot(plot_missing  = False,
                                                 plot_outliers = False,
                                                 fileio=BytesIO())
                        }

            if use:
                tqdm.write(' -- %s added NEU wrms: %5.2f %5.2f %5.2f NEU vel: %5.2f %5.2f %5.2f'
                           % (stn_id,
                              etm.factor[0]*1000, etm.factor[1]*1000, etm.factor[2]*1000,
                              etm.Linear.p.params[0, 1]*1000,
                              etm.Linear.p.params[1, 1]*1000,
                              etm.Linear.p.params[2, 1]*1000))
                use_station.append(stn)
                v = getvel()
                velocities.append(v)

                min_lon = min(v['lon'], min_lon)
                max_lon = max(v['lon'], max_lon)
                min_lat = min(v['lat'], min_lat)
                max_lat = max(v['lat'], max_lat)

            elif etm.A is not None:
                discarded.append(getvel())

        except pyETM.pyETMException as e:
            tqdm.write(' -- %s: %s' % (stn_id, str(e)))


    tqdm.write(' >> Total number of stations for linear model: %i' % len(use_station))
    map = Basemap(llcrnrlon  = min_lon - 2,
                  llcrnrlat  = min_lat - 2,
                  urcrnrlon  = max_lon + 2,
                  urcrnrlat  = max_lat + 2,
                  resolution = 'i',
                  projection = 'merc',
                  lon_0      = (max_lon - min_lon)/2 + min_lon,
                  lat_0      = (max_lat - min_lat)/2 + min_lat)

    plt.figure(figsize=(15, 10))
    map.drawcoastlines()
    map.drawcountries()
    # map.drawstates()
    # map.fillcontinents(color='#cc9966', lake_color='#99ffff')
    # draw parallels and meridians.
    # map.drawparallels(np.arange(np.floor(min_lat), np.ceil(max_lat), 2.))
    # map.drawmeridians(np.arange(np.floor(min_lon), np.ceil(max_lon), 2.))
    # map.drawmapboundary(fill_color='#99ffff')
    map.quiver([l['lon'] for l in velocities],
               [l['lat'] for l in velocities],
               [l['ve']  for l in velocities],
               [l['vn']  for l in velocities],
               scale=0.25,
               latlon=True, color='blue', zorder=3)
    plt.title("Transverse Mercator Projection")
    plt.savefig('production/test.png')
    plt.close()

    outvar = np.array([[v['lon'], v['lat'], v['ve'], v['vn']]
                       for v in velocities])
    np.savetxt(filename, outvar)
    if kmz:
        generate_kmz(kmz, velocities, discarded)


def process_postseismic(cnn, stnlist, force_stnlist, stack, interseimic_filename, events, sigma_cutoff, lat_lim,
                        filename, kmz):
    tqdm.write(' >> Analyzing suitability of station list to participate in interseismic trajectory model...')
    tqdm.write(' -- output filename: %s' % filename)

    use_station = []
    discarded   = []
    velocities  = []
    min_lon     =  9999
    max_lon     = -9999
    min_lat     =  9999
    max_lat     = -9999

    # load the interseismic model
    model = np.loadtxt(interseimic_filename)

    model[:, 0] -= 360

    for stn in tqdm(stnlist, ncols=160, disable=None):
        stn_id = stationID(stn)
        try:
            lla = cnn.query_float('SELECT lat,lon FROM stations WHERE "NetworkCode" = \'%s\' AND "StationCode" = \'%s\''
                                  % (stn['NetworkCode'], stn['StationCode']), as_dict=True)[0]

            ve = griddata(model[:, 0:2], model[:, 2] / 1000, (lla['lon'], lla['lat']), method='cubic')
            vn = griddata(model[:, 0:2], model[:, 3] / 1000, (lla['lon'], lla['lat']), method='cubic')

            etm = pyETM.GamitETM(cnn, stn['NetworkCode'], stn['StationCode'],
                                 stack_name   = stack,
                                 interseismic = [vn, ve, 0.])

            etm.plot('production/%s_gamit_model.png' % stn_id)
            file_write('production/%s_gamit_model.json' % stn_id,
                       json.dumps(etm.todictionary(time_series=True, model=True),
                                  indent    = 4,
                                  sort_keys = False))
            # only check everything is station not included in the force list
            # if stn not in force_stnlist:

        except pyETM.pyETMException as e:
            tqdm.write(' -- %s: %s' % (stn_id, str(e)))


def main():

    parser = argparse.ArgumentParser(description='Archive operations Main Program')

    parser.add_argument('stack', type=str, nargs=1, metavar='{stack name}',
                        help="Name of the GAMIT stack to use for the trajectories")

    parser.add_argument('-stn', '--stations', nargs='+', type=str, metavar='{station list}', default=[],
                        help="Specify the list of networks/stations given in [net].[stnm] format or just [stnm] "
                             "that will be filtered using the selected field specifications. If [stnm] is "
                             "not unique in the database, all stations with that name will be processed."
                             "Alternatively, a file with the station list can be provided.")

    parser.add_argument('-force_stn', '--force_stations', nargs='+', type=str, metavar='{station list}', default=[],
                        help="Force stations to be included in the selected field. "
                             "Specify the list of networks/stations given in [net].[stnm] format or just [stnm]. "
                             "If [stnm] is not unique in the database, all stations with that name will be processed."
                             "Alternatively, a file with the station list can be provided.")

    parser.add_argument('-lat_lim', '--latitude_limits', nargs=2, type=float, metavar='{min_lat max_lat}',
                        help="Latitude limits (decimal degrees). Discard stations outside of this limit.")

    parser.add_argument('-sigma', '--sigma_cutoff', nargs=1, type=float, metavar='{mm}', default=[2.5],
                        help="Reject stations based on the ETM's wrms (in mm). This filter does not apply for forced "
                             "station list.")

    parser.add_argument('-vel', '--velocity_cutoff', nargs=1, type=float, metavar='{mm/yr}', default=[50],
                        help="ETM velocity cutoff value to reject stations for velocity interpolation "
                             "(norm of NE in mm/yr).")

    parser.add_argument('-interseismic', '--interseismic_process', nargs='*', type=str,
                        metavar='[velocity_cutoff] [output_filename] [kmz_filename]',
                        help="Process stations for interseismic velocity field computation. Reject stations with "
                             "interseismic velocity > {velocity_cutoff} (default 50 mm/yr). Filename to output the "
                             "selected stations (default filename interseismic.txt). Optionally, specify a kmz "
                             "filename to output the selected and rejected stations with their velocity components and "
                             "ETMs embedded in the kmz (default no kmz).")

    parser.add_argument('-postseismic', '--postseismic_process', nargs='+', type=str,
                        metavar='{velocity_field_grid} {event_date} [secondary_relaxation] [output_filename]',
                        help="Process stations for postseismic field computation. Reject stations with "
                             "interseismic velocity > {velocity_cutoff} (default 50 mm/yr). Filename to output the "
                             "selected stations (default filename interseismic.txt)")

    args = parser.parse_args()

    cnn = dbConnection.Cnn("gnss_data.cfg")

    # station list
    stnlist       = Utils.process_stnlist(cnn, args.stations)
    force_stnlist = Utils.process_stnlist(cnn, args.force_stations, summary_title='Forced station list:')

    # get the station list
    if args.interseismic_process is not None:
        # defaults
        l = len(args.interseismic_process)
        args.interseismic_process += ['50.', 'interseismic.txt', None][min(l, 3):]

        process_interseismic(cnn, stnlist, force_stnlist,
                             args.stack[0],
                             args.sigma_cutoff[0],
                             float(args.interseismic_process[0]),
                             args.latitude_limits,
                             args.interseismic_process[1],
                             args.interseismic_process[2])

    if args.postseismic_process is not None:
        process_postseismic(cnn, stnlist, force_stnlist,
                            args.stack[0],
                            args.postseismic_process[0],
                            [],
                            [], [], 'out.txt', 'sss.kmz')

if __name__ == '__main__':
    main()
