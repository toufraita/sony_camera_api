import json
import urllib
import urllib2
import time
import socket
import re

SSDP_ADDR = "239.255.255.250"  # The remote host
SSDP_PORT = 1900  # The same port as used by the server
SSDP_MX = 1
SSDP_ST = "urn:schemas-sony-com:service:ScalarWebAPI:1"
SSDP_TIMEOUT = 10000  # msec
PACKET_BUFFER_SIZE = 1024


class ControlPoint(object):
    def __init__(self):
        self.__bind_sockets()

    def __bind_sockets(self):
        self.__udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.__udp_socket.settimeout(1)
        return

    def discover(self, duration=None):
        # Default timeout of 1s
        if duration == None:
            duration = 1

        # Set the socket to broadcast mode.
        self.__udp_socket.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)

        msg = '\r\n'.join(["M-SEARCH * HTTP/1.1",
                           "HOST: 239.255.255.250:1900",
                           "MAN: ssdp:discover",
                           "MX: " + str(duration),
                           "ST: " + SSDP_ST,
                           "USER-AGENT: ",
                           "",
                           ""])

        # Send the message.
        self.__udp_socket.sendto(msg, (SSDP_ADDR, SSDP_PORT))
        # Get the responses.
        packets = self._listen_for_discover(duration)
        return packets

    def _listen_for_discover(self, duration):
        start = time.time()
        packets = []
        while (time.time() < (start + duration)):
            try:
                data, addr = self.__udp_socket.recvfrom(1024)
                packets.append((data, addr))
            except:
                pass
        return packets

    def _parse_device_definition(self, doc):
        """
        Parse the XML device definition file.
        """
        dd_regex = ("<av:X_ScalarWebAPI_Service>"
                    "\s*"
                    "<av:X_ScalarWebAPI_ServiceType>"
                    "(.+?)"
                    "</av:X_ScalarWebAPI_ServiceType>"
                    "\s*"
                    "<av:X_ScalarWebAPI_ActionList_URL>"
                    "(.+?)"
                    "/sony"  # and also strip "/sony"
                    "</av:X_ScalarWebAPI_ActionList_URL>"
                    "\s*"
                    "<av:X_ScalarWebAPI_AccessType\s*/>"  # Note: QX10 has "Type />", HX60 has "Type/>"
                    "\s*"
                    "</av:X_ScalarWebAPI_Service>")

        services = {}
        print doc
        for m in re.findall(dd_regex, doc):
            service_name = m[0]
            endpoint = m[1]
            services[service_name] = endpoint
        return services

    def _read_device_definition(self, url):
        """
        Fetch and parse the device definition, and extract the URL endpoint for
        the camera API service.
        """
        r = urllib2.urlopen(url)
        services = self._parse_device_definition(r.read())

        return services['camera']


# Common Header
# 0--------1--------2--------+--------4----+----+----+----8
# |0xFF    |payload | sequence number | Time stamp        |
# |        |type    |                 |                   |
# +-------------------------------------------------------+
#
# Payload Header
# 0--------------------------4-------------------7--------8
# | Start code               |  JPEG data size   | Padding|
# +--------------------------4------5---------------------+
# | Reserved                 | 0x00 | ..                  |
# +-------------------------------------------------------+
# | .. 115[B] Reserved                                    |
# +-------------------------------------------------------+
# | ...                                                   |
# ------------------------------------------------------128
#
# Payload Data
# in case payload type = 0x01
# +-------------------------------------------------------+
# | JPEG data size ...                                    |
# +-------------------------------------------------------+
# | ...                                                   |
# +-------------------------------------------------------+
# | Padding data size ...                                 |
# ------------------------------JPEG data size + Padding data size



import binascii


def common_header(bytes):
    start_byte = int(binascii.hexlify(bytes[0]), 16)
    payload_type = int(binascii.hexlify(bytes[1]), 16)
    sequence_number = int(binascii.hexlify(bytes[2:4]), 16)
    time_stemp = int(binascii.hexlify(bytes[4:8]), 16)
    if start_byte != 255:  # 0xff fixed
        return '[error] wrong QX livestream start byte'
    if payload_type != 1:  # 0x01 - liveview images
        return '[error] wrong QX livestream payload type'
    common_header = {'start_byte': start_byte,
                     'payload_type': payload_type,
                     'sequence_number': sequence_number,
                     'time_stemp': time_stemp,  # milliseconds
                     }
    return common_header


