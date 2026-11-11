"""Minimaler TDMS-Leser: float64-Kanäle, nicht verschachtelt, mehrere Chunks je Segment."""
import struct,sys,json
SIZES={1:1,2:2,3:4,4:8,5:1,6:2,7:4,8:8,9:4,10:8,0x21:1,0x44:16}
def read(path):
    data=open(path,'rb').read(); pos=0; order=[]; count={}; vals={}
    while pos+28<=len(data):
        tag,mask,ver,nxt,rawoff=struct.unpack('<4sIIQQ',data[pos:pos+28])
        assert tag==b'TDSm'
        m=pos+28
        if mask&0x2:
            if mask&0x4: order=[]
            nobj,=struct.unpack('<I',data[m:m+4]); m+=4
            for _ in range(nobj):
                L,=struct.unpack('<I',data[m:m+4]); m+=4; path_=data[m:m+L].decode(); m+=L
                ri,=struct.unpack('<I',data[m:m+4]); m+=4
                if ri not in (0xFFFFFFFF,0):
                    dt,dim,cnt=struct.unpack('<IIQ',data[m:m+16]); m+=ri-4
                    count[path_]=cnt
                    if path_ not in order: order.append(path_)
                elif ri==0 and path_ not in order: order.append(path_)
                nprops,=struct.unpack('<I',data[m:m+4]); m+=4
                for _ in range(nprops):
                    L,=struct.unpack('<I',data[m:m+4]); m+=4+L
                    t,=struct.unpack('<I',data[m:m+4]); m+=4
                    if t==0x20:
                        L,=struct.unpack('<I',data[m:m+4]); m+=4+L
                    else: m+=SIZES[t]
        raw=data[pos+28+rawoff:pos+28+nxt]; chunk=sum(count[p] for p in order)*8
        off=0
        while chunk and off+chunk<=len(raw):
            for p in order:
                n=count[p]; vals.setdefault(p,[]).extend(struct.unpack('<%dd'%n,raw[off:off+n*8])); off+=n*8
        pos=pos+28+nxt
    return vals
if __name__=='__main__':
    v=read(sys.argv[1]); print({k:len(x) for k,x in v.items()})
