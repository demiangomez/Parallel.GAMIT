#!/usr/bin/env python
"""
Project: Parallel.GAMIT
Date: 11/8/17 9:24 AM
Author: Demian D. Gomez

Script to download stations Rinex files from external servers for a given date range
to the directory specified in:
   [Config.repository]/data_in
Runs scripts stored in:
   [Config.format_scripts_path]
"""
# py
import os
import argparse
from datetime import datetime
import shutil
import glob
import subprocess
import tempfile
import traceback
import queue
import socket
import time
import errno
from typing import Any, NamedTuple, Dict, Optional, List, Union
# @todo py3.8:
# from typing import Literal
from abc import ABC, abstractmethod
import _thread
import threading
import ftplib

# deps
import numpy as np
from tqdm import tqdm
import paramiko
import requests

# app
import pyOptions
import dbConnection
import Utils
import pyArchiveStruct
import pyRinex
import pyRinexName
import pyStationInfo
import pyJobServer
from pyDate import Date
from Utils import (required_length,
                   process_date,
                   print_columns,
                   stationID,
                   file_try_remove,
                   dir_try_remove)


SERVER_REFRESH_INTERVAL      = 2   # in seconds
SERVER_CONNECTION_TIMEOUT    = 20  # in seconds
SERVER_RECONNECTION_INTERVAL = 3   # in seconds
SERVER_MAX_RECONNECTIONS     = 8

DEBUG = True

CONFIG_FILE = 'gnss_data.cfg'

PBAR_FORMAT = '{l_bar}{bar}| {n_fmt}/{total_fmt} {elapsed}<{remaining} {postfix}'

###############################################################################
# Utils
###############################################################################


def path_replace_tags(filename, date : Date, NetworkCode='', StationCode='', Marker=0, CountryCode='ARG'):
    str_marker = str(Marker).zfill(2)

    # create RinexNameFormat objects to create RINEX 2/3 filenames
    rnx2 = pyRinexName.RinexNameFormat(None, StationCode=StationCode, monument=str_marker[0], receiver=str_marker[1],
                                       country=CountryCode, date=date, version=2)
    rnx3 = pyRinexName.RinexNameFormat(None, StationCode=StationCode, monument=str_marker[0], receiver=str_marker[1],
                                       country=CountryCode, date=date, version=3)

    return (filename.replace('${year}',     str(date.year))
                    .replace('${doy}',      str(date.doy).zfill(3)) 
                    .replace('${day}',      str(date.day).zfill(2)) 
                    .replace('${month}',    str(date.month).zfill(2)) 
                    .replace('${gpsweek}',  str(date.gpsWeek).zfill(4)) 
                    .replace('${gpswkday}', str(date.gpsWeekDay)) 
                    .replace('${year2d}',   str(date.year)[2:]) 
                    .replace('${month2d}',  str(date.month).zfill(2)) 
                    .replace('${STATION}',  StationCode.upper()) 
                    .replace('${station}',  StationCode.lower())
                    .replace('${NETWORK}',  NetworkCode.upper()) 
                    .replace('${network}',  NetworkCode.lower())
                    .replace('${marker}',   str_marker)
                    .replace('${COUNTRY}',  CountryCode.upper())
                    .replace('${country}',  CountryCode.lower())
                    .replace('${RINEX2}',   rnx2.to_rinex_format(pyRinexName.TYPE_CRINEZ, True))
                    .replace('${RINEX3_30}', rnx3.to_rinex_format(pyRinexName.TYPE_CRINEZ, True, '30S'))
                    .replace('${RINEX3_15}', rnx3.to_rinex_format(pyRinexName.TYPE_CRINEZ, True, '15S'))
                    .replace('${RINEX3_10}', rnx3.to_rinex_format(pyRinexName.TYPE_CRINEZ, True, '10S'))
                    .replace('${RINEX3_05}', rnx3.to_rinex_format(pyRinexName.TYPE_CRINEZ, True, '05S'))
                    .replace('${RINEX3_01}', rnx3.to_rinex_format(pyRinexName.TYPE_CRINEZ, True, '01S')))


# The 'fqdn' stored in the db is really fqdn + [:port]
def fqdn_parse(fqdn, default_port=None):
    if ':' in fqdn:
        fqdn, port = fqdn.split(':')
        return fqdn, int(port[1])
    else:
        return fqdn, default_port

###############################################################################
# Model
###############################################################################
class Source(NamedTuple):
    # Server fields:
    server_id       : int
    protocol        : str
    fqdn            : str
    username        : str
    password        : str
    # Source or Server fields:
    path            : str
    format          : Optional[str]

class Station(NamedTuple):
    stationID           : str
    NetworkCode         : str
    StationCode         : str
    Marker              : int
    CountryCode         : str
    sources             : List[Source]
    abspath_station_dir : str  # station download dir

class FileDescriptor(NamedTuple):
    stn_idx  : int 
    src_idx  : int
    date_mjd : int 

class File(NamedTuple):
    # Descriptor:
    stn_idx  : int
    src_idx  : int
    date_mjd : int
    # Derived:
    # (@todo py >= 3.7, make lazy/cached with dataclass)
    station           : Station
    source            : Source
    date              : Date
    urlpath_file      : str
    filename          : str
    abspath_down_file : str
    desc              : str
    url               : str
    src_desc          : str

    @staticmethod
    def from_descriptor(stations, fd : FileDescriptor):
        return File.from_params(stations, fd.stn_idx, fd.date_mjd, fd.src_idx)
    
    @staticmethod
    def from_params(stations, stn_idx : int, date_mjd : int, src_idx : int):
        stn   = stations[stn_idx]
        src   = stn.sources[src_idx]
        date  = Date(mjd=date_mjd)

        urlpath_file      = path_replace_tags(src.path, date, stn.NetworkCode, stn.StationCode, stn.Marker,
                                              stn.CountryCode)
        filename          = os.path.basename(urlpath_file)
        abspath_down_file = os.path.join(stn.abspath_station_dir,
                                         filename)
        url      = src.protocol.lower() + "://" + src.fqdn + urlpath_file
        src_desc = "(source=#%d/%d server-%03d)" % (src_idx+1, len(stn.sources), src.server_id)

        return File(stn_idx           = stn_idx,
                    src_idx           = src_idx,
                    date_mjd          = date_mjd,
                    station           = stn,
                    source            = src,
                    date              = date,
                    urlpath_file      = urlpath_file,
                    filename          = filename,
                    abspath_down_file = abspath_down_file,
                    desc              = '[%s %s]' % (stn.stationID, date.iso_date()),
                    url               = url,
                    src_desc          = src_desc
                    )
    
    def to_descriptor(self):
        return FileDescriptor(stn_idx=self.stn_idx,
                              src_idx=self.src_idx,
                              date_mjd=self.date_mjd)

