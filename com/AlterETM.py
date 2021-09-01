#!/usr/bin/env python

import argparse
import copy

# deps
import pg

# app
import dbConnection
import Utils
from Utils import required_length
from pyBunch import Bunch

from pyETM import (DEFAULT_FREQUENCIES,
                   DEFAULT_POL_TERMS,
                   DEFAULT_RELAXATION)


def main():

    parser = argparse.ArgumentParser(description='Program to alter the default ETM parameters for each station. '
                                                 'The command can be executed on several stations at the same time. '
                                                 'It is also possible to alter parameters for PPP and GAMIT '
                                                 'simultaneously.')

    parser.add_argument('stnlist', type=str, nargs='+', metavar='all|net.stnm',
                        help="List of networks/stations to process given in [net].[stnm] format or just [stnm] "
                             "(separated by spaces; if [stnm] is not unique in the database, all stations with that "
                             "name will be processed). Use keyword 'all' to process all stations in the database. "
                             "If [net].all is given, all stations from network [net] will be processed. "
                             "Alternatively, a file with the station list can be provided.")

    parser.add_argument('-fun', '--function_type', nargs='+', metavar=('function', 'argument'), default=[],
                        help="Specifies the type of function to work with. Can be polynomial (p), jump (j), or "
                             "periodic (q). Each one accepts a list of arguments. "
                             "p {terms} where terms equals the number of polynomial terms in the ETM, i.e. "
                             "terms = 2 is constant velocity and terms = 3 is velocity + acceleration, etc.\n"
                             "j {action} {type} {date} {relax} where action can be + or -. A + indicates that a jump "
                             "should be added while a - means that an existing jump should be removed; "
                             "type = 0 is a mechanic jump and 1 is a geophysical jump; "
                             "date is the date of the event in all the accepted formats "
                             "(yyyy/mm/dd yyyy_doy gpswk-wkday fyear); and relax is a list of relaxation times for the "
                             "logarithmic decays (only used when type = 1, they are ignored when type = 0).\n"
                             "q {periods} where periods is a list expressed in days (1 yr = 365.25)")

    parser.add_argument('-soln', '--solution_type', nargs='+', choices=['ppp', 'gamit'],
                        default=['ppp', 'gamit'], action=required_length(1, 2),
                        help="Specifies the type of solution that this command will affect. If left empty, the ETMs "
                             "for both PPP and GAMIT will be affected. Otherwise, specify gamit to insert or "
                             "remove the function on GAMIT ETMs only or ppp to insert or remove the function on PPP "
                             "ETMs only.")

    parser.add_argument('-print', '--print_params', action='store_true',
                        help="Print the parameters present in the database for the selected stations.")

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
                print(' %s.%s %-5s %-5s %2i' \
                      % (station['NetworkCode'], station['StationCode'], p['soln'], p['object'], p['terms']))


def insert_modify_param(parser, cnn, stnlist, args):

    # determine if passed function is valid
    if len(args.function_type) < 2:
        parser.error('invalid number of arguments')

    elif args.function_type[0] not in ('p', 'j', 'q'):
        parser.error('function type should be one of the following: polynomial (p), jump (j), or periodic (q)')

    # create a bunch object to save all the params that will enter the database
    tpar = Bunch()
    tpar.NetworkCode = None
    tpar.StationCode = None
    tpar.soln        = None
    tpar.object      = None
    tpar.terms       = None
    tpar.frequencies = None
    tpar.jump_type   = None
    tpar.relaxation  = None
    tpar.Year        = None
    tpar.DOY         = None
    tpar.action      = None

    ftype = args.function_type[0]

    try:
        if ftype == 'p':
            tpar.object = 'polynomial'
            tpar.terms  = int(args.function_type[1])

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

            if tpar.jump_type not in (0, 1):
                parser.error('jump type should be either 0 or 1')

            try:
                date, _ = Utils.process_date([args.function_type[3]])

                # recover the year and doy
                tpar.Year = date.year
                tpar.DOY  = date.doy

            except Exception as e:
                parser.error('while parsing jump date: ' + str(e))


            if tpar.jump_type == 1:
                tpar.relaxation = [float(f) for f in args.function_type[4:]]

                if not tpar.relaxation:
                    if tpar.action == '-':
                        tpar.relaxation = None
                    elif tpar.action == '+':
                        parser.error('jump type == 1 but no relaxation parameter, please specify relaxation')

        elif ftype == 'q':
            tpar.object      = 'periodic'
            tpar.frequencies = [float(1/float(p)) for p in args.function_type[1:]]

    except ValueError:
        parser.error('invalid argument type for function "%s"' % ftype)


    for station in stnlist:
        for soln in args.solution_type:
            tpar.NetworkCode = station['NetworkCode']
            tpar.StationCode = station['StationCode']
            tpar.soln        = soln

            ppar = copy.deepcopy(dict(tpar))
            ppar = {k : v
                    for k, v in ppar.items()
                    if v not in (None, []) and k not in ('action', 'relaxation', 'jump_type',
                                                         'terms', 'frequencies')}

            station_soln = "%s.%s (%s)" % (station['NetworkCode'], station['StationCode'], soln)
            # check if solution exists for this station
            try:
                epar = cnn.get('etm_params', ppar, list(ppar.keys()))
                
                print(' >> Found a set of matching parameters for station ' + station_soln)

                print(' -- Deleting ' + station_soln)

                cnn.delete('etm_params', epar)

            except pg.DatabaseError:
                print(' >> No set of parameters found for station ' + station_soln)

            cnn.insert('etm_params', tpar)
            # insert replaces the uid field
            del tpar.uid

            print(' -- Inserting %s for %s' % (tpar.object, station_soln))


if __name__ == '__main__':
    main()

