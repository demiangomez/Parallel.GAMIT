#! /bin/bash

if [ $# -lt 1 ]
  then
    more << EOF
	Script to find log files recursively from the ./ directory and execute the BASH# command
	Example: $0 igm1
	Too few arguments. Usage:
	rename_crinex.sh [station name]
EOF
	exit
fi

files=`find . -name "$1*.log"`

for log_file in $files
do
	cmd=`grep "^BASH#" "$log_file" | sed 's/^BASH#//g'`
	echo $cmd
	$cmd
done

echo "Done."

