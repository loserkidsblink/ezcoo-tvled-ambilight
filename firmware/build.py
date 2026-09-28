"""Reproducible offline build; never opens USB or contacts devices."""
import hashlib
import json
import subprocess
from pathlib import Path

P = Path(__file__).resolve().parent
STOCK_SHA = 'ad3bd3805885527a0aadb092e520a2c3c408dc3251385411a4fc5dd8f7ca59df'
WORKING_SHA = 'b6f8cc855f3a6db106c1c9b32acbf4a44f54b953cb18864def3fae64e616ec0c'
stock = (P / 'STOCK-readback.bin').read_bytes()
comparison_file = P / 'WORKING-lldv-rollback.bin'
working = comparison_file.read_bytes() if comparison_file.exists() else stock
assert hashlib.sha256(stock).hexdigest() == STOCK_SHA
assert hashlib.sha256(working).hexdigest() == (WORKING_SHA if comparison_file.exists() else STOCK_SHA)
assert len(stock) == len(working) == 0x1b000
def run(*cmd): subprocess.run(cmd, cwd=P, check=True)
run('arm-none-eabi-as', '-mcpu=cortex-m3', '-mthumb', '-o', 'candidate.o', 'candidate.S')
run('arm-none-eabi-ld', '-T', 'candidate.ld', '-Map=candidate.map', '-o', 'candidate.elf', 'candidate.o')
image, patches = bytearray(stock), []
for name, address, expected in [('.route_hook',0x0800966c,'c8880528'),
                              ('.ratio_hook',0x08009462,'2de9f04f'),
                              ('.filter_hook',0x0801635e,'01234a46'),
                              ('.avi_hook',0x08013d44,'c01e82b2'),
                              ('.extension',0x0801ee6c,None)]:
    out = name[1:] + '.bin'
    run('arm-none-eabi-objcopy','-O','binary','-j',name,'candidate.elf',out)
    data = (P/out).read_bytes()
    off = address - 0x08004000
    old = stock[off:off+len(data)]
    assert old.hex() == expected if expected else len(data) <= 404 and old == b'\xff'*len(data)
    image[off:off+len(data)] = data
    patches.append({'section':name,'address':hex(address),'size':len(data),
                    'original':old.hex(),'replacement':data.hex()})
assert len(image) == len(stock)
filename = 'EXPERIMENTAL-tvled-transport.bin'
(P/filename).write_bytes(image)
pages = [hex(0x08004000+i) for i in range(0,len(stock),2048) if working[i:i+2048] != image[i:i+2048]]
report = {'status':'Experimental transport patch; see docs/validation.md for scoped physical results',
          'file':filename,'sha256':hashlib.sha256(image).hexdigest(),'length':len(image),
          'stock_sha256':STOCK_SHA,'working_lldv_sha256':WORKING_SHA,
          'base':'0x08004000','end_exclusive':'0x0801f000','changed_2k_pages':pages,'comparison_sha256':hashlib.sha256(working).hexdigest(),
          'patches':patches}
(P/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k != 'patches'},indent=2))
