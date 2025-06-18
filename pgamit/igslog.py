"""IGS log files parser
Adapted from:
Geoscience Australia
GNSS Analysis Toolbox (GNSSAnalysis) - IGS log file parser
under Apache License 2.0
https://github.com/GeoscienceAustralia/gnssanalysis/blob/main/gnssanalysis/gn_io/igslog.py
Revisions by Patrick D Smith, Jan 2025
"""

r"""
notes from PDS Jan 2025

_REGEX_ID_V1 appears to be missing the parenthesis between OR aka | operator:
    change from (?:Four\sCharacter\sID|Site\sID)
    to: ((?:Nine\sCharacter\sID)|(?:Four\sCharacter\sID)|(?:Site\sID))
    (ps. probably same issue in the regex for igs format v2)
    It also needs to allow 'Nine Character ID' in v1
    
extract_id_block() inside:
    id_block = [id_block[1].decode().upper(), id_block[2].decode().upper()] = 
    station code is second entry aka flip the id_block indices
    change to:
    id_block = [id_block[2].decode().upper(), id_block[1].decode().upper()] = 
    
    also add in force upper on the provided code when comparing id_block[1]
        if code != file_code:
        becomes if code != file_code.upper():

old _REGEX_LOC_V1
    2.+\W+City\sor\sTown\s+\:\s*(\w[^\(\n\,/\?]+|).*\W+
    State.+\W+Country\s+\:\s*([^\(\n\,\d]+|).*\W+(?:\s{25}.+\W+|)
                     __
new _REGEX_LOC_V1
    2.+\W+City\sor\sTown\s+\:\s*(\w[^\(\n\,/\?]+|).*\W+
    State.+\W+Country.+\:\s*([^\(\n\,\d]+|).*\W+(?:\s{25}.+\W+|)
                     __
    (appears to be the same issue in v2)

update parse_igs_log_data() to return a single array with 
    receiver and antenna entries for each time block
    new time block for each equipment changeout
    
example output info expected:
*SITE  Station Name      Session Start      Session Stop        Ant Ht  HtCod   Ant N    Ant E   Receiver Type         Vers                  SwVer  Receiver SN           Antenna Type     Dome   Antenna SN         
 OFLA  OFLA              2015 298  0  0  0  2015 298 23 59 59   0.0490  DHARP   0.0000   0.0000  LEICA GR25            3.11/6.403            0.00   1831129               LEIAS10          UNKN   13291092            mstinf: ../rinex/ofla298u.15o?

DDG: corrected some logic issues

"""

import logging
import re as _re
from typing import Union, List, Tuple
from datetime import datetime
import numpy as _np

logger = logging.getLogger(__name__)

# Defines what IGS Site Log format versions we currently support.
# Example logs for the first two versions can be found at:
# Version 1: https://files.igs.org/pub/station/general/blank.log
# Version 2: https://files.igs.org/pub/station/general/blank_v2.0.log

_REGEX_LOG_VERSION_1 = _re.compile(rb"""(site log\))""")
_REGEX_LOG_VERSION_2 = _re.compile(rb"""(site log v2.0)""")

_REGEX_ID_V1 = _re.compile(
    rb"""
    (?:Nine\sCharacter\sID|Four\sCharacter\sID|Site\sID)\s+\:\s*(\w{4}).*\W+
    .*\W+
    (?:\s{25}.+\W+|)
    IERS.+\:\s*(\w{9}|)
    """,
    _re.IGNORECASE | _re.VERBOSE,
)

_REGEX_ID_V2 = _re.compile(
    rb"""
    (?:Nine\sCharacter\sID|Site\sID)\s+\:\s*(\w{4}).*\W+
    .*\W+
    (?:\s{25}.+\W+|)
    IERS.+\:\s*(\w{9}|)
    """,
    _re.IGNORECASE | _re.VERBOSE,
)

_REGEX_LOC_V1 = _re.compile(
    rb"""
    2.+\W+City\sor\sTown\s+\:\s*(\w[^\(\n\,/\?]+|).*\W+
    State.+\W+Country.+\:\s*([^\(\n\,\d]+|).*\W+(?:\s{25}.+\W+|)
    Tectonic.+\W+(?:\s{25}.+\W+|).+\W+
    X.+\:\s*([\d\-\+\.\,]+|).*\W+
    Y.+\:\s*([\d\-\+\.\,]+|).*\W+
    Z.+\:\s*([\d\-\+\.\,]+|).*\W+
    Latitude.+\:\s*([\d\.\,\-\+]+|).*\W+
    Longitud.+\:\s*([\d\.\,\-\+]+|).*\W+
    Elevatio.+\:\s*([\d\.\,\-\+]+|).*
    """,
    _re.IGNORECASE | _re.VERBOSE,
)

