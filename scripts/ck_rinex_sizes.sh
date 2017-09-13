#!/bin/bash
#d call with ck_rinex_sizes.sh rinexfile
#d calculate length of rinex file in decimal hours, counts epochs
#d uses/finds sampling rate
#d and optionally remove short files

PNTERR=0
RMBAD=0
MINSATS=1
MINSATS=4

if [ $# -eq 0 ]
then
 PNTERR=1
elif [ $# -eq 1 ]
then
 echo check existance $1
 if [ ! -e $1 ]
 then
  echo file not found
  PNTERR=1
 else
  rinexfile=$1
 fi
elif [ $# -gt 2 ]
then
  PNTERR=1
fi

if [ $PNTERR == 1 ]
then
 grep \^#d $0
 exit
else
 echo process file $rinexfile
fi

YR2=`echo $rinexfile | cut -c 10-11`
YR1=`echo $YR2 | cut -c 2-2`

# two things to do - find interval and epoch id lines
# not all rinex files headers have the interval specified
# interval in header somtimes incorrect, but it there assume good for now (teqc +qc needs interval)

# calculate interval from first two epochs - works when first two epochs are correct
# cant make assumption that any two consecutive epochs are correct

# look for epoch data format, sometimes 2 digit, sometimes 1 digit - eg " 00 " or "  0 "

# echo find interval if exists, assume "END OF HEADER" is last line of header to stop it from reading whole file
# bad assumption in line above, 1993 rinex files do not have "END OF HEADER" header line. But all header
# lines have non numeric character in column 61, all data lines, inlcuding epoch id lines, have a number or blank
# in col 61 (de pedo), so for now assume a non numeric character in col 61 is header (not data)
# else are going to have to search for header line identifiers.
# also - comment, and possibley other header, lines can show up anywhere in the file.

#CARRIER PHASE MEASUREMENTS: PHASE SHIFTS REMOVED            COMMENT
#                                                            END OF HEADER
# 10  3 10  0  0  0.0000000  0 18G 3G 6G14G15G16G18G19G21G22G24G26G29
#                                R 1R 2R 3R 8R17R23
# 115083890.09417  89675847.03358  21899743.578 7                  21899748.16048
#                                        47.600          36.900

# seems headers have CAPITAL letter descriptor, or a number sign - #, in column 61

# also stop reading when find interval
   INT=" "
   INT=`nawk '{if ( !/END OF HEADER/ ){ if ( /INTERVAL/ ) { print $1; exit; } } else { exit } }' $rinexfile`

   if [ -z "${INT}" ]
   then
     echo interval not in header - $rinexfile - try to find from data 
# hope it stable, beginning epochs sometimes intermittent
#   echo find epoch id line
    EPOCHID=`nawk 'BEGIN {CNT=0}; /^ [ 0-9][0-9] [ 0-3][0-9]/&&(!match(substr($0,61,1),"[A-Z]")) {CNT=CNT+1; print substr($0,17,9); if (CNT==2){exit}}' $rinexfile`
    INT=`echo $EPOCHID | nawk '{DIF=$2-$1; if (DIF < 0 ) { DIF=DIF+60 }; printf("%4.1f", DIF)}'`
    echo [${INT}], $rinexfile
    teqc -O.int $INT $rinexfile > ${rinexfile}.tmp
    mv ${rinexfile}.tmp ${rinexfile}
   else
   echo INT [$INT]
   fi

