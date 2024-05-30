#!/usr/bin/env python
# -*- coding: utf-8 -*-



import argparse
import datetime
import os
import sys
import time
import pyproj
import urllib.request, urllib.parse, urllib.error
import urllib.parse
import logging
import xml.etree.ElementTree as ET
from builtins import input
from collections import namedtuple

from dateutil.tz import tzlocal
from lib.exif_read import ExifRead as EXIF
from lib.exif_write import ExifEdit
from lib.geo import interpolate_lat_lon
import lib.gps_parser as gps_parser
import lib.nmea_filter as nmea_filter

logfile_name = "correlate.log"
# source for logging : http://sametmax.com/ecrire-des-logs-en-python/
# création de l'objet logger qui va nous servir à écrire dans les logs
logger = logging.getLogger()
# on met le niveau du logger à DEBUG, comme ça il écrit tout
logger.setLevel(logging.INFO)
 
# création d'un formateur qui va ajouter le temps, le niveau
# de chaque message quand on écrira un message dans le log
formatter = logging.Formatter('%(asctime)s :: %(levelname)s :: %(message)s')
# création d'un handler qui va rediriger une écriture du log vers
# un fichier
file_handler = logging.FileHandler(logfile_name, 'w')
# on lui met le niveau sur DEBUG, on lui dit qu'il doit utiliser le formateur
# créé précédement et on ajoute ce handler au logger
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)
 
# création d'un second handler qui va rediriger chaque écriture de log
# sur la console
stream_handler = logging.StreamHandler()
stream_handler.setLevel(logging.INFO)
logger.addHandler(stream_handler)

Master_Picture_infos = namedtuple('Picture_infos', ['path', 'DateTimeOriginal', 'SubSecTimeOriginal', 'Latitude', 'Longitude', 'Ele', 'Gps_quality', 'Gps_Horizontal_error', 'Gps_DateTime'])
Picture_infos = Master_Picture_infos(path=None, DateTimeOriginal=None, SubSecTimeOriginal=None, Latitude=None, Longitude=None, Ele=None, Gps_quality=None, Gps_Horizontal_error=None, Gps_DateTime=None)
New_Picture_infos = namedtuple('New_Picture_infos',
                               ['path', 'DateTimeOriginal', 'SubSecTimeOriginal', "New_DateTimeOriginal",
                                "New_SubSecTimeOriginal", "Longitude", "Latitude", "Ele", "ImgDirection", 'Gps_quality', 'Gps_Horizontal_error'])
log_infos = namedtuple('log_infos',
                       ['log_timestamp', 'action', 'return_timestamp', 'time_to_answer', 'cam_return', 'pic_number', ])


               
class BraceMessage(object):
    """This class here to use the new-style formating inside the logger. More details here :
    https://docs.python.org/3/howto/logging-cookbook.html#formatting-styles
    """
    def __init__(self, fmt, *args, **kwargs):
        self.fmt = fmt
        self.args = args
        self.kwargs = kwargs

    def __str__(self):
        return self.fmt.format(*self.args, **self.kwargs)

__ = BraceMessage

def list_geoimages(directory):
    """
    Create a list of image tuples sorted by capture timestamp.
    @param directory: directory with JPEG files
    @return: a list of image tuples with time, directory, lat,long...
    """
    file_list = []
    for root, sub_folders, files in os.walk(directory):
        file_list += [os.path.join(root, filename) for filename in files if filename.lower().endswith(".jpg")]

    files = []
    # get DateTimeOriginal data from the images and sort the list by timestamp
    for filepath in file_list:
        metadata = EXIF(filepath)
        try:
            t = metadata.extract_capture_time()
            s = int(t.microsecond / 1000000)
            gps_t = metadata.extract_gps_time()
            geo = metadata.extract_geo()
            lat = geo.get("latitude")
            lon = geo.get("longitude")
            ele = geo.get("altitude")
            files.append(Picture_infos._replace(path=filepath, DateTimeOriginal = t, SubSecTimeOriginal = s,
                                                                Latitude = lat, Longitude = lon, Ele = ele, Gps_DateTime = gps_t))

        except KeyError as e:
            # if any of the required tags are not set the image is not added to the list
            print("Skipping {0}: {1}".format(filepath, e))

    files.sort(key=lambda file: file.DateTimeOriginal)
    # print_list(files)
    return files


