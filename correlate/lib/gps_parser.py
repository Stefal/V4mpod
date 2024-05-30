#!/usr/bin/python

import sys
import os
import datetime
import time
from enum import IntEnum
from dataclasses import dataclass
from copy import deepcopy
from .geo import gpgga_to_dms, utc_to_localtime

import gpxpy
import pynmea2

@dataclass
class PointInfo:
    timestamp = None
    lat = None
    long = None
    alt = None
    gps_quality = None
    horizontal_error = None
    pdop = None

    def reset(self):
        self.timestamp = None
        self.lat = None
        self.long = None
        self.alt = None
        self.gps_quality = None
        self.horizontal_error = None
        self.pdop : int
    def __str__(self):
        return str("timestamp: {} - Latitude: {} - Longitude: {} - Altitude: {} - Gps Quality: {} - Hor. Error: {} - Pdop: {}".format(
                self.timestamp, \
                self.lat, \
                self.long, \
                self.alt, \
                self.gps_quality, \
                self.horizontal_error, \
                self.pdop,
                    )
                )

class GpsQuality(IntEnum):
    INVALID = 0
    MANUAL = 1
    SINGLE = 2
    DGPS = 3
    RTK_FLOAT = 4
    RTK_FIXED = 5
    PPP = 6


nmea_gps_qual = {0:GpsQuality.INVALID, 1:GpsQuality.SINGLE, 2:GpsQuality.DGPS, 4:GpsQuality.RTK_FIXED, 5:GpsQuality.RTK_FLOAT, 7:GpsQuality.MANUAL, 9:GpsQuality.DGPS}
pos_gps_qual = {'5':GpsQuality.SINGLE, '4':GpsQuality.DGPS, '2':GpsQuality.RTK_FLOAT, '1':GpsQuality.RTK_FIXED, '6':GpsQuality.PPP}



'''
Methods for parsing gps data from various file format e.g. GPX, NMEA, SRT.
'''


def get_lat_lon_time_from_gpx(gpx_file, local_time=True):
    '''
    Read location and time stamps from a track in a GPX file.

    Returns a list of tuples (time, lat, lon).

    GPX stores time in UTC, by default we assume your camera used the local time
    and convert accordingly.
    '''
    with open(gpx_file, 'r') as f:
        gpx = gpxpy.parse(f)

    points = []
    if len(gpx.tracks)>0:
        for track in gpx.tracks:
            for segment in track.segments:
                for point in segment.points:
                        
                    t = utc_to_localtime(point.time) if local_time else point.time
                    points.append( (t, point.latitude, point.longitude, point.elevation) )
                    
    '''if len(gpx.waypoints) > 0:
        for point in gpx.waypoints:
            t = utc_to_localtime(point.time) if local_time else point.time
            points.append( (t, point.latitude, point.longitude, point.elevation) )'''

    # sort by time just in case
    points.sort()


    return points


