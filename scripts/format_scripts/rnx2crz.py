#!/usr/bin/env python3
import sys
abspath_down_file, fname_down, abspath_tmp_dir = sys.argv[1:4]
#

import shutil
# scheme rnx2crz does not require any pre-process, just copy the file
shutil.copy(abspath_down_file, abspath_tmp_dir)
