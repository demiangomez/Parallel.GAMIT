#! /bin/bash

if [ $# -eq 1 ]; then
	proxy=$1
fi

# run with sudo
# postgres bin directory should be in PATH
# begin updating pip, if needed
curl https://bootstrap.pypa.io/get-pip.py | python

# install dependencies of pygresql, compress
sudo apt install libpq-dev ncompress bc zip gzip

# copy libgpstk.so
sudo cp /opt/gpstk/build/libgpstk.so /usr/lib/libgpstk.so

# modules to install
modules="pygresql tqdm scandir simplekml numpy matplotlib scipy pp pysftp simplekml sklearn"

# sequence of packages to install
if [ -z "$proxy" ]; then
	pip install $modules --proxy=$proxy
else
	pip install $modules --proxy=$proxy
fi

