"""TV-led transport experiment installer. --rollback restores the working LLDV image. --execute required; never writes bootloader.
DFU address/erase/download protocol from GigaDevice's published dfu_core.c.
No SET_INTERFACE, mass erase, option-byte command, or automatic reset.
"""
import argparse,hashlib,json,re,struct,time
from pathlib import Path
import usb.core,usb.util
P=Path(__file__).resolve().parent
BASE,END,TRANSFER=0x08004000,0x0801f000,2048
ORIGINAL='b6f8cc855f3a6db106c1c9b32acbf4a44f54b953cb18864def3fae64e616ec0c'
PREVIOUS='43c9edf1cadb4e5866bd531c3dc971222929fa8262606de25690b3200c4fe48b'
CANDIDATE='efc27e3ef3079c346f8afcc6df5dd524077163770647f0b84c5b0e2d0ca7084d'
def digest(b):return hashlib.sha256(b).hexdigest()
def page_map(desc):
 parts=desc.split('/')
 if len(parts)!=3 or not parts[0].startswith('@') or int(parts[1],16)!=0x08000000:
  raise RuntimeError('Unrecognized flash layout: '+desc)
 address=int(parts[1],16);pages=[]
 for segment in parts[2].split(','):
  m=re.fullmatch(r'\s*(\d+)\*(\d+)([BK])([a-g])\s*',segment)
  if not m:raise RuntimeError('Unrecognized flash segment: '+segment)
  count,size,unit,access=m.groups();size=int(size)*(1024 if unit=='K' else 1)
  if size not in (1024,2048) or access!='g':raise RuntimeError('Unsupported erase size/access')
  for _ in range(int(count)):
   pages.append((address,size));address+=size
 selected=[(a,n) for a,n in pages if BASE<=a and a+n<=END]
 if not selected or selected[0][0]!=BASE or selected[-1][0]+selected[-1][1]!=END:
  raise RuntimeError('Application extent does not align with flash layout')
 return selected
