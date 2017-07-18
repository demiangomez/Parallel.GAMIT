"""
Project:
Date: 6/5/17 9:40 AM
Author: Demian D. Gomez
"""
import dbConnection
import pyOptions
import pp
import Utils
import time
import traceback
import datetime
from tqdm import tqdm

class callback_class():
    def __init__(self, pbar):
        self.errors = None
        self.pbar = pbar

    def callbackfunc(self, args):
        msg = args
        self.errors = msg
        self.pbar.update(1)

def speed_test():

    try:
        cnn = dbConnection.Cnn("gnss_data.cfg") # type: dbConnection.Cnn

        rs = cnn.query('SELECT count(*) as "cuenta" FROM rinex')

        rnx = rs.dictresult()[0]

        return str(rnx['cuenta'])

    except:

        return traceback.format_exc()

def output_handle(callback):

    messages = [outmsg.errors for outmsg in callback]

    # function to print any error that are encountered during parallel execution
    for msg in messages:
        if msg:
            f = open('errors_speed_test.log','a')
            f.write('ON ' + datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') + ' an unhandled error occurred:\n')
            f.write(msg + '\n')
            f.write('END OF ERROR =================== \n\n')
            f.close()

    return []

def main():
    Config = pyOptions.ReadOptions('gnss_data.cfg')  # type: pyOptions.ReadOptions

    cnn = dbConnection.Cnn("gnss_data.cfg")  # type: dbConnection.Cnn

    rs = cnn.query('SELECT count(*) as "cuenta" FROM rinex')

    rnx = rs.dictresult()[0]

    print rnx['cuenta']

    if Config.run_parallel:
        # ppservers = ('192.168.0.232', '192.168.0.240', '192.168.0.244', '192.168.0.237', '192.168.0.231', '192.168.0.241', '192.168.0.242')
        ppservers = ('*',)
        job_server = pp.Server(ncpus=Utils.get_processor_count(), ppservers=ppservers)
        time.sleep(1)
        print "Starting pp with", job_server.get_active_nodes(), "workers"
    else:
        job_server = None

    pbar = tqdm(total=100, ncols=80)
    callback = []
    submit = 0
    for i in range(100):
        callback.append(callback_class(pbar))
        job_server.submit(speed_test,
                          modules=('dbConnection','traceback'),
                          callback=callback[submit].callbackfunc)

        submit += 1

        if submit > 64:
            # when we submit more than 300 jobs, wait until this batch is complete
            job_server.wait()
            # handle any output messages during this batch
            callback = output_handle(callback)
            submit = 0

    if Config.run_parallel:
        job_server.wait()

    # handle any output messages during this batch
    output_handle(callback)
    pbar.close()

    if Config.run_parallel:
        print "\n"
        job_server.print_stats()

if __name__ == '__main__':
    main()