#!/usr/bin/env python
"""
Project: Parallel.GAMIT
Date: 7/18/18 10:28 AM
Author: Demian D. Gomez

Program to generate a KML with the stations in a project
and the stations out of a project
"""

import argparse
import base64
import datetime
import io
import os

# deps
import matplotlib

if not os.environ.get('DISPLAY', None):
    matplotlib.use('Agg')

import numpy
import simplekml
from tqdm import tqdm

# app
from pgamit import dbConnection, pyDate, pyJobServer, pyOptions, pyStationInfo
from pgamit.pyGamitConfig import GamitConfiguration
from pgamit.Utils import process_stnlist, stationID, plot_rinex_completion, add_version_argument

global kml, folder_project, folder_allstns, stnlist


def main():

    global stnlist

    parser = argparse.ArgumentParser(
        description='Generate KML file to inspect archive in Google Earth')

    parser.add_argument('project_file', type=str, nargs=1,
                        metavar='{project cfg file}',
                        help='''Project CFG file with all the stations
                             being processed in Parallel.GAMIT''')

    parser.add_argument('-stn', '--station_list', type=str, nargs='+',
                        metavar='[net.stnm]', default=[],
                        help='''List of stations to produce KML.
                             Default returns all stations. Network and station
                             codes allow using wildcards.''')

    parser.add_argument('-stninfo', '--station_info', action='store_true',
                        help='''Run integrity checks on station information
                             and output results to kmz file.
                             The icons of the stations will represent
                             any problems in the station info records.''')

    parser.add_argument('-data', '--available_data', action='store_true',
                        default=False,
                        help='Produce detailed plots with available data.')

    parser.add_argument('-kmz', '--kmz_filename', type=str, nargs=1,
                        metavar='{filename}.kmz',
                        help='''Path and filename for the kmz file (do not
                             append the extension). Default uses
                             production/{project_name} where {project_name}
                             is the project name declared in the
                             PG cfg file.''')

    parser.add_argument('-np', '--noparallel', action='store_true',
                        help="Execute command without parallelization.")

    add_version_argument(parser)

    args = parser.parse_args()

    cnn = dbConnection.Cnn("gnss_data.cfg")

    config = pyOptions.ReadOptions('gnss_data.cfg')

    # type: GamitConfiguration
    GamitConfig = GamitConfiguration(args.project_file[0],
                                     check_config=False)

    # global variable that contains the station list in the project
    stnlist = [stationID(s) for s in process_stnlist(
        cnn, GamitConfig.NetworkConfig['stn_list'].split(','),
        summary_title='Station in %s:' % args.project_file[0])]
    stnonly = [stationID(s) for s in process_stnlist(
        cnn, args.station_list,
        summary_title='Stations requested:')]

    # if the stnonly is empty, print all to tell the user
    # that they will get all the station list
    if not stnonly:
        print('    all')

    JobServer = pyJobServer.JobServer(config, check_archive=False,
                                      check_executables=False,
                                      check_atx=False,
                                      run_parallel=not args.noparallel)

    netid = GamitConfig.NetworkConfig.network_id.lower()

    if args.kmz_filename is not None:
        kmz_filename = args.kmz_filename[0]
    else:
        kmz_filename = os.path.join('production', netid)

    generate_kml_stninfo(JobServer, cnn, netid, args.available_data,
                         args.station_info, stnonly, kmz_filename)


def description_content(stn, DateS, DateE, count, completion, stn_issues,
                        stninfo, stninfo_records, data, style):

    cnn = dbConnection.Cnn("gnss_data.cfg")

    if data:
        data_plt = """
            <p style="font-family: monospace; font-size: 8pt;"><br><br>
            <strong>Observation distribution:</strong><br>
            </p>
            <img src="data:image/png;base64, %s" alt="Available data" />
                        """ % plot_rinex_completion(cnn, stn['NetworkCode'], stn['StationCode'])
    else:
        data_plt = ""

    description = """<strong>%s -> %s</strong>
    RINEX count: %i PPP soln: %s%%<br><br>
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
    </table>""" % (DateS, DateE, count, completion,
                   '<br>'.join(stn_issues) if stn_issues else (
                       'NO ISSUES FOUND OR NOT REQUESTED'), stninfo,
                   plot_station_info_rinex(cnn,
                                           stn['NetworkCode'],
                                           stn['StationCode'],
                                           stninfo_records), data_plt)

    return stn, style, description


