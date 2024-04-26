from lib import gps_parser
import datetime

def test_nmea_1():
    points = gps_parser.get_lat_lon_time_from_nmea('nmea1.nmea')
    assert (points[0].timestamp == datetime.datetime(2024, 4, 21, 13, 16, 15, 600000, tzinfo=datetime.timezone.utc))
    assert (points[0].lat == 46.96461558833333)
    assert (points[0].long == -1.3067823766666666)
    assert (points[0].alt == 43.613)
    assert (points[0].gps_quality == gps_parser.GpsQuality.RTK_FIXED)  
    assert (points[0].horizontal_error == 0.01) 
    assert (points[0].pdop == 0.95)

def test_nmea_2():
    points = gps_parser.get_lat_lon_time_from_nmea('nmea1.nmea')
    assert (len(points) == 2)
    assert (points[1].timestamp == datetime.datetime(2024, 4, 21, 13, 16, 17, 600000, tzinfo=datetime.timezone.utc))
    assert (points[1].lat == 46.964761663333334)
    assert (points[1].long == -1.306697725)
    assert (points[1].alt == 43.068)
    assert (points[1].gps_quality == gps_parser.GpsQuality.RTK_FIXED)  
    assert (points[1].horizontal_error == 0.01) 
    assert (points[1].pdop == 0.95)
