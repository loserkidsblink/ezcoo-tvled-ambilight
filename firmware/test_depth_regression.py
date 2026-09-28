"""Derive depth representation from real RX code, reproduce v1 rejection, verify v2."""
import json,struct
from pathlib import Path
import test_candidate as t
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS, UC_HOOK_CODE
from unicorn.arm_const import *
P=Path(__file__).resolve().parent
t.IMAGES['failed']=(P/'INSTALLED-tvled-v1.bin').read_bytes()
def read_depth(hardware_code):
 u=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS)
 u.mem_map(0x08000000,0x40000);u.mem_write(0x08004000,t.IMAGES['stock'])
 u.mem_map(0x20000000,0x10000);u.mem_write(t.SRC+0x3c,struct.pack('<I',t.SV))
 def hook(m,a,size,unused):
  if a==0x08008f40:
   args=[m.reg_read(r) for r in t.REGS]
   assert args==[0x1b020,3,0x30,4],args
   dest=struct.unpack('<I',m.mem_read(m.reg_read(UC_ARM_REG_SP),4))[0]
   m.mem_write(dest,bytes([hardware_code]))
  elif a!=0x0800d13c:return
  m.reg_write(UC_ARM_REG_R0,0);m.reg_write(UC_ARM_REG_PC,m.reg_read(UC_ARM_REG_LR))
 u.hook_add(UC_HOOK_CODE,hook);u.reg_write(UC_ARM_REG_R0,t.SRC)
 u.reg_write(UC_ARM_REG_SP,0x2000f000);u.reg_write(UC_ARM_REG_LR,0x08003ff1)
 u.emu_start(0x0800b721,0x08003ff0,count=1000)
 return u.mem_read(t.SV,1)[0]
values=[read_depth(i) for i in range(4)]
assert values==[24,30,36,48],values
# The test harness API accepts bits/component and encodes the derived internal representation.
depth=values[0]//3
cases={}
for fn in ['route','ratio','filter','avi_forward']:
 before=t.run('failed',fn,depth=depth,dst_depth=depth)
 after=t.run('new',fn,depth=depth,dst_depth=depth)
 if fn=='route':assert before['result']==1 and after['result']==3
 elif fn=='ratio':assert before['result']!=257 and after['result']==257
 elif fn=='filter':
  assert before['packets'][0]['op']=='write'
  assert after['packets'][0]['op']=='enable' and after['packets'][0]['enable']==0
 else:
  old=bytes.fromhex(before['buffers'][0]['bytes']);new=bytes.fromhex(after['buffers'][0]['bytes'])
  assert (old[1]>>5)&7==0 and (new[1]>>5)&7==1
  assert before['video']==after['video'] and before['writes']==after['writes']
 cases[fn]={'before':before,'after':after}
a=t.IMAGES['failed'];b=t.IMAGES['new'];diff=[{'address':hex(0x08004000+i),'old':x,'new':y} for i,(x,y) in enumerate(zip(a,b)) if x!=y]
assert len(diff)==2 and all(x['old']==8 and x['new']==24 for x in diff)
report={'hardware_depth_codes':values,'binary_changes':diff,'cases':cases,'scope':'Actual compiled ARM with modeled register IO; hardware retest still required'}
(P/'depth-regression-results.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'depth_codes':values,'regressions_passed':list(cases),'binary_changes':diff},indent=2))
