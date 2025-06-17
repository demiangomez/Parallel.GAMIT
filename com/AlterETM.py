#!/usr/bin/env python

# deps
import argparse
import copy

# app
from pgamit import dbConnection
from pgamit import Utils
from pgamit.Utils import required_length, process_date, station_list_help, add_version_argument
from pgamit.pyBunch import Bunch
from pgamit import pyETM

from pgamit.pyETM import (DEFAULT_FREQUENCIES,
                          DEFAULT_POL_TERMS,
                          DEFAULT_RELAXATION)


class SmartFormatter(argparse.HelpFormatter):

    def _split_lines(self, text, width):
        if text.startswith('R|'):
            return text[2:].splitlines()
        # this is the RawTextHelpFormatter._split_lines
        return argparse.HelpFormatter._split_lines(self, text, width)


def main():

    parser = argparse.ArgumentParser(description='Program to alter the default ETM parameters for each station. '
                                                 'The command can be executed on several stations at the same time. '
                                                 'It is also possible to alter parameters for PPP and GAMIT '
                                                 'simultaneously.', formatter_class=SmartFormatter)

    parser.add_argument('stnlist', type=str, nargs='+', metavar='all|net.stnm',
                        help=station_list_help())

    parser.add_argument('-fun', '--function_type', nargs='+', metavar=('function', 'argument'), default=[],
                        help="R|Specifies the type of function to work with. Can be polynomial (p), jump (j), "
                             "periodic (q) or bulk earthquake jump removal (t). Each one accepts a list of arguments.\n"
                             "p {terms} where terms equals the number of polynomial terms in the ETM, i.e. "
                             "terms = 2 is constant velocity and terms = 3 is velocity + acceleration, etc.\n"
                             "j {action} {type} {date} {relax} where action can be + or -. A + indicates that a jump "
                             "should be added while a - means that an existing jump should be removed; "
                             "type = 0 is a mechanic jump, 1 is a geophysical jump, and 2 is a decay-only "
                             "discontinuity; date is the date of the event in all the accepted formats "
                             "(yyyy/mm/dd yyyy_doy gpswk-wkday fyear); and relax is a list of relaxation times for the "
                             "logarithmic decays (only used when type = 1, they are ignored when type = 0).\n"
                             "q {periods} where periods is a list expressed in days (1 yr = 365.25).\n"
                             "t {max_magnitude} {stack_name} removes any earthquake Mw <= max_magnitude from "
                             "the specified stations' trajectory models; if GAMIT solutions are invoked, provide the "
                             "stack_name to obtain the ETMs of the stations.\n"
                             "m {stack_name} [start_date] [end_date|days] removes mechanical jumps between given dates "
                             "from the specified stations' trajectory models; if no dates are provided, remove all "
                             "mechanical jumps. If only first date is provided, remove starting at that date until "
                             "today. Can also specify {start_date} {days} to add to {start_date}. "
                             "Provide the stack_name to obtain the ETMs of the stations. "
                             "If PPP solutions only (-soln ppp), stack_name is ignored. If both solutions are "
                             "indicated (or -soln is not specified) then stack_name must be provided.")

    parser.add_argument('-soln', '--solution_type', nargs='+', choices=['ppp', 'gamit'],
                        default=['ppp', 'gamit'], action=required_length(1, 2),
                        help="Specifies the type of solution that this command will affect. If left empty, the ETMs "
                             "for both PPP and GAMIT will be affected. Otherwise, specify gamit to insert or "
                             "remove the function on GAMIT ETMs only or ppp to insert or remove the function on PPP "
                             "ETMs only.")

    parser.add_argument('-print', '--print_params', action='store_true',
                        help="Print the parameters present in the database for the selected stations.")

    add_version_argument(parser)

    args = parser.parse_args()

    cnn = dbConnection.Cnn("gnss_data.cfg")
    # get the station list
    stnlist = Utils.process_stnlist(cnn, args.stnlist)

    if args.print_params:
        print_params(cnn, stnlist)
    else:
        insert_modify_param(parser, cnn, stnlist, args)


def print_params(cnn, stnlist):

    for station in stnlist:
        params = cnn.query_float('SELECT * FROM etm_params WHERE "NetworkCode" = \'%s\' AND "StationCode" = \'%s\''
                                 % (station['NetworkCode'], station['StationCode']), as_dict=True)

        for p in params:
            print(' %s.%s %-5s %-5s %2i' % (station['NetworkCode'], station['StationCode'],
                                            p['soln'], p['object'], p['terms']))


