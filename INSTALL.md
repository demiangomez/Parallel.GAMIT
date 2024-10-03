Installation
=================




To install PGAMIT create an environment in Python v3.10 after installing the pgadmin4-desktop dependencies:

```
sudo sh -c 'echo "deb https://ftp.postgresql.org/pub/pgadmin/pgadmin4/apt/focal/ pgadmin4 main" > /etc/apt/sources.list.d/pgadmin4.list && apt update'
sudo apt install pgadmin4-desktop
```

Once mamba is installed, the environment can be built (and activated) within
the base directory of Parallel.GAMIT:

```
python3 -m venv "pgamit"
pip install pgamit
```
All the Python dependencies should be automatically installed. You can run pgamit from any folder containing the .cfg file with the configuration to access the RINEX and orbits archive, database, etc. Commands are included in your PATH so you can execute, for example `PlotETM.py igm1`

> [!IMPORTANT]
> pgamit still requires access to some executables (and GAMIT) which are not installed by default. These programs, however, are not all needed if you are planning to just execute time series analysis. The external dependencies are:
> + GAMIT/GLOBK: http://www-gpsg.mit.edu/gg/
> + GFZRNX: https://gnss.gfz-potsdam.de/services/gfzrnx
> + rnx2crx / crx2rnx: https://terras.gsi.go.jp/ja/crx2rnx.html (although this is also installed with GAMIT/GLOBK)
> + GPSPACE: https://github.com/demiangomez/GPSPACE (forked from https://github.com/lahayef/GPSPACE)



