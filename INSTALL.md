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
python -m pip install numpy==1.16.0
python -m pip install wheel
python -m pip install PyGreSQL==5.0.4
python -m pip install scipy==1.2.0 
python -m pip install matplotlib==2.0.0 
python -m pip install tqdm==4.19.4
python -m pip install scandir==1.6
python -m pip install dispy==4.11.0
python -m pip install netifaces==0.10.9
python -m pip install psutil==5.6.3
python -m pip install pycos==4.8.11
python -m pip install dirsync==2.2.4
python -m pip install simplekml==1.3.1
python -m pip install hdf5storage==0.1.18
python -m pip install git+git://github.com/usgs/libcomcat.git@2.0.10
python -m pip install git+git://github.com/usgs/earthquake-impact-utils@0.8.27
python -m pip install requests==2.25.1
python -m pip install obspy==1.2.2
python -m pip install pandas==1.1.5
python -m pip install shapely==1.7.1
python -m pip install fiona==1.8.19
python -m pip install openpyxl==3.0.7
python -m pip install cartopy==0.19.0 
python -m pip install sklearn==0.24.2
# Required by pysftp/paramiko, newer versions require Rust to build
python -m pip install cryptography==3.3.2
python -m pip install paramiko==2.10.1
python -m pip install pysftp==0.2.9
```



