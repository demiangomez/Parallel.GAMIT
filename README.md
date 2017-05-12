# Parallel.GAMIT
# Author: Demián D. Gómez
Python wrapper to parallelize GAMIT executions.

Parallel.GAMIT is a Python software solution for parallel GPS processing of large regional or global networks. It also incorporates a metadata and RINEX data management tool that guarantees a consistent archive. It relies on Postgres SQL (https://www.postgresql.org/) to store station metadata and the Natural Resources of Canada Precise-Point-Positioning (NRCAN PPP) software (not included in this repository) to obtain reliable daily a-priori coordinates for GAMIT.

The software is divided into two modules: Parallel.GAMIT (PG) and Parallel.PPP (PP). PG requires all GAMIT-GLOBK (http://www-gpsg.mit.edu/~simon/gtgk/) dependencies installed in the processing nodes. PP requires NRCAN's PPP (http://www.nrcan.gc.ca/earth-sciences/geomatics/geodetic-reference-systems/tools-applications/10925#ppp) and several other dependencies detailed later in this document. Although PP was designed to use NRCAN's PPP, it can be easily changed to use any other open source PPP software such as RTKLIB (http://www.rtklib.com/), although this has not been tested.

PG uses Parallel Python to create Python pickles that are sent to local or remote nodes for execution. PG has the ability to split a network of GPS stations into subnetworks for processing in GAMIT (when the network is larger than 60 or 80 stations, depending on PG's configuration). The parallel execution is performed per day-subnetwork. In other words, a GAMIT pickle is built for each subnetwork-day in the processing and sent to the available nodes. At the end of each PG run, the subnetworks are combined with GLOBK and inserted as records in the Postgres database for later use. Some routines (such as the SINEX parser) are modified versions of the code from @softwarespartan (https://github.com/softwarespartan).

PP is a Python wrapper for the NRCAN PPP (not included in this repository) which uses the same Postgres SQL database to store the daily PPP solutions and medatadata of all station-days in the GPS archive. Some of the abilities of PP are:

- Scan a directory structure containing RINEX files and add them to the Postgres database (DB).
- Manage station metadata in GAMIT's station info format with consistency check of the records.
- Add new RINEX data to the database by geolocation, i.e. the data is incorporated not by station name but by running PPP and finding the corresponding station in the DB. This avoids problems with duplicate station codes and misidentified RINEX files.
- Handle ocean loading coefficients to correct the PPP coordinates and produce consistent time series before running GAMIT. This allows to find problems in the metadata BEFORE executing a long GAMIT run.
- Plot PPP time series using Bevis and Brown's (2014) extended trajectory model.
- Merge stations with different names that in reality are the same station (but renamed or moved a couple of meters), if desired.
- Merge, delete and add metadata directly from GAMIT station info files or from the pipeline using UNAVCO's GSAC (https://www.unavco.org/software/data-management/gsac/user-info/user-info.html)
- Both PP and PG tolerate station duplicates by using a three-letter network code. Although this is not supported by GAMIT, PG converts duplicate station codes (stored in different networks) to unique IDs that are used during processing, which are later converted back to the original names after the GLOBK combination of the subnetworks.
- Because all the information is stored in a relational database, PP and PG can handle very large datasets very easily (it has been tested with ~ 600,000 station-days but Postgres can easily handle millions of records in a regular home computer). Also, the relational database guarantees then consistency of the data and does not allow accidental duplicates in metadata.

PG and PP require the following dependencies:

- Python version > 2.7.13
- GAMIT-GLOBK: although PP does not use GAMIT in it's full, it relies on grdtab otl.grid and sh_rx2apr to obtain the ocean loading coefficients and station coordinates (when PPP fails to process a station-day). Bare in mind that sh_rx2apr need the following dependencies to run in a computer without GAMIT installed:
 - svdiff
 - svpos
 - tform
 - sh_rx2apr
 - doy
- teqc: the good-old RINEX quality check tool
- RinSum: one of the programs of GPSTk found in http://www.gpstk.org/bin/view/Documentation/WebHome
- pygressql: Python interface to connect to Postgres
- tqdm: a Python progress bar to show the processing 
- rnx2crx: RINEX to CRINEX
- crx2rnx: CRINEX to RINEX
- crz2rnx: this is a script modified by me which is based on the the scripts found in http://terras.gsi.go.jp/ja/crx2rnx.html with a few minor tweaks to handle the most common problems found in CRINEZ files.
- rnx2crz: the regular C-shell script
- compress/gzip
- Parallel Python (pp-1.6.5)
- matplotlib
- Numpy

