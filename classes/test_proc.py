
import threading
import subprocess
import pyRinex
import pyArchiveStruct
import dbConnection
import pyStationInfo
import pyDate
import datetime
import pyRunWithRetry
import pySp3
import pyBrdc
import pyEOP
import pyPPP
import pyParseAntex
import pyEarthquakes
import pyPPPETM_full_cov
import pyPPPETM
import pyOptions
import atexit
import os

class run_command(threading.Thread):
    def __init__(self,command):
        self.stdout = None
        self.stderr = None
        self.cmd = command
        threading.Thread.__init__(self)

    def run(self):
        self.p = subprocess.Popen(self.cmd.split(),
                             shell=False,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)

        self.stdout, self.stderr = self.p.communicate()

    def wait(self, timeout=None):

        self.join(timeout=timeout)
        if self.is_alive():
            try:
                self.p.kill()
            except:
                # the process was done
                return False
            return True

def insert_stninfo_ign(cnn):

    stnInfo = pyStationInfo.StationInfo(cnn)

    stninfo = stnInfo.parse_station_info('/Volumes/home/ign/stationinfo/cord.station.info')

    # insert all the receivers and antennas in the db

    for stn in stninfo:
        try:
            cnn.insert('receivers', ReceiverCode=stn.get('ReceiverType'))
        except dbConnection.dbErrInsert:
            pass
        try:
            cnn.insert('antennas', AntennaCode=stn.get('AntennaType'))
        except dbConnection.dbErrInsert:
            pass

    # ready to insert stuff to station info table
    for stn in stninfo:
        sdate1 = stn.get('SessionStart').split()
        if int(sdate1[2]) > 23:
            sdate1[2] = '23'; sdate1[3] = '59'; sdate1[4] = '59'
        date_start = pyDate.Date(year=sdate1[0], doy=sdate1[1])
        date_start = datetime.datetime(int(date_start.year),date_start.month,date_start.day,int(sdate1[2]),int(sdate1[3]),int(sdate1[4]))
        date_start = date_start.strftime('%Y/%m/%d %H:%M:%S')

        sdate2 = stn.get('SessionStop').split()
        if sdate2[0] == '9999':
            date_end = []
        else:
            date_end = pyDate.Date(year=sdate2[0], doy=sdate2[1])
            if int(sdate2[2]) > 23:
                sdate2[2] = '23'; sdate2[3] = '59'; sdate2[4] = '59'
            date_end = datetime.datetime(int(date_end.year),date_end.month,date_end.day,int(sdate2[2]),int(sdate2[3]),int(sdate2[4]))
            date_end = date_end.strftime('%Y/%m/%d %H:%M:%S')

        try:
            cnn.insert('stationinfo',
                       NetworkCode='rnx',
                       StationCode=stn.get('StationCode').lower(),
                       ReceiverCode=stn.get('ReceiverType'),
                       ReceiverSerial=stn.get('ReceiverSN'),
                       ReceiverFirmware=stn.get('SwVer'),
                       AntennaCode=stn.get('AntennaType'),
                       AntennaSerial=stn.get('AntennaSN'),
                       AntennaHeight=stn.get('AntHt'),
                       AntennaNorth=stn.get('AntN'),
                       AntennaEast=stn.get('AntE'),
                       HeightCode=stn.get('HtCod'),
                       RadomeCode=stn.get('Dome'),
                       ReceiverVers=stn.get('Vers'),
                       DateStart=date_start,
                       DateEnd=date_end)
        except dbConnection.dbErrInsert as e:
            print str(e)
            continue

def process_prueba(i):
    return 'hola ' + str(i)

def imprimir_resultado(inp):

    print inp

def kill_ppp():
    os.system('kill -9 ppp34613')

def main():
    #myclass = run_command('crx2rnx -f azul2490.08d')
    #myclass = run_command('crx2rnx')
    #myclass.start()
    #timeout = myclass.wait(2)

    #if timeout:
    #    print "timeout expired"
    #else:
    #    print "process finished"
    Config = pyOptions.ReadOptions('gnss_data.cfg') # type: pyOptions.ReadOptions

    cnn = dbConnection.Cnn('gnss_data.cfg')

    #atx = pyParseAntex.ParseAntexFile('igs08.atx')

    #stninfo2 = pyStationInfo.StationInfo(cnn, 'rnx', 'igm1', pyDate.Date(year=2017, doy=40))
    #stninfo3 = pyStationInfo.StationInfo(cnn, 'rnx', 'igm1')

    #pyEarthquakes.AddEarthquakes(cnn)
    #etm = pyPPPETM.ETM(cnn,'arg','ecgm',plotit=True)

    #x, s = etm.get_xyz_s(2003,180)
    #insert_stninfo_ign(cnn)


    #rs = cnn.query('select * from stations where "StationCode" = \'lhcl\'')
    #igm1 = rs.dictresult()


    rs = cnn.query('SELECT * FROM stations WHERE "NetworkCode" NOT LIKE \'?%%\' ORDER BY "NetworkCode", "StationCode"')

    stns = rs.dictresult()

    for stn in stns:
        try:
            etm = pyPPPETM.ETM(cnn,stn['NetworkCode'],stn['StationCode'], False)
            etm.plot('production/' + etm.NetworkCode + '.' + etm.StationCode + '.png')
        except IndexError:
            pass

    return

    etm.get_xyz_s(2010, 7)

    date = pyDate.Date(year=2016, doy=190)

    rinexinfo = pyRinex.ReadRinex('rms', 'mgva', 'mgva2570.12d.Z')  # type: pyRinex.ReadRinex
    brdc = pyBrdc.GetBrdcOrbits(Config.brdc_path, pyDate.Date(year=2012, doy=257), rinexinfo.rootdir)

    _, x = rinexinfo.auto_coord(brdc)

    stninfo1 = pyStationInfo.StationInfo(cnn, 'rms', 'rufi', date)
    #rinexinfo.normalize_header(stninfo1,x=igm1[0].get('auto_x'),y=igm1[0].get('auto_y'),z=igm1[0].get('auto_z'))

    options = pyOptions.ReadOptions('gnss_data.cfg')

    #ppp = pyPPP.RunPPP(rinexinfo,'',options.options,options.sp3types,0,False)

    #try:
    #    ppp.exec_ppp()
    #except pyPPP.pyRunPPPException as e:
    #    print str(e)
    #except Exception as e:
    #    print str(e)

    try:
        rinexinfo.normalize_header(stninfo1, brdc=None, x=1, y=2, z=3)
        with pyPPP.RunPPP(rinexinfo,'',options.options,options.sp3types, options.sp3altrn,0,False,False) as ppp:


            ppp.exec_ppp()
    except pyPPP.pyRunPPPException as e:
            cnn.insert_warning(str(e))
    except Exception as e:
            cnn.insert_warning(str(e))

    print ppp.x
    #insert_stninfo_ign(cnn)

    print "out"
    #archive = pyArchiveStruct.RinexStruct(cnn)
    #file = archive.build_rinex_path('rnx','vbca',2006,98)
    #rinexinfo = pyRinex.ReadRinex('rnx', 'ucor', '/Volumes/home/ign/rnx/2004/091/ucor0910.04d.Z')
    #xyz = rinexinfo.auto_coords

    #rnx = pyRinex.ReadRinex('rnx','mgue','/Volumes/home/ign/rnx/2013/')
    cnn.close()


if __name__ == '__main__':
    main()