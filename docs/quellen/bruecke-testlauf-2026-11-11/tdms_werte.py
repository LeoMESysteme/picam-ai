import struct,sys
data=open(sys.argv[1],'rb').read()
pos=0; vals=[]; segs=[]
while pos+28<=len(data):
    tag,mask,ver,nxt,rawoff=struct.unpack('<4sIIQQ',data[pos:pos+28])
    if tag!=b'TDSm': print('bad tag',pos,tag); break
    start=pos+28+rawoff; end=pos+28+nxt if nxt!=0xFFFFFFFFFFFFFFFF else len(data)
    raw=data[start:end]
    n=len(raw)//8
    segs.append(n); vals+=struct.unpack('<%dd'%n,raw[:n*8])
    pos=end
print('segments',len(segs),'values',len(vals))
import json; json.dump(vals,open(sys.argv[2],'w'))
print(vals[:20]); print(segs[:40])
