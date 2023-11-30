#!/usr/bin/env python3
import sys
import os
import pyTrimbleT0x

abspath_down_file, fname_down, abspath_tmp_dir = sys.argv[1:4]

stnm = fname_down[0:4]

pyTrimbleT0x.convert_trimble(abspath_down_file, stnm, abspath_tmp_dir, plain_path=True)