class Dfu:
 def __init__(self,dev,interface):self.dev,self.interface=dev,interface
 def read(self,req,value,length):return bytes(self.dev.ctrl_transfer(0xa1,req,value,self.interface,length,timeout=5000))
 def send(self,req,value=0,payload=b''):
  if req not in (1,4,6):raise RuntimeError('Forbidden request')
  if req in (4,6):
   if value or payload:raise RuntimeError('Bad control request')
  elif value==0:
   if len(payload)!=5 or payload[0] not in (0x21,0x41):raise RuntimeError('Forbidden special command')
   address=struct.unpack('<I',payload[1:])[0]
   if not (BASE<=address<END or (payload[0]==0x21 and address==0x08000000)):raise RuntimeError('Address outside application')
  elif value!=2 or not payload or len(payload)>TRANSFER:raise RuntimeError('Forbidden download')
  self.dev.ctrl_transfer(0x21,req,value,self.interface,payload,timeout=5000)
 def status(self):
  d=self.read(3,0,6)
  if len(d)!=6:raise RuntimeError('Short DFU status')
  return d[0],int.from_bytes(d[1:4],'little'),d[4]
 def idle(self):
  error,delay,state=self.status()
  if state==10:self.send(4)
  elif error:raise RuntimeError(f'DFU error {error}, state {state}')
  self.send(6)
  error,delay,state=self.status()
  if error or state!=2:raise RuntimeError('Unable to reach DFU idle')
 def completed(self):
  for _ in range(100):
   error,delay,state=self.status()
   if error:raise RuntimeError(f'DFU operation failed: {error}/{state}')
   if state==5:return
   if state not in (3,4):raise RuntimeError(f'Unexpected DFU state {state}')
   time.sleep(min(max(delay/1000,0.005),1))
  raise RuntimeError('DFU operation timed out')
 def command(self,opcode,address):
  self.idle();self.send(1,0,bytes([opcode])+struct.pack('<I',address));self.completed()
 def bootloader(self):
  self.command(0x21,0x08000000);self.idle()
  result=b''.join(self.read(2,2+i,TRANSFER) for i in range(8))
  self.idle();return result
 def image(self):
  self.command(0x21,BASE);self.idle();b=bytearray()
  for offset in range(0,END-BASE,TRANSFER):
   chunk=self.read(2,2+offset//TRANSFER,TRANSFER)
   if len(chunk)!=TRANSFER:raise RuntimeError('Short application read')
   b.extend(chunk)
  self.idle();return bytes(b)
 def erase_page(self,address,size):
  if size not in (1024,2048) or address%size or not BASE<=address or address+size>END:
   raise RuntimeError('Invalid page bounds')
  for offset in range(0,size,1024):self.command(0x41,address+offset)
 def write_page(self,address,data):
  if len(data) not in (1024,2048) or address%len(data) or not BASE<=address or address+len(data)>END:
   raise RuntimeError('Invalid page bounds')
  self.command(0x21,address)
  self.send(1,2,data);self.completed()

def install(dfu,pages,target,original,candidate,rollback=False):
 before=dfu.image()
 if before!=dfu.image():raise RuntimeError('Preflight reads differ')
 changed=[(a,n) for a,n in pages if original[a-BASE:a-BASE+n]!=candidate[a-BASE:a-BASE+n]]
 if before not in (original,candidate) and digest(before)!=PREVIOUS:
  if not rollback:raise RuntimeError('Installed image is neither approved baseline nor candidate')
  for a,n in pages:
   if (a,n) not in changed and before[a-BASE:a-BASE+n]!=original[a-BASE:a-BASE+n]:
    raise RuntimeError('Unexpected changes outside approved patch pages')
 pending=[(a,n) for a,n in pages if before[a-BASE:a-BASE+n]!=target[a-BASE:a-BASE+n]]
 for a,n in pending:
  if (a,n) not in changed:raise RuntimeError('Write exceeds approved patch pages')
 # Installed bootloader locks FMC after every write and does not unlock in erase.
 # Therefore all erases must precede all writes in a fresh DFU session.
 for a,n in pending:dfu.erase_page(a,n)
 if pending:
  erased=dfu.image()
  expected=bytearray(before)
  for a,n in pending:expected[a-BASE:a-BASE+n]=b'\xff'*n
  if erased!=expected:raise RuntimeError('Erase verification failed; do not program or boot; reset into DFU')
 for a,n in pending:
  dfu.write_page(a,target[a-BASE:a-BASE+n])
  print(f'Programmed application page {a:#010x} ({n} bytes)',flush=True)
 after=dfu.image()
 if after!=target or dfu.image()!=target:raise RuntimeError('Post-write verification failed; remain in DFU for rollback')
 return {'before_sha256':digest(before),'after_sha256':digest(after),'two_post_write_reads_match':True}
def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--execute',action='store_true');parser.add_argument('--rollback',action='store_true')
 args=parser.parse_args()
 original=(P/'WORKING-lldv-rollback.bin').read_bytes();candidate=(P/'EXPERIMENTAL-tvled-transport.bin').read_bytes()
 if digest(original)!=ORIGINAL or digest(candidate)!=CANDIDATE or len(original)!=END-BASE or len(candidate)!=END-BASE:
  raise RuntimeError('Artifact identity/size check failed')
 if not args.execute:
  print('Artifacts verified. No USB device opened. --execute writes the attached device; read docs/recovery.md first.');return
 dev=usb.core.find(idVendor=0x28e9,idProduct=0x0189)
 if dev is None:raise RuntimeError('EZCOO not in DFU mode')
 cfg=dev.get_active_configuration()
 interfaces=[i for i in cfg if i.bInterfaceClass==0xfe and i.bInterfaceSubClass==1 and i.bAlternateSetting==0]
 if len(interfaces)!=1:raise RuntimeError('Unexpected DFU interface')
 itf=interfaces[0];desc=usb.util.get_string(dev,itf.iInterface)
 if desc is None:desc=usb.util.get_string(dev,5)
 extra=bytes(itf.extra_descriptors)+bytes(cfg.extra_descriptors);functional=None
 while len(extra)>=2 and extra[0]>=2:
  n=extra[0]
  if extra[1]==0x21 and n>=9:functional=extra[:n];break
  extra=extra[n:]
 if functional is None or functional[2]&3!=3 or struct.unpack_from('<H',functional,5)[0]!=TRANSFER:
  raise RuntimeError('Unexpected DFU capabilities')
 usb.util.claim_interface(dev,itf.bInterfaceNumber)
 try:
  d=Dfu(dev,itf.bInterfaceNumber)
  if desc=='@Internal Flash   /0x08000000/16*002Ka,112*002Kg':
   # Verified installed bootloader protects <0x08004000 in erase/write wrappers
   # (0x080002e8 / 0x0800041c), despite its stale 32 KiB descriptor protection.
   boot=d.bootloader()
   if boot!=d.bootloader() or digest(boot)!='d73d694f4b7cab429047ea17e9d15b8989b349cc45705182be97bc2e05a7f55c':
    raise RuntimeError('Unknown bootloader: cannot use corrected flash profile')
   pages=[(a,2048) for a in range(BASE,END,2048)]
  else:pages=page_map(desc)
  d.idle();commands=d.read(2,0,3);d.idle()
  if not all(x in commands for x in (0x21,0x41)):raise RuntimeError('Required DFU commands not advertised')
  target=original if args.rollback else candidate
  result=install(d,pages,target,original,candidate,args.rollback)
  result.update({'flash_descriptor':desc,'rollback':args.rollback})
  log=P/('dfu-install-'+time.strftime('%Y%m%d-%H%M%S')+'.json');log.write_text(json.dumps(result,indent=2))
  print(json.dumps(result,indent=2));print('Verified. Reconnect power normally; no reset command sent.')
 finally:
  usb.util.release_interface(dev,itf.bInterfaceNumber);usb.util.dispose_resources(dev)
if __name__=='__main__':main()
