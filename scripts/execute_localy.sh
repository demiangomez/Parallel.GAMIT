#!/bin/bash
export PYTHONPATH=/home/demian/Dropbox/Geofisica/postdoc/ParallelPPP/classes:/home/demian/Dropbox/Geofisica/IGN/Parallel.GAMIT/project_v2.1

python /home/demian/Dropbox/Geofisica/IGN/Parallel.GAMIT/project_v2.1/pyParallelGamit.py --session_cfg $1 --year $2 --doys $3

