#!/bin/bash

# Add GAMIT and GLOBK paths relative to the home directory
# export PATH="$PATH:/fs/project/gomez.124/opt/gamit_10.7/gamit/bin:/fs/project/gomez.124/opt/gamit_10.7/kf/bin:/fs/project/gomez.124/opt/gamit_10.7/com:/fs/project/gomez.124/opt/bin"
# export PATH="$PATH:/home/kendrick.42/gamit_10.71/com:/home/kendrick.42/gamit_10.71/gamit/bin:/home/kendrick.42/gamit_10.71/kf/bin:/fs/project/gomez.124/opt/bin" 
export PATH="$PATH:/fs/project/gomez.124/opt/gamit_10.71/gamit/bin:/fs/project/gomez.124/opt/gamit_10.71/kf/bin:/fs/project/gomez.124/opt/gamit_10.71/com:/fs/project/gomez.124/opt/bin"
# GAMIT and GLOBK help
export HELP_DIR="~/gg/help/"
# processing institute
export INSTITUTE=OSU
# definitions for Parallel.GAMIT
export PYTHONPATH="/fs/project/gomez.124/parallel.gamit/classes:/fs/project/gomez.124/parallel.gamit/parallel_gamit:/fs/project/gomez.124/parallel.gamit/stacker"
# shortcut for the archive folder
export ARCHIVE="/fs/project/gomez.124/archive"
# for GPSTk
export LD_LIBRARY_PATH=/usr/local/GPSTk/2.12/lib64

# new: virtual environment for Python 3
# created following setup script from Nahuel Greco
source /fs/project/gomez.124/opt/Parallel.GAMIT/venv/bin/activate

# load modules to use interactively
# ml GPSTk/2.12 not needed anymore
ml python/3.7-2020.02

