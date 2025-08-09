# ArchiveService.py

**Overview**  
No description found in the ArgumentParser setup.

**Arguments**  
- `-purge`, `--purge_locks`:  
  Delete any network starting with '?' from the stations table and purge the contents of the locks table, deleting the associated files from `data_in`.

- `-np`, `--noparallel`:  
  Execute command without parallelization.

**Usage**  
```bash
./ArchiveService.py [options]
```

# AlterETM.py

**Overview**  
Program to alter the default ETM parameters for each station. The command can be executed on several stations at the same time. It is also possible to alter parameters for PPP and GAMIT simultaneously.

**Arguments**  
- `stnlist`:  
  List of networks/stations to process given in `[net].[stnm]` format or just `[stnm]` (separated by spaces; if `[stnm]` is not unique in the database, all stations with that name will be processed). Use keyword `all` to process all stations in the database. If `[net].all` is given, all stations from network `[net]` will be processed. Three-letter ISO 3166 international standard codes can be provided (always in uppercase) to select all stations within a country. If a station name is given using a `*` in front (e.g., `*igs.pwro` or `*pwro`), then the station will be removed from the list. If `*net.all` or ISO country code was used (e.g., `*igs.all` or `*ARG`), then remove the stations within this group. Wildcards are accepted using the regex postgres convention. Use `[]` to provide character ranges (e.g., `ars.at1[3-5]` or `ars.[a-b]x01`). Char `%` matches any string (e.g., `ars.at%`). Char `|` represents the OR operator that can be used to select one string or another (e.g., `ars.at1[1|2]` to choose at11 and at12). To specify a wildcard using a single character, use `_` (equivalent to `?` in POSIX regular expressions). Alternatively, a file with the station list can be provided (using all the same conventions described above). When using a file, `*` can be replaced with `-` for clarity in removing stations from `.all` lists.

- `-fun`, `--function_type`:  
  Specifies the type of function to work with. Can be polynomial (p), jump (j), periodic (q), or bulk earthquake jump removal (t). Each type accepts specific arguments:
  
  - `p {terms}`: Specifies the number of polynomial terms in the ETM, e.g., `terms = 2` for constant velocity, `terms = 3` for velocity + acceleration.
  - `j {action} {type} {date} {relax}`: Action can be `+` (add jump) or `-` (remove jump); `type = 0` is mechanical, `type = 1` is geophysical; `date` is the event date in accepted formats (e.g., `yyyy/mm/dd`, `yyyy_doy`, `gpswk-wkday`, `fyear`); and `relax` is a list of relaxation times for logarithmic decays (used only when `type = 1`, ignored when `type = 0`).
  - `q {periods}`: Specifies periods as a list in days (1 yr = 365.25).
  - `t {max_magnitude} {stack_name}`: Removes any earthquake with magnitude ≤ `max_magnitude` from the specified stations' trajectory models. If GAMIT solutions are invoked, provide the `stack_name` to obtain the ETMs of the stations.
  - `m {stack_name} [start_date] [end_date|days]`: Removes mechanical jumps between specified dates. If no dates are provided, removes all mechanical jumps. If only the first date is provided, removal starts from that date. To specify a duration, use `{start_date} {days}`.

- `-soln`, `--solution_type`:  
  Specifies the solution type (`ppp`, `gamit`) that this command will affect. If left empty, ETMs for both PPP and GAMIT will be affected. Use `gamit` to affect only GAMIT ETMs, or `ppp` for only PPP ETMs.

- `-print`, `--print_params`:  
  Prints the parameters present in the database for the selected stations.

**Usage**  
```bash
./AlterETM.py [options]
```

# DownloadSources.py

**Overview**  
No description found in the ArgumentParser setup.

**Arguments**  
- `stnlist`:  
  List of networks/stations to process given in `[net].[stnm]` format or just `[stnm]` (separated by spaces; if `[stnm]` is not unique in the database, all stations with that name will be processed). Use keyword `all` to process all stations in the database. If `[net].all` is given, all stations from network `[net]` will be processed. Three-letter ISO 3166 international standard codes can be provided (always in uppercase) to select all stations within a country. If a station name is given using a `*` in front (e.g., `*igs.pwro` or `*pwro`), then the station will be removed from the list. If `*net.all` or ISO country code was used (e.g., `*igs.all` or `*ARG`), then remove the stations within this group. Wildcards are accepted using the regex postgres convention. Use `[]` to provide character ranges (e.g., `ars.at1[3-5]` or `ars.[a-b]x01`). Char `%` matches any string (e.g., `ars.at%`). Char `|` represents the OR operator that can be used to select one string or another (e.g., `ars.at1[1|2]` to choose at11 and at12). To specify a wildcard using a single character, use `_` (equivalent to `?` in POSIX regular expressions). Alternatively, a file with the station list can be provided (using all the same conventions described above). When using a file, `*` can be replaced with `-` for clarity in removing stations from `.all` lists.

- `-date`, `--date_range`:  
  Date range to check given as `[date_start]` or `[date_start]` and `[date_end]`. Allowed formats are `yyyy.doy` or `yyyy/mm/dd`.

- `-win`, `--window`:  
  Download data from a given time window determined by `today - {days}`.

- `-np`, `--noparallel`:  
  Execute command without parallelization.

**Usage**  
```bash
./DownloadSources.py [options]
```

# ScanArchive.py

**Overview**  
Archive operations Main Program

**Arguments**  
- `stnlist`:  
  List of networks/stations to process given in `[net].[stnm]` format or just `[stnm]`.

