#!/usr/bin/env python3
import sys
abspath_down_file, fname_down, abspath_tmp_dir = sys.argv[1:4]
#

import shutil, gzip, os

abspath_out_file = os.path.join(abspath_tmp_dir,
                                fname_down.replace('o.Z', 'o').replace('O.Z', 'o').lower())

with gzip.open(abspath_down_file, 'rb') as f_in:
    with open(abspath_out_file, 'wb') as f_out:
        shutil.copyfileobj(f_in, f_out)

