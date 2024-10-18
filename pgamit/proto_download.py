"""
Project: Parallel.GAMIT 
Date: 10/18/24 11:53 AM 
Author: Demian D. Gomez

Description goes here

"""

# deps
from typing import NamedTuple, Optional
import threading
import requests
from abc import ABC, abstractmethod
import ftplib
import socket
import paramiko
import errno
import _thread
import subprocess
import shutil
import os
import time
from tqdm import tqdm
import traceback

# app
from pgamit.Utils import  file_try_remove, dir_try_remove

SERVER_REFRESH_INTERVAL      = 2   # in seconds
SERVER_CONNECTION_TIMEOUT    = 20  # in seconds
SERVER_RECONNECTION_INTERVAL = 3   # in seconds
SERVER_MAX_RECONNECTIONS     = 8

DEBUG = False


class IProtocol(ABC):
    def __init__(self, protocol: str,
                 fqdn: str, port: int,
                 username: Optional[str], password: Optional[str]):
        self.protocol = protocol
        self.fqdn = fqdn
        self.port = port
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
    def download(self, server_path: str, dest_path: str) -> bool:
        pass

    @abstractmethod
    def list_dir(self, server_path: str):
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
        self.ftp = ftplib.FTP(timeout=SERVER_CONNECTION_TIMEOUT)

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
    def _check_critical_error(reply: str):
        code = reply[:3]
        if code in ('530',  # Not logged in
                    '332',  # Need account for login.
                    '425'):  # Can't open data connection.
            # https://datatracker.ietf.org/doc/html/rfc959
            # Critical errors, must break the connection
            raise Exception(reply)

    def download(self, server_path: str, dest_path: str):
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

    def list_dir(self, server_path: str):
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
        super(ProtocolSFTP, self).__init__('sftp', *args, **kargs)
        self.transport = None
        self.sftp = None

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

    def list_dir(self, server_path: str):
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

    def __init__(self, *args, protocol='http', **kargs):
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

        self.base_url = protocol + '://%s:%s' % (self.fqdn, self.port)

    def connect(self):
        pass

    def refresh(self):
        # The HTTP persistent connection will be automatically refreshed
        pass

    def download(self, server_path: str, dest_path: str):

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

    def list_dir(self, server_path: str):
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


class Client:
    class NextDownload(NamedTuple):
        urlpath_file: str
        abspath_down_file: str

    server_id: int
    proto: IProtocol
    cond: threading.Condition
    state: str  # Literal['STARTED', 'STOP_PENDING', 'STOPPED', "FINISH_PENDING", "FINISHED"]
    next_download: Optional[NextDownload]

    def __init__(self,
                 on_download_result, on_client_stopped,
                 server_id: int,
                 protocol, host, port, username, password):

        self.on_download_result = on_download_result
        self.on_client_stopped = on_client_stopped

        self.server_id = server_id
        self.cond = threading.Condition()
        self.state = 'STARTED'
        self.next_download = None

        protoClass = {'FTP': ProtocolFTP,
                      'FTPA': ProtocolFTPA,
                      'SFTP': ProtocolSFTP,
                      'HTTP': ProtocolHTTP,
                      'HTTPS': ProtocolHTTPS,
                      }[protocol]

        self.proto = protoClass(host,
                                port or protoClass.DEFAULT_PORT,
                                username,
                                password)

    def start_thread(self):
        _thread.start_new_thread(self._client_thread, ())

    def set_next_download(self, urlpath_file: str, abspath_down_file: str):
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
        prefix = '[SERVER-%03d]' % self.server_id
        conn_retries = 0
        connected = False

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
                                self.cond.wait(timeout=SERVER_REFRESH_INTERVAL)

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
                                                          timeout=SERVER_REFRESH_INTERVAL):
                            try:
                                self.proto.refresh()
                            except:
                                pass

                except:
                    tqdm.write("%s CONNECTION ERROR (try #%d/%d) to %s:\n%s\n %s%s" %
                               (prefix, conn_retries, SERVER_MAX_RECONNECTIONS, self.proto.desc(),
                                '~' * 70, traceback.format_exc(), '~' * 70))

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
                f = None
                state = None
                with self.cond:
                    if not self.next_download and self.state != 'FINISH_PENDING':
                        self.cond.wait()

                    f = self.next_download
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