def write_metadata(image_lists):
    """
    Write the exif metadata in the jpeg file
    :param image_lists : A list in list of New_Picture_infos namedtuple
    """
    for image_list in image_lists:
        for image in image_list:
            #TODO dans ces if, chercher pourquoi j'ai '' comme valeur, au lieu de None, ce qui
            #rendrait la condition plus lisible (if image.Latitude is not None:)
            # metadata = pyexiv2.ImageMetadata(image.path)
            metadata = ExifEdit(image.path)
            # metadata.read()
            #metadata.add_date_time_original(image.DateTimeOriginal)
            # metadata.add_subsec_time_original(image.New_SubSecTimeOriginal)
            
            #if image.Latitude != "" and image.Longitude != "":
                #import pdb; pdb.set_trace()
            #    metadata.add_lat_lon(image.Latitude, image.Longitude)
                
            #if image.ImgDirection != "":
            #    metadata.add_direction(image.ImgDirection)
                
            #if image.Ele != "" and image.Ele is not None:
            #    metadata.add_altitude(image.Ele)
            if image.Gps_Horizontal_error is None and image.Gps_quality is None:
                print('Skipping ', image.path)
                continue
            if image.Gps_Horizontal_error is not None and image.Gps_Horizontal_error != "":
                metadata.add_gps_horizontal_error(image.Gps_Horizontal_error)
            if image.Gps_quality is not None and image.Gps_quality >= gps_parser.GpsQuality.DGPS:
                metadata.add_gps_differential(1)
            if image.Gps_quality is not None and image.Gps_quality < gps_parser.GpsQuality.DGPS:
                metadata.add_gps_differential(0)
            metadata.add_gps_datum("EPSG:9777") #RGF93

            metadata.write()
            print('Writing new Exif metadata to ', image.path)


def filter_images(piclists):
    """
    Filter the image lists to remove the "False" and "path=None" items
    :param piclists: A list of list of Picture_infos namedtuple
    :return: The same lists, but filtered
    """
    for i, piclist in enumerate(piclists):
        piclist = [j for j in piclist if type(j) != bool]
        piclist = [j for j in piclist if j.path is not None]
        piclists[i] = piclist

    return piclists


def geotag_from_gpx(piclist, gpx_file, offset_time=0, offset_bearing=0, offset_distance=0, timesource='Exif_DateTimeOriginal'):
    """This function will try to find the location (lat lon) for each pictures in each list, compute the direction
    of the pictures with an offset if given, and offset the location with a distance if given. Then, these
    coordinates will be added in the New_Picture_infos namedtuple.
    :param piclist:
    :param gpx_file: a gpx or nmea or pos file path
    :param offset_time: time offset between the gpx/nmea file, and the image's timestamp
    :param offset_bearing: the offset angle to add to the direction of the images (for side camera)
    :param offset_distance: a distance (in meter) to move the image from the computed location. (Use this setting to
    not have all the images from a multicam setup at the same exact location
    :return: nothing, the function update the New_Picture_infos namedtuple inside the lists"""
    now = datetime.datetime.now(tzlocal())
    
    if timesource == 'Exif_DateTimeOriginal':
        print("Your local timezone is {0}, if this is not correct, your geotags will be wrong.".format(
        now.strftime('%Y-%m-%d %H:%M:%S %z')))
    elif timesource == 'Exif_GpsDateTime':
        print("Using Exif GpsDateTime (UTC)")

    # read gpx file to get track locations
    #if gpx_file.lower().endswith(".gpx"):
    #    gpx = gps_parser.get_lat_lon_time_from_gpx(gpx_file)
    if gpx_file.lower().endswith(".nmea"):
        filtered_file = nmea_filter.filter_nmea(gpx_file)
        gpx = gps_parser.get_lat_lon_time_from_nmea(filtered_file.fileno())
    elif gpx_file.lower().endswith(".pos"):
        gpx = gps_parser.get_lat_lon_time_from_rtklib_pos(gpx_file)
    else:
        print("\nWrong gnss file! It should be a .nmea or .pos file.")
        sys.exit()

    #for piclist, offset_bearing in zip(piclists, offset_bearings):
    start_time = time.time()
    print("===\nStarting geotagging of {0} images using {1}.\n===".format(len(piclist), gpx_file))

    # for filepath, filetime in zip(piclist.path, piclist.New_DateTimeOriginal):
    for i, pic in enumerate(piclist):
        # add_exif_using_timestamp(filepath, filetime, gpx, time_offset, bearing_offset)
        # metadata = ExifEdit(filename)
        #import pdb; pdb.set_trace()
        if timesource == 'Exif_DateTimeOriginal':
            t = pic.DateTimeOriginal - datetime.timedelta(seconds=offset_time)
            t = t.replace(tzinfo=tzlocal()) # <-- TEST pour cause de datetime aware vs naive
        elif timesource == 'Exif_GpsDateTime':
            t = pic.Gps_DateTime

        try:
            lat, lon, bearing, elevation, hor_err, gps_quality = interpolate_lat_lon(gpx, t, max_dt=0, max_points_dt=1)
            #removed already consumed gpx points
            cp_gpx = list(gpx)
            gpx_length = len(gpx)
            for j,point in enumerate(cp_gpx):
                if j+2 < gpx_length and cp_gpx[j].timestamp < t and cp_gpx[j+1].timestamp < t:
                    gpx.pop(0)
                else:
                    break
            corrected_bearing = (bearing + offset_bearing) % 360
            # Apply offset to the coordinates if distance_offset exists
            if offset_distance != 0:
                #new_Coords = LatLon(lat, lon).offset(corrected_bearing, offset_distance / 1000)
                #lat = new_Coords.lat.decimal_degree
                #lon = new_Coords.lon.decimal_degree
                lon, lat, unusedbackazimuth = (pyproj.Geod(ellps='WGS84').fwd(lon, lat, corrected_bearing, offset_distance))
            # Add coordinates, elevation and bearing to the New_Picture_infos namedtuple
            piclist[i] = pic._replace(Longitude=lon, Latitude=lat, Ele=elevation, Gps_Horizontal_error=hor_err, Gps_quality=gps_quality)

        except ValueError as e:
            print("Skipping {0}: {1}".format(pic.path, e))
            
        except TypeError as f:
            print("Skipping {0}: {1} - {2}".format(pic.path, f, i))

    print("Done geotagging {0} images in {1:.1f} seconds.".format(len(piclist), time.time() - start_time))

