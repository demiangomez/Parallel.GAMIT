"""
Project: Parallel.Archive
Date: 02/16/2017
Author: Demian D. Gomez
"""

import pyRunCommand
import os

class RunCommandWithRetryExeception(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return str(self.value)

class RunCommand():
    def __init__(self,command,time_out,cwd=os.getcwd(),cat_file=None):
        self.stdout = None
        self.stderr = None
        self.cmd = command
        self.time_out = time_out
        self.cwd = cwd
        self.cat_file = cat_file

    def run_shell(self):
        try:
            retry = 0
            while True:
                with pyRunCommand.command(self.cmd,self.cwd,self.cat_file) as cmd:
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
                        break

            # remove non-ASCII chars
            if not cmd.stderr is None:
                cmd.stderr = ''.join([i if ord(i) < 128 else ' ' for i in cmd.stderr])

        except:
            raise

        return cmd.stdout, cmd.stderr