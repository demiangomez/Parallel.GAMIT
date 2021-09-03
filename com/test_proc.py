#!/usr/bin/env python

import os

# deps
from tqdm import tqdm

# app
import dbConnection
import pyJobServer
import pyOptions
import pyArchiveStruct
import pyRinex


class callback_class():
    # class to handle the output of the parallel processing
    def __init__(self, pbar):
        self.msg = None
        self.stns = None
        self.pbar = pbar

    def callbackfunc(self, args):
        self.msg = args
        self.pbar.update(1)


def check_rinex(NetworkCode, StationCode, path, filename):

    f = os.path.join(path, filename)

    with pyRinex.ReadRinex(NetworkCode, StationCode, f, allow_multiday=True) as r:

        if 'P2' not in r.observables:
            return '%s.%s %s has not P2 -> available observables are %s' % (NetworkCode, StationCode, r.date.yyyyddd()
                                                                            , ' '.join(r.observables))
        else:
            return ''


def output_handle(callback):

    for c in callback:
        if c.msg != '':
            tqdm.write(c.msg)

    return []


def main():

    Config = pyOptions.ReadOptions('gnss_data.cfg')
    JobServer = pyJobServer.JobServer(Config)  # type: pyJobServer.JobServer

    cnn = dbConnection.Cnn('gnss_data.cfg')

    archive = pyArchiveStruct.RinexStruct(cnn)

    rinex = cnn.query_float('SELECT * FROM rinex WHERE "ObservationYear" <= 1995 ORDER BY "NetworkCode", '
                            '"StationCode", "ObservationYear", "ObservationDOY"', as_dict=True)

    pbar = tqdm(desc='%-30s' % ' >> Processing rinex files', total=len(rinex), ncols=160)

    modules = ('os', 'pyRinex')
    callback = []

    for rnx in rinex:

        filename = archive.build_rinex_path(rnx['NetworkCode'],
                                            rnx['StationCode'],
                                            rnx['ObservationYear'],
                                            rnx['ObservationDOY'],
                                            filename=rnx['Filename'])

        arguments = (rnx['NetworkCode'], rnx['StationCode'], Config.archive_path, filename)

        JobServer.SubmitJob(check_rinex, arguments, (), modules, callback,
                            callback_class(pbar), 'callbackfunc')

        if JobServer.process_callback:
            # handle any output messages during this batch
            callback = output_handle(callback)
            JobServer.process_callback = False

    tqdm.write(' >> waiting for jobs to finish...')
    JobServer.job_server.wait()
    tqdm.write(' >> Done.')

    # process the errors and the new stations
    output_handle(callback)

    pbar.close()


if __name__ == '__main__':
    main()