_REGEX_LOC_V2 = _re.compile(
    rb"""
    2.+\W+City\sor\sTown\s+\:\s*(\w[^\(\n\,/\?]+|).*\W+
    State.+\W+Country\sor\sRegion\s+\:\s*([^\(\n\,\d]+|).*\W+(?:\s{25}.+\W+|)
    Tectonic.+\W+(?:\s{25}.+\W+|).+\W+
    X.{22}\:?\s*([\d\-\+\.\,]+|).*\W+
    Y.{22}\:?\s*([\d\-\+\.\,]+|).*\W+
    Z.{22}\:?\s*([\d\-\+\.\,]+|).*\W+
    Latitude.+\:\s*([\d\.\,\-\+]+|).*\W+
    Longitud.+\:\s*([\d\.\,\-\+]+|).*\W+
    Elevatio.+\:\s*([\d\.\,\-\+]+|).*
    """,
    _re.IGNORECASE | _re.VERBOSE,
)

_REGEX_REC = _re.compile(
    rb"""
    3\.\d+[ ]+Receiver[ ]Type\W+\:[ ]*([\+\-\w\ ]+|)\W+                           # Receiver Type line
    (?:Satellite[ ]System[ ]+\:[ ]*(?:(.+|)[ ]*[\r\n ]+[ ]+)|)      # Satellite System (normally present)
    Serial[ ]Number[ ]+\:[ ]*(\w+|).*\W+                                              # Receiver S/N line
    Firmware[ ]Version[ ]+\:[ ]*([\w\.\/ ]+|).*\W+                     # Receiver Firmware Version line
    ()()()                                             # 3 empty groups to align with antenna block
    (?:Elevation[ ]Cutoff\sSetting[ ]*\:[ ]*(?:.+|)|)\W+ # Elevation Cutoff Setting (normally present)
    Date[ ]Installed\W+\:[ ]*(\d{4}.+|).*\W+                                    # Date Installed line
    (?:Date[ ]Removed\W+\:(?:[ ]*(\d{4}.+|))|)                 # Date Removed line (normally present)
    """,
    _re.IGNORECASE | _re.VERBOSE,
)

_REGEX_ANT = _re.compile(
    rb"""
    4\.\d+[ ]+Antenna[ ]Type\W+:[\t ]*([\/\_\S]+|)[ \t]*(\w+|)[\,?.]*\W+            # Antenna Type line
    Serial[ ]Number[ ]+:[ ]*(\S+|\S+[ ]\S+|\S+[ ]\S+[ ]\S+|).*\W+                      # Antenna S/N line
    (?:Antenna[ ]Height.+\W+|)                                        # Antenna H (normally present)
    (?:Antenna[ ]Ref.+\W+|)                                  # Antenna Ref. Point (normally present)
    (?:Degree.+\W+|)                                             # Degree offset line (rarely used)
    (?:Marker->ARP[ ]Up.+\:[ ]*([\-\d\.]+|).*\W+
    Marker->ARP[ ]North.+\:[ ]*([\-\d\.]+|).*\W+
    Marker->ARP[ ]East.+\:[ ]*([\-\d\.]+|).*\W+|)               # Marker Ecc block (normally present)
    (?:Alignment.+[\n\r](?:[ ]{25}.+[\r\n]+|)\W+|)   # Alignment from True N line (normally present)
    Antenna[ ]Rad.+\:[ ]?(.+|)(?:\(.+\)|)\W+                               # Antenna Radome Type line
    (?:(?:(?:Rad|Antenna[ ]Rad).+\W+|)         # Radome S/N or Antenna Radome S/N (normally present)
    Ant.+[\n\r]+(?:[ ]{25}.+[\r\n]+|)\W+                                   # Antenna Cable Type line
    Ant.+[\n\r]+(?:[ ]{25}.+[\r\n]+|)\W+|)                               # Antenna Cable Length line
    Date[ ]Installed[ ]+\:[ ]*(\d{4}.+|).*\W+                                    # Date Installed line
    (?:Date[ ]Removed[ ]+\:(?:[ ]*(\d{4}.+|))|)                 # Date Removed line (normally present)
    """,
    _re.IGNORECASE | _re.VERBOSE,
)


