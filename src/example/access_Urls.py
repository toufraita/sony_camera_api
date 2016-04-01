__author__ = 'marc'

import pysony
import time

cam=pysony.SonyAPI()

# cam.setCameraFunction('Contents Transfer')
# time.sleep(6)

print cam.getDates()
print cam.getFilesCount('20160401')

for i in range (0,1):

    date='20160401'
    stIdx=100*i
    cnt=100
    type=None
    view='date'
    sort='ascending'

    uri=cam.source
    date = date[0:4] + '-' + date[4:6] + '-' + date[6:8]
    uri = uri + '?path=' + date

    paramsList = {'uri': uri,
                          'stIdx': stIdx,
                          'cnt': cnt,
                          'type': type,
                          'view': view,
                          'sort': sort}

    #t1=time.time()
    res = cam.getContentList(paramsList)
    #t2=time.time()

    # print(t2-t1)

    res=res['result'][0]

    urls=[elt['content']['original'][0]['url'] for elt in res]

    for url in urls:
        print url

imports=['http://192.168.122.1:8080/contentstransfer/orgjpeg/index%3A%2F%2F1000%2F00000001-default%2F0000847F-00000A12_33919_1_1000',
         'http://192.168.122.1:8080/contentstransfer/orgjpeg/index%3A%2F%2F1000%2F00000001-default%2F00008480-00000A13_33920_1_1000',
         'http://192.168.122.1:8080/contentstransfer/orgjpeg/index%3A%2F%2F1000%2F00000001-default%2F00008480&-00000A13_33920_1_1000',             'http://192.168.122.1:8080/contentstransfer/orgjpeg/index%3A%2F%2F1000%2F00000001-default%2F00008480-00000A13_33920_1_1000',
         'http://192.168.122.1:8080/contentstransfer/orgjpeg/index%3A%2F%2F1000%2F00000001-default%2F00008481-00000A14_33921_1_1000']