def callback_handle(job):
    # callback to add the station to the kml
    global kml, folder_project, folder_allstns, stnlist

    if job.result is not None:
        stn = job.result[0]
        style = job.result[1]
        description = job.result[2]

        if stationID(stn) in stnlist:
            folder = folder_project
        else:
            folder = folder_allstns

        pt = folder.newpoint(name=stationID(stn),
                             coords=[(stn['lon'], stn['lat'])])
        pt.stylemap = style
        pt.description = description


def generate_kml_stninfo(JobServer, cnn, project, data=False,
                         run_stninfo_check=True,
                         stnonly=(), kmz_filename='PG.kmz'):

    tqdm.write('  >> Generating KML for this run (see production directory).')

    global kml, folder_project, folder_allstns, stnlist
    kml = simplekml.Kml()

    if stnonly:
        rs = cnn.query_float('SELECT * FROM stations WHERE "NetworkCode" NOT LIKE \'?%%\' AND '
                             '"NetworkCode" || \'.\' || "StationCode" IN (\'%s\')'
                             'ORDER BY "NetworkCode", "StationCode" ' % '\',\''.join(stnonly), as_dict=True)
    else:
        rs = cnn.query_float('''SELECT * FROM stations
                             WHERE "NetworkCode" NOT LIKE \'?%\'
                             ORDER BY "NetworkCode", "StationCode" ''',
                             as_dict=True)

    folder_project = kml.newfolder(name=project)
    folder_allstns = kml.newfolder(name='all stations')

    ICON_SQUARE = (
        'http://maps.google.com/mapfiles/kml/shapes/placemark_square.png')
    ICON_WARN = (
        'http://maps.google.com/mapfiles/kml/shapes/caution.png')
    ICON_CIRCLE = (
        'http://maps.google.com/mapfiles/kml/shapes/placemark_circle.png')

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

    if run_stninfo_check:
        styles_nok = simplekml.StyleMap()
        styles_nok.normalstyle.iconstyle.icon.href = ICON_WARN
        styles_nok.normalstyle.iconstyle.color = 'ff0000ff'
        styles_nok.normalstyle.iconstyle.scale = 1.5
        styles_nok.normalstyle.labelstyle.scale = 0

        styles_nok.highlightstyle.iconstyle.icon.href = ICON_WARN
        styles_nok.highlightstyle.iconstyle.color = 'ff0000ff'
        styles_nok.highlightstyle.iconstyle.scale = 2
        styles_nok.highlightstyle.labelstyle.scale = 2
    else:
        styles_nok = simplekml.StyleMap()
        styles_nok.normalstyle.iconstyle.icon.href = ICON_SQUARE
        styles_nok.normalstyle.iconstyle.color = 'ff0000ff'
        styles_nok.normalstyle.iconstyle.scale = 1.5
        styles_nok.normalstyle.labelstyle.scale = 0

        styles_nok.highlightstyle.iconstyle.icon.href = ICON_SQUARE
        styles_nok.highlightstyle.iconstyle.color = 'ff0000ff'
        styles_nok.highlightstyle.iconstyle.scale = 2
        styles_nok.highlightstyle.labelstyle.scale = 2

    pbar = tqdm(
        desc=' >> Adding stations', total=len(rs), ncols=80, disable=None)

    depfuncs = (plot_station_info_rinex, plot_rinex_completion, stationID)

    JobServer.create_cluster(description_content,
                             depfuncs,
                             callback_handle,
                             pbar,
                             modules=('pgamit.pyDate', 'pgamit.dbConnection',
                                      'datetime', 'numpy', 'io', 'base64'))

    for stn in rs:

        count = cnn.query_float('''SELECT count(*) as cc FROM rinex_proc
                                WHERE "NetworkCode" = \'%s\'
                                AND "StationCode" = \'%s\' '''
                                % (stn['NetworkCode'],
                                   stn['StationCode']))[0][0]

        ppp_s = cnn.query_float('''SELECT count(*) as cc FROM ppp_soln
                                WHERE "NetworkCode" = \'%s\'
                                AND "StationCode" = \'%s\' '''
                                % (stn['NetworkCode'],
                                   stn['StationCode']))[0][0]

        completion = ('%.1f'
                      % (float(ppp_s) / float(count) * 100) if count else 'NA')

        DateS = '%.3f' % stn['DateStart'] if stn['DateStart'] else 'NA'
        DateE = '%.3f' % stn['DateEnd'] if stn['DateStart'] else 'NA'

        try:
            stninfo = pyStationInfo.StationInfo(cnn,
                                                stn['NetworkCode'],
                                                stn['StationCode'],
                                                allow_empty=True)
            _ = stninfo.return_stninfo_short()
        except pyStationInfo.pyStationInfoHeightCodeNotFound as e:
            tqdm.write('Error: %s. Station will be skipped.' % str(e))
            continue

        stninfotxt = stninfo.return_stninfo_short().replace('\n', '<br>')

        if run_stninfo_check:
            # run the station info checks
            gaps = stninfo.station_info_gaps()

            # mark the stations with less than 100 observations
            # or with less than 60% completion (PPP)
            stn_issues = []
            if not gaps and len(stninfo.records) > 0:
                style = styles_ok
            else:
                style = styles_nok

                if len(stninfo.records) == 0:
                    stn_issues.append(
                        'Station has not station information records!')

                for gap in gaps:
                    if gap['record_start'] and gap['record_end']:
                        stn_issues.append('''At least %i RINEX file(s)
                                          outside of station info record
                                          ending at %s and
                                          next record starting at %s'''
                                          % (gap['rinex_count'],
                                             str(gap['record_end']
                                                    ['DateEnd']),
                                             str(gap['record_start']
                                                 ['DateStart'])))

                    elif gap['record_start'] and not gap['record_end']:
                        stn_issues.append('''At least %i RINEX file(s)
                                          outside of station info record
                                          starting at %s '''
                                          % (gap['rinex_count'],
                                             str(gap['record_start']
                                             ['DateStart'])))

                    elif not gap['record_start'] and gap['record_end']:
                        stn_issues.append('''At least %i RINEX file(s)
                                          outside of station info record
                                          ending at %s '''
                                          % (gap['rinex_count'],
                                             str(gap['record_end']
                                                 ['DateEnd'])))
        else:
            # DDG: if no station information check,
            # just mark the stations with red and green
            # mark the stations with less than 100 observations
            # or with less than 60% completion (PPP)
            if stationID(stn) in stnlist:
                if count >= 100 and (float(ppp_s)
                                     / float(count) * 100) >= 60.0:
                    style = styles_ok
                else:
                    style = styles_nok
            else:
                style = stylec

            stn_issues = []

        JobServer.submit(stn, DateS, DateE, count, completion, stn_issues,
                         stninfotxt, stninfo.records, data, style)

    JobServer.wait()

    pbar.close()

    JobServer.close_cluster()

    if os.path.dirname(kmz_filename):
        if not os.path.exists(os.path.dirname(kmz_filename)):
            os.makedirs(os.path.dirname(kmz_filename))

    # remove the extension if supplied
    ext = os.path.splitext(kmz_filename)

    # DDG Jun 17 2025: the wrong version of simplekml was being used, now using latest
    # to fix the issue from simple kml
    # AttributeError: module 'cgi' has no attribute 'escape'
    # see: https://github.com/tjlang/simplekml/issues/38
    # import cgi
    # import html
    # cgi.escape = html.escape
    kml.savekmz(ext[0] + '.kmz')