class Msg:
    """ Messages to main thread """

    # Messages from DB Query:
    class NEW_FILE(NamedTuple):
        file : FileDescriptor

    class FILE_IGNORED_EXISTS_IN_DB(NamedTuple):
        file : FileDescriptor

    class FILE_SKIPPED_INACTIVE_STATION(NamedTuple):
        file : FileDescriptor

    # Messages from downloaders:
    class DOWNLOAD_RESULT(NamedTuple):
        server_id    : int
        elapsed_time : int
        size         : int
        error        : Optional[str]

    class CLIENT_STOPPED(NamedTuple):
        server_id : int

    # Messages from dispy job manager:
    class PROCESS_RESULT(NamedTuple):
        file  : Optional[FileDescriptor]
        error : Optional[str]


###############################################################################
# Database
###############################################################################

# @todo move this to a .sql file
DB_MIGRATION_SQL = (
"""
CREATE TABLE sources_formats (
    format VARCHAR NOT NULL, 
    PRIMARY KEY(format)
);
""",
"""
INSERT INTO sources_formats (format) VALUES ('DEFAULT_FORMAT');
""",
"""
CREATE TABLE sources_servers (
    server_id  INT     NOT NULL GENERATED ALWAYS AS IDENTITY,
    protocol   VARCHAR NOT NULL CHECK (protocol IN ('ftp', 'http', 'sftp', 'https', 'ftpa', 'FTP', 'HTTP', 'SFTP', 'HTTPS', 'FTPA')),
    fqdn       VARCHAR NOT NULL,

    username   VARCHAR,
    "password" VARCHAR, 

    -- overrideable by sources_stations:
    "path"     VARCHAR, 
    "format"   VARCHAR NOT NULL REFERENCES sources_formats(format) DEFAULT 'DEFAULT_FORMAT',

    PRIMARY KEY(server_id)
);
""",
"""
CREATE TABLE sources_stations (
   "NetworkCode" VARCHAR(3) NOT NULL,
   "StationCode" VARCHAR(4) NOT NULL,
   try_order     SMALLINT   NOT NULL DEFAULT 1, 

   server_id     INT        NOT NULL REFERENCES sources_servers(server_id),

   -- If present overrides sources_servers fields:
   "path"        VARCHAR, 
   "format"      VARCHAR REFERENCES sources_formats(format),

   PRIMARY KEY("NetworkCode", "StationCode", try_order),
   FOREIGN KEY("NetworkCode", "StationCode") REFERENCES stations("NetworkCode", "StationCode")
);
"""
)


def db_migrate_if_needed(cnn):
    if cnn.query("SELECT table_name FROM information_schema.tables "
                 "WHERE table_name = 'sources_stations' LIMIT 1").dictresult():
        # New tables are present, no need to migrate.
        return False

    try:
        cnn.begin_transac()
        # Create new tables
        for sql in DB_MIGRATION_SQL:
            cnn.query(sql)

        # Migrate data
        cnn.query("INSERT INTO sources_formats (format) "
                   "SELECT UPPER(format) FROM data_source WHERE format IS NOT NULL GROUP BY format")

        cnn.query("INSERT INTO sources_servers (protocol, fqdn, username, password) "
                  "SELECT protocol, fqdn, username, password "
                       "FROM data_source "
                       "GROUP BY protocol, fqdn, username, password")

        cnn.query('INSERT INTO sources_stations ("NetworkCode", "StationCode", try_order, path, format, server_id) '
                   'SELECT "NetworkCode", "StationCode", try_order, d.path, '
                           "UPPER(COALESCE(d.format, 'DEFAULT_FORMAT')) AS format, "
                           "v.server_id "
                       "FROM data_source d "
                       "LEFT JOIN sources_servers v ON v.protocol = d.protocol AND "
                                                      "v.fqdn     = d.fqdn     AND "
                                                      "v.username IS NOT DISTINCT FROM d.username AND "
                                                      "v.password IS NOT DISTINCT FROM d.password ")
        # Drop old table
        # @todo uncomment
        # cnn.query("DROP TABLE data_source")
        cnn.commit_transac()
    except:
        cnn.rollback_transac()
        raise Exception("Can't migrate to new schema")
    return True


def source_host_desc(src : Source):
    return "%s://%s%s" % (src.protocol, src.username + "@" if src.username else '', src.fqdn)


def db_get_sources_for_station(cnn, NetworkCode, StationCode) -> List[Source]:
    return [Source(**r) for r in
            cnn.query(#'SELECT server_id, "NetworkCode", "StationCode", '
                      'SELECT server_id, '
                            'COALESCE(st.path,   sv.path)   AS path, '
                            'COALESCE(st.format, sv.format) AS format, '
                            'protocol, fqdn, username, password '
                       'FROM sources_stations st '
                       'LEFT JOIN sources_servers sv USING(server_id) '
                       'WHERE "NetworkCode" = $1 AND '
                             '"StationCode" = $2 '
                       'ORDER BY try_order ASC', (NetworkCode, StationCode)).dictresult()]


###############################################################################
# Files Bag
###############################################################################

# A file not present in source-1 must be queued to be fetched from source-2.
# Limiting the queue size between source-1 and source-2 by applying backpressure
# is not possible because we want to maximize fetching parallelism. So
# an arbitrarily sized queue is needed, but it can be too memory expensive
# for multi-year / multi-stations fetches. A way to store the queue compactly
# in memory is needed. FIFO order is not required, so use an unordered collection.

# FileDescriptor limits
MAX_DATE_MJD = 2 ** 32


