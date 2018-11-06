"""
Project: Parallel.Archive
Date: 02/16/2017
Author: Demian D. Gomez
"""

from scipy.io import FortranFile
import numpy as np
import os

# sequentially read the parameters needed to open the file
f = open('/home/demian/Desktop/temp/msirga.127', 'rb')
f.seek(24, os.SEEK_SET)
params = np.fromfile(f, dtype='i4', count=1)[0]

f.seek(24 + 4 + 20*params + 2*4*params + 2*8*params, os.SEEK_SET)
nsat = np.fromfile(f, dtype='i4', count=1)[0]

f.seek(24 + 4 + 20*params + 2*4*params + 2*8*params + 4 + 4*nsat, os.SEEK_SET)
nsite = np.fromfile(f, dtype='i4', count=1)[0]

f.seek(24 + 4 + 20*params + 2*4*params + 2*8*params + 4 + 4*nsat + 4 + 12*nsite, os.SEEK_SET)
nrfile = np.fromfile(f, dtype='i4', count=1)[0]

f.seek(24 + 4 + 20*params + 2*4*params + 2*8*params + 4 + 4*nsat + 4 + 12*nsite + 4 + 16*nrfile, os.SEEK_SET)
ntfile = np.fromfile(f, dtype='i4', count=1)[0]

f.close()

A = np.fromfile('/home/demian/Desktop/temp/msirga.127',
                np.dtype([('st', 'i4'),
                          ('iflag', 'i4'),
                          ('nwds', 'i4'),
                          ('nversn', 'i4'),
                          ('ndy', 'i4'),
                          ('nepch', 'i4'),
                          ('mtpart', 'i4'),
                          ('alabel', (np.string_, 20), params),
                          ('idms', 'i4', params),
                          ('islot1', 'i4', params),
                          ('aprval', 'float64', params),
                          ('adjust', 'float64', params),
                          ('nsat', 'i4'),
                          ('isat', 'i4', nsat),
                          ('nsite', 'i4'),
                          ('sitet', (np.string_, 12), nsite),
                          ('nrfile', 'i4'),
                          ('rfname', (np.string_, 16), nrfile),
                          ('ntfile', 'i4'),
                          ('tfname', (np.string_, 16), ntfile),
                          ('norb', 'i4')
                          ]))


