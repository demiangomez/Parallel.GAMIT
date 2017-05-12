#! /bin/bash

if [ $# -lt 2 ]
  then
    more << EOF
	Script to rename crinex files
	Example: rename_crine.sh liva lvra
	Will also rename D.Z or d.z to d.Z to comply with rinex name format
	Too few arguments. Usage:
	rename_crinex.sh [original station name] [new station name]
EOF
	echo $0
	exit
fi

filename=$1
newname=$2

files=(`find . -name "$filename*.??[Dd].[Zz]"`)

for file in ${files[*]}
do
	rename=`echo $file | sed "s/$filename/$newname/g"`
	rename=`echo $rename | sed 's/./\L&/g' | sed 's/d.z/d.Z/g'`
	mv -i $file $rename
done
