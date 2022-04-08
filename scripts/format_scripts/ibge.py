#!/usr/bin/env python3
import sys
abspath_down_file, fname_down, abspath_tmp_dir = sys.argv[1:4]
#

import shutil
shutil.unpack_archive(abspath_down_file, abspath_tmp_dir)
