#!/usr/bin/env python
# -*- coding: utf-8 -*-

# celui là il est pour chercher à corriger le bug des timestamps compris entre 0 et 100 millisecondes

import os, sys, datetime
import pprint
import argparse
#from datetime import datetime
from dateutil.tz import tzlocal
from lib_temp.exif_read import ExifRead as EXIF
from lib_temp.exif_write import ExifEdit

def arg_parse():
    parser = argparse.ArgumentParser(
        description="Fix the Gopro timestamp drift, and fix the timestamp with a missing 0 in front of the subsectimeoriginal value"
    )
    parser.add_argument(
        "paths",
        nargs="+",
        help="paths to the images folders",
    )
    parser.add_argument(
        "-n",
        "--nowrite",
        help="don't write the new timestamp in the image",
        action="store_true",
        default=False,
    )
    parser.add_argument(
        "-r",
        "--recursive",
        help="search images in subdirectory",
        action="store_true",
        default=False,
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version="release 0.1"
    )
    args = parser.parse_args()
    print(args)
    return args

def print_list(list):
    for i, image in enumerate(list):
        print(i, image)

def list_images(directory):
    ''' 
    Create a list of image tuples sorted by capture timestamp.
    @param directory: directory with JPEG files 
    @return: a list of image tuples with time, directory, lat,long...
    '''

    file_list = [os.path.join(os.path.abspath(directory), file) for file in os.listdir(directory) if file.lower().endswith(".jpg")]
    if len(file_list) == 0:
        print("No image found!")
        return
    files = []
    # get DateTimeOriginal data from the images and sort the list by timestamp
    for filepath in file_list:
        metadata = EXIF(filepath)
        #metadata.read()
        try:
            t = metadata.extract_capture_time()
            #print(t)
            #print(type(t))
            #s = metadata["Exif.Photo.SubSecTimeOriginal"].value
            files.append((filepath, t))
        except KeyError as e:
            # if any of the required tags are not set the image is not added to the list
            print("Skipping {0}: {1}".format(filename, e))
    
    files.sort(key=lambda timestamp: timestamp[1])
    #print_list(files)
    return files

def big_pic_delta(image_list, delta, file_destination): #check if path is ok
    print("delta est", delta)
    image_with_new_timestamp_list=[]
    for i,image in enumerate(image_list):
        new_fulltime= image[1] + datetime.timedelta(seconds=(i*(delta-1)))
        new_datetimeoriginal= new_fulltime.replace(microsecond=0)
        new_subsectimeoriginal="%.6d"%(new_fulltime.microsecond)
        image_with_new_timestamp_list.append((image[0],new_datetimeoriginal, new_subsectimeoriginal))
        print (image[1], 'new time is', new_datetimeoriginal, 'subsec is', new_subsectimeoriginal)
    #print(image_with_new_timestamp_list)
    #print('type de', image_with_new_timestamp_list[0][2], " est ", type(image_with_new_timestamp_list[0][2]))

    ###write_metadata(image_with_new_timestamp_list) #write the new timestamp

    #moving files
    
    if not os.path.exists(file_destination):
        os.makedirs(file_destination)
    for image in image_list:
        path , filename = os.path.split(image[0])
        out_file=file_destination+'/'+filename
        print("moving ", filename, "to ", file_destination)
        os.rename(image[0],out_file)

def interpolate_timestamp(image_list, delta):
    print("delta est", delta)
    image_with_new_timestamp_list=[]
    gap0=next((i for i, v in enumerate(image_list) if v[2] == 0), None)
    if gap0:
        #ajouter 1 seconde à image[gap0]
        image_list[gap0] = (image_list[gap0][0], (image_list[gap0][1] + datetime.timedelta(seconds=1)))
 
    #debug
    #if delta < 1:
     #   import pdb; pdb.set_trace()
        
    for i,image in enumerate(image_list):
        new_fulltime= image_list[0][1] + datetime.timedelta(seconds=(i*delta))
        new_datetimeoriginal= new_fulltime.replace(microsecond=0)
        new_subsectimeoriginal="%.6d"%(new_fulltime.microsecond)
        image_with_new_timestamp_list.append((image[0],new_datetimeoriginal, new_subsectimeoriginal))
        print (image[1], 'new time is', new_datetimeoriginal, 'subsec is', new_subsectimeoriginal)
    #print(image_with_new_timestamp_list)
    #print('type de', image_with_new_timestamp_list[0][2], " est ", type(image_with_new_timestamp_list[0][2]))

    write_metadata(image_with_new_timestamp_list) #write the new timestamp