def generate_kml(cnn, project, data=False):
    global stnlist

    stnlist = [stationID(s) for s in stnlist]

    tqdm.write('  >> Generating KML for this run (see production directory).')

    kml = simplekml.Kml()

    rs = cnn.query_float('''SELECT * FROM stations
                         WHERE "NetworkCode" NOT LIKE \'?%\'
                         ORDER BY "NetworkCode", "StationCode" ''',
                         as_dict=True)

    tqdm.write(' >> Adding stations in database')

    folder1 = kml.newfolder(name=project)
    folder2 = kml.newfolder(name='all stations')

    ICON_CIRCLE = (
        'http://maps.google.com/mapfiles/kml/shapes/placemark_circle.png')
    ICON_SQUARE = (
        'http://maps.google.com/mapfiles/kml/shapes/placemark_square.png')

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

        count = cnn.query_float('''SELECT count(*) as cc FROM rinex_proc
                                WHERE "NetworkCode" = \'%s\'
                                AND "StationCode" = \'%s\' '''
                                % (stn['NetworkCode'], stn['StationCode']))

        ppp_s = cnn.query_float('''SELECT count(*) as cc FROM ppp_soln
                                WHERE "NetworkCode" = \'%s\'
                                AND "StationCode" = \'%s\' '''
                                % (stn['NetworkCode'], stn['StationCode']))

        try:
            stninfo = pyStationInfo.StationInfo(cnn,
                                                stn['NetworkCode'],
                                                stn['StationCode'],
                                                allow_empty=True)
            _ = stninfo.return_stninfo_short()
        except pyStationInfo.pyStationInfoHeightCodeNotFound as e:
            tqdm.write('Error: %s. Station will be skipped.' % str(e))
            continue

        if count[0][0]:
            completion = '%.1f' % (float(ppp_s[0][0])
                                   / float(count[0][0]) * 100)
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
            # mark the stations with less than 100 observations
            #  or with less than 60% completion (PPP)
            if count[0][0] >= 100 and (float(ppp_s[0][0])
                                       / float(count[0][0]) * 100) >= 60.0:
                style = styles_ok
            else:
                style = styles_nok
        else:
            folder = folder2
            style = stylec

        plt = plot_station_info_rinex(cnn, stn['NetworkCode'],
                                      stn['StationCode'], stninfo)

        if data:
            data_plt = """
<p style="font-family: monospace; font-size: 8pt;"><br><br>
<strong>Observation distribution:</strong><br>
</p>
<img src="data:image/png;base64, %s" alt="Available data" />
            """ % plot_rinex_completion(cnn, stn['NetworkCode'], stn['StationCode'])
        else:
            data_plt = ""

        pt = folder.newpoint(name=stn_id, coords=[(stn['lon'], stn['lat'])])
        pt.stylemap = style

        pt.description = """<strong>%s -> %s</strong>
RINEX count: %i PPP soln: %s%%<br><br>
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
</table>""" % (DS, DE, count[0][0], completion,
               stninfo.return_stninfo_short().replace('\n', '<br>'),
               plt, data_plt)

    if not os.path.exists('production'):
        os.makedirs('production')

    # DDG Jun 17 2025: the wrong version of simplekml was being used, now using latest
    # to fix the issue from simple kml
    # AttributeError: module 'cgi' has no attribute 'escape'
    # see: https://github.com/tjlang/simplekml/issues/38
    # import cgi
    # import html
    # cgi.escape = html.escape

    kml.savekmz('production/' + project + '.kmz')


