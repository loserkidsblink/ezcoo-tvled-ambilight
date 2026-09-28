"""Approximate TV-led HDMI IPT to sRGB for ambilight, no dynamic RPU processing.
Only HDR-YUV segment is replaced; original SDR and HDR-RGB segments retained.
Matrix basis: libplacebo src/colorspace.c pl_ipt_rgb2lms/pl_ipt_lms2ipt.
"""
import hashlib,json,shutil
from pathlib import Path
import numpy as np
P=Path(__file__).resolve().parent
N=256**3*3
IPTI=np.linalg.inv([[.4,.4,.2],[4.455,-4.851,.396],[.8056,.3572,-1.1628]])
XYZ=np.array([[.636958,.144617,.168881],[.262700,.677998,.059302],[0,.028073,1.060985]])
HPE=np.array([[.40024,.70760,-.08081],[-.22630,1.16532,.04570],[0,0,.91822]])
CT=np.full((3,3),.04);np.fill_diagonal(CT,.92)
TO709=np.array([[1.660491,-.587641,-.07285],[-.12455,1.1329,-.00835],[-.01815,-.10058,1.11873]])
LINEAR=TO709@np.linalg.inv(CT@HPE@XYZ)
def convert(c):
 v=np.asarray(c,dtype=np.float64).copy();v[...,1:]-=128;v/=255
 x=np.clip(v@IPTI.T,0,1)**(1/(2523/32))
 lms=(np.maximum(x-3424/4096,0)/np.maximum(2413/128-2392/128*x,1e-8))**(1/(2610/16384))*10000
 out=np.maximum(lms@LINEAR.T,0);out=out/(out+100)
 out=np.where(out<=.0031308,12.92*out,1.055*out**(1/2.4)-.055)
 return np.rint(np.clip(out,0,1)*255).astype(np.uint8)
def main():
 import argparse
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--input',type=Path,required=True,help='Original three-segment HyperHDR LUT')
 parser.add_argument('--output',type=Path,required=True,help='New file; refuses to overwrite')
 args=parser.parse_args()
 if args.input.resolve()==args.output.resolve():parser.error('Input and output must differ')
 if args.input.stat().st_size!=3*N:parser.error('Expected 150994944-byte three-segment LUT')
 # Exclusive creation keeps an existing LUT safe even if another process creates it.
 with args.input.open('rb') as src,args.output.open('xb') as dst:shutil.copyfileobj(src,dst)
 u,y=np.meshgrid(np.arange(256),np.arange(256),indexing='ij')
 with args.output.open('r+b') as f:
  f.seek(N)
  for v in range(256):f.write(convert(np.stack([y,u,np.full_like(y,v)],-1)).tobytes())
 a=np.memmap(args.input,dtype=np.uint8,mode='r');b=np.memmap(args.output,dtype=np.uint8,mode='r')
 if not (np.array_equal(a[:N],b[:N]) and np.array_equal(a[2*N:],b[2*N:])):raise RuntimeError('Preserved segment verification failed')
 print(json.dumps({'sha256':hashlib.sha256(args.output.read_bytes()).hexdigest(),'bytes':args.output.stat().st_size,'preserved':['HDR RGB','SDR YUV'],'replaced':'HDR YUV'},indent=2))
if __name__=='__main__':main()