def payload_header(bytes):
    start_code = int(binascii.hexlify(bytes[0:4]), 16)
    jpeg_data_size = int(binascii.hexlify(bytes[4:7]), 16)
    padding_size = int(binascii.hexlify(bytes[7]), 16)
    reserved_1 = int(binascii.hexlify(bytes[8:12]), 16)
    flag = int(binascii.hexlify(bytes[12]), 16)  # 0x00, fixed
    reserved_2 = int(binascii.hexlify(bytes[13:]), 16)
    if flag != 0:
        return '[error] wrong QX payload header flag'
    if start_code != 607479929:
        return '[error] wrong QX payload header start'

    payload_header = {'start_code': start_code,
                      'jpeg_data_size': jpeg_data_size,
                      'padding_size': padding_size,
                      'reserved_1': reserved_1,
                      'flag': flag,
                      'resreved_2': reserved_2,
                      }
    return payload_header


class SonyAPI():
    def __init__(self, QX_ADDR='http://192.168.122.1:8080', scheme='storage', source='storage:memoryCard1'):
        """Creation of link to camera. Default parameters are written for Sony ActionCas

        :param QX_ADDR: String.
        :param scheme: String
        :param source: String
        :return:
        """
        self.QX_ADDR = QX_ADDR
        self.scheme = scheme
        self.source = source

    def _toList(self, param):
        params = []
        if type(param) != list:
            param = [param]
        for x in param:
            if type(x) != str:
                params.append(x)
            else:
                if x.lower() == 'true':
                    params.append(True)
                elif x.lower() == 'false':
                    params.append(False)
                else:
                    params.append(x)
        return params

    def _cmd(self, method=None, params=None, version='1.0', numid=1, target="camera"):
        """Method used to use API with the camera, using urllib2 and json. The "getAVailableApiList" seems not to
        list avContent APIs

        :param method:String. API name
        :param params:String List. Paramters for this API
        :param version:String. Version of the API. '1.0' by default.
        :param numid:Int. API id.
        :param target:String.Last part of endpoint url. "camera" by default, but can also be "avContent" or "system"
        depending on the API
        :return:Dict. Result of the API.
        """
        true = True
        false = False
        null = None

        if not method in ["getAvailableApiList"] and target not in ["avContent"]:
            camera_api_list = self.getAvailableApiList()["result"][0]
            if method not in camera_api_list:
                return "[ERROR] this api is not available"

        if params:
            params = self._toList(params)
        else:
            params = []

        datain = {'method': method, 'params': params, 'id': numid, 'version': version}

        # print datain

        try:
            result = eval(urllib2.urlopen(self.QX_ADDR + "/sony/" + target, json.dumps(datain)).read())
        except Exception as e:
            result = "[ERROR] camera doesn't work : " + str(e)

        # time.sleep(1)
        return result

    # <editor-fold desc="Listing Data">
    def getDates(self):
        # Gets Folders dates without changing current Camera Function.

        # Change mode to Contents Transfer if needed
        reChange = False
        camFunction = self.getCameraFunction()['result'][0]
        if not camFunction == 'Contents Transfer':
            reChange = True
            self.setCameraFunction(params='Contents Transfer')

        # Recover dates
        paramsList = {'uri': self.source,
                      'stIdx': 0,
                      'cnt': 100,
                      'type': None,
                      'view': 'date',
                      'sort': 'ascending'}
        contList = self.getContentList(paramsList)['result'][0]
        dateList = [elt['title'] for elt in contList]
        # dateUriList = [elt['uri'] for elt in contList]

        # Change to previous Camera Function
        if reChange:
            self.setCameraFunction(camFunction)

        return dateList

    def getFilesCount(self, date=None, type=None):
        # Initialize variables
        recType = None
        view = 'flat'

        # Change mode to Contents Transfer if needed
        camFunction = self.getCameraFunction()['result'][0]
        if not camFunction == 'Contents Transfer':
            reChange = True
            self.setCameraFunction(params='Contents Transfer')

        uri = self.source

        # Type needs to be a list
        if type and isinstance(type, str):
            type = [type]

        # If date is specified, it is appended to the default uri (ie scheme + storage source), and view is switched
        # to date
        if date:
            date = date[0:4] + '-' + date[4:6] + '-' + date[6:8]
            uri = uri + '?path=' + date
            view = 'date'

        ##Type specification is possible only in date view. Thus if type is specified without a date, all the files
        # should be first listed, and then processed with python to count only the files with specified type. Specified type
        # is recorded in recType
        if not date and type:
            recType = type
            type = None

        if not recType:
            paramsList = {'uri': uri,
                          'type': type,
                          'view': view}
            res = self.getContentCount(paramsList)
            try:
                res = res['result'][0]['count']
            except KeyError:
                res = res['error']


        else:
            paramsList = {'uri': uri,
                          'stIdx': 0,
                          'cnt': 100,
                          'type': type,
                          'view': view,
                          'sort': 'ascending'}
            res = self.getContentList(paramsList)
            try:
                res = res['result'][0]
                res = [elt['contentKind'] for elt in res]
                if len(res) >= 100:
                    return "Error:Type chosen with no date, more than 100 files listed "
                    # Possible upgrade : list files until len(res)<100. Really useful?
                else:
                    c = 0
                    for elt in res:
                        if elt in recType:
                            c += 1
                        res = c
            except KeyError:
                res = res['error']

        return res

    def getFilesList(self, date=None, type=None, stIdx=0, cnt=100, sort='ascending'):

        # Initialize variables
        recType = None
        view = 'flat'

        # Change mode to Contents Transfer if needed
        reChange = False
        camFunction = self.getCameraFunction()['result'][0]
        if not camFunction == 'Contents Transfer':
            reChange = True
            self.setCameraFunction(params='Contents Transfer')

        uri = self.source

        # Type needs to be a list
        if type and isinstance(type, str):
            type = [type]

        # If date is specified, it is appended to the default uri (ie scheme + storage source), and view is switched
        # to date
        if date:
            date = date[0:4] + '-' + date[4:6] + '-' + date[6:8]
            uri = uri + '?path=' + date
            view = 'date'

        ##Type specification is possible only in date view. Thus if type is specified without a date, all the files
        # should be first listed, and then processed with python to keep only the type specified. Specified type
        # is recorded in recType
        if not date and type:
            recType = type
            type = None

        paramsList = {'uri': uri,
                      'stIdx': stIdx,
                      'cnt': cnt,
                      'type': type,
                      'view': view,
                      'sort': sort}
        # print(paramsList)

        res = self.getContentList(paramsList)

        try:
            # print self.getContentList(paramsList)
            res = res['result'][0]

            # if recType has been specified, keep only files matching type initially given
            if recType:
                res = [elt for elt in res if elt['contentKind'] in recType]

        except KeyError:
            print "Error : Cannot obtain content list. Supposedly there's no file matching specified type. Returns empty" \
                  " list "
            res = []

        finally:
            return res

    def getFilesInRange(self, date, timeBegin, timeEnd, type=None):
        """List the files recorded during a specified range of time during a specified day.

        date -- string, Date of the recording : YearMonthDay (ex '20160513')
        timeBegin -- string, time of initial created time : Hour:Min:Sec (ex '10:34:23')
        timeEnd -- string, time of last created time : Hour:Min:Sec (ex '10:36:27')
        folder -- string, folder where images will be recorded (ex '/home/Toto/folder')
        type -- String List, types of elements to be recorded among 'still', 'movie_mp4', 'movie_xavcs'
            (ex  ['still','movie_mp4'])
        """

        # Defaul setting for files type
        if not type:
            type = ['still']

        # Variables
        filesList = []
        FirstCreatedTime = date[0:4] + '-' + date[4:6] + '-' + date[6:8] + 'T' + timeBegin
        LastCreatedTime = date[0:4] + '-' + date[4:6] + '-' + date[6:8] + 'T' + timeEnd
        firstFileFound = False
        lastFileFound = False
        numFiles = self.getFilesCount(date, type)
        indSearch = 0
        indFirstFile = numFiles - 1  # By default (if all files begin before timeBegin) pick the last file
        indLastFile = numFiles - 1

        while not firstFileFound and indSearch < numFiles:
            files = self.getFilesList(date, type, stIdx=indSearch)
            times = [elt['createdTime'] for elt in files]
            for i, time in enumerate(times):
                # If created time is after timeBegin, take file just before
                if time[0:19] >= FirstCreatedTime:
                    if indSearch == 0 and i == 0:
                        indFirstFile = 0
                        print("On " + date + ", first file was created after timeBegin")
                    else:
                        indFirstFile = indSearch + i - 1
                    firstFileFound = True
                    break
            indSearch += 100

        # If all files begin before timeBegin, the last one only is picked (cf indFirstFile=numFiles-1)
        # indSearch is set indFirstFile to begin listing the data
        indSearch = indFirstFile

        while not lastFileFound and indSearch < numFiles:
            files = self.getFilesList(date, type, stIdx=indSearch)
            times = [elt['createdTime'] for elt in files]
            for i, time in enumerate(times):
                if time[0:19] > LastCreatedTime:
                    indLastFile = indSearch + i - 1
                    lastFileFound = True
                    break
                else:
                    filesList.append(files[i])
            indSearch += 100

        filesListLength = indLastFile - indFirstFile + 1

        return filesList, filesListLength

    def getFilesOriginalUrl(self, date=None, stIdx=0, cnt=100, type=None, sort='ascending'):
        contList = self.getFilesList(date, stIdx, cnt, type, sort)
        # print contList
        Urls = [elt['content']['original'][0]['url'] for elt in contList]
        return Urls

    def getJpgList(self, date=None, stIdx=0, cnt=100, sort='ascending'):
        return self.getFilesList(date=date, stIdx=stIdx, cnt=cnt, type=['still'], sort=sort)

    # </editor-fold>

    # <editor-fold desc="Download Data">

    def saveFile(self, url, folder, name=None):
        url = url.translate(None, '\\')

        # If no name given, the file is named after the url address
        if not name:
            name = url.split('/org/')[1]

        path = folder + '/' + name
        u = urllib2.urlopen(url)
        f = open(path, 'wb')
        buffer = u.read()
        f.write(buffer)
        f.close()

    #
    def saveFilesInRange(self, date, timeBegin, timeEnd, folder, type=None):
        """Downloads the files recorded during a specified range of time during a specified day. Files names will be
            "CreatedTime_N (ISO8601, ex "2014-08-18T12:34:56+09:00"), where N differentiates files with similar created time
            (ex 2014-08-18T12:34:56+09:00_2)

        date -- string, Date of the recording : YearMonthDay (ex '20160513')
        timeBegin -- string, time of initial created time : Hour:Min:Sec (ex '10:34:23')
        timeEnd -- string, time of last created time : Hour:Min:Sec (ex '10:36:27')
        folder -- string, folder where images will be recorded (ex '/home/Toto/folder')
        type -- String List, types of elements to be recorded among 'still', 'movie_mp4', 'movie_xavcs'
            (ex  ['still','movie_mp4'])
        """

        # Default setting for files type
        if not type:
            type = ['still']

        filesList, numFiles = self.getFilesInRange(date, timeBegin, timeEnd, type=type)

        urls = [elt['content']['original'][0]['url'] for elt in filesList]
        times = [elt['createdTime'] for elt in filesList]
        N = 0
        prevTime = "-1"

        for i, url in enumerate(urls):
            time = times[i]
            if time == prevTime:
                N += 1
            else:
                N = 0
            prevTime = time
            name=time + '_' + str(N)
            self.saveFile(url,folder,name)

    # </editor-fold>

    # <editor-fold desc="Liveview">
    def liveview(self, params=None):
        if not params:
            liveview = self._cmd(method="startLiveview")
        else:
            liveview = self._cmd(method="startLiveviewWithSize", params=params)
        if isinstance(liveview, dict):
            try:
                url = liveview['result'][0].replace('\\', '')
                result = urllib2.urlopen(url)
            except:
                result = "[ERROR] liveview is dict type but there are no result: " + str(liveview['result'])
        else:
            print "[WORN] liveview is not a dict type"
            result = liveview
        return result

    def startLiveviewWithSize(self, params=None):
        if not params:
            print """[ERROR] please enter the param like below
        "L"     XGA size scale (the size varies depending on the camera models,
                and some camera models change the liveview quality instead of
                making the size larger.)
        "M"     VGA size scale (the size varies depending on the camera models)
        """

        return self._cmd(method="startLiveviewWithSize", params=params)

    def setLiveviewFrameInfo(self, params=None):
        if not params:
            print """
        "frameInfo"
                true - Transfer the liveview frame information
                false - Not transfer
        e.g) SonyAPI.setLiveviewFrameInfo(params=[{"frameInfo": True}])
        """
        return self._cmd(method="setLiveviewFrameInfo", params=params)

    def setLiveviewSize(self, params=None):
        return self._cmd(method="setLiveviewSize", params=params)

    # </editor-fold>

    def setShootMode(self, params=None):
        if not params:
            print ("[ERROR] please enter the param like below\n"
                   "			\"still\"            Still image shoot mode\n"
                   "			\"movie\"            Movie shoot mode\n"
                   "			\"audio\"            Audio shoot mode\n"
                   "			\"intervalstill\"    Interval still shoot mode\n"
                   "			e.g) In[26]:  camera.setShootMode(params=['still'])\n"
                   "				 Out[26]: {'id': 1, 'result': [0]}\n"
                   "			")
        return self._cmd(method="setShootMode", params=params)

    def actZoom(self, params=None):
        if not params:
            print """ ["direction", "movement"]
            direction
                "in"        Zoom-In
                "out"       Zoom-Out
            movement
                "start"     Long push
                "stop"      Stop
                "1shot"     Short push
            e.g) SonyAPI.actZoom(params=["in", "start"])
            """
        return self._cmd(method="actZoom", params=params)

    def setZoomSetting(self, params=None):
        if not params:
            print """
            "zoom"
                "Optical Zoom Only"                Optical zoom only.
                "On:Clear Image Zoom"              On:Clear Image Zoom.
            e.g) SonyAPI.setZoomSetting(params=[{"zoom": "Optical Zoom Only"}])
            """
        return self._cmd(method="setZoomSetting", params=params)

    def setTouchAFPosition(self, params=None):
        if not params:
            print """ [ X-axis position, Y-axis position]
                X-axis position     Double
                Y-axis position     Double
            e.g) SonyAPI.setTouchAFPosition(params=[ 23.2, 45.2 ])
            """
        return self._cmd(method="setTouchAFPosition", params=params)

    def actTrackingFocus(self, params=None):
        if not params:
            print """
                "xPosition"     double                X-axis position
                "yPosition"     double                Y-axis position
            e.g) SonyAPI.actTrackingFocus(params={"xPosition":23.2, "yPosition": 45.2})
            """
        return self._cmd(method="actTrackingFocus", params=params)

    def setTrackingFocus(self, params=None):
        return self._cmd(method="setTrackingFocus", params=params)

    def setContShootingMode(self, params=None):
        return self._cmd(method="setContShootingMode", params=params)

    def setContShootingSpeed(self, params=None):
        return self._cmd(method="setContShootingSpeed", params=params)

    def setSelfTimer(self, params=None):
        return self._cmd(method="setSelfTimer", params=params)

    def setExposureMode(self, params=None):
        return self._cmd(method="setExposureMode", params=params)

    def setFocusMode(self, params=None):
        return self._cmd(method="setFocusMode", params=params)

    def setExposureCompensation(self, params=None):
        return self._cmd(method="setExposureCompensation", params=params)

    def setFNumber(self, params=None):
        return self._cmd(method="setFNumber", params=params)

    def setShutterSpeed(self, params=None):
        return self._cmd(method="setShutterSpeed", params=params)

    def setIsoSpeedRate(self, params=None):
        return self._cmd(method="setIsoSpeedRate", params=params)

    def setWhiteBalance(self, params=None):
        return self._cmd(method="setWhiteBalance", params=params)

    def setProgramShift(self, params=None):
        return self._cmd(method="setProgramShift", params=params)

    def setFlashMode(self, params=None):
        return self._cmd(method="setFlashMode", params=params)

    def setAutoPowerOff(self, params=None):
        return self._cmd(method="setAutoPowerOff", params=params)

    def setBeepMode(self, params=None):
        return self._cmd(method="setBeepMode", params=params)

    def setCurrentTime(self, params=None):
        return self._cmd(method="setCurrentTime", params=params, target="system")

    def setStillSize(self, params=None):
        return self._cmd(method="setStillSize", params=params)

    def setStillQuality(self, params=None):
        return self._cmd(method="setStillQuality", params=params)

    def setPostviewImageSize(self, params=None):
        return self._cmd(method="setPostviewImageSize", params=params)

    def setMovieFileFormat(self, params=None):
        return self._cmd(method="setMovieFileFormat", params=params)

    def setMovieQuality(self, params=None):
        return self._cmd(method="setMovieQuality", params=params)

    def setSteadyMode(self, params=None):
        return self._cmd(method="setSteadyMode", params=params)

    def setViewAngle(self, params=None):
        return self._cmd(method="setViewAngle", params=params)

    def setSceneSelection(self, params=None):
        return self._cmd(method="setSceneSelection", params=params)

    def setColorSetting(self, params=None):
        return self._cmd(method="setColorSetting", params=params)

    def setIntervalTime(self, params=None):
        return self._cmd(method="setIntervalTime", params=params)

    def setLoopRecTime(self, params=None):
        return self._cmd(method="setLoopRecTime", params=params)

    def setFlipSetting(self, params=None):
        return self._cmd(method="setFlipSetting", params=params)

    def setTvColorSystem(self, params=None):
        return self._cmd(method="setTvColorSystem", params=params)

    def startRecMode(self):
        return self._cmd(method="startRecMode")

    def stopRecMode(self):
        return self._cmd(method="stopRecMode")

    def getCameraFunction(self):
        return self._cmd(method="getCameraFunction")

    def getSupportedCameraFunction(self):
        return self._cmd(method="getSupportedCameraFunction")

    def getAvailableCameraFunction(self):
        return self._cmd(method="getAvailableCameraFunction")

    def getAudioRecording(self):
        return self._cmd(method="getAudioRecording")

    def getSupportedAudioRecording(self):
        return self._cmd(method="getSupportedAudioRecording")

    def getAvailableAudioRecording(self):
        return self._cmd(method="getAvailableAudioRecording")

    def getWindNoiseReduction(self):
        return self._cmd(method="getWindNoiseReduction")

    def getSupportedWindNoiseReduction(self):
        return self._cmd(method="getSupportedWindNoiseReduction")

    def getAvailableWindNoiseReduction(self):
        return self._cmd(method="getAvailableWindNoiseReduction")

    def setCameraFunction(self, params=None):
        return self._cmd(method="setCameraFunction", params=params)

    def setAudioRecording(self, params=None):
        return self._cmd(method="setAudioRecording", params=params)

    def setWindNoiseReduction(self, params=None):
        return self._cmd(method="setWindNoiseReduction", params=params)

    def getSourceList(self, params=None):
        return self._cmd(method="getSourceList", params=params, target="avContent")

    def getContentCount(self, params=None):
        return self._cmd(method="getContentCount", params=params, target="avContent", version='1.2')

    def getContentList(self, params=None):
        return self._cmd(method="getContentList", params=params, target="avContent", version='1.3')

    def setStreamingContent(self, params=None):
        return self._cmd(method="setStreamingContent", params=params, target="avContent")

    def seekStreamingPosition(self, params=None):
        return self._cmd(method="seekStreamingPosition", params=params, target="avContent")

    def requestToNotifyStreamingStatus(self, params=None):
        return self._cmd(method="requestToNotifyStreamingStatus", params=params, target="avContent")

    def deleteContent(self, params=None):
        return self._cmd(method="deleteContent", params=params, target="avContent", version='1.1')

    def setInfraredRemoteControl(self, params=None):
        return self._cmd(method="setInfraredRemoteControl", params=params)

    def getEvent(self, params=None):
        return self._cmd(method="getEvent", params=params)

    def getMethodTypes(self, params=None, target=None):  # camera, system and avContent
        return self._cmd(method="getMethodTypes", params=params)

    def getShootMode(self):
        return self._cmd(method="getShootMode")

    def getSupportedShootMode(self):
        return self._cmd(method="getSupportedShootMode")

    def getAvailableShootMode(self):
        return self._cmd(method="getAvailableShootMode")

    def actTakePicture(self):
        return self._cmd(method="actTakePicture")

    def awaitTakePicture(self):
        return self._cmd(method="awaitTakePicture")

    def startContShooting(self):
        return self._cmd(method="startContShooting")

    def stopContShooting(self):
        return self._cmd(method="stopContShooting")

    def startMovieRec(self):
        return self._cmd(method="startMovieRec")

    def stopMovieRec(self):
        return self._cmd(method="stopMovieRec")

    def startLoopRec(self):
        return self._cmd(method="startLoopRec")

    def stopLoopRec(self):
        return self._cmd(method="stopLoopRec")

    def startAudioRec(self):
        return self._cmd(method="startAudioRec")

    def stopAudioRec(self):
        return self._cmd(method="stopAudioRec")

    def startIntervalStillRec(self):
        return self._cmd(method="startIntervalStillRec")

    def stopIntervalStillRec(self):
        return self._cmd(method="stopIntervalStillRec")

    def startLiveview(self):
        return self._cmd(method="startLiveview")

    def stopLiveview(self):
        return self._cmd(method="stopLiveview")

    def getLiveviewSize(self):
        return self._cmd(method="getLiveviewSize")

    def getSupportedLiveviewSize(self):
        return self._cmd(method="getSupportedLiveviewSize")

    def getAvailableLiveviewSize(self):
        return self._cmd(method="getAvailableLiveviewSize")

    def getLiveviewFrameInfo(self):
        return self._cmd(method="getLiveviewFrameInfo")

    def getZoomSetting(self):
        return self._cmd(method="getZoomSetting")

    def getSupportedZoomSetting(self):
        return self._cmd(method="getSupportedZoomSetting")

    def getAvailableZoomSetting(self):
        return self._cmd(method="getAvailableZoomSetting")

    def actHalfPressShutter(self):
        return self._cmd(method="actHalfPressShutter")

    def cancelHalfPressShutter(self):
        return self._cmd(method="cancelHalfPressShutter")

    def getTouchAFPosition(self):
        return self._cmd(method="getTouchAFPosition")

    def cancelTouchAFPosition(self):
        return self._cmd(method="cancelTouchAFPosition")

    def cancelTrackingFocus(self):
        return self._cmd(method="cancelTrackingFocus")

    def getTrackingFocus(self):
        return self._cmd(method="getTrackingFocus")

    def getSupportedTrackingFocus(self):
        return self._cmd(method="getSupportedTrackingFocus")

    def getAvailableTrackingFocus(self):
        return self._cmd(method="getAvailableTrackingFocus")

    def getContShootingMode(self):
        return self._cmd(method="getContShootingMode")

    def getSupportedContShootingMode(self):
        return self._cmd(method="getSupportedContShootingMode")

    def getAvailableContShootingMode(self):
        return self._cmd(method="getAvailableContShootingMode")

    def getContShootingSpeed(self):
        return self._cmd(method="getContShootingSpeed")

    def getSupportedContShootingSpeed(self):
        return self._cmd(method="getSupportedContShootingSpeed")

    def getAvailableContShootingSpeed(self):
        return self._cmd(method="getAvailableContShootingSpeed")

    def getSelfTimer(self):
        return self._cmd(method="getSelfTimer")

    def getSupportedSelfTimer(self):
        return self._cmd(method="getSupportedSelfTimer")

    def getAvailableSelfTimer(self):
        return self._cmd(method="getAvailableSelfTimer")

    def getExposureMode(self):
        return self._cmd(method="getExposureMode")

    def getSupportedExposureMode(self):
        return self._cmd(method="getSupportedExposureMode")

    def getAvailableExposureMode(self):
        return self._cmd(method="getAvailableExposureMode")

    def getFocusMode(self):
        return self._cmd(method="getFocusMode")

    def getSupportedFocusMode(self):
        return self._cmd(method="getSupportedFocusMode")

    def getAvailableFocusMode(self):
        return self._cmd(method="getAvailableFocusMode")

    def getExposureCompensation(self):
        return self._cmd(method="getExposureCompensation")

    def getSupportedExposureCompensation(self):
        return self._cmd(method="getSupportedExposureCompensation")

    def getAvailableExposureCompensation(self):
        return self._cmd(method="getAvailableExposureCompensation")

    def getFNumber(self):
        return self._cmd(method="getFNumber")

    def getSupportedFNumber(self):
        return self._cmd(method="getSupportedFNumber")

    def getAvailableFNumber(self):
        return self._cmd(method="getAvailabeFNumber")

    def getShutterSpeed(self):
        return self._cmd(method="getShutterSpeed")

    def getSupportedShutterSpeed(self):
        return self._cmd(method="getSupportedShutterSpeed")

    def getAvailableShutterSpeed(self):
        return self._cmd(method="getAvailableShutterSpeed")

    def getIsoSpeedRate(self):
        return self._cmd(method="getIsoSpeedRate")

    def getSupportedIsoSpeedRate(self):
        return self._cmd(method="getSupportedIsoSpeedRate")

    def getAvailableIsoSpeedRate(self):
        return self._cmd(method="getAvailableIsoSpeedRate")

    def getWhiteBalance(self):
        return self._cmd(method="getWhiteBalance")

    def getSupportedWhiteBalance(self):
        return self._cmd(method="getSupportedWhiteBalance")

    def getAvailableWhiteBalance(self):
        return self._cmd(method="getAvailableWhiteBalance")

    def actWhiteBalanceOnePushCustom(self):
        return self._cmd(method="actWhiteBalanceOnePushCustom")

    def getSupportedProgramShift(self):
        return self._cmd(method="getSupportedProgramShift")

    def getFlashMode(self):
        return self._cmd(method="getFlashMode")

    def getSupportedFlashMode(self):
        return self._cmd(method="getSupportedFlashMode")

    def getAvailableFlashMode(self):
        return self._cmd(method="getAvailableFlashMode")

    def getStillSize(self):
        return self._cmd(method="getStillSize")

    def getSupportedStillSize(self):
        return self._cmd(method="getSupportedStillSize")

    def getAvailableStillSize(self):
        return self._cmd(method="getAvailableStillSize")

    def getStillQuality(self):
        return self._cmd(method="getStillQuality")

    def getSupportedStillQuality(self):
        return self._cmd(method="getSupportedStillQuality")

    def getAvailableStillQuality(self):
        return self._cmd(method="getAvailableStillQuality")

    def getPostviewImageSize(self):
        return self._cmd(method="getPostviewImageSize")

    def getSupportedPostviewImageSize(self):
        return self._cmd(method="getSupportedPostviewImageSize")

    def getAvailablePostviewImageSize(self):
        return self._cmd(method="getAvailablePostviewImageSize")

    def getMovieFileFormat(self):
        return self._cmd(method="getMovieFileFormat")

    def getSupportedMovieFileFormat(self):
        return self._cmd(method="getSupportedMovieFileFormat")

    def getAvailableMovieFileFormat(self):
        return self._cmd(method="getAvailableMovieFileFormat")

    def getMovieQuality(self):
        return self._cmd(method="getMovieQuality")

    def getSupportedMovieQuality(self):
        return self._cmd(method="getSupportedMovieQuality")

    def getAvailableMovieQuality(self):
        return self._cmd(method="getAvailableMovieQuality")

    def getSteadyMode(self):
        return self._cmd(method="getSteadyMode")

    def getSupportedSteadyMode(self):
        return self._cmd(method="getSupportedSteadyMode")

    def getAvailableSteadyMode(self):
        return self._cmd(method="getAvailableSteadyMode")

    def getViewAngle(self):
        return self._cmd(method="getViewAngle")

    def getSupportedViewAngle(self):
        return self._cmd(method="getSupportedViewAngle")

    def getAvailableViewAngle(self):
        return self._cmd(method="getAvailableViewAngle")

    def getSceneSelection(self):
        return self._cmd(method="getSceneSelection")

    def getSupportedSceneSelection(self):
        return self._cmd(method="getSupportedSceneSelection")

    def getAvailableSceneSelection(self):
        return self._cmd(method="getAvailableSceneSelection")

    def getColorSetting(self):
        return self._cmd(method="getColorSetting")

    def getSupportedColorSetting(self):
        return self._cmd(method="getSupportedColorSetting")

    def getAvailableColorSetting(self):
        return self._cmd(method="getAvailableColorSetting")

    def getIntervalTime(self):
        return self._cmd(method="getIntervalTime")

    def getSupportedIntervalTime(self):
        return self._cmd(method="getSupportedIntervalTime")

    def getAvailableIntervalTime(self):
        return self._cmd(method="getAvailableIntervalTime")

    def getLoopRecTime(self):
        return self._cmd(method="getLoopRecTime")

    def getSupportedLoopRecTime(self):
        return self._cmd(method="getSupportedLoopRecTime")

    def getAvailableLoopRecTime(self):
        return self._cmd(method="getAvailableLoopRecTime")

    def getFlipSetting(self):
        return self._cmd(method="getFlipSetting")

    def getSupportedFlipSetting(self):
        return self._cmd(method="getSupportedFlipSetting")

    def getAvailableFlipSetting(self):
        return self._cmd(method="getAvailableFlipSetting")

    def getTvColorSystem(self):
        return self._cmd(method="getTvColorSystem")

    def getSupportedTvColorSystem(self):
        return self._cmd(method="getSupportedTvColorSystem")

    def getAvailableTvColorSystem(self):
        return self._cmd(method="getAvailableTvColorSystem")

    def startStreaming(self):
        return self._cmd(method="startStreaming", target="avContent")

    def pauseStreaming(self):
        return self._cmd(method="pauseStreaming", target="avContent")

    def stopStreaming(self):
        return self._cmd(method="stopStreaming", target="avContent")

    def getInfraredRemoteControl(self):
        return self._cmd(method="getInfraredRemoteControl")

    def getSupportedInfraredRemoteControl(self):
        return self._cmd(method="getSupportedInfraredRemoteControl")

    def getAvailableInfraredRemoteControl(self):
        return self._cmd(method="getAvailableInfraredRemoteControl")

    def getAutoPowerOff(self):
        return self._cmd(method="getAutoPowerOff")

    def getSupportedAutoPowerOff(self):
        return self._cmd(method="getSupportedAutoPowerOff")

    def getAvailableAutoPowerOff(self):
        return self._cmd(method="getAvailableAutoPowerOff")

    def getBeepMode(self):
        return self._cmd(method="getBeepMode")

    def getSupportedBeepMode(self):
        return self._cmd(method="getSupportedBeepMode")

    def getAvailableBeepMode(self):
        return self._cmd(method="getAvailableBeepMode")

    def getSchemeList(self):
        return self._cmd(method="getSchemeList", target="avContent")

    def getStorageInformation(self):
        return self._cmd(method="getStorageInformation")

    def actFormatStorage(self):
        return self._cmd(method="actFormatStorage")

    def getAvailableApiList(self):
        return self._cmd(method="getAvailableApiList")

    def getApplicationInfo(self):
        return self._cmd(method="getApplicationInfo")

    def getVersions(self, target=None):
        return self._cmd(method="getVersions", target=target)
