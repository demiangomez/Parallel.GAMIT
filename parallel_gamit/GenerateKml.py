"""
Project: Parallel.GAMIT
Date: 7/18/18 10:28 AM
Author: Demian D. Gomez

Program to generate a KML with the stations in a project and the stations out of a project
"""

import argparse
import os
import base64
import datetime as dt
from io import BytesIO

# deps
import matplotlib

if not os.environ.get('DISPLAY', None):
    matplotlib.use('Agg')

import matplotlib.dates as mdates
from matplotlib.collections import PolyCollection
from tqdm import tqdm
import numpy as np
import simplekml

# app 
import pyDate
import pyStationInfo
import dbConnection
from pyGamitConfig import GamitConfiguration
from Utils import process_stnlist, stationID


def main():

    parser = argparse.ArgumentParser(description='GNSS time series stacker')

    parser.add_argument('project_file', type=str, nargs=1, metavar='{project cfg file}',
                        help="Project CFG file with all the stations being processed in Parallel.GAMIT")
    parser.add_argument('-stninfo', '--station_info', action='store_true',
                        help='Run integrity checks on station information and output results to kmz file. '
                             'The icons of the stations will represent any problems in the station info records.')
    parser.add_argument('-data', '--available_data', action='store_true', default=False,
                        help='Produce detailed plots with available data.')

    args = parser.parse_args()

    cnn = dbConnection.Cnn("gnss_data.cfg")

    GamitConfig = GamitConfiguration(args.project_file[0], check_config=False)  # type: GamitConfiguration

    stations = process_stnlist(cnn, GamitConfig.NetworkConfig['stn_list'].split(','))

    if not args.station_info:
        generate_kml(cnn, GamitConfig.NetworkConfig.network_id.lower(), stations, args.available_data)
    else:
        generate_kml_stninfo(cnn, GamitConfig.NetworkConfig.network_id.lower(), stations, args.available_data)


