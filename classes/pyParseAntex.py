"""
Project: Parallel.Archive
Date: 2/25/17 7:15 PM
Author: Demian D. Gomez
"""

class ParseAntexFile():

    def __init__(self,filename):

        try:
            with open(filename, 'r') as fileio:
                antex = fileio.readlines()
        except:
            raise

        self.Antennas = []
        self.Radomes  = []

        for line in antex:
            if 'TYPE / SERIAL NO' in line and len(line.split()) <= 6:
                self.Antennas.append(line.split()[0])
                self.Radomes.append (line.split()[1])

        # make a unique list
        self.Antennas = list(set(self.Antennas))
        self.Radomes  = list(set(self.Radomes))