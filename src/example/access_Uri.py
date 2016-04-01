__author__ = 'marc'

import pysony
import time

cam=pysony.SonyAPI()

# cam.setCameraFunction('Contents Transfer')
# time.sleep(6)

# print cam.getDates()
# print cam.getFilesCount('20160401')
print cam.getAvailableApiList()

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

    uris=[elt['uri'] for elt in res]

    for uri in uris:
        print uri
#
# deluri={'uri':['image:content?contentId=index%3A%2F%2F1000%2F00000001-default%2F0000847D-00000A10_33917_1_1000',
#                'image:content?contentId=index%3A%2F%2F1000%2F00000001-default%2F0000847E-00000A11_33918_1_1000',
#                'image:content?contentId=index%3A%2F%2F1000%2F00000001-default%2F000084RE-00000A11_33918_1_1000',
#                'image:content?contentId=index%3A%2F%2F1000%2F00000001-default%2F0000847F-00000A12_33919_1_1000',
#                'image:content?contentId=index%3A%2F%2F1000%2F00000001-default%2F00008480-00000A13_33920_1_1000']}
#
# cam.deleteContent(deluri)