class LogVersionError(Exception):
    """
    Log file does not conform to known IGS version standard
    """

    pass


def determine_log_version(data: bytes) -> str:
    """Given the byes object that results from reading an IGS log file, determine the version ("v1.0" or "v2.0")

    :param bytes data: IGS log file bytes object to determine the version of
    :return str: Return the version number: "v1.0" or "v2.0" (or "Unknown" if file does not conform to standard)
    """

    # Remove leading newline if present, to be safe, then truncate to first line
    first_line_bytes = data.lstrip(b"\n").split(b"\n")[0]

    result_v1 = _REGEX_LOG_VERSION_1.search(first_line_bytes)
    if result_v1:
        return "v1.0"

    result_v2 = _REGEX_LOG_VERSION_2.search(first_line_bytes)
    if result_v2:
        return "v2.0"

    raise LogVersionError(f"File does not conform to any known IGS Site Log version. First line is: {first_line_bytes}")


def extract_id_block(
    data: bytes, file_path: str, version: Union[str, None] = None
) -> Union[List[str], _np.ndarray]:
    """Extract the site ID block given the bytes object read from an IGS site log file

    :param bytes data: The bytes object returned from an open() call on a IGS site log in "rb" mode
    :param str file_path: The path to the file from which the "data" bytes object was obtained
    :param str version: Version number of log file (e.g. "v2.0") - determined if version=None, defaults to None
    :raises LogVersionError: Raises an error if an unknown version string is passed in
    :return bytes: The site ID block of tshe IGS site log
    
    PDS Jan 2025
    remove code&date input; only input file name (don't check log matches code later)
    """
    if version == None:
        version = determine_log_version(data)

    if version == "v1.0":
        _REGEX_ID = _REGEX_ID_V1
    elif version == "v2.0":
        _REGEX_ID = _REGEX_ID_V2
    else:
        raise LogVersionError(f"Incorrect version string '{version}' passed to the extract_id_block() function")

    id_block = _REGEX_ID.search(data)

    if id_block is None:
        logger.warning(f"ID rejected from {file_path}")
        return _np.array([]).reshape(0, 12)

    id_block = [id_block[1].decode().upper(), id_block[2].decode().upper()]  # no .groups() thus 1 and 2
    code = id_block[0]
    return id_block


def extract_location_block(data: bytes, file_path: str, version: Union[str, None] = None) -> _np.ndarray:
    """Extract the location block given the bytes object read from an IGS site log file

    :param bytes data: The bytes object returned from an open() call on a IGS site log in "rb" mode
    :param str file_path: The path to the file from which the "data" bytes object was obtained
    :param str version: Version number of log file (e.g. "v2.0") - will be determined from input data unless
        provided here.
    :raises LogVersionError: Raises an error if an unknown version string is passed in
    :return _np.ndarray: The location block of the IGS site log, as a numpy NDArray of strings
    """
    if version == None:
        version = determine_log_version(data)

    if version == "v1.0":
        _REGEX_LOC = _REGEX_LOC_V1
    elif version == "v2.0":
        _REGEX_LOC = _REGEX_LOC_V2
    else:
        raise LogVersionError(f"Incorrect version string '{version}' passed to extract_location_block() function")

    location_block = _REGEX_LOC.search(data)
    if location_block is None:
        logger.warning(f"LOC rejected from {file_path}")
        return _np.array([]).reshape(0, 12)
    return location_block


def extract_receiver_block(data: bytes, file_path: str) -> Union[List[Tuple[bytes]], _np.ndarray]:
    """Extract the location block given the bytes object read from an IGS site log file

    :param bytes data: The bytes object returned from an open() call on a IGS site log in "rb" mode
    :param str file_path: The path to the file from which the "data" bytes object was obtained
    :return List[Tuple[bytes]] or _np.ndarray: The receiver block of the data. Each list element specifies an receiver.
        If regex doesn't match, an empty numpy NDArray is returned instead.
    """
    receiver_block = _REGEX_REC.findall(data)
    if receiver_block == []:
        logger.warning(f"REC rejected from {file_path}")
        return _np.array([]).reshape(0, 12)

    for i, r in enumerate(receiver_block):
        receiver_block[i] = list(receiver_block[i])
        if not r[8]:
            receiver_block[i][8] = b'2100-12-31T23:59Z'
        
        receiver_block[i][7] = datetime.strptime(receiver_block[i][7].decode("utf-8"), '%Y-%m-%dT%H:%MZ')
        receiver_block[i][8] = datetime.strptime(receiver_block[i][8].decode("utf-8"), '%Y-%m-%dT%H:%MZ')
        
    return receiver_block


