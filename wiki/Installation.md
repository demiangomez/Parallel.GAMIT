Parallel.GAMIT (PGAMIT) has two main components: the command line interface (CLI) which allows you to execute parallel jobs for GNSS processing, and the web interface (web-ui) which allows you to visualize results and manage station metadata. This installation guide covers how to install the CLI. The installation steps for the web-ui are detailed in the web-ui branch of this repository.

# First steps for installing PGAMIT: database server

To install PGAMIT you will, ideally, need two systems/computers: one to run the Postgresql database engine, and another one to run PGAMIT itself. While it is possible to run the database server on the same computer that you run the PGAMIT CLI, this is not recommended if you intend to obtain high efficiency processing. The installation of Postgresql is not covered in this guide, but you can find plenty of information online. The database basic structure can be found in [database/gnss_data_dump.sql](https://github.com/demiangomez/Parallel.GAMIT/blob/master/database/gnss_data_dump.sql) and this file must be used to deploy the database skeleton.

Once the database skeleton has been deployed, you need to configure (using pgadmin, Postgresql graphical user interface) the following tables:

- keys: this table contains the names of different keys that are used in PGAMIT. They are stored in this table for more flexibility. Download the following csv file and insert each row in your keys table: [keys.csv](https://github.com/user-attachments/files/20883810/keys.csv)

- rinex_tank_struct: this table contains the structure you will use for storing rinex files in your PGAMIT system. A recommended structure is to use `Level = 1 KeyCode = network; Level = 2 KeyCode = year; Level = 3 KeyCode = doy`. You can ignore any columns named api_id, since these will be auto generated. To download a csv with this proposed structure, click here: [rinex_tank_struct.csv](https://github.com/user-attachments/files/20883773/rinex_tank_struct.csv)

- antennas and receivers: these tables contain the allowed receivers and antennas (codes from the IGS) and provides a start point for the system. As you expand your PGAMIT installation, you will insert new models in these tables. Download the csv files with the basic antenna and receiver codes: [receivers.csv](https://github.com/user-attachments/files/20883887/receivers.csv) [antennas.csv](https://github.com/user-attachments/files/20883901/antennas.csv)

- gamit_htc: this table contains the horizontal and vertical offsets for each antenna and height code. You will insert more records here as new models appear. Download the csv file for this table and insert all the records: [gamit_htc.csv](https://github.com/user-attachments/files/20883967/gamit_htc.csv)

# Prerequisites for installing PGAMIT

In the following, we will assume that you are working with Linux (any flavor is fine) and that you have basic knowledge on installing and configuring this OS. To function, PGAMIT requires several external programs that are not distributed with the PGAMIT installation and you must ensure they are correctly installed and available in your PATH before running any PGAMIT program. 

> [!IMPORTANT]
> A program in the PATH will work from any directory and you can check this by typing `which [program]`. For example, if crx2rnx is correctly installed and you type `which crx2rnx`, your Linux shell should return something like `/home/demian/gg/gamit/bin/crx2rnx`. 

This guide does not cover the installation of each dependency, and you can find the installation instructions for each one here:
+ GAMIT/GLOBK: http://www-gpsg.mit.edu/gg/
+ GFZRNX: https://gnss.gfz-potsdam.de/services/gfzrnx
+ rnx2crx / crx2rnx: https://terras.gsi.go.jp/ja/crx2rnx.html (although this is also installed with GAMIT/GLOBK)
+ GPSPACE: https://github.com/demiangomez/GPSPACE (forked from https://github.com/lahayef/GPSPACE)

# Installing and setting up PGAMIT

Once you have installed the depencendies and they are working correctly, you can install PGAMIT using the following command:
```
pip install pgamit
```
This can be done in your system directly or using your favorite python environment manager. Make sure to use python 3.10. Once PGAMIT is installed, create a directory anywhere in your system. You will run PGAMIT from this directory and you can call this directory anything you want. Inside your execution directory, copy the following skeleton configuration file:
```
[postgres]
# information to connect to the database (self explanatory). Make sure to replace username and database with your database information
hostname = [your server fqdn]
username = gnss_data_osu
password = *************
database = gnss_data_osu

# This directory points to the location of the scripts used to download RAW data. If you don't know what this is yet, just create the directory and put its path here. You will learn about it later on.
format_scripts_path = /fs/project/gomez.124/resources/format_scripts

# set up the tanks for RINEX files, repository (where incoming RINEX files go), sp3 and brdc, and ionex files (required for GAMIT runs)
# valid keys for brdc and sp3 tanks
# $year, $doy, $month, $day, $gpsweek, $gpswkday
#
[archive]
# absolute location of the rinex tank
path = /fs/project/gomez.124/archive_osu
repository = /fs/project/gomez.124/repository_osu
# absolute path location of the ionex files
ionex = /fs/project/gomez.124/orbits/ionex/$year

# absolute location of the broadcast orbits
brdc = /fs/project/gomez.124/orbits/brdc/$year

# absolute location of the sp3 orbits
sp3 = /fs/project/gomez.124/orbits/sp3/$gpsweek

# this list should contain the hostnames of the computers you will use to run PGAMIT in parallel. If you are using just one computer, simply put the hostname or IP address of that machine
# parallel execution of certain tasks
node_list=u111,u112,u113,u114,u140,u141,u142,u143

# orbit center type precedence:
#  This section follows the IGS convention for orbit names: AC stands for Analysis Center, CS for campaign, and ST for solution type.
sp3_ac = COD,IGS
sp3_cs = OPS,R03,MGX
sp3_st = FIN,SNX,RAP

[otl]
# location of grdtab to compute OTL
grdtab = /fs/project/gomez.124/opt/gamit_10.71/gamit/bin/grdtab
# location of the grid to be used by grdtab
otlgrid = /fs/project/gomez.124/opt/gamit_10.71/tables/otl.grid
# model name used for OTL
otlmodel = FES2014b

[ppp]
# location of the PPP program structure. 
ppp_path = /fs/project/gomez.124/opt/PPP_NRCAN_1.10
ppp_exe = /fs/project/gomez.124/opt/PPP_NRCAN_1.10/source/ppp
institution = The Ohio State University
info = Division of Geodetic Science - Geodesy and Geodynamics Group (G2)
# the following list establishes a list of frames available for PPP. If you provide more than one, use commas to separate. Then create keys with the same name and establish the date ranges to use each frame.
frames = IGS20,
IGS20 = 1987_1,
# provide a list of ATX files in the same order as in "frames"
atx = /fs/project/gomez.124/resources/atx/igs20_2335_plus.atx
```

Once all these sections are configured, you are ready to start running PGAMIT.
