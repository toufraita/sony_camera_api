__author__ = 'marc'

import pysony

cam=pysony.X1000V()

cam.changeToRemoteShooting(duration=10)

cam.setShootMode('intervallstill')

cam.startIntervalStillRec()