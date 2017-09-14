#!/bin/bash
export PYTHONPATH=/home/demian/Dropbox/Geofisica/postdoc/ParallelPPP/classes:/home/demian/Dropbox/Geofisica/IGN/Parallel.GAMIT/project_v2.1

# execute parallel python server with 12 workers
# DDG 09-14-2017: recommended call: python `which ppserver.py` rather than just ppserver.py
#                 this is because the shebang might be referencing another python version which is not the recommended one (> 2.7.13)
python `which ppserver.py` -a -r -w 12 -d
