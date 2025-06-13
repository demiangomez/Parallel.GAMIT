#!/usr/bin/env python3
import sys
import os
import ConvertRaw

abspath_down_file, fname_down, abspath_tmp_dir = sys.argv[1:4]

stnm = fname_down[0:4]

convert = ConvertRaw.ConvertRaw(stnm, abspath_down_file, abspath_tmp_dir)

convert.process_files()