def extract_antenna_block(data: bytes, file_path: str) -> Union[List[Tuple[bytes]], _np.ndarray]:
    """Extract the antenna block given the bytes object read from an IGS site log file

    :param bytes data: The bytes object returned from an open() call on a IGS site log in "rb" mode
    :param str file_path: The path to the file from which the "data" bytes object was obtained
    :return List[Tuple[bytes]] or _np.ndarray: The antenna block of the data. Each list element specifies an antenna.
        If regex doesn't match, an empty numpy NDArray is returned instead.
    """
    antenna_block = _REGEX_ANT.findall(data)
    if antenna_block == []:
        logger.warning(f"ANT rejected from {file_path}")
        return _np.array([]).reshape(0, 12)
    
    for i, a in enumerate(antenna_block):
        antenna_block[i] = list(antenna_block[i])
        if not a[8]:
            antenna_block[i][8] = b'2100-12-31T23:59Z'
        
        antenna_block[i][7] = datetime.strptime(antenna_block[i][7].decode("utf-8"), '%Y-%m-%dT%H:%MZ')
        antenna_block[i][8] = datetime.strptime(antenna_block[i][8].decode("utf-8"), '%Y-%m-%dT%H:%MZ')
        
    return antenna_block


def parse_igs_log_data(data: bytes, file_path: str) -> Union[_np.ndarray, None]:
    """Given the bytes object returned opening a IGS log file, parse to produce an ndarray with relevant data

    :param bytes data: The bytes object returned from an open() call on a IGS site log in "rb" mode
    :param str file_path: The path to the file from which the "data" bytes object was obtained
    :param str file_code: Code from the file_path_array passed to the parse_igs_log() function
    :return Union[_np.ndarray, None]: Returns array with relevant data from the IGS log file bytes object,
        or `None` for unsupported version of the IGS Site log format.
    
    PDS Jan 2025
    remove code&date input; only input file name (don't check log matches code later)
    unified output has receiver and antenna entries for each time block
    simplified output with data pgamit needs
    """
       
    # PDS Jan 2025 edit
    # split antenna entries at receiver entry dates & vice versa
    #
    # receiver and antenna change-out is not always concurrent =>
    #   have different time blocks
    #   read both time blocks and make new entries for each sub blocks
    #
    #   eg figure:
    #   -------------------- >  time scale
    #   |       |       | receiver blocks
    #   |   |           | antenna blocks
    #   |   |   |       | output blocks
    
    # Determine the version of the IGS log based on the data, Warn if unrecognised
    try:
        version = determine_log_version(data)
    except LogVersionError as e:
        logger.warning(f"Error: {e}, skipping parsing the log file")
        return None

    # Extract information from ID block
    blk_id = extract_id_block(data=data, file_path=file_path, version=version)
    code = [blk_id[0]]  # Site code
    
    # Extract information from Location block
    blk_loc = extract_location_block(
        data=data,
        file_path=file_path,
        version=version,
    )
    blk_loc = [group.decode(encoding="utf8", errors="ignore") for group in blk_loc.groups()]
    # Combine ID and Location information:
    # PDS Jan 2025
    #blk_id_loc = _np.asarray([0] + blk_id + blk_loc, dtype=object)[_np.newaxis]
    blk_id_loc=_np.asarray([blk_id[0], blk_loc[0]], dtype=object)[_np.newaxis]
    
    # Extract and re-format information from receiver block:
    blk_rec = extract_receiver_block(data=data, file_path=file_path)
    blk_rec = _np.asarray(blk_rec)
    len_recs = blk_rec.shape[0]
    blk_rec = _np.concatenate(
        [
            _np.asarray([1] * len_recs, dtype=object)[:, _np.newaxis],
            _np.asarray(code * len_recs, dtype=object)[:, _np.newaxis],
            blk_rec,
        ],
        axis=1,
    )
    # Extract and re-format information from antenna block:
    blk_ant = extract_antenna_block(data=data, file_path=file_path)
    blk_ant = _np.asarray(blk_ant)
    len_ants = blk_ant.shape[0]
    blk_ant = _np.concatenate(
        [
            _np.asarray([2] * len_ants, dtype=object)[:, _np.newaxis],
            _np.asarray(code * len_ants, dtype=object)[:, _np.newaxis],
            blk_ant,
        ],
        axis=1,
    )
    
    # combine values for all install times of receiver block and antenna block
    break_ant=blk_ant[:,9]
    break_rec=blk_rec[:,9]
    break_times=_np.sort(_np.unique(_np.concatenate([break_ant,break_rec],axis=0)))
    
    # Split data by break_times & formatted with values we need in sql database
    blk_full=_np.zeros((len(break_times), 16), dtype=object)

    for i in range(len(break_times)):

        _start_time = break_times[i]
        
        # Find active antenna block
        _et_a = _np.where((blk_ant[:,9] <= _start_time) & (blk_ant[:,10] > _start_time))[0]
        _et_a = _et_a[0] if _et_a.size > 0 else -1  # -1 means no valid antenna found

        # Find active receiver block
        _et_r = _np.where((blk_rec[:,9] <= _start_time) & (blk_rec[:,10] > _start_time))[0]
        _et_r = _et_r[0] if _et_r.size > 0 else -1  # -1 means no valid receiver found

        if _et_a == -1 or _et_r == -1:
            logger.warning(f"Missing antenna or receiver data for time {_start_time}")
            continue  # Skip this interval or handle as needed
    
        session_end = min(blk_rec[_et_r,10], blk_ant[_et_a,10])
        
        blk_full[i,:]=_np.concatenate(
        [
            # station code
            blk_rec[_et_r,(1)],
            # station name
             _np.asarray(blk_loc[0]),
            # session start
             _np.asarray([_start_time],dtype=object),
            #session end
            _np.asarray(session_end,dtype=object),
            #Ant Ht,
            blk_ant[_et_a,(5)],
            #HtCod, 
            _np.asarray(['DHARP'],dtype=object),
            #Ant N, Ant E
            blk_ant[_et_a,(6,7)],
            # receiver type
            blk_rec[_et_r,(2)].decode("utf-8"),
            # rec firmware vers
            blk_rec[_et_r,(5)].decode("utf-8"),
            # rec SW vers
            _np.asarray([''],dtype=object),
            # rec S/N
            blk_rec[_et_r,(4)].decode("utf-8"),
            # antenna_type dome sn
            blk_ant[_et_a,2].decode("utf-8"),
            blk_ant[_et_a,3].decode("utf-8"),
            blk_ant[_et_a,4].decode("utf-8"),
            # comment            
            _np.asarray(["from IGS logfile: "+file_path],dtype=object)
        ], axis=None)
        
    return blk_full

    # Create unified information block:
    #blk_uni = _np.concatenate([blk_id_loc, blk_rec, blk_ant], axis=0)
    #file_path_arr = _np.asarray([file_path] * (1 + len_ants + len_recs))[:, _np.newaxis]
    #return _np.concatenate([blk_uni, file_path_arr], axis=1)