def arg_parse():
    """ Parse the command line you use to launch the script
    """
    parser = argparse.ArgumentParser(description="Script to add gps accuracy in exif images metadata")
    parser.add_argument('--version', action='version', version='0.2')
    parser.add_argument("source", nargs="?",
                        help="Path source of the folders with the pictures. Without this parameter, "
                             "the script will use the current directory as the source", default=os.getcwd())
    parser.add_argument("-g", "--gpxfile", help="Path to the nmea/pos file. Without this parameter, "
                                                "the script will search in the current directory")
    parser.add_argument("-t", "--time_offset",
                        help="Time offset between GPX and photos. If your camera is ahead by one minute, time_offset is 60.",
                        default=0, type=float)
    parser.add_argument('-s', "--timesource", help="Choose source time for correlation, Exif_DateTimeOriginal (default) or Exif_GpsDateTime", type=str, default='Exif_DateTimeOriginal')
    parser.add_argument("-w", "--write_exif", help="Ask to write the new exif tags in the images", action="store_true")
    parser.add_argument('-v', '--verbose', help="Display verbose informations", action='store_true')

    args = parser.parse_args()
    print(args)
    return args

def find_file(directory, file_extension):
    """Try to find the files with the given extension in a directory
    :param directory: the directory to look in
    :param file_extension: the extension (.jpg, .gpx, ...)
    :return: a list containing the files found in the directory"""
    file_list = []
    for root, sub_folders, files in os.walk(directory):
        file_list += [os.path.join(root, filename) for filename in files if filename.lower().endswith(file_extension)]
    
    # removing correlate.log from the result list
    # TODO Sortir le choix du ou des fichiers de cette fonction. Cela devrait se faire ailleurs
    # par exemple dans main.
    file_list = [x for x in file_list if "correlate.log" not in x]
    if len(file_list) == 1:
        file = file_list[0]
        print("{0} : {1} will be used in the script".format(file_extension, file))
    elif len(file_list) > 1:
        file = file_list[0]
        print("Warning, more than one {0} file found".format(file_extension))
        print("{0} : {1} will be used in the script".format(file_extension, file))
    elif len(file_list) == 0:
        file = None
        print("Warning, no {0} file found".format(file_extension))

    return file


def find_directory(working_dir, strings_to_find):
    """Try to find the folders containing a given string in their names
    :param working_dir: The base folder to search in
    :param strings_to_find: a list of strings to find in the folder's names
    :return: a list of folder with the string_to_find in their name"""
    images_path = []
    dir_list = [i for i in os.listdir(working_dir) if os.path.isdir(i)]
    for string in strings_to_find:
        try:
            idx = [i.lower() for i in dir_list].index(string.lower())
            images_path.append(os.path.abspath(os.path.join(working_dir, dir_list[idx])))
        except ValueError:
            print("I can't find {0}".format(string))
            images_path.append("none")
            #sys.exit()
    return images_path

if __name__ == '__main__':
    # Parsing the command line arguments
    args = arg_parse()

    # Trying to find a nmea file in the working directory if none is given in the command line
    if args.gpxfile is None:
        print("=" * 30)
        args.gpxfile = find_file(args.source, "nmea")
    # Or a gpx file if there is no nmea file
    if args.gpxfile is None:
        args.gpxfile = find_file(args.source, "gpx")
    # Or a pos file if there is no gpx file
    if args.gpxfile is None:
        args.gpxfile = find_file(args.source, "pos")

    if args.gpxfile is None:
        print("No gpx/nmea file found... Exiting...")
        sys.exit()

    # Searching for all the jpeg images
    piclist = list_geoimages(args.source)
    
    #cam_group.filter_images(data=True)
    #import pdb; pdb.set_trace()
    print("=" * 80)
    geotag_from_gpx(piclist, args.gpxfile, args.time_offset, timesource=args.timesource)
    print("=" * 80)

    if args.verbose:
        for pic in piclist:
            print(pic.path, pic.Gps_Horizontal_error, pic.Gps_quality)
    # Write the new exif data in the pictures.
    print("=" * 80)

    if args.write_exif:
        #user_input = input("Write the new exif data in the pictures? (y or n) : ")
        #if user_input == "y":
            #remove pictures without lat/long
            #cam_group.filter_images(latlon = True)
        write_metadata([piclist])

print("End of correlation")