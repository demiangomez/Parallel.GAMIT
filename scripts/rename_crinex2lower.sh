#! /bin/bash

if [ $# -gt 0 ]
  then
    more << EOF
	Script to rename crinex files to lowercase
	Just run without arguments
EOF
	echo $0
	exit
fi

files=(`find . -name "[[:upper:]]*.??[Dd].[Zz]"`)

for file in ${files[*]};
do
	rename=`echo $file | sed 's/./\L&/g' | sed 's/d.z/d.Z/g'`
	echo $file $rename
	mv -i $file $rename
done