def get_lat_lon_time_from_nmea(nmea_file, local_time=True):
    '''
    Read location and time stamps from a track in a NMEA file.

    Returns a list of tuples (time, lat, lon).

    GPX stores time in UTC, by default we assume your camera used the local time
    and convert accordingly.
    '''

    gga_Talker_id = ("$GNGGA", "$GPGGA", "$GLGGA", "$GBGGA", "$GAGGA")
    rmc_Talker_id = ("$GNRMC", "$GPRMC", "$GLRMC", "$GBRMC", "$GARMC")
    gst_Talker_id = ("$GNGST", "$GPGST", "$GLGST", "$GBGST", "$GAGST")
    gsa_Talker_id = ("$GNGSA", "$GPGSA", "$GLGSA", "$GBGSA", "$GAGSA")
    
    with open(nmea_file, "r") as f:
        lines = f.readlines()
        lines = [l.rstrip("\n\r") for l in lines]

    # Get initial date
    date = None
    for l in lines:
        if any(rmc in l for rmc in rmc_Talker_id):
            data = pynmea2.parse(l, check=False)
            date = data.datetime.date()
            break
        
    if date is None:
            raise(Exception, "No initial date found")

    # Parse GPS trace
    points = []
    timestamp = prev_timestamp = None
    lat = long = alt = alt = gps_quality = horizontal_error = pdop = None
    new_point = PointInfo()
    for l in lines:
        if any(rmc in l for rmc in rmc_Talker_id):
            data = pynmea2.parse(l, check=False)
            date = data.datetime.date()

        if any(gga in l for gga in gga_Talker_id):
            data = pynmea2.parse(l, check=False)
            timestamp = datetime.datetime.combine(date, data.timestamp)
            lat, long, alt = data.latitude, data.longitude, data.altitude
            gps_quality = nmea_gps_qual.get(data.gps_qual, 'invalid')
            
        
        if any(gst in l for gst in gst_Talker_id):
            data = pynmea2.parse(l, check=False)
            timestamp = datetime.datetime.combine(date, data.timestamp)
            max_hor_err = max(data.std_dev_latitude, data.std_dev_longitude)
            horizontal_error = max_hor_err if max_hor_err > 0 else None

        if any(gsa in l for gsa in gsa_Talker_id):
            data = pynmea2.parse(l, check=False)
            pdop = float(data.pdop)

        #if timestamp and lat and lon and alt :
        #    points.append((timestamp, lat, lon, alt, hor_err, gps_quality))
        if timestamp != prev_timestamp:
            #print("prev {} - new {}".format(prev_timestamp, timestamp))
            if new_point.lat != None and lat != None:
                points.append(deepcopy(new_point))
                #print("Reset new point")
                new_point.reset()
                new_point.timestamp = timestamp
                new_point.lat = lat
                new_point.long = long
                new_point.alt = alt
                new_point.gps_quality = gps_quality
                #print("après reset, newpoint.lat ", new_point.lat)
                lat = long = alt = alt = gps_quality = horizontal_error = pdop = None
            prev_timestamp = timestamp
            continue
        #print("point lat: ", new_point.lat)
        if timestamp != None : new_point.timestamp = timestamp
        if lat != None: new_point.lat = lat
        if long != None: new_point.long = long
        if alt != None: new_point.alt = alt
        if gps_quality != None : new_point.gps_quality = gps_quality
        if horizontal_error != None : new_point.horizontal_error = horizontal_error
        if pdop != None : new_point.pdop = pdop
        #print("len points: ", len(points))
    #push last point
    if new_point.lat != None:
        points.append(deepcopy(new_point))     
    points.sort(key=lambda point: point.timestamp)
    return points

def get_lat_lon_time_from_rtklib_pos(pos_file, local_time=True):
    #find header
    with open(pos_file, 'r') as f:
        while True:
            line = f.readline()
            if not line:
                break
            if line.startswith("%  "):
                header = line[3:].split()
                timestamp_idx = header.index("DateTime") # use two list member
                lat_idx = header.index("latitude(deg)")
                long_idx = header.index("longitude(deg)")
                ele_idx = header.index("height(m)")
                quality_idx = header.index("Q")
                sat_nbr_idx = header.index("ns")
                sdn_idx = header.index("sdn(m)")
                sde_idx = header.index("sde(m)")
                sdu_idx = header.index("sdu(m)")
                age_idx = header.index("age(s)")
                ratio_idx = header.index("ratio")
                break
    #parse pos file
    with open(pos_file, 'r') as f:
        lines = f.readlines()
        lines = [l for l in lines if not l.startswith('%')]

    points = []
    for line in lines:
        new_point = PointInfo()
        sline = line.split()
        sline[timestamp_idx:timestamp_idx + 2] = [' '.join(sline[timestamp_idx:timestamp_idx + 2])]
        try:
            timestamp = datetime.datetime.strptime(sline[timestamp_idx], "%Y/%m/%d %H:%M:%S.%f")
            new_point.timestamp = timestamp.replace(tzinfo=datetime.timezone.utc)
            new_point.lat = float(sline[lat_idx])
            new_point.long = float(sline[long_idx])
            new_point.alt = float(sline[ele_idx])
            max_hor_err = max(float(sline[sdn_idx]), float(sline[sde_idx]))
            new_point.horizontal_error = max_hor_err if max_hor_err > 0 else None
            new_point.gps_quality = pos_gps_qual.get(sline[quality_idx], 'invalid')
            # TODO add Q for differential or not. Try yo use the same value as nmea
            if new_point.timestamp and new_point.lat and new_point.long and new_point.alt:
                points.append(new_point)
        except Exception as e:
            print("Skipping pos point: ",e)
    
    points.sort(key=lambda point: point.timestamp)
    return points


