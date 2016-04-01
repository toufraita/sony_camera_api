__author__ = 'marc'

"""
Specific functions to control the X1000 camera to take pictures every 1 second and recover/delete them.
"""

import pysony
import time
import urllib2


def getIDsInRange(camera, date, time_begin=None, time_end=None):
    '''Function used to give the IDs (end of the Uri and urls) of files in a specified range. It is assumed that
    pictures (and only pictures) are taken every second. The format of uri for pictures is

    'image:content?contentId=index%3A%2F%2F1000%2F00000001-default%2F00008476-0000395A_33910_1_1000'
    --------------------------------cste----------------------------|-hexa1--|-hexa2--|deci1|-cste-
    --------------------------------cste----------------------------|-----------ID----------|-cste-

    with int(hexa1,16)=int(deci1), and hexa1, hexa2, deci1 inremented of 1 at each photo taken.

    The format of urls is

    http://192.168.122.1:8080/contentstransfer/orgjpeg/index%3A%2F%2F1000%2F00000001-default%2F00008476-0000395A_33910_1_1000
    -----------------------------------------cste---------------------------------------------|-----------ID----------|-cste-

    :param camera:
    :param date:
    :param time_begin:
    :param time_end:
    :return:
    '''

    # Recovering first file of the day
    # first_file=camera.getFilesList(date=date,stIdx=0,cnt=1)['result'][0][0]
    first_file = camera.getFilesList(date=date, stIdx=0, cnt=1)[0]

    # If no end time is specified, take the time of the last picture
    if not time_end:
        num_files = camera.getFilesCount(date=date)
        last_file = camera.getFilesList(date=date, stIdx=num_files - 1, cnt=1)[0]
        time_end = last_file['createdTime'][11:19]


    # Created Time an uri of the first file on date specified
    time_init = first_file['createdTime']
    uri_init = first_file['uri']

    # Conversion in seconds
    time_init = hmsToSec(time_init[11:19])

    # If no begin time is specified, take the time of first picture
    if not time_begin:
        time_begin = time_init
    # Otherwise convert in seconds
    else:
        time_begin = hmsToSec(time_begin)

    time_end = hmsToSec(time_end)

    duration_to_begin = time_begin - time_init
    duration_to_end = time_end - time_init

    # Identification numbers
    try:
        id_num = uri_init[64:94]
        hexa1_fst = int(id_num[0:8], 16)
        hexa2_fst = int(id_num[9:17], 16)
        deci1_fst = int(id_num[18:30].split('_')[0])
        assert hexa1_fst == deci1_fst
    except AssertionError:
        print("Format of identification number does not match hypothesis")
    except ValueError:
        print("Error : invalid litteral expression in identification numbers, could not be read")

    # ID numbers matching begin and end
    deci1_begin = deci1_fst + duration_to_begin
    deci1_end = deci1_fst + duration_to_end

    hexa2_begin = hexa2_fst + duration_to_begin
    hexa2_end = hexa2_fst + duration_to_end

    # Lists of IDs decimal numbers
    deci1 = range(deci1_begin, deci1_end + 1)
    hexa2 = range(hexa2_begin, hexa2_end + 1)

    hexa1 = [format(elt, '08X') for elt in deci1]
    hexa2 = [format(elt, '08X') for elt in hexa2]
    deci1 = [format(elt, 'd') for elt in deci1]

    # List of ID
    ID = ['{0}-{1}_{2}_1_1000'.format(h1, h2, d1) for h1, h2, d1 in zip(hexa1, hexa2, deci1)]

    return ID


def getUrisInRange(camera,date,time_begin=None,time_end=None,
                   cst_part='image:content?contentId=index%3A%2F%2F1000%2F00000001-default%2F'):
    '''
    Returns the Uris of photos taken within specified range. It is assumed that photos (and photos only) are taken
    continuously every second
    :param camera:
    :param date:
    :param time_begin:
    :param time_end:
    :param cst_part:
    :return:
    '''
    IDs=getIDsInRange(camera,date,time_begin,time_end)
    uris=[cst_part+ID for ID in IDs]

    return uris


def getUrlsInRange(camera,date,time_begin=None,time_end=None,
                   cst_part='http://192.168.122.1:8080/contentstransfer/orgjpeg/index%3A%2F%2F1000%2F00000001-default%2F'):
    '''
    Returns the Urls of photos taken within specified range. It is assumed that photos (and photos only) are taken
    continuously every second
    :param camera:
    :param date:
    :param time_begin:
    :param time_end:
    :param cst_part:
    :return:
    '''
    IDs=getIDsInRange(camera,date,time_begin,time_end)
    urls=[cst_part+ID for ID in IDs]

    return urls


def deleteFilesInRange(camera,date,time_begin,time_end):
    '''
    Delete the photos taken within the specified range. It is assumed that photos (and photos only) are taken
    continuously every second. Note that if getUrlsInRange provides wrong urls, it will not prevent the programme to
    delete the files matching the correct urls
    :param camera:
    :param date:
    :param time_begin:
    :param time_end:
    :return:
    '''

    uris=getUrisInRange(camera,date,time_begin,time_end)

    num_uris=len(uriss)
    cnt=num_uris//100
    rest=num_uris%100

    for i in range (0,cnt*100,100):
        camera.deleteContent({'url':uris[i:i+100]})

    cxh=cnt*100
    camera.deleteContent({'url':uris[cxh,cxh+rest]})


def saveFilesInRange(camera,date,time_begin,time_end,folder):
    '''
    Save the photos taken within the specified range. It is assumed that photos (and photos only) are taken
    continuously every second.
    :param camera:
    :param date:
    :param time_begin:
    :param time_end:
    :return:
    '''
    urls=getUrlsInRange(camera,date,time_begin,time_end)

    #Get time to name the files
    time_begin=hmsToSec(time_begin)
    time_end=hmsToSec(time_end)
    times=range(time_begin,time_end+1,1)
    times=[secToHms(t) for t in times]

    #Rename date
    date=date[0:4]+'-'+date[4:6]+'-'+date[6:9]+'T'

    #Saving
    for url,time in zip(urls,times):
        name=date+time
        camera.saveFile(url,folder,name)


def deleteFirstDay(camera):
    dates=camera.getDates()
    deleteFilesInRange(camera,dates[0])


def secToHms(nb_sec):
    '''
    Converts sec in Hour:Min:Sec
    :param nb_sec:
    :return:
    '''
    q,s=divmod(nb_sec,60)
    h,m=divmod(q,60)
    return "%d:%d:%d" %(h,m,s)


def hmsToSec(time):
    res = int(time[0:2]) * 3600 + int(time[3:5]) * 60 + int(time[6:8])
    return res

if __name__ == "__main__":
    cam = pysony.SonyAPI()
    print cam.getDates()
    ID = getUrlsInRange(cam,'20160331')
    for elt in ID:
        print elt
