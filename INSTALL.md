Installation
=================


Prerequisites
---------------

```sh
apt-get install python3-venv
```

Libraries
----------

```sh
export PROJ_DIR=/your/prefeered/path
export PROJ_LIB=$PROJ_DIR/share/proj/

mkdir /tmp/proj
cd /tmp/proj
wget https://download.osgeo.org/proj/proj-7.2.1.tar.gz
tar xvfz proj-7.2.1.tar.gz
cd proj-7.2.1
./configure --prefix=$PROJ_DIR
make install
```

Create and activate Python Environment
--------------------------------------------

```sh
python3 -m venv venv 
source venv/bin/activate
```

Install Python packages
---------------------------

```sh
python3 -m pip install --user numpy==1.16.0
python3 -m pip install --user wheel
python3 -m pip install --user PyGreSQL==5.0.4
python3 -m pip install --user scipy==1.2.0 
python3 -m pip install --user matplotlib==2.0.0 
python3 -m pip install --user tqdm==4.19.4
python3 -m pip install --user scandir==1.6
python3 -m pip install --user dispy==4.11.0
python3 -m pip install --user netifaces==0.10.9
python3 -m pip install --user psutil==5.6.3
python3 -m pip install --user pycos==4.8.11
python3 -m pip install --user dirsync==2.2.4
python3 -m pip install --user simplekml==1.3.1
python3 -m pip install --user hdf5storage==0.1.18
python3 -m pip install --user git+git://github.com/usgs/libcomcat.git@2.0.10
python3 -m pip install --user git+git://github.com/usgs/earthquake-impact-utils@0.8.27
python3 -m pip install --user requests==2.25.1
python3 -m pip install --user obspy==1.2.2
python3 -m pip install --user pandas==1.1.5
python3 -m pip install --user shapely==1.7.1
python3 -m pip install --user fiona==1.8.19
python3 -m pip install --user openpyxl==3.0.7
python3 -m pip install --user cartopy==0.19.0 
python3 -m pip install --user sklearn==0.24.2
```



