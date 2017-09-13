#! /bin/bash
net=$1
stn=$2

stn=`echo $stn | tr '[:upper:]' '[:lower:]'`
STN=`echo $stn | tr '[:lower:]' '[:upper:]'`

#grep "^ $STN" station_ign.info 
cat /Users/gomez.124/mounts/qnap/ign/external/igs/$stn/$stn.station.info

#grep "^ $STN" station_ign.info | python pyScanArchive.py --stn $stn --net $net --stninfo
cat /Users/gomez.124/mounts/qnap/ign/external/igs/$stn/$stn.station.info | python pyScanArchive.py --stn $stn --net $net --stninfo --stninfo_path stdin

python pyIntegrityCheck.py --stn $stn --net $net --print_stninfo long