def generate_kml_stninfo(cnn, project, stations, data=False):
    stnlist = [stationID(s) for s in stations]

    tqdm.write('  >> Generating KML for this run (see production directory)...')

    kml = simplekml.Kml()

    rs = cnn.query_float('SELECT * FROM stations WHERE "NetworkCode" NOT LIKE \'?%\' '
                         'ORDER BY "NetworkCode", "StationCode" ', as_dict=True)

    tqdm.write(' >> Adding stations in database')

    folder1 = kml.newfolder(name=project)
    folder2 = kml.newfolder(name='all stations')

    ICON_SQUARE = 'http://maps.google.com/mapfiles/kml/shapes/placemark_square.png'
    ICON_WARN = 'http://maps.google.com/mapfiles/kml/shapes/caution.png'

    styles_ok = simplekml.StyleMap()
    styles_ok.normalstyle.iconstyle.icon.href = ICON_SQUARE
    styles_ok.normalstyle.iconstyle.color = 'ff00ff00'
    styles_ok.normalstyle.iconstyle.scale = 1.5
    styles_ok.normalstyle.labelstyle.scale = 0

    styles_ok.highlightstyle.iconstyle.icon.href = ICON_SQUARE
    styles_ok.highlightstyle.iconstyle.color = 'ff00ff00'
    styles_ok.highlightstyle.iconstyle.scale = 2
    styles_ok.highlightstyle.labelstyle.scale = 2

    styles_nok = simplekml.StyleMap()
    styles_nok.normalstyle.iconstyle.icon.href = ICON_WARN
    styles_nok.normalstyle.iconstyle.color = 'ff0000ff'
    styles_nok.normalstyle.iconstyle.scale = 1.5
    styles_nok.normalstyle.labelstyle.scale = 0

    styles_nok.highlightstyle.iconstyle.icon.href = ICON_WARN
    styles_nok.highlightstyle.iconstyle.color = 'ff0000ff'
    styles_nok.highlightstyle.iconstyle.scale = 2
    styles_nok.highlightstyle.labelstyle.scale = 2

    for stn in tqdm(rs, ncols=80):
        stn_id = stationID(stn)

        count = cnn.query_float('SELECT count(*) as cc FROM rinex_proc WHERE "NetworkCode" = \'%s\' '
                                'AND "StationCode" = \'%s\''
                                % (stn['NetworkCode'], stn['StationCode']))

        ppp_s = cnn.query_float('SELECT count(*) as cc FROM ppp_soln WHERE "NetworkCode" = \'%s\' '
                                'AND "StationCode" = \'%s\''
                                % (stn['NetworkCode'], stn['StationCode']))

        try:
            stninfo = pyStationInfo.StationInfo(cnn, stn['NetworkCode'], stn['StationCode'], allow_empty=True)
            _ = stninfo.return_stninfo_short()
        except pyStationInfo.pyStationInfoHeightCodeNotFound as e:
            tqdm.write('Error: %s. Station will be skipped.' % str(e))
            continue

        if count[0][0]:
            completion = '%.1f' % (float(ppp_s[0][0]) / float(count[0][0]) * 100)
        else:
            completion = 'NA'

        if stn['DateStart']:
            DS = '%.3f' % stn['DateStart']
            DE = '%.3f' % stn['DateEnd']
        else:
            DS = 'NA'
            DE = 'NA'

        if stn_id in stnlist:
            folder = folder1
        else:
            folder = folder2

        # run the station info checks
        gaps = stninfo.station_info_gaps()

        # mark the stations with less than 100 observations or with less than 60% completion (PPP)
        stn_issues = []
        if not gaps and len(stninfo.records) > 0:
            style = styles_ok
        else:
            style = styles_nok

            if len(stninfo.records) == 0:
                stn_issues.append('Station has not station information records!')

            for gap in gaps:
                if gap['record_start'] and gap['record_end']:
                    stn_issues.append('At least %i RINEX file(s) outside of station info record ending at %s and next '
                                      'record starting at %s' % (gap['rinex_count'],
                                                                 str(gap['record_start']['DateStart']),
                                                                 str(gap['record_end']['DateEnd'])))

                elif gap['record_start'] and not gap['record_end']:
                    stn_issues.append('At least %i RINEX file(s) outside of station info record starting at %s '
                                      % (gap['rinex_count'], str(gap['record_start']['DateStart'])))

                elif not gap['record_start'] and gap['record_end']:
                    stn_issues.append('At least %i RINEX file(s) outside of station info record ending at %s '
                                      % (gap['rinex_count'], str(gap['record_end']['DateEnd'])))

        plt = plot_station_info_rinex(cnn, stn['NetworkCode'], stn['StationCode'], stninfo)

        if data:
            data_plt = """
        <p style="font-family: monospace; font-size: 8pt;"><br><br>
        <strong>Observation distribution:</strong><br>
        </p>
        <img src="data:image/png;base64, %s" alt="Available data" />
                    """ % plot_rinex(cnn, stn['NetworkCode'], stn['StationCode'])
        else:
            data_plt = ""

        pt = folder.newpoint(name=stn_id, coords=[(stn['lon'], stn['lat'])])
        pt.stylemap = style

        pt.description = """<strong>%s -> %s</strong> RINEX count: %i PPP soln: %s%%<br><br>
<strong>Station Information issues:</strong><br>
%s<br><br>
<strong>Station Information:</strong><br>
<table width="880" cellpadding="0" cellspacing="0">
<tr>
<td align="left" valign="top">
<p style="font-family: monospace; font-size: 8pt;">%s<br><br>
<strong>Observation distribution:</strong><br>
</p>
<img src="data:image/png;base64, %s" alt="Observation information" />
%s
</tr>
</td>
</table>""" % (DS, DE, count[0][0], completion, '<br>'.join(stn_issues),
               stninfo.return_stninfo_short().replace('\n', '<br>'), plt, data_plt)

    if not os.path.exists('production'):
        os.makedirs('production')

    kml.savekmz('production/' + project + '.kmz')