def parse_igs_log_file(file_path: _np.ndarray) -> Union[_np.ndarray, None]:
    """Reads igs log file and outputs ndarray with parsed data

    :param _np.ndarray file_path: Metadata on input log file. Expects ndarray of the form [PATH]
    :return Union[_np.ndarray, None]: Returns array with data from the parsed IGS log file, or `None` for unsupported
        version of the IGS Site log format.
        
    PDS Jan 2025
    remove code&date input; only input file name (don't check log matches code later)
    """
    with open(file_path, "rb") as file:
        data = file.read()

    return parse_igs_log_data(data=data, file_path=file_path)


if __name__ == "__main__":
    test_input = ('CHOY.log')
    result = parse_igs_log_file(test_input)
    fs = ' {:4.4}  {:16.16}  {:19.19}{:19.19}{:7.4f}  {:5.5}  {:7.4f}  {:7.4f}  {:20.20}  ' \
                     '{:20.20}  {:>5.5}  {:20.20}  {:15.15}  {:5.5}  {:20.20}'

    stninfo = []
    for row in result:
        stninfo.append(fs.format(
        row[0],  # station code
        row[1],  # station name
        row[2],  # session start
        row[3],  # session end
        float(row[4]),  # antenna height
        row[5],  # height code
        float(row[6]),  # antenna north offset
        float(row[7]),  # antenna east offset
        row[8],  # receiver type
        row[9],  # receiver firmware version
        row[10],  # software version
        row[11],  # receiver serial number
        row[12],  # antenna type
        row[13],  # radome
        row[14],  # antenna serial number
        row[15],  # comment
        ))
    
    for row in stninfo:
        print(row)
