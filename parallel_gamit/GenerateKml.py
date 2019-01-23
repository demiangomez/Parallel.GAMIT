"""
Project: Parallel.GAMIT
Date: 7/18/18 10:28 AM
Author: Demian D. Gomez

Program to generate a KML with the stations in a project and the stations out of a project
"""

import argparse
import dbConnection
from Utils import process_stnlist
import os
from pyGamitConfig import GamitConfiguration
from tqdm import tqdm
import simplekml
import pyStationInfo

import datetime as dt
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.collections import PolyCollection
from io import BytesIO
import base64

def main():

    parser = argparse.ArgumentParser(description='GNSS time series stacker')

    parser.add_argument('project_file', type=str, nargs=1, metavar='{project cfg file}',
                        help="Project CFG file with all the stations being processed in Parallel.GAMIT")

    args = parser.parse_args()

    cnn = dbConnection.Cnn("gnss_data.cfg")

    GamitConfig = GamitConfiguration(args.project_file[0], check_config=False)  # type: GamitConfiguration

    stations = process_stnlist(cnn, GamitConfig.NetworkConfig['stn_list'].split(','))

    generate_kml(cnn, GamitConfig.NetworkConfig.network_id.lower(), stations)


def generate_kml(cnn, project, stations):

    stnlist = [s['NetworkCode'] + '.' + s['StationCode'] for s in stations]

    tqdm.write('  >> Generating KML for this run (see production directory)...')

    kml = simplekml.Kml()

    rs = cnn.query_float('SELECT * FROM stations WHERE "NetworkCode" NOT LIKE \'?%\' '
                         'ORDER BY "NetworkCode", "StationCode" ', as_dict=True)

    tqdm.write(' >> Adding stations in database')

    folder1 = kml.newfolder(name=project)
    folder2 = kml.newfolder(name='all stations')

    stylec = simplekml.StyleMap()
    stylec.normalstyle.iconstyle.icon.href = 'http://maps.google.com/mapfiles/kml/shapes/placemark_circle.png'
    stylec.normalstyle.labelstyle.scale = 0

    stylec.highlightstyle.iconstyle.icon.href = 'http://maps.google.com/mapfiles/kml/shapes/placemark_circle.png'
    stylec.highlightstyle.labelstyle.scale = 2

    styles_ok = simplekml.StyleMap()
    styles_ok.normalstyle.iconstyle.icon.href = 'http://maps.google.com/mapfiles/kml/shapes/placemark_square.png'
    styles_ok.normalstyle.iconstyle.color = 'ff00ff00'
    styles_ok.normalstyle.labelstyle.scale = 0

    styles_ok.highlightstyle.iconstyle.icon.href = 'http://maps.google.com/mapfiles/kml/shapes/placemark_square.png'
    styles_ok.highlightstyle.iconstyle.color = 'ff00ff00'
    styles_ok.highlightstyle.labelstyle.scale = 2

    styles_nok = simplekml.StyleMap()
    styles_nok.normalstyle.iconstyle.icon.href = 'http://maps.google.com/mapfiles/kml/shapes/placemark_square.png'
    styles_nok.normalstyle.iconstyle.color = 'ff0000ff'
    styles_nok.normalstyle.labelstyle.scale = 0

    styles_nok.highlightstyle.iconstyle.icon.href = 'http://maps.google.com/mapfiles/kml/shapes/placemark_square.png'
    styles_nok.highlightstyle.iconstyle.color = 'ff0000ff'
    styles_nok.highlightstyle.labelstyle.scale = 2

    for stn in tqdm(rs, ncols=80):

        count = cnn.query_float('SELECT count(*) as cc FROM rinex_proc WHERE "NetworkCode" = \'%s\' '
                                'AND "StationCode" = \'%s\''
                                % (stn['NetworkCode'], stn['StationCode']))

        ppp_s = cnn.query_float('SELECT count(*) as cc FROM ppp_soln WHERE "NetworkCode" = \'%s\' '
                                'AND "StationCode" = \'%s\''
                                % (stn['NetworkCode'], stn['StationCode']))

        stninfo = pyStationInfo.StationInfo(cnn, stn['NetworkCode'], stn['StationCode'], allow_empty=True)

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

        if stn['NetworkCode'] + '.' + stn['StationCode'] in stnlist:
            folder = folder1
            # mark the stations with less than 100 observations or with less than 60% completion (PPP)
            if count[0][0] >= 100 and (float(ppp_s[0][0]) / float(count[0][0]) * 100) >= 60.0:
                style = styles_ok
            else:
                style = styles_nok
        else:
            folder = folder2
            style = stylec

        plt = plot_station_info_rinex(cnn, stn['NetworkCode'], stn['StationCode'], stninfo)

        pt = folder.newpoint(name=stn['NetworkCode'] + '.' + stn['StationCode'], coords=[(stn['lon'], stn['lat'])])
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
</tr>
</td>
</table>""" % (DS, DE, count[0][0], completion, stninfo.return_stninfo_short().replace('\n', '<br>'), plt)

    if not os.path.exists('production'):
        os.makedirs('production')

    kml.savekmz('production/' + project + '.kmz')


def plot_station_info_rinex(cnn, NetworkCode, StationCode, stninfo):

    cats = {"rinex": 1, "stninfo": 2}
    colormapping = {"rinex": "C0", "stninfo": "C1"}

    data = []

    if stninfo.records is not None:
        for record in stninfo.records:
            if record['DateEnd'].year is not None:
                data.append((record['DateStart'].datetime(), record['DateEnd'].datetime(), 'stninfo'))
            else:
                data.append((record['DateStart'].datetime(), dt.datetime.now(), 'stninfo'))

    rinex = cnn.query_float('SELECT * FROM rinex_proc WHERE "NetworkCode" = \'%s\' '
                            'AND "StationCode" = \'%s\'' % (NetworkCode, StationCode), as_dict=True)

    for r in rinex:
        data.append((r['ObservationSTime'], r['ObservationETime'], 'rinex'))

    verts = []
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

    #plt.savefig(figfile, format='png')
    plt.show()
    #figfile.seek(0)  # rewind to beginning of file

    #figdata_png = base64.b64encode(figfile.getvalue())

    #plt.close()

    #return figdata_png


if __name__ == '__main__':
    main()