def insert_modify_param(parser, cnn, stnlist, args):

    # determine if passed function is valid
    if len(args.function_type) < 2:
        parser.error('invalid number of arguments')

    elif args.function_type[0] not in ('p', 'j', 'q', 't', 'm'):
        parser.error('function type should be one of the following: polynomial (p), jump (j), periodic (q), '
                     'bulk geophysical jump removal (t), bulk mechanical jump removal (m).')

    # create a bunch object to save all the params that will enter the database
    tpar = Bunch()
    tpar.NetworkCode = tpar.StationCode = tpar.soln = tpar.object = tpar.terms = tpar.frequencies = None
    tpar.jump_type = tpar.relaxation = tpar.Year = tpar.DOY = tpar.action = None

    ftype = args.function_type[0]
    remove_eq = remove_mec = False

    try:
        if ftype == 'p':
            tpar.object = 'polynomial'
            tpar.terms = int(args.function_type[1])

            if tpar.terms <= 0:
                parser.error('polynomial terms should be > 0')

        elif ftype == 'j':
            tpar.object = 'jump'
            # insert the action
            tpar.action = args.function_type[1]

            if tpar.action not in ('+', '-'):
                parser.error('action for function type jump (j) should be + or -')

            # jump type
            tpar.jump_type = int(args.function_type[2])

            if tpar.jump_type not in (0, 1, 2):
                parser.error('jump type should be either 0, 1, or 2')

            try:
                date, _ = Utils.process_date([args.function_type[3]])

                # recover the year and doy
                tpar.Year, tpar.DOY = date.year, date.doy

            except Exception as e:
                parser.error('while parsing jump date: ' + str(e))

            if tpar.jump_type >= 1 :
                tpar.relaxation = [float(f) for f in args.function_type[4:]]

                if not tpar.relaxation:
                    if tpar.action == '-':
                        tpar.relaxation = None
                    elif tpar.action == '+':
                        parser.error('jump type == 1 but no relaxation parameter, please specify relaxation')

        elif ftype == 'q':
            tpar.object = 'periodic'
            tpar.frequencies = [float(1/float(p)) for p in args.function_type[1:]]

        elif ftype == 't':
            tpar.object = 'jump'
            remove_eq = True
        elif ftype == 'm':
            tpar.object = 'jump'
            remove_mec = True

    except ValueError:
        parser.error('invalid argument type for function "%s"' % ftype)

    for station in stnlist:
        for soln in args.solution_type:
            tpar.NetworkCode = station['NetworkCode']
            tpar.StationCode = station['StationCode']
            tpar.soln = soln

            station_soln = "%s.%s (%s)" % (station['NetworkCode'], station['StationCode'], soln)

            if remove_eq:
                # load the ETM parameters for this station
                print(' >> Obtaining ETM parameters for  ' + station_soln)

                if soln == 'ppp':
                    etm = pyETM.PPPETM(cnn, station['NetworkCode'], station['StationCode'])
                else:
                    etm = pyETM.GamitETM(cnn, station['NetworkCode'], station['StationCode'],
                                         stack_name=args.function_type[2])

                for eq in [e for e in etm.Jumps.table
                           if e.p.jump_type in (pyETM.CO_SEISMIC_DECAY, pyETM.CO_SEISMIC_JUMP_DECAY,
                                                pyETM.CO_SEISMIC_JUMP)]:
                    if eq.magnitude <= float(args.function_type[1]):
                        # this earthquake should be removed, fill in the data
                        tpar.Year, tpar.DOY = eq.date.year, eq.date.doy
                        tpar.jump_type = 1
                        tpar.relaxation = None
                        tpar.action = '-'
                        apply_change(cnn, station, tpar, soln)

            elif remove_mec:
                # load the ETM parameters for this station
                print(' >> Obtaining ETM parameters for  ' + station_soln)

                if soln == 'ppp':
                    etm = pyETM.PPPETM(cnn, station['NetworkCode'], station['StationCode'])
                else:
                    etm = pyETM.GamitETM(cnn, station['NetworkCode'], station['StationCode'],
                                         stack_name=args.function_type[1])

                for jump in [e for e in etm.Jumps.table
                             if e.p.jump_type in (pyETM.ANTENNA_CHANGE, pyETM.GENERIC_JUMP)]:

                    # process the dates. If no date, returns from 1980 until now
                    sdate = process_date(args.function_type[2:])

                    if sdate[0] <= jump.date <= sdate[1]:
                        # this jump should be removed, fill in the data
                        tpar.Year, tpar.DOY = jump.date.year, jump.date.doy
                        tpar.jump_type = 0
                        tpar.relaxation = None
                        tpar.action = '-'
                        apply_change(cnn, station, tpar, soln)

            else:
                apply_change(cnn, station, tpar, soln)


def apply_change(cnn, station, tpar, soln):
    ppar = copy.deepcopy(dict(tpar))
    ppar = {k: v
            for k, v in ppar.items()
            if v not in (None, []) and k not in ('action', 'relaxation', 'jump_type',
                                                 'terms', 'frequencies')}

    station_soln = "%s.%s (%s)" % (station['NetworkCode'], station['StationCode'], soln)
    # check if solution exists for this station
    try:
        epar = cnn.get('etm_params', ppar, list(ppar.keys()))
        print(' >> Found a set of matching parameters for station ' + station_soln)
        print(' -- Deleting ' + station_soln)
        cnn.delete('etm_params', **epar)

    except Exception:
        print(' >> No set of parameters found for station ' + station_soln)

    cnn.insert('etm_params', **tpar)
    # insert replaces the uid field
    # del tpar.uid
    print(' -- Inserting %s for %s' % (tpar.object, station_soln))


if __name__ == '__main__':
    main()
