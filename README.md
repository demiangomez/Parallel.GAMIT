# Parallel.GAMIT
## A Python wrapper to manage GNSS data and metadata and parallelize GAMIT executions
### Author: Demián D. Gómez

Parallel.GAMIT (PGAMIT) is a Python software solution for parallel GNSS processing of large regional or global networks. It incorporates a metadata and RINEX data management tool that guarantees a consistent archive. It relies on Postgres SQL (https://www.postgresql.org/) to store station metadata and the GPSPACE Precise-Point-Positioning (PPP) software (see installation instructions) to obtain reliable daily a-priori coordinates for GAMIT.

The software can be installed as a Python package (see `INSTALL.md`) allowing to import modules to perform time series analysis and extraction of trajectory parameters from the database.

PGAMIT also includes a backend (see branch web-ui-backend) and web frontend (see branch web-ui-frontend) that can be easily deployed to edit station related metadata (such as observation files and pictures) and processing metadata. The backend was developed in django and the frontend was developed using node.js.

PGAMIT uses dispy (https://github.com/pgiri/dispy) to create Python pickles that are sent to local or remote nodes for execution. PGAMIT has the ability to split a network of GNSS stations into subnetworks for processing in GAMIT (when the network is larger than 50 stations, depending on PGAMIT's configuration). The parallel execution is performed per day-subnetwork. In other words, a GAMIT pickle is built for each subnetwork-day being processed and sent to the available nodes. At the end of each PGAMIT run, the subnetworks are combined with GLOBK and inserted as records in the Postgres database for later use. Some routines (such as the SINEX parser) are modified versions of the code from @softwarespartan (https://github.com/softwarespartan).

Some of the tasks that PGAMIT can perform include:

- Scan a directory structure containing RINEX files and add them to the Postgres database.
- Manage station metadata in GAMIT's station info format with consistency check of the records.
- Add new RINEX data to the database by geolocation, i.e. the data is incorporated not by station name but by running PPP and finding the corresponding station in the DB. This avoids problems with duplicate station codes and misidentified RINEX files.
- Handle ocean loading coefficients to correct the PPP and GAMIT coordinates.
- Plot PPP time series using Bevis and Brown's (2014) extended trajectory model.
- Manage (i.e. add, merge, delete) GNSS stations.
- Parse zenith tropospheric delays and store them in the database.
- Stack the GAMIT solutions to produce regional or global reference frames following Bevis and Brown's (2014) and Gómez et al (2022).
- Station name duplicate-tolerance by using a three-letter network code. Although this is not supported by GAMIT, PGAMIT converts duplicate station codes (stored in different networks) to unique IDs that are used during processing, which are later converted back to the original names after the GLOBK combination of the subnetworks.
- Because all the information is stored in a relational database, PGAMIT can handle very large datasets easily (it has been tested with ~ 14M station-days but Postgres can easily handle more than 100 million records). Also, the relational database guarantees then consistency of the data and does not allow accidental duplicates in metadata.

