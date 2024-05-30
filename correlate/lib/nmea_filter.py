#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
from tempfile import SpooledTemporaryFile
import pynmea2
nmea_file = os.path.abspath('nmea_with_ubx.nmea')
talker_ids = ("$GN", "$GP", "$GL", "$GB", "$GA")

def filter_nmea(nmea_file):
    """
    Filter file and output only nmea messages
    Mainly useful for files containing mixing ubx and nmea messages
    return a Spooled temporary file
    """
    talker_ids = ("$GN", "$GP", "$GL", "$GB", "$GA")
    filtered_file = SpooledTemporaryFile()
    with open(nmea_file, 'r', encoding='ANSI') as nmea_file:
        for line in nmea_file.readlines():
            nmea = filter_nmea_line(line)
            try:
                if nmea:
                    pynmea2.parse(nmea)
                    nmea_line = (nmea + '\n').encode(encoding='ASCII')
                    #print(repr(nmea))
                    filtered_file.write(nmea_line)
            except (UnicodeEncodeError, pynmea2.ParseError):
                print("Skipping malformed sentence")
        filtered_file.seek(0)
        return filtered_file

def filter_nmea_line(line):
    for talker_header in talker_ids:
        idx = line.find(talker_header)
        #print(line)
        if idx >= 0:
            #print(repr(line[idx:]))
            #print(line[idx:].strip())
            return line[idx:].strip()

#new_file = filter_nmea(nmea_file)

#for i,line in enumerate(new_file.readlines()):
#    print(i,' : ', line)