def write_metadata(image_list):
    for image in image_list:
        #metadata = pyexiv2.ImageMetadata(image[0])
        metadata = ExifEdit(image[0])
        #metadata.read()
        #metadata["Exif.Photo.DateTimeOriginal"] = image[1]
        metadata.add_date_time_original(image[1])
        #metadata["Exif.Photo.SubSecTimeOriginal"] = image[2]
        #metadata.add_subsectimeoriginal(image[2])
        
        metadata.write()
        #print('Writing new timestamp to ', image[0])

def interpolate_fixed_timestamp(image_list, start_time=None, delta=0.5):
    if start_time == None:
        start_time = image_list[0][1]
    print("Timestamp de départ : ", start_time)
    image_with_new_timestamp_list = []
    for i, image in enumerate(image_list):
        new_fulltime= start_time + datetime.timedelta(seconds=(i*delta))
        new_datetimeoriginal= new_fulltime.replace(microsecond=0)
        new_subsectimeoriginal="%.6d"%(new_fulltime.microsecond)
        image_with_new_timestamp_list.append((image[0],new_datetimeoriginal, new_subsectimeoriginal))
        
 
def generate_group(a_list):
    group_list = []
    for i,j in enumerate(a_list):
        if j[2]<=1:
            group_list.append(j)
            
        elif (j[2]>1 and i > 0):
            #big_gap_list.append((i,j))
            print("gros gap:", i, j[0], j[2])
            if len(group_list) > 1:
                yield group_list
                group_list = []
                group_list.append(j)
            else:
                group_list = []
                group_list.append(j)
                
    yield group_list
            
def move_to_subfolder(file_list, destination_path):
    for file in file_list:
        os.replace(file[0], os.path.join(destination_path, os.path.basename(file[0])))

def main(path):
    images_list = list_images(path)
    metadata = EXIF(images_list[0][0])
    cam_model= metadata.extract_model()
    print("Cam model: ", cam_model)
    print("directory is: ", path)
    #pp = pprint.PrettyPrinter()
    #pp.pprint(images_list)
    starttime = images_list[0][1]
    if "HERO9" in cam_model:
        rtc_fix = 0.007
    elif "HERO11" in cam_model:
        #rtc_fix = 0.0039
        #rtc_fix = 0.002
        rtc_fix = 0.00164
    newlist = []
    #print("RTC fix: ", rtc_fix)
    #sys.exit()
    for image in images_list:
        #fix wrong subsecond
        #Not needed anymore since the latest GoPro Hero Firmware
        #img_timestamp = image[1].replace(microsecond=image[1].microsecond*10)
        img_timestamp = image[1]
        #fix rtc drift
        img_timestamp = img_timestamp - ((img_timestamp - starttime) * rtc_fix/100)
        print("ori : {} - new = {}".format(image[1], img_timestamp))
        newlist.append((image[0], img_timestamp))

    #for image in images_list:
        #fix wrong gopro subsecond value
        #image = (image[0], image[1].replace(microsecond=image[1].microsecond*10))
        #image = (image[0], "prout")

        #image[1] = image[1].replace(year=1976)
    
    #pp.pprint(newlist)
    if not args.nowrite:
        print("writing new timestamp")
        write_metadata(newlist)
                  
if __name__ == '__main__':
    args=arg_parse()
    for _path in args.paths:
        if args.recursive:
            for sub_path in [f.path for f in os.scandir(_path) if f.is_dir()]:
                print(sub_path)
                main(sub_path)
        elif not args.recursive:
            print(_path)
            main(_path)

    print("End of Script")
	

