#!/bin/bash

WCD=$(ps -ef | grep 'dispynode.py' | grep -v 'grep' | wc -l)

if [ "$WCD" -eq 0  ]; then
	source /media/leleiona/ParallelPPP/bin/setup.sh
	if [ "`hostname`" == "bevis06.geology.ohio-state.edu" ]; then
	        nohup /Library/Frameworks/Python.framework/Versions/2.7/bin/dispynode.py -c 2 -d --clean --daemon >/dev/null 2>&1 &
	else
		nohup /opt/local/Library/Frameworks/Python.framework/Versions/2.7/bin/dispynode.py -c 8 -d --clean --daemon >/dev/null 2>&1 &
	fi
else
        echo "Daemon is already running..."
fi

#__END__.
