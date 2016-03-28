__author__ = 'marc'

import pysony
import urllib2

cam=pysony.SonyAPI()

print cam.getDates()

cam.saveFilesInRange('20160324','07:46:00','07:46:13','/home/marc/merapi/camera/test')



