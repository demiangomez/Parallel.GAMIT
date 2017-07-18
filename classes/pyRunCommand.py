
import subprocess
import threading
import os

class command(threading.Thread):
    def __init__(self,command,cwd=os.getcwd(),cat_file=None):
        self.stdout = None
        self.stderr = None
        self.cmd = command
        self.cwd = cwd
        self.cat_file = cat_file

        threading.Thread.__init__(self)

    def run(self):

        try:
            if self.cat_file:
                cat = subprocess.Popen(['cat',self.cat_file], shell=False, stdout=subprocess.PIPE,cwd=self.cwd)
                self.p = subprocess.Popen(self.cmd.split(), shell=False, stdin=cat.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=self.cwd)
            else:
                self.p = subprocess.Popen(self.cmd.split(),shell=False,stdout=subprocess.PIPE,stderr=subprocess.PIPE,cwd=self.cwd)

            self.stdout, self.stderr = self.p.communicate()
        except:
            print self.cmd
            raise

    def wait(self, timeout=None):

        self.join(timeout=timeout)
        if self.is_alive():
            try:
                self.p.kill()
            except:
                # the process was done
                return False

            return True

        return False

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            self.p.terminate()
        except Exception:
            pass
        except:
            raise

        self.p = None

    def __enter__(self):
        return self