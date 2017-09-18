#!/bin/bash

# set the PYTHONPATH
homef="/Users/abel"
export PYTHONPATH="/media/leleiona/ParallelPPP/classes"
export PATH="/media/leleiona/ParallelPPP/bin:/opt/local/bin:/opt/local/sbin:/opt/local/lib/postgresql94/bin:$homef/gamit/gamit/bin:$homef/gamit/kf/bin:$homef/gamit/com:$PATH"

# create a temp folder for execution
if [ -e "$homef/parallelppp/gnss_data.cfg" ]; then
    # remove the config file (to account for possible updates)
    rm $homef/parallelppp/gnss_data.cfg
fi

# copy the config file
cp /media/leleiona/ParallelPPP/classes/gnss_data.cfg $homef/parallelppp

cd $homef/parallelppp

# execute parallel python
python /media/leleiona/ParallelPPP/classes/pyIntegrityCheck.py "${@:1}"
