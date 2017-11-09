"""
Project: Parallel.Archive
Date: 02/16/2017
Author: Demian D. Gomez
"""

import os
import pyEvents
import subprocess
import threading
import time
import platform

class RunCommandWithRetryExeception(Exception):
    def __init__(self, value):
        self.value = value
        self.event = pyEvents.Event(Description=value, EventType='error', module=type(self).__name__)
    def __str__(self):
        return str(self.value)


class command(threading.Thread):

    def __init__(self,command,cwd=os.getcwd(),cat_file=None):
        self.stdout = None
        self.stderr = None
        self.cmd = command
        self.cwd = cwd
        self.cat_file = cat_file

        threading.Thread.__init__(self)

    def run(self):
        retry = 0
        while True:
            try:
                if self.cat_file:
                    cat = subprocess.Popen(['cat',self.cat_file], shell=False, stdout=subprocess.PIPE, cwd=self.cwd, close_fds=True, bufsize=-1, universal_newlines=True)
                    self.p = subprocess.Popen(self.cmd.split(), shell=False, stdin=cat.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=self.cwd, close_fds=True, bufsize=-1, universal_newlines=True)
                else:
                    self.p = subprocess.Popen(self.cmd.split(), shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=self.cwd, close_fds=True, bufsize=-1, universal_newlines=True)

                self.stdout, self.stderr = self.p.communicate()
                break
            except OSError as e:
                if str(e) == '[Errno 35] Resource temporarily unavailable':
                    if retry <= 2:
                        retry += 1
                        # wait a moment
                        time.sleep(0.5)
                        continue
                    else:
                        print self.cmd
                        raise OSError(str(e) + ' after 3 retries on node: ' + platform.node())
                else:
                    print self.cmd
                    raise
            except Exception:
                print self.cmd
                raise

    def wait(self, timeout=None):

        self.join(timeout=timeout)
        if self.is_alive():
            try:
                self.p.kill()
            except Exception:
                # the process was done
                return False

            return True

        return False

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            self.p.terminate()
        except Exception:
            pass

        self.p = None

    def __enter__(self):
        return self


class RunCommand():
    def __init__(self,command,time_out,cwd=os.getcwd(),cat_file=None):
        self.stdout = None
        self.stderr = None
        self.cmd = command
        self.time_out = time_out
        self.cwd = cwd
        self.cat_file = cat_file

    def run_shell(self):
        retry = 0
        while True:
            with command(self.cmd,self.cwd,self.cat_file) as cmd:
                cmd.start()
                timeout = cmd.wait(self.time_out)
                if timeout:
                    if retry <= 2:
                        retry += 1
                        continue
                    else:
                        raise RunCommandWithRetryExeception(
                            "Error in RunCommand.run_shell -- (" + self.cmd + "): Timeout after 3 retries")
                else:
                    # remove non-ASCII chars
                    if not cmd.stderr is None:
                        cmd.stderr = ''.join([i if ord(i) < 128 else ' ' for i in cmd.stderr])

                    return cmd.stdout, cmd.stderr