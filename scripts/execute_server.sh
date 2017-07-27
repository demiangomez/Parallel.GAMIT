#!/bin/bash
export PYTHONPATH=/home/demian/Dropbox/Geofisica/postdoc/ParallelPPP/classes:/home/demian/Dropbox/Geofisica/IGN/Parallel.GAMIT/project_v2.1

# execute parallel python server with 12 workers
ppserver.py -a -r -w 12 -d