def plot_station_info_rinex(cnn, NetworkCode, StationCode, stninfo_records):

    import matplotlib.pyplot as plt

    stnfo = []

    if stninfo_records is not None:
        for record in stninfo_records:
            stnfo.append([record['DateStart'].fyear,
                          (record['DateEnd'].fyear
                           if record['DateEnd'].year is not None
                           else pyDate.Date(
                               datetime=datetime.datetime.now()).fyear)
                          ])

    rinex = numpy.array(cnn.query_float(
        '''SELECT "ObservationFYear" FROM rinex_proc
        WHERE "NetworkCode" = \'%s\'
        AND "StationCode" = \'%s\'''' % (NetworkCode, StationCode)))

    fig, ax = plt.subplots(figsize=(7, 3))

    ax.grid(True)
    ax.set_title('RINEX and Station Information for %s.%s'
                 % (NetworkCode, StationCode))

    for poly in stnfo:
        ax.plot(poly, [1, 1], 'o-', linewidth=2,
                markersize=4, color='tab:orange')
        # break line to clearly show the stop of a station info
        ax.plot([poly[1], poly[1]],
                [-0.5, 1.5], ':', color='tab:orange')

    ax.plot(rinex, numpy.zeros(rinex.shape[0]), 'o',
            color='tab:blue', markersize=3)
    ax.set_yticks([0, 1])
    ax.set_yticklabels(["rinex", "stninfo"])
    plt.ylim([-.5, 1.5])
    figfile = io.BytesIO()

    try:
        plt.savefig(figfile, format='png')
        # plt.show()
        figfile.seek(0)  # rewind to beginning of file

        figdata_png = base64.b64encode(figfile.getvalue()).decode()
    except Exception:
        # either no rinex or no station info
        figdata_png = ''
    plt.close()

    return figdata_png


if __name__ == '__main__':
    main()
