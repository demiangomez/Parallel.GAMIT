#! /bin/bash
net=$1
stn=$2

stn=`echo $stn | tr '[:upper:]' '[:lower:]'`
STN=`echo $stn | tr '[:lower:]' '[:upper:]'`

#grep "^ $STN" station_ign.info 
cat ~/mounts/qnap/ign/repository/data_in/arg/$stn/$stn.station.info

#grep "^ $STN" station_ign.info | python pyScanArchive.py --stn $stn --net $net --stninfo
cat ~/mounts/qnap/ign/repository/data_in/arg/$stn/$stn.station.info | python pyScanArchive.py --stn $stn --net $net --stninfo

python pyIntegrityCheck.py --stn $stn --net $net --print_stninfo long