def generate_kml(cnn, project, stations, data=False):

    stnlist = [stationID(s) for s in stations]

    tqdm.write('  >> Generating KML for this run (see production directory)...')

    kml = simplekml.Kml()

    rs = cnn.query_float('SELECT * FROM stations WHERE "NetworkCode" NOT LIKE \'?%\' '
                         'ORDER BY "NetworkCode", "StationCode" ', as_dict=True)

    tqdm.write(' >> Adding stations in database')

    folder1 = kml.newfolder(name=project)
    folder2 = kml.newfolder(name='all stations')

    ICON_CIRCLE = 'http://maps.google.com/mapfiles/kml/shapes/placemark_circle.png'
    ICON_SQUARE = 'http://maps.google.com/mapfiles/kml/shapes/placemark_square.png'

    stylec = simplekml.StyleMap()
    stylec.normalstyle.iconstyle.icon.href = ICON_CIRCLE
    stylec.normalstyle.iconstyle.scale = 1.5
    stylec.normalstyle.labelstyle.scale = 0

    stylec.highlightstyle.iconstyle.icon.href = ICON_CIRCLE
    stylec.highlightstyle.iconstyle.scale = 2
    stylec.highlightstyle.labelstyle.scale = 2

    styles_ok = simplekml.StyleMap()
    styles_ok.normalstyle.iconstyle.icon.href = ICON_SQUARE
    styles_ok.normalstyle.iconstyle.color = 'ff00ff00'
    styles_ok.normalstyle.iconstyle.scale = 1.5
    styles_ok.normalstyle.labelstyle.scale = 0

    styles_ok.highlightstyle.iconstyle.icon.href = ICON_SQUARE
    styles_ok.highlightstyle.iconstyle.color = 'ff00ff00'
    styles_ok.highlightstyle.iconstyle.scale = 2
    styles_ok.highlightstyle.labelstyle.scale = 2

    styles_nok = simplekml.StyleMap()
    styles_nok.normalstyle.iconstyle.icon.href = ICON_SQUARE
    styles_nok.normalstyle.iconstyle.color = 'ff0000ff'
    styles_nok.normalstyle.iconstyle.scale = 1.5
    styles_nok.normalstyle.labelstyle.scale = 0

    styles_nok.highlightstyle.iconstyle.icon.href = ICON_SQUARE
    styles_nok.highlightstyle.iconstyle.color = 'ff0000ff'
    styles_nok.highlightstyle.iconstyle.scale = 2
    styles_nok.highlightstyle.labelstyle.scale = 2

    for stn in tqdm(rs, ncols=80):
        stn_id = stationID(stn)

        count = cnn.query_float('SELECT count(*) as cc FROM rinex_proc WHERE "NetworkCode" = \'%s\' '
                                'AND "StationCode" = \'%s\''
                                % (stn['NetworkCode'], stn['StationCode']))

        ppp_s = cnn.query_float('SELECT count(*) as cc FROM ppp_soln WHERE "NetworkCode" = \'%s\' '
                                'AND "StationCode" = \'%s\''
                                % (stn['NetworkCode'], stn['StationCode']))

        try:
            stninfo = pyStationInfo.StationInfo(cnn, stn['NetworkCode'], stn['StationCode'], allow_empty=True)
            _ = stninfo.return_stninfo_short()
        except pyStationInfo.pyStationInfoHeightCodeNotFound as e:
            tqdm.write('Error: %s. Station will be skipped.' % str(e))
            continue

        if count[0][0]:
            completion = '%.1f' % (float(ppp_s[0][0]) / float(count[0][0]) * 100)
        else:
            completion = 'NA'

        if stn['DateStart']:
            DS = '%.3f' % stn['DateStart']
            DE = '%.3f' % stn['DateEnd']
        else:
            DS = 'NA'
            DE = 'NA'

        if stn_id in stnlist:
            folder = folder1
            # mark the stations with less than 100 observations or with less than 60% completion (PPP)
            if count[0][0] >= 100 and (float(ppp_s[0][0]) / float(count[0][0]) * 100) >= 60.0:
                style = styles_ok
            else:
                style = styles_nok
        else:
            folder = folder2
            style  = stylec

        plt = plot_station_info_rinex(cnn, stn['NetworkCode'], stn['StationCode'], stninfo)

        if data:
            data_plt = """
<p style="font-family: monospace; font-size: 8pt;"><br><br>
<strong>Observation distribution:</strong><br>
</p>
<img src="data:image/png;base64, %s" alt="Available data" />
            """ % plot_rinex(cnn, stn['NetworkCode'], stn['StationCode'])
        else:
            data_plt = ""

        pt = folder.newpoint(name=stn_id, coords=[(stn['lon'], stn['lat'])])
        pt.stylemap = style

        pt.description = """<strong>%s -> %s</strong> RINEX count: %i PPP soln: %s%%<br><br>
<strong>Station Information:</strong><br>
<table width="880" cellpadding="0" cellspacing="0">
<tr>
<td align="left" valign="top">
<p style="font-family: monospace; font-size: 8pt;">%s<br><br>
<strong>Observation distribution:</strong><br>
</p>
<img src="data:image/png;base64, %s" alt="Observation information" />
%s
</tr>
</td>
</table>""" % (DS, DE, count[0][0], completion, stninfo.return_stninfo_short().replace('\n', '<br>'), plt, data_plt)

    if not os.path.exists('production'):
        os.makedirs('production')

    kml.savekmz('production/' + project + '.kmz')