- `-rinex`, `--rinex`:  
  Scan the current archive for RINEX 2/3 files and add them to the database if missing. Station list will be used to filter specific networks and stations if `{ignore_stnlist} = 0`. For example: `ScanArchive [net].all -rinex 0` will process all the stations in network `[net]`, but networks and stations have to exist in the database. If `ScanArchive [net].all -rinex 1`, the station list will be ignored, and everything in the archive will be checked (and added to the database if missing) even if networks and stations don’t exist. Networks and stations will be added if they don’t exist.

- `-otl`, `--ocean_loading`:  
  Calculate ocean loading coefficients using FES2004. To calculate FES2014b coefficients, use `OTL_FES2014b.py`.

- `-stninfo`, `--station_info`:  
  Insert station information to the database. If no arguments are given, scan the archive for station info files and use their location (folder) to determine the network to use during insertion. Only stations in the station list will be processed. If a filename is provided, scan that file only, in which case a second argument specifies the network to use during insertion (e.g., `-stninfo ~/station.info arg`). In cases where multiple networks are being processed, the network argument disambiguates station code conflicts.

- `-export`, `--export_station`:  
  Export a station from the local database that can be imported into another Parallel.GAMIT system using the `-import` option. One file is created per station in the current directory. If the `[dataless seed]` switch is passed (e.g., `-export true`), the export seed is created without data (only metadata, such as station info and station record).

- `-import`, `--import_station`:  
  Import a station from zip files produced by another Parallel.GAMIT system. Wildcards are accepted to import multiple zip files. If a station does not exist, use `{default net}` to specify the network where the station should be added. If `{default net}` does not exist, it will be created.

- `-get`, `--get_from_archive`:  
  Get the specified station from the archive and copy it to the current directory. Adjust it to match the station information in the database.

- `-ppp`, `--ppp`:  
  Run PPP on the RINEX files in the database. Append `[date_start]` and optionally `[date_end]` to limit the range of the processing. Allowed formats are `yyyy_doy`, `wwww-d`, `fyear`, or `yyyy/mm/dd`. Append the keyword `hash` to check PPP hash values against the station information records. If hash doesn’t match, recalculate the PPP solutions.

- `-rehash`, `--rehash`:  
  Check PPP hash against the station information hash. Rehash PPP solutions to match the station information hash without recalculating the PPP solution. Optionally append `[date_start]` and `[date_end]` to limit the rehashing time window. Allowed formats are `yyyy.doy` or `yyyy/mm/dd`.

- `-tol`, `--stninfo_tolerant`:  
  Specify a tolerance (in hours) for station information gaps (only for early survey data). Default is zero.

**Usage**  
```bash
./ScanArchive.py [options]
```

# PlotETM.py

**Overview**  
Plot ETM for stations in the database.

**Arguments**  
- `stnlist`:  
  List of stations to process, using `station_list_help()` for guidance.

- `-nop`, `--no_plots`:  
  Do not produce plots. Default is `False`.

- `-nom`, `--no_missing_data`:  
  Do not show missing days. Default is `False`.

- `-nm`, `--no_model`:  
  Plot time series without fitting a model.

- `-r`, `--residuals`:  
  Plot time series residuals. Default is `False`.

- `-dir`, `--directory`:  
  Directory to save the resulting PNG files. If not specified, defaults to the production directory.

- `-json`, `--json`:  
  Export ETM adjustment to JSON. Use `0` for ETM parameters only, `1` for time series without model, and `2` for both time series and model.

- `-gui`, `--interactive`:  
  Interactive mode: allows zooming and viewing the plot interactively.

- `-rj`, `--remove_jumps`:  
  Remove jumps from model and time series before plotting. Default is `False`.

- `-rp`, `--remove_polynomial`:  
  Remove polynomial terms from model and time series before plotting. Default is `False`.

- `-win`, `--time_window`:  
  Date range to window data. Can be specified as `yyyy/mm/dd`, `yyyy.doy`, or an integer `N` representing the last epoch minus `N`.

- `-q`, `--query`:  
  Dates to query the ETM. Specify "model" or "solution" to get the ETM value or daily solution (if exists). Output is in XYZ.

- `-gamit`, `--gamit`:  
  Plot the GAMIT time series, specifying which stack name to plot.

- `-lang`, `--language`:  
  Change the language of the plots. Default is English (`ENG`). Use `ESP` for Spanish.

- `-hist`, `--histogram`:  
  Plot histogram of residuals.

- `-file`, `--filename`:  
  Obtain data from an external source (filename). Accepts variables `{net}` and `{stn}` for multi-file processing. Specify file format with `-format`.

- `-format`, `--format`:  
  Specify order of fields in the input file, to be used with `--filename`. Format options include `gpsWeek`, `gpsWeekDay`, `year`, `doy`, `fyear`, `month`, `day`, `mjd`, `x`, `y`, `z`, `na`. Fields labeled `na` will be ignored.

- `-outliers`, `--plot_outliers`:  
  Plot an additional panel with outliers.

- `-dj`, `--detected_jumps`:  
  Plot unmodeled detected jumps.

- `-vel`, `--velocity`:  
  Output velocity in XYZ during query.

- `-seasonal`, `--seasonal_terms`:  
  Output seasonal terms in NEU during query.

- `-quiet`, `--suppress_messages`:  
  Quiet mode: suppress information messages.

**Usage**  
```bash
./PlotETM.py [options]
```