class FilesBag:
    class Dates:
        CHUNK_SIZE = 4096

        def __init__(self):
            self.chunks = []
            self.last_chunk_len = 0
            # always keep a chunk to optimize 0/1 oscillation case
            self._first_chunk = np.empty(self.CHUNK_SIZE, dtype=np.uint32)

        def push(self, date_mjd : int):
            if not self.chunks or self.last_chunk_len == self.CHUNK_SIZE:
                chunk = self._first_chunk if not self.chunks else \
                        np.empty(self.CHUNK_SIZE, dtype=np.uint32)
                self.chunks.append(chunk)
                self.last_chunk_len = 0 
            else:
                chunk = self.chunks[-1]
            chunk[self.last_chunk_len] = date_mjd
            self.last_chunk_len += 1

        def pop(self):
            date_mjd = self.chunks[-1][self.last_chunk_len - 1]
            if self.last_chunk_len == 1:
                self.chunks.pop() 
                self.last_chunk_len = self.CHUNK_SIZE if len(self.chunks) else 0 
            else:
                self.last_chunk_len -= 1
            return date_mjd
        
        def is_empty(self):
            return len(self.chunks) <= 1 and self.last_chunk_len == 0
        
        def __len__(self):
            if not len(self.chunks):
                return 0
            return (len(self.chunks) - 1) * self.CHUNK_SIZE + self.last_chunk_len
            
    def __init__(self):
        self.stations = {}  # stn_idx -> { src_idx : FilesBag.Dates }
        self.qty = 0
        self.nonempty_keys = set() 
        
    def push(self, f : FileDescriptor):
        assert 0 <= f.date_mjd < MAX_DATE_MJD
        
        stn = self.stations.get(f.stn_idx, None)
        if stn == None:
            self.stations[f.stn_idx] = stn = {}

        dates = stn.get(f.src_idx, None)
        if dates == None:
            stn[f.src_idx] = dates = FilesBag.Dates()

        dates.push(f.date_mjd)
        # for faster retrieval:
        self.nonempty_keys.add((f.stn_idx, f.src_idx))
        self.qty += 1
        
    def pop(self) -> FileDescriptor:
        if not self.qty:
            raise Exception("Empty FilesBag")
        
        (stn_idx, src_idx) = next(iter(self.nonempty_keys))
        dates    = self.stations[stn_idx][src_idx]
        date_mjd = dates.pop()
        if dates.is_empty():
            # don't delete, optimize for 1/0 oscillation case
            self.nonempty_keys.remove((stn_idx, src_idx))
        self.qty -= 1
        return FileDescriptor(stn_idx  = stn_idx,
                              src_idx  = src_idx,
                              date_mjd = date_mjd)
    
    def __len__(self):
        return self.qty

    def is_empty(self):
        return not self.qty


###############################################################################
# DB Query thread - File producer
###############################################################################

def thread_queue_all_files(cnn, drange, stations, msg_outbox):
    db_archive = pyArchiveStruct.RinexStruct(cnn)
    SI         = pyStationInfo
    stations_items = tuple(stations.items())

    # iterate in (date, stations) order instead of (station, date) to maximize
    # parallelism between different station servers.
    for date_mjd in drange:
        date = Date(mjd=date_mjd)
        for (stn_idx, stn) in stations_items:                
            f = FileDescriptor(stn_idx = stn_idx, date_mjd = date_mjd, src_idx = 0)

            # if stn_idx in stations_stopped:
            #     # fail fast if all sources for station are offline
            #     tqdm.write('%s FILE NOT TRIED! All sources (%d) stopped' %
            #                (f.desc, len(f.station.sources)))
            #     continue

            try:
                # Query DB
                _ = SI.StationInfo(cnn, stn.NetworkCode, stn.StationCode, date=date)
            except SI.pyStationInfoHeightCodeNotFound:
                # if the error is that no height code is found, then there is a record
                pass
            except SI.pyStationInfoException:
                # no possible data here, inform and skip
                # DDG: unless the is NO record, then assume new station with no stninfo yet (try to download)
                stn_reconds = SI.StationInfo(cnn, stn.NetworkCode, stn.StationCode, allow_empty=True)
                if stn_reconds.records:
                    msg_outbox.put(Msg.FILE_SKIPPED_INACTIVE_STATION(file=f))
                    continue
                else:
                    pass

            # Query DB
            rinex = db_archive.get_rinex_record(NetworkCode     = stn.NetworkCode,
                                                StationCode     = stn.StationCode,
                                                ObservationYear = date.year,
                                                ObservationDOY  = date.doy)

            exists_in_db = (rinex and rinex[0]['Completion'] >= 0.5)
            msg_outbox.put(Msg.FILE_IGNORED_EXISTS_IN_DB(file=f) if exists_in_db else
                           Msg.NEW_FILE(file=f))

###############################################################################
# Process Manager
###############################################################################


class JobsManager:
    """ Submits PROCESS jobs to cluster while minimizing dispy queue usage """

    def __init__(self, job_server : pyJobServer.JobServer, abspath_scripts_dir : str):
        self.job_server          = job_server
        self.abspath_scripts_dir = abspath_scripts_dir

        self.files_pending  = FilesBag()
        self.cpus_qty       = 0 if job_server.run_parallel else 1
        self.jobs_submitted = {} # jobID -> File
        self.jobs_lock      = threading.RLock()
        
        self.stations          = None
        self.on_process_result = None
        
    def on_nodes_changed(self, nodes : list):
        """ called by dispy """
        with self.jobs_lock:
            self.cpus_qty = sum(n.avail_cpus for n in nodes)
            tqdm.write(' >> %d Cluster Nodes with %d CPUs will be used for File Processing' %
                       (len(nodes), self.cpus_qty))
            self._submit_pending()
       
    def on_job_result(self, job):
        """ called by dispy """
        with self.jobs_lock:
            f = self.jobs_submitted[job.id]
            del self.jobs_submitted[job.id]
            
            self.on_process_result(f, job.exception)
            
            self._submit_pending()

    def _can_submit_more(self):
        # cpus * 2 only to ensure dispy always has work to do
        return len(self.jobs_submitted) < (self.cpus_qty*2)
            
    def _submit(self, f : File):
        with self.jobs_lock:
            # If configured as runparallel, this will schedule an asynchrounous
            # call of process_file() in another node, if not, will run
            # asynchronously on a thread in this process.

            # process_file(...) will be called with this args in the remote node.
            job = self.job_server.submit_async(self.abspath_scripts_dir,
                                               f.abspath_down_file,
                                               f.source.format,
                                               f.station.StationCode)
            self.jobs_submitted[job.id] = f
            
            if DEBUG:
                tqdm.write('%s Submitted for processing format=%r' % (f.desc, f.source.format))

    def _submit_pending(self):
        with self.jobs_lock:
            while self._can_submit_more() and not self.files_pending.is_empty():
                fd = self.files_pending.pop()
                self._submit(File.from_descriptor(self.stations, fd))
        
    def queue_process(self, f : File):
        with self.jobs_lock:
            if self._can_submit_more():
                self._submit(f)
            else:
                self.files_pending.push(f)
                if DEBUG:
                    tqdm.write('%s Queued Process format=%r: %s' % (f.desc, f.source.format, f.url))

