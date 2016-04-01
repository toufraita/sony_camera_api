import pysony
import time

cam=pysony.SonyAPI()

for i in range (0,1):

    date='20160324'
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
    print(len(res))

    uris=[elt['uri'] for elt in res]

    t1=time.time()
    cam.deleteContent({'uri':uris})
    t2=time.time()

    print (t2-t1)