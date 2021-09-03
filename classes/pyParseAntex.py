"""
Project: Parallel.Archive
Date: 2/25/17 7:15 PM
Author: Demian D. Gomez
"""
from Utils import file_readlines

class ParseAntexFile():

    def __init__(self,filename):
        antex = file_readlines(filename)

        antennas = set()
        radomes  = set()

        for line in antex:
            if 'TYPE / SERIAL NO' in line:
                fields = line.split()
                if len(fields) <= 6:
                    antennas.add(fields[0])
                    radomes.add (fields[1])

        # make a unique list
        self.Antennas = list(antennas)
        self.Radomes  = list(radomes)