###############################################################################
# Download coordinator
###############################################################################
# The files are downloaded by a single running node (this), to keep connections to
# servers persistent, but are processed by the entire cluster.


def download_all_stations_data(cnn                    : dbConnection.Cnn,
                               jobs_manager           : JobsManager,
                               abspath_repository_dir : str,
                               stnlist                : List[Any],
                               drange):

    class Server:
        files_pending : FilesBag
        file_current  : Optional[File]
        client        : Client
        stopped       : bool
        
        def __init__(self, client):
            self.client        = client
            self.files_pending = FilesBag()
            self.file_current  = None
            self.stopped       = False        

    msg_inbox : queue.Queue[Msg]   = queue.Queue(8192)  # Limit memory usage / overall backpressure
    stations  : Dict[int, Station] = {}  # station_idx -> Station
    servers   : Dict[int, Server]  = {}  # server_id -> Server

    files_pending_qty = 0 

    def on_download_result(server_id : int, error : Optional[str],
                           elapsed_time = 0, size = 0, timeout = None):
        try:
            msg_inbox.put(Msg.DOWNLOAD_RESULT(server_id    = server_id,
                                              elapsed_time = elapsed_time,
                                              size         = size, 
                                              error        = error),
                          timeout = timeout)
            return True
        except queue.Full:
            return False

    def on_process_result(file : FileDescriptor, error : Optional[str]):
        msg_inbox.put(Msg.PROCESS_RESULT(file  = file,
                                         error = error))
    
    def on_client_stopped(server_id : int):
        msg_inbox.put(Msg.CLIENT_STOPPED(server_id = server_id))

    class stats:
        ok            = 0
        not_found     = 0
        db_exists     = 0
        db_no_info    = 0
        process_ok    = 0
        process_error = 0

    pbar = None

    def file_finished(f : File, result : str):
        nonlocal files_pending_qty, pbar, servers, stats
        
        files_pending_qty -= 1
        tqdm.write("%s END: %s" % (f.desc, result))

        s_stopped     = 0
        s_idle        = 0
        s_downloading = 0
        for s in servers.values():
            if s.stopped:
                s_stopped += 1
            elif s.file_current:
                s_downloading += 1
            else:
                s_idle += 1

        pbar.set_postfix(#refresh=False,
                         files="[db_no_info=%d db_exists=%d not_found=%d process_ok=%d process_error=%d ok=%d]" %
                         (stats.db_no_info, stats.db_exists, stats.not_found,
                          stats.process_ok, stats.process_error, stats.ok),
                         servers="[active=%d idle=%d stopped=%d]" % (s_downloading, s_idle, s_stopped)
                         )
        pbar.update()
        # print("files_pending_qty=%d" % files_pending_qty)

    def queue_download(stn_idx : int, date_mjd : int, src_idx : int):
        nonlocal stats, stations
        
        stn = stations[stn_idx]
        if src_idx < len(stn.sources):
            src    = stn.sources[src_idx]
            server = servers.get(src.server_id, None)
            if not server:
                host, port = fqdn_parse(src.fqdn)

                # def on_server_stopped(self):
                #     # Reschedule ALL pending files to his next source
                #     # (if a file was being downloaded, it will be rescheduled in
                #     # the DOWNLOAD_RESULT+error handler)
                #     while not server.files_pending.is_empty():
                #         fd = server.files_pending.pop()
                #         queue_download_next_source(fd)
                
                client = Client(on_download_result, on_client_stopped,
                                src.server_id,
                                src.protocol, host, port,
                                src.username, src.password)
                server = Server(client)
                servers[src.server_id] = server
                client.start_thread()

            f = File.from_params(stations,
                                 stn_idx  = stn_idx,
                                 date_mjd = date_mjd,
                                 src_idx  = src_idx)

            if server.file_current:
                # if DEBUG:
                #     tqdm.write('%s QUEUE download %s: %s' % (f.desc, f.src_desc, f.url))
                server.files_pending.push(f)
            else:
                # tqdm.write('%s DOWNLOAD START %s: %s' % (f.desc, f.src_desc, f.url))
                # tqdm.write('%s Download Trying %s' % (f.desc, f.src_desc))
                server.client.set_next_download(f.urlpath_file, f.abspath_down_file)
                server.file_current = f

        else:
            # Sources exhausted
            f = File.from_params(stations,
                                 stn_idx  = stn_idx,
                                 date_mjd = date_mjd,
                                 src_idx  = 0)
            stats.not_found += 1
            file_finished(f, 'FILE NOT FOUND')

    def queue_download_next_source(f : FileDescriptor):
        queue_download(f.stn_idx, f.date_mjd, f.src_idx + 1)

    ##
    #  1- Query DB for stations + source sinfo
    ##
    
    with tqdm(desc=' >> Querying Stations',
              dynamic_ncols = True,              
              total=len(stnlist),
              bar_format = PBAR_FORMAT,
              disable=None
              ) as pbar:

        tqdm.write(" >> Querying Stations info")

        stn_ignored_qty = 0
        stn_idx_next    = 0
        for stn in stnlist:
            station_id = stationID(stn)

            sources = db_get_sources_for_station(cnn, stn['NetworkCode'], stn['StationCode'])
            if not sources:
                tqdm.write('[%s] WARNING Station ignored: NO Sources defined' % station_id)
                stn_ignored_qty += 1
            else:
                tqdm.write("[%s] Station loaded (%d sources)" % (station_id, len(sources)))
                abspath_station_dir = os.path.join(abspath_repository_dir, station_id)
                if not os.path.exists(abspath_station_dir):
                    tqdm.write('[%s] Creating dir %s' % (station_id, abspath_station_dir))
                    os.makedirs(abspath_station_dir)

                stations[stn_idx_next] = Station(stationID           = station_id,
                                                 NetworkCode         = stn['NetworkCode'],
                                                 StationCode         = stn['StationCode'],
                                                 Marker              = stn['marker'],
                                                 CountryCode         = stn['country_code'],
                                                 sources             = sources,
                                                 abspath_station_dir = abspath_station_dir)
                stn_idx_next += 1
            
            pbar.set_postfix(#refresh=False,
                             stations="[loaded=%d ignored=%d]" % (len(stations), stn_ignored_qty)
                             )
            pbar.update()

        
    tqdm.write('-'*70)
    tqdm.write("%d Stations of %d requested ready for download" % (len(stations) , len(stnlist)))
    tqdm.write('-'*70)

    files_pending_qty = len(stations) * len(drange)

    jobs_manager.stations          = stations
    jobs_manager.on_process_result = on_process_result
    
    #
    # 2- Start thread to Query DB for files
    #
    # stations_stopped = set()
    _thread.start_new_thread(thread_queue_all_files, (cnn, drange, stations, msg_inbox))


    #
    # 3- Coordinate downloads & process
    #
    pbar = tqdm(desc=' >> Download',
                dynamic_ncols = True,              
                total         = files_pending_qty,
                bar_format    = PBAR_FORMAT,
                disable = None
                )
    with pbar:
        while files_pending_qty:
            msg = msg_inbox.get()
    
            if isinstance(msg, Msg.NEW_FILE):
                fd = msg.file
                # query first source
                queue_download(fd.stn_idx, fd.date_mjd, fd.src_idx)
                
            elif isinstance(msg, Msg.FILE_SKIPPED_INACTIVE_STATION):
                f = File.from_descriptor(stations, msg.file)
                stats.db_no_info += 1
                file_finished(f, 'FILE SKIPPED: No Station info in DB - assume Station is inactive for this date')
                
            elif isinstance(msg, Msg.FILE_IGNORED_EXISTS_IN_DB):
                f = File.from_descriptor(stations, msg.file)
                stats.db_exists += 1
                file_finished(f, 'FILE IGNORED: File exists in DB')
                
            elif isinstance(msg, Msg.CLIENT_STOPPED):
                server = servers[msg.server_id]
                tqdm.write('[SERVER-%03d] WARNING: CONNECTION STOPPED (%s)' %
                           (msg.server_id, server.client.proto.desc()))
                server.stopped = True

                # for (stn_idx, stn) in stations.items():
                #     for src in stn.sources:
                #         srv = servers.get(src.server_id, None)
                #         if not srv or not srv.stopped:
                #             break
                #     else:
                #         stations_stopped.add(stn_idx)
                    
            elif isinstance(msg, Msg.DOWNLOAD_RESULT):
                server = servers[msg.server_id]
                f = server.file_current
                server.file_current = None

                if msg.error:
                    tqdm.write('%s Download Error! %s %s: %s' % (f.desc, f.src_desc, f.url, msg.error))
                    queue_download_next_source(f)
                else:
                    postfix = "size=%dkB time=%ds speed=%dkB/s %s %s" % (msg.size//1024, msg.elapsed_time,
                                                                         (msg.size//1024)/msg.elapsed_time,
                                                                         f.src_desc, f.url)
                    fmt = f.source.format
                    if fmt and fmt != 'DEFAULT_FORMAT':
                        tqdm.write('%s Downloaded ok! format=%r %s' % (f.desc, fmt, postfix))
                        jobs_manager.queue_process(f)
                    else:
                        stats.ok += 1 
                        file_finished(f, 'DOWNLOAD OK: %s' % postfix)
                        
                # Pop next file for same server
                if not server.files_pending.is_empty():
                    fd = server.files_pending.pop()
                    queue_download(fd.stn_idx, fd.date_mjd, fd.src_idx)

            elif isinstance(msg, Msg.PROCESS_RESULT):
                f = File.from_descriptor(stations, msg.file)
                if msg.error:
                    tqdm.write('%s Process ERROR! format=%r: %s %s\n%s' % (f.desc, f.source.format,
                                                                           f.src_desc, f.url, msg.error))
                    # Try next download source, maybe file is in better shape in another server
                    stats.process_error +=1 
                    queue_download_next_source(f)
                else:
                    stats.process_ok +=1 
                    file_finished(f, 'PROCESS OK')
                            

    #
    # 4- Cleanup
    #

    tqdm.write('-'*70)
    tqdm.write('Finished all Downloads and Processing')

    for server in servers.values():
        server.client.finish()

    for stn in stations.values():
        # This will keep the dest_dir if files are present in it:
        dir_try_remove(stn.abspath_station_dir, recursive=False)


###############################################################################
# After download by-format processing 
###############################################################################

def process_file(abspath_scripts_dir : str,
                 abspath_down_file   : str,
                 src_format          : str,
                 StationCode         : str):

    DEBUG = False
    abspath_down_dir, fname_down = os.path.split(abspath_down_file)
    
    abspath_tmp_dir = None
    try:
        abspath_tmp_dir = tempfile.mkdtemp(suffix = '.tmp',
                                           prefix = os.path.join(abspath_down_dir, 'process.'))
        if src_format:
            src_format = src_format.lower()

        if not src_format or src_format in ('default_format', 'rnx2crz'):
            # but src_format must not reach here.
            # scheme rnx2crz does not require any pre-process, just copy the file
            shutil.move(abspath_down_file,
                        abspath_tmp_dir)
        else:
            for ext in ('', '.sh', '.py'):
                abspath_script_file = os.path.join(abspath_scripts_dir, src_format) + ext
                if os.path.isfile(abspath_script_file):
                    # Process must leave all the rinex files on temp_dir
                    args = [abspath_script_file,
                            abspath_down_file, fname_down, abspath_tmp_dir]
                    cmd  = subprocess.run(args,
                                          stdout = subprocess.PIPE,
                                          stderr = subprocess.STDOUT)
                    if DEBUG:
                        tqdm.write('"%s" returncode=%d output:' % (' '.join(args), cmd.returncode))
                        tqdm.write(cmd.stdout.decode('UTF-8', errors='ignore'))
                        
                    if cmd.returncode:
                        raise Exception("Format script %r failed, output: %r" % (abspath_script_file, cmd.stdout))
                    break
            else:
                raise Exception("No script for format %r: %s not found in current node" %
                                (src_format, abspath_script_file))

        # @TODO: this only works for RINEX 2, needs to work for RINEX 3 as well
        # DDG: ADDED * at the end of /*.??[oOdD](*) to also pick up Z and gz files
        abspath_out_files = glob.glob(abspath_tmp_dir + '/*.??[oOdD]*')

        # if DEBUG:
        #     tqdm.write('abspath_out_files'+repr(abspath_out_files))

        if not abspath_out_files:
            raise Exception("No files found after processing")

        for file in abspath_out_files:  # usually only a single file
            # before trying to open it, check if naming convention is consistent with RINEX
            try:
                _ = pyRinexName.RinexNameFormat(file)
            except pyRinexName.RinexNameException:
                # move the file to a valid rinex convention name (use RINEX 2 as default)
                _, extension = os.path.splitext(file)
                new_file = os.path.join(os.path.dirname(file), StationCode + '0010' + extension)
                shutil.move(file, new_file)
                file = new_file

            rinex = pyRinex.ReadRinex('???', StationCode, file)
            # compress rinex and output it to abspath_down_dir
            # DDG: apply the naming convention before moving the file
            #      this solves uppercase to lowercase, wrong date, etc
            rinex.apply_file_naming_convention()
            rinex.compress_local_copyto(abspath_down_dir)
        
    finally:
        if abspath_tmp_dir:
            dir_try_remove(abspath_tmp_dir, recursive=True)
        file_try_remove(abspath_down_file)


###############################################################################
# Download Protocols 
###############################################################################


class IProtocol(ABC):
    def __init__(self, protocol : str,
                 fqdn : str, port : int,
                 username : Optional[str], password: Optional[str]):
        self.protocol = protocol
        self.fqdn     = fqdn
        self.port     = port
        self.username = username
        self.password = password

    def desc(self):
        return "%s://%s%s" % (self.protocol, self.username + "@" if self.username else '',
                              self.fqdn)
    @abstractmethod
    def connect(self):
        pass

    @abstractmethod
    def refresh(self):
        pass
    
    @abstractmethod
    def download(self, server_path : str, dest_path : str) -> bool:
        pass

    @abstractmethod
    def list_dir(self, server_path : str):
        pass

    @abstractmethod
    def disconnect(self):
        pass
    
# -------
# FTP
# -------


class ProtocolFTP(IProtocol):
    DEFAULT_PORT = 21
        
    def __init__(self, *args, **kargs):
        super(ProtocolFTP, self).__init__('ftp', *args, **kargs)
        # timeout here is for all socket operations, not only connection
        self.ftp = ftplib.FTP(timeout = SERVER_CONNECTION_TIMEOUT)
        
    def connect(self):
        self.ftp.connect(self.fqdn, self.port)
        if self.username and self.password:
            self.ftp.login(self.username, self.password)
        self.ftp.set_pasv(True)

    def refresh(self):
        # Some servers close the connection with a message like
        # "421 Timeout (no operation for 1800 seconds)" even when
        # we send PWD's. So here we also other commands.
        self.ftp.pwd()
        self.ftp.sendcmd('NOOP')
        # self.ftp.sendcmd('STAT')

    @staticmethod
    def _check_critical_error(reply:str):
        code = reply[:3]
        if code in ('530',  # Not logged in
                    '332',  # Need account for login.
                    '425'): # Can't open data connection.
            # https://datatracker.ietf.org/doc/html/rfc959
            # Critical errors, must break the connection
            raise Exception(reply)
        
    def download(self, server_path : str, dest_path : str):
        try:
            try:
                with open(dest_path, 'wb') as f:
                    reply = self.ftp.retrbinary("RETR " + server_path, f.write)
                    self._check_critical_error(reply)
                    code = reply[:3]
                    if code == '226':
                        return None
                    else:
                        return reply
            except:
                file_try_remove(dest_path)
                raise
                
        except ftplib.error_perm as e:
            # error_perm can be "550 error to open file" but also
            # "530 Not logged in"
            self._check_critical_error(str(e))
            return str(e)

    def list_dir(self, server_path : str):
        self.ftp.cwd(os.path.dirname(server_path))
        return set(self.ftp.nlst())

    def disconnect(self):
        self.ftp.quit()

# ------------------
# FTP IN ACTIVE MODE
# ------------------


class ProtocolFTPA(ProtocolFTP):
    DEFAULT_PORT = 21

    def __init__(self, *args, **kargs):
        super(ProtocolFTPA, self).__init__(*args, **kargs)
        # timeout here is for all socket operations, not only connection
        self.ftp = ftplib.FTP(timeout=SERVER_CONNECTION_TIMEOUT)

    def connect(self):
        # overrides the set_pasv = true with false for active connection
        self.ftp.connect(self.fqdn, self.port)
        if self.username and self.password:
            self.ftp.login(self.username, self.password)
        self.ftp.set_pasv(False)

# -------
# SFTP
# -------


class ProtocolSFTP(IProtocol):
    DEFAULT_PORT = 22
    
    def __init__(self, *args, **kargs):
        super(ProtocolSFTP, self).__init__('sftp', *args,**kargs)
        self.transport = None
        self.sftp      = None
        
    def connect(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(SERVER_CONNECTION_TIMEOUT)
        s.connect((self.fqdn, self.port))
        # if socket not specified, Transport constructor will
        # trigger a tcp connection with no timeout. 
        t = paramiko.Transport(s)
        self.transport = t
        t.banner_timeout = SERVER_CONNECTION_TIMEOUT
        t.connect(username=self.username, password=self.password)
        self.sftp = paramiko.SFTPClient.from_transport(t)
        
    def refresh(self):
        # Must use stat, paramiko has no real cwd()
        self.sftp.stat('.')
    
    def download(self, server_path: str, dest_path: str):
        try:
            self.sftp.get(server_path, dest_path)
            return None
        except IOError as e:
            # paramiko maps SFTP errors to errno codes:
            if e.errno in (errno.ENOENT, errno.EACCES):
                return errno.errorcode[e.errno] + " " + e.strerror
            else:
                raise 

    def list_dir(self, server_path : str):
        return set(self.sftp.listdir(server_path))

    def disconnect(self):
        if self.sftp:
            self.sftp.close()
        if self.transport:
            self.transport.close()

# -------
# HTTP
# -------


class ProtocolHTTP(IProtocol):
    DEFAULT_PORT = 80
    
    def __init__(self, *args, protocol = 'http', **kargs):
        super(ProtocolHTTP, self).__init__(protocol, *args, **kargs)

        # NASA server is problematic. It never sends a "401 Unauthorized" response
        # and also needs to get the Authorization header in intermediate requests
        # after the 302 redirect. By default the 'requests' library strips the
        # Authorization header after the redirects, so we need to create a custom
        # Session class who preserves it.
        # See:
        #   https://cddis.nasa.gov/Data_and_Derived_Products/CDDIS_Archive_Access.html
        #   https://github.com/psf/requests/issues/2949#issuecomment-288858676
        class CustomSession(requests.Session):
            def rebuild_auth(self, prepared_request, response):
                return
        # activate the following lines to output complete header information
        # from http.client import HTTPConnection
        # import logging
        # HTTPConnection.debuglevel = 1
        # logging.basicConfig(level=logging.DEBUG)
        # The requests will use an HTTP persistent connection
        self.session = CustomSession()

        if self.username and self.password:
            # HTTP Basic Authorization
            self.session.auth = (self.username, self.password)

        self.base_url = protocol+'://%s:%s' % (self.fqdn, self.port)

    def connect(self):
        pass
    
    def refresh(self):
        # The HTTP persistent connection will be automatically refreshed
        pass

    def download(self, server_path : str, dest_path : str):

        if 'gage' in self.base_url:
            result = subprocess.run(['es', 'sso', 'access', '--token'], stdout=subprocess.PIPE)
            gage_token = {'Authorization': 'Bearer ' + result.stdout.decode('utf-8').strip()}
            # print(result.stdout.decode('utf-8'))
        else:
            gage_token = None

        with self.session.get(self.base_url + server_path,
                              stream=True,
                              timeout=SERVER_CONNECTION_TIMEOUT,
                              headers=gage_token) as r:
            if 200 <= r.status_code <= 299:
                with open(dest_path, 'wb') as f:
                    shutil.copyfileobj(r.raw, f)
                return None
            else:
                error = "%d %s" % (r.status_code, r.reason)
                if 500 <= r.status_code <= 599:
                    raise Exception(error)
                else:
                    return error

    def list_dir(self, server_path : str):
        r = self.session.get(self.base_url + server_path)
        if r.status_code == 200:
            return r.text
        else:
            raise Exception('HTTP returned status code %i' % r.status_code)

    def disconnect(self):
        self.session.close()

# --------
# HTTPS
# --------


class ProtocolHTTPS(ProtocolHTTP):
    DEFAULT_PORT = 443

    def __init__(self, *args, **kargs):
        super(ProtocolHTTPS, self).__init__(*args, protocol='https', **kargs)
        

###############################################################################
# Download Client
###############################################################################

class Client:
    class NextDownload(NamedTuple):
        urlpath_file      : str
        abspath_down_file : str

    server_id     : int
    proto         : IProtocol
    cond          : threading.Condition
    state         : str  # Literal['STARTED', 'STOP_PENDING', 'STOPPED', "FINISH_PENDING", "FINISHED"]
    next_download : Optional[NextDownload] 
    
    def __init__(self,
                 on_download_result, on_client_stopped,
                 server_id : int,
                 protocol, host, port, username, password):

        self.on_download_result = on_download_result
        self.on_client_stopped  = on_client_stopped
        
        self.server_id = server_id
        self.cond      = threading.Condition()
        self.state     = 'STARTED'
        self.next_download = None
        
        protoClass = { 'FTP'  :  ProtocolFTP,
                       'FTPA' :  ProtocolFTPA,
                       'SFTP' :  ProtocolSFTP,
                       'HTTP' :  ProtocolHTTP,
                       'HTTPS':  ProtocolHTTPS,
                      }[protocol]
        
        self.proto = protoClass(host,
                                port or protoClass.DEFAULT_PORT,
                                username,
                                password)

    def start_thread(self):
        _thread.start_new_thread(self._client_thread, ())
        
    def set_next_download(self, urlpath_file : str, abspath_down_file : str):
        with self.cond:
            assert not self.next_download
            assert self.state not in ('FINISH_PENDING', 'FINISHED')
            self.next_download = Client.NextDownload(urlpath_file=urlpath_file,
                                                     abspath_down_file=abspath_down_file)
            self.cond.notify()

    def stop(self):
        with self.cond:
            if self.state != 'STOPPED': 
                self.state = 'STOP_PENDING'
                self.cond.notify()

    def finish(self):
        with self.cond:
            if self.state != 'FINISHED': 
                self.state = 'FINISH_PENDING'
                self.cond.notify()

    def _client_thread(self):
        prefix       = '[SERVER-%03d]' % self.server_id
        conn_retries = 0
        connected    = False

        def try_proto_disconnect():
            nonlocal connected
            try:
                if connected:
                    self.proto.disconnect()
            except:
                pass
            connected = False

        try:
            while True:
                try:
                    conn_retries += 1
                    postfix = '(try #%d/%d) to: %s' % (conn_retries, SERVER_MAX_RECONNECTIONS,
                                                       self.proto.desc())
                    tqdm.write('%s CONNECTING %s' % (prefix, postfix))
                    self.proto.connect()
                    connected = True
                    tqdm.write('%s CONNECT OK %s' % (prefix, postfix))

                    while True:
                        f = None

                        with self.cond:
                            if not self.next_download and self.state != 'STOP_PENDING':
                               self.cond.wait(timeout = SERVER_REFRESH_INTERVAL)

                            f = self.next_download
                            if not f and self.state == 'STOP_PENDING':
                                return
                            
                        if not f:
                            self.proto.refresh()
                            continue
                        
                        if os.path.isfile(f.abspath_down_file):
                            # tqdm.write('   -- Destination file %s is present (from '
                            #             'previous run?), removing it' % f.abspath_down_file)
                            file_try_remove(f.abspath_down_file)

                        # tqdm.write('%s Downloading %s to %s' % (prefix, f.urlpath_file, f.abspath_down_file))
                        if DEBUG:
                            tqdm.write('%s Download start: %s' % (prefix, f.urlpath_file))

                        t_elapsed = size = 0
                        t_start = time.time()
                        error = None
                        try:
                            error = self.proto.download(f.urlpath_file,
                                                        f.abspath_down_file)
                            t_elapsed = time.time() - t_start
                            if not error:
                                size = os.path.getsize(f.abspath_down_file)
                            # A good download means server is back in shape, give it more chance
                            # for next disconnection:
                            conn_retries = 0
                        except:
                            error = True
                            raise
                        finally:
                            if error:
                                file_try_remove(f.abspath_down_file)
                        
                        if DEBUG:
                            tqdm.write('%s %s %s' % (prefix,
                                                     "Transfer OK!" if not error else "ERROR: " + error,
                                                     f.urlpath_file))

                        with self.cond:
                            self.next_download = None

                        while not self.on_download_result(self.server_id,
                                                          None if not error else error,
                                                          t_elapsed,
                                                          size,
                                                          timeout = SERVER_REFRESH_INTERVAL):
                            try:
                                self.proto.refresh()
                            except:
                                pass
                            
                except:
                    tqdm.write("%s CONNECTION ERROR (try #%d/%d) to %s:\n%s\n %s%s" %
                               (prefix, conn_retries, SERVER_MAX_RECONNECTIONS, self.proto.desc(),
                                '~'*70,traceback.format_exc(), '~'*70))

                    if conn_retries < SERVER_MAX_RECONNECTIONS:
                        try_proto_disconnect()
                        time.sleep(SERVER_RECONNECTION_INTERVAL)
                        continue
                    else:
                        return
        finally:
            tqdm.write("%s STOPPING connection to: %s" % (prefix, self.proto.desc()))
            self.on_client_stopped(self.server_id)

            try_proto_disconnect()

            # After deciding the server is not operative, discard all immediatly
            while True:
                f     = None
                state = None
                with self.cond:
                    if not self.next_download and self.state != 'FINISH_PENDING':
                        self.cond.wait()

                    f     = self.next_download
                    state = self.state

                if f:
                    # We want to log the complete tries for all the files, so they are
                    # discarded here just like before.
                    self.on_download_result(self.server_id, "Connection STOPPED")
                    with self.cond:
                        self.next_download = None
                elif state == 'FINISH_PENDING':
                    with self.cond:
                        self.state = 'FINISHED'
                    return
                    

###############################################################################
# Main
###############################################################################

def main():
    parser = argparse.ArgumentParser(description='Archive operations Main Program')

    parser.add_argument('stnlist', type=str, nargs='+', metavar='all|net.stnm',
                        help="List of networks/stations to process given in [net].[stnm] format or just [stnm] "
                             "(separated by spaces; if [stnm] is not unique in the database, all stations with that "
                             "name will be processed). Use keyword 'all' to process all stations in the database. "
                             "If [net].all is given, all stations from network [net] will be processed. "
                             "Alternatively, a file with the station list can be provided.")

    parser.add_argument('-date', '--date_range', nargs='+', action=required_length(1, 2),
                        metavar='date_start|date_end',
                        help="Date range to check given as [date_start] or [date_start] "
                             "and [date_end]. Allowed formats are yyyy.doy or yyyy/mm/dd..")

    parser.add_argument('-win', '--window', nargs=1, metavar='days', type=int,
                        help="Download data from a given time window determined by today - {days}.")

    parser.add_argument('-np', '--noparallel', action='store_true', help="Execute command without parallelization.")

    try:
        args = parser.parse_args()

        cnn    = dbConnection.Cnn(CONFIG_FILE)
        Config = pyOptions.ReadOptions(CONFIG_FILE)

        tqdm.write(" >> Configuration loaded from %r" % CONFIG_FILE)
        tqdm.write('       Repository Path: ' + Config.repository_data_in)
        tqdm.write('   Format Scripts Path: ' + Config.format_scripts_path)
        # tqdm.write('-----------------------')

        stnlist = Utils.process_stnlist(cnn, args.stnlist)
        stnlist.sort(key=stationID)
        
        # print(' >> Selected station list:')
        # print_columns([stationID(item) for item in stnlist])
        
        dates = []
        now   = datetime.now()
        
        try:
            if args.window:
                # today - ndays
                d = Date(year  = now.year,
                         month = now.month,
                         day   = now.day)
                dates = [d-int(args.window[0]), d]
            else:
                dates = process_date(args.date_range)

        except ValueError as e:
            parser.error(str(e))

        min_date = Date(gpsWeek=650, gpsWeekDay=0)
        if dates[0] < min_date:
            dates = [min_date,
                     Date(year  = now.year,
                          month = now.month,
                          day   = now.day)]

        # go through the dates
        drange = np.arange(dates[0].mjd,
                           dates[1].mjd + 1,
                           1,
                           dtype=int)

        ####
    
        if db_migrate_if_needed(cnn):
            tqdm.write(" ** DB MIGRATED TO NEW VERSION ** ")
        
        # Cluster Job Server

        job_server = pyJobServer.JobServer(Config, 
                                           run_parallel = not args.noparallel)

        # process_file dependencies:
        depfuncs = (dir_try_remove, file_try_remove)
        depmodules = ('tempfile', 'shutil', 'os', 'subprocess', 'glob',
                      # app
                      'pyRinex', 'pyRinexName')

        jobs_mgr = JobsManager(job_server, Config.format_scripts_path)
        job_server.create_cluster(process_file,  # called in remote node
                                  depfuncs,
                                  jobs_mgr.on_job_result,
                                  None, #pbar,
                                  modules=depmodules,
                                  on_nodes_changed = jobs_mgr.on_nodes_changed,
                                  #verbose=True
                                  )

        try: 
            download_all_stations_data(cnn, jobs_mgr,
                                       Config.repository_data_in,
                                       stnlist, drange)
            job_server.wait()
        finally:
            job_server.close_cluster()

    except argparse.ArgumentTypeError as e:
        parser.error(str(e))

    tqdm.write(" ** Finished")


if __name__ == '__main__':
    main()



