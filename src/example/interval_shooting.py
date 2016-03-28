__author__ = 'marc'

import pysony
import time
from threading import Timer

class RepeatedPhoto(object):
    def __init__(self, interval, function, *args, **kwargs):
        self._timer     = None
        self.interval   = interval
        self.function   = function
        self.args       = args
        self.kwargs     = kwargs
        self.is_running = False
        self.start()

    def _run(self):
        self.is_running = False
        self.start()
        self.function(*self.args, **self.kwargs)

    def start(self):
        if not self.is_running:
            self._timer = Timer(self.interval, self._run)
            self._timer.start()
            self.is_running = True

    def stop(self):
        self._timer.cancel()
        self.is_running = False

def takePicture(cam):
    cam.actTakePicture()
    print("photo")


cam=pysony.SonyAPI()

camFunction = cam.getCameraFunction()['result'][0]
if camFunction == 'Contents Transfer':
    cam.setCameraFunction(params='Remote Shooting')

camMode=cam.getShootMode()
if not camMode == 'still':
    cam.setShootMode(params='still')

print "starting... \n "
rp=RepeatedPhoto(0.5,takePicture,cam)

try:
    time.sleep(10) # your long-running job goes here...
finally:
    rp.stop() # better in a try/finally block to make sure the program ends!