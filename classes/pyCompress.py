"""
Project: Parallel.Archive
Date: 2/23/17 9:28 AM
Author: Demian D. Gomez

Not really used for the moment...
"""

import magic
import zipfile
import gzip

class Compress():

    def __init__(self,file,dest):

        pymagic  = magic.Magic(uncompress=False)
        filetype = pymagic.from_file(file)

        if 'zip archive' in filetype.lower():
            file = zipfile.ZipFile(file)
            file.extractall(dest)

        elif 'gzip' in filetype.lower():
            with gzip.open(dest, 'rt', encoding='utf8', errors='ignore') as f:
                sp3file = f.read()
