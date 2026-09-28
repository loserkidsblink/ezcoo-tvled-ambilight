"""Offline NOR-flash/DFU simulator tests; no USB access."""
import contextlib,io,struct,unittest,os
import ezcoo_dfu_install as m
class Device:
 def __init__(self,image,page):
  self.memory=bytearray(b'B'*(m.END-0x08000000+2048));self.memory[m.BASE-0x8000000:m.END-0x8000000]=image
  self.page=page;self.pointer=m.BASE;self.state=2;self.pending=None;self.writes=[];self.fail=False;self.locked=False
 def ctrl_transfer(self,typ,req,value,index,data,timeout):
  if typ==0xa1:
   if req==3:
    if self.state==3:
     block,payload=self.pending
     if block==0:
      opcode=payload[0];addr=struct.unpack('<I',payload[1:])[0]
      if opcode==0x21:self.pointer=addr
      elif opcode==0x41:
       if self.locked:raise RuntimeError('FMC locked after programming')
       addr=addr//self.page*self.page
       assert m.BASE<=addr<addr+self.page<=m.END
       off=addr-0x8000000;self.memory[off:off+self.page]=b'\xff'*self.page;self.writes.append(('erase',addr,self.page))
      else:raise AssertionError(opcode)
     else:
      assert block==2
      addr=self.pointer;off=addr-0x8000000
      assert m.BASE<=addr<addr+len(payload)<=m.END
      for i,b in enumerate(payload):
       assert self.memory[off+i]&b==b
       self.memory[off+i]=b
       if self.fail and i==31:self.fail=False;raise OSError('simulated lost USB during page programming')
      self.writes.append(('write',addr,len(payload)));self.locked=True
     self.state=5;return bytes([0,0,0,0,4,0])
    return bytes([0,0,0,0,self.state,0])
   if req==2:
    assert self.state in (2,9)
    self.state=9
    if value==0:return b'\x00\x21\x41'
    off=self.pointer+(value-2)*m.TRANSFER-0x8000000
    return self.memory[off:off+data]
   raise AssertionError(req)
  assert typ==0x21
  if req in (4,6):self.state=2;return 0
  assert req==1 and self.state in (2,5)
  self.pending=(value,bytes(data));self.state=3;return len(data)
class Tests(unittest.TestCase):
 def setUp(self):
  if os.environ.get('FIRMWARE_REAL_IMAGES')=='1':
   self.original=(m.P/'WORKING-lldv-rollback.bin').read_bytes()
   self.candidate=(m.P/'EXPERIMENTAL-tvled-transport.bin').read_bytes()
   self.previous=(m.P/'INSTALLED-tvled-v1.bin').read_bytes()
  else:
   # Synthetic bytes exercise DFU mechanics without redistributing firmware.
   self.original=bytes([0xa5])*(m.END-m.BASE)
   c=bytearray(self.original)
   for off in (0x1000,0x3000,0x18000):c[off:off+100]=bytes(range(100))
   self.candidate=bytes(c);c[0x18010]^=1;c[0x18020]^=1;self.previous=bytes(c)
   old=m.ORIGINAL,m.CANDIDATE,m.PREVIOUS
   def restore():m.ORIGINAL,m.CANDIDATE,m.PREVIOUS=old
   self.addCleanup(restore)
   m.ORIGINAL,m.CANDIDATE,m.PREVIOUS=map(m.digest,(self.original,self.candidate,self.previous))
 def invoke(self,device,target,rollback=False):
  pages=m.page_map(f'@Internal Flash /0x08000000/{128 if device.page==1024 else 64:03}*{device.page//1024:03}Kg')
  with contextlib.redirect_stdout(io.StringIO()):return m.install(m.Dfu(device,0),pages,target,self.original,self.candidate,rollback)
 def test_install_and_restore_preserve_other_memory(self):
  for page in (1024,2048):
   with self.subTest(page=page):
    d=Device(self.original,page);before=bytes(d.memory)
    r=self.invoke(d,self.candidate);self.assertEqual(r['after_sha256'],m.CANDIDATE)
    self.assertEqual(bytes(d.memory[:0x4000]),before[:0x4000]);self.assertEqual(bytes(d.memory[m.END-0x8000000:]),before[m.END-0x8000000:])
    d.locked=False;self.invoke(d,self.original,True);self.assertEqual(bytes(d.memory),before)
 def test_upgrade_installed_v1_and_rollback(self):
  previous=self.previous
  self.assertEqual(m.digest(previous),m.PREVIOUS)
  for page in (1024,2048):
   with self.subTest(page=page):
    d=Device(previous,page);before=bytes(d.memory)
    r=self.invoke(d,self.candidate)
    self.assertEqual(r['before_sha256'],m.PREVIOUS)
    self.assertEqual(r['after_sha256'],m.CANDIDATE)
    self.assertEqual(bytes(d.memory[:0x4000]),before[:0x4000])
    d.locked=False;self.invoke(d,self.original,True)
    self.assertEqual(bytes(d.memory[0x4000:0x1f000]),self.original)
 def test_interrupted_upgrade_v1_can_roll_back(self):
  d=Device(self.previous,1024);d.fail=True
  with self.assertRaises(OSError):self.invoke(d,self.candidate)
  d.state=2;d.pending=None;d.locked=False
  self.invoke(d,self.original,True)
  self.assertEqual(bytes(d.memory[0x4000:0x1f000]),self.original)
 def test_two_kib_transfer_on_one_kib_flash(self):
  d=Device(self.original,1024);before=bytes(d.memory)
  pages=[(a,2048) for a in range(m.BASE,m.END,2048)]
  with contextlib.redirect_stdout(io.StringIO()):
   m.install(m.Dfu(d,0),pages,self.candidate,self.original,self.candidate)
   d.locked=False
   m.install(m.Dfu(d,0),pages,self.original,self.original,self.candidate,True)
  self.assertEqual(bytes(d.memory),before)
 def test_identical_image_does_not_erase(self):
  d=Device(self.candidate,1024);self.invoke(d,self.candidate);self.assertEqual(d.writes,[])
 def test_unknown_firmware_rejected_before_erase(self):
  image=bytearray(self.original);image[100]^=1;d=Device(image,1024)
  with self.assertRaises(RuntimeError):self.invoke(d,self.candidate)
  self.assertEqual(d.writes,[])
 def test_partial_write_can_roll_back(self):
  d=Device(self.original,1024);before=bytes(d.memory);d.fail=True
  with self.assertRaises(OSError):self.invoke(d,self.candidate)
  d.state=2;d.pending=None
  d.locked=False;self.invoke(d,self.original,True);self.assertEqual(bytes(d.memory),before)
 def test_rollback_rejects_unrelated_damage(self):
  image=bytearray(self.candidate);image[100]^=1;d=Device(image,1024)
  with self.assertRaises(RuntimeError):self.invoke(d,self.original,True)
  self.assertEqual(d.writes,[])
 def test_bootloader_and_mass_erase_commands_rejected(self):
  d=Device(self.original,1024);f=m.Dfu(d,0)
  for req,value,payload in [(1,0,b'\x41'),(1,0,b'\x41'+struct.pack('<I',0x08000000)),(1,0,b'\x21'+struct.pack('<I',m.END)),(1,1,b'x'),(0,0,b'')]:
   with self.assertRaises(RuntimeError):f.send(req,value,payload)
  self.assertEqual(d.writes,[])
if __name__=='__main__':unittest.main()
