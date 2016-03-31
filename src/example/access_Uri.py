__author__ = 'marc'

import pysony
import time

cam=pysony.SonyAPI()

cam.setCameraFunction('Contents Transfer')
time.sleep(6)

print cam.getDates()
print cam.getFilesCount('20160331')

#deluri={'uri':['image:content?contentId=index%3A%2F%2F1000%2F00000001-default%2F00008466-0000394C_33894_1_1000',
               # 'image:content?contentId=index%3A%2F%2F1000%2F00000001-default%2F00008467-0000394D_33895_1_1000']}

# cam.deleteContent(deluri)

for i in range (0,1):

    date='20160331'
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




#file=cam.getFilesInRange('20160324','08:10:00','12:00:00')