def plot_station_info_rinex2(cnn, NetworkCode, StationCode, stninfo):

    import matplotlib.pyplot as plt

    cats = {"rinex": 1, 
            "stninfo": 2}
    colormapping = {"rinex": "C0",
                    "stninfo": "C1"}

    data = []

    if stninfo.records is not None:
        for record in stninfo.records:
            data.append((record['DateStart'].datetime(),
                         (record['DateEnd'].datetime() if record['DateEnd'].year is not None \
                          else dt.datetime.now()),
                         'stninfo'))

    rinex = cnn.query_float('SELECT * FROM rinex_proc WHERE "NetworkCode" = \'%s\' '
                            'AND "StationCode" = \'%s\'' % (NetworkCode, StationCode), as_dict=True)

    for r in rinex:
        data.append((r['ObservationSTime'], r['ObservationETime'], 'rinex'))

    verts  = []
    colors = []
    for d in data:
        v = [(mdates.date2num(d[0]), cats[d[2]] - .4),
             (mdates.date2num(d[0]), cats[d[2]] + .4),
             (mdates.date2num(d[1]), cats[d[2]] + .4),
             (mdates.date2num(d[1]), cats[d[2]] - .4),
             (mdates.date2num(d[0]), cats[d[2]] - .4)]
        verts.append(v)
        colors.append(colormapping[d[2]])

    bars = PolyCollection(verts, facecolors=colors)

    fig, ax = plt.subplots(figsize=(7, 3))

    ax.grid(True)
    ax.add_collection(bars)
    ax.autoscale()
    ax.set_title('RINEX and Station Information for %s.%s' % (NetworkCode, StationCode))

    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))

    ax.set_yticks([1, 2])
    ax.set_yticklabels(["rinex", "stninfo"])
    fig.autofmt_xdate()

    figfile = BytesIO()

    try:
        plt.savefig(figfile, format='png')
        # plt.show()
        figfile.seek(0)  # rewind to beginning of file

        figdata_png = base64.b64encode(figfile.getvalue())
    except ValueError:
        # either no rinex or no station info
        figdata_png = ''
        tqdm.write(' -- Error processing %s.%s: station appears to have no RINEX or Station Info'
                   % (NetworkCode, StationCode))

    plt.close()

    return figdata_png


def plot_station_info_rinex(cnn, NetworkCode, StationCode, stninfo):

    import matplotlib.pyplot as plt

    stnfo = []

    if stninfo.records is not None:
        for record in stninfo.records:
            stnfo.append([record['DateStart'].fyear,
                          (record['DateEnd'].fyear if record['DateEnd'].year is not None \
                           else pyDate.Date(datetime=dt.datetime.now()).fyear)
                          ])

    rinex = np.array(cnn.query_float('SELECT "ObservationFYear" FROM rinex_proc WHERE "NetworkCode" = \'%s\' '
                                     'AND "StationCode" = \'%s\'' % (NetworkCode, StationCode)))

    fig, ax = plt.subplots(figsize=(7, 3))

    ax.grid(True)
    ax.set_title('RINEX and Station Information for %s.%s' % (NetworkCode, StationCode))

    for poly in stnfo:
        ax.plot(poly, [1, 1], 'o-', linewidth=2, markersize=4, color='tab:orange')
        # break line to clearly show the stop of a station info
        ax.plot([poly[1], poly[1]], [-0.5, 1.5], ':', color='tab:orange')

    ax.plot(rinex, np.zeros(rinex.shape[0]), 'o', color='tab:blue', markersize=3)
    ax.set_yticks([0, 1])
    ax.set_yticklabels(["rinex", "stninfo"])
    plt.ylim([-.5, 1.5])
    figfile = BytesIO()

    try:
        plt.savefig(figfile, format='png')
        # plt.show()
        figfile.seek(0)  # rewind to beginning of file

        figdata_png = base64.b64encode(figfile.getvalue()).decode()
    except Exception:
        # either no rinex or no station info
        figdata_png = ''
        tqdm.write(' -- Error processing %s.%s: station appears to have no RINEX or Station Info'
                   % (NetworkCode, StationCode))

    plt.close()

    return figdata_png


def plot_rinex(cnn, NetworkCode, StationCode):

    import matplotlib.pyplot as plt

    # find the available data
    rinex = np.array(cnn.query_float('SELECT "ObservationYear", "ObservationDOY" FROM rinex_proc WHERE '
                                     '"NetworkCode" = \'%s\' AND "StationCode" = \'%s\'' % (NetworkCode, StationCode)))

    fig, ax = plt.subplots(figsize=(7, 3))

    ax.grid(True)
    ax.set_title('RINEX and missing data for %s.%s' % (NetworkCode, StationCode))

    if rinex.size:
        # create a continuous vector for missing data
        md = np.arange(0, 366)
        my = np.unique(rinex[:, 0])
        for yr in my:
            ax.scatter(md, np.repeat(yr, 366), facecolors='none', edgecolors='k', s=4)

        ax.scatter(rinex[:, 1], rinex[:, 0], facecolors='tab:blue', edgecolors='k', s=4)

    ax.set_ylabel('Years')
    ax.set_xlabel('DOYs')
    # ax.set_yticklabels(["DOY", "Year"])
    figfile = BytesIO()

    try:
        plt.savefig(figfile, format='png')
        # plt.show()
        figfile.seek(0)  # rewind to beginning of file

        figdata_png = base64.b64encode(figfile.getvalue()).decode()
    except Exception:
        # either no rinex or no station info
        figdata_png = ''
        tqdm.write(' -- Error processing %s.%s: station appears to have no RINEX or Station Info'
                   % (NetworkCode, StationCode))

    plt.close()

    return figdata_png


if __name__ == '__main__':
    main()
