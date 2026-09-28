"""Independent full-table validation of this fixed IPT model; no device access.
Confirms numerical implementation, not Dolby source-format conformance.
"""
import argparse,json,hashlib
from pathlib import Path
import numpy as np
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--original',type=Path,required=True)
parser.add_argument('--generated',type=Path,required=True)
args=parser.parse_args()
N=256**3*3
original,installed=args.original,args.generated
a=np.memmap(original,dtype=np.uint8,mode='r');b=np.memmap(installed,dtype=np.uint8,mode='r')
assert len(a)==len(b)==3*N
assert np.array_equal(a[:N],b[:N]);assert np.array_equal(a[2*N:],b[2*N:])
table=b[N:2*N].reshape(256,256,256,3)
gray=table[128,128,:,:].astype(int)
assert np.max(np.ptp(gray,axis=1))<=1
assert np.all(np.diff(gray,axis=0)>=0)
assert np.array_equal(gray[0],[0,0,0])
# Independent ST2084 known neutral values, tolerance accounts for input 8-bit quantization.
refs=[]
for pq,nits in [(0,0),(.5080784215,100),(.7518270962,1000),(1,10000)]:
 index=round(pq*255);linear=nits/(nits+100)
 expected=12.92*linear if linear<=.0031308 else 1.055*linear**(1/2.4)-.055
 expected=round(expected*255);actual=gray[index].tolist();assert max(abs(x-expected) for x in actual)<=2
 refs.append({'nits':nits,'input_I':index,'expected_rgb':expected,'actual':actual})
# Validate all LUT cells against an independently written scalar-basis/vector evaluation.
# Hard-coded IPT inverse from libplacebo; LMS->XYZ derived independently by numerical inverse.
ipti=np.array([[1,.0975689,.205226],[1,-.113876,.133217],[1,.0326151,-.676887]])
xyz709=np.array([[.4123907993,.3575843394,.1804807884],[.2126390059,.7151686788,.0721923154],[.0193308187,.1191947798,.9505321522]])
hpe=np.array([[.40024,.7076,-.08081],[-.2263,1.16532,.0457],[0,0,.91822]])
ct=np.full((3,3),.04);np.fill_diagonal(ct,.92)
lms2rgb=np.linalg.inv(xyz709)@np.linalg.inv(hpe)@np.linalg.inv(ct)
u,y=np.meshgrid(np.arange(256),np.arange(256),indexing='ij');maxdiff=0;cells=0;different=0
for v in range(256):
 values=np.stack([y,u-128,np.full_like(y,v-128)],-1)/255
 lmsq=np.clip(values@ipti.T,0,1);pp=lmsq**(1/78.84375)
 lm=((np.maximum(pp-.8359375,0))/(18.8515625-18.6875*pp))**(1/.1593017578125)*10000
 rgb=np.maximum(lm@lms2rgb.T,0);rgb=rgb/(rgb+100)
 encoded=np.where(rgb<=.0031308,12.92*rgb,1.055*rgb**(1/2.4)-.055)
 expected=np.rint(np.clip(encoded,0,1)*255).astype(int);delta=np.abs(expected-table[v].astype(int));maxdiff=max(maxdiff,int(delta.max()));different+=int(np.any(delta,axis=-1).sum());cells+=256**2
assert maxdiff<=1
print(json.dumps({'cells_checked':cells,'maximum_byte_difference':maxdiff,'rounding_differences':different,'neutral_landmarks':refs,'preserved_segments':['HDR RGB','SDR YUV'],'sha256':hashlib.sha256(installed.read_bytes()).hexdigest()},indent=2))
