"""Run the actual linked ARM image with simulated packet/register I/O only.

Compare legacy cases with both stock and the working LLDV image. This does
not model pixel hardware, link training, EDID negotiation or color accuracy.
"""
import hashlib
import itertools
import json
import struct
from pathlib import Path
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS, UC_HOOK_CODE
from unicorn.arm_const import *

P = Path(__file__).resolve().parent
IMAGES = {'stock': (P/'STOCK-readback.bin').read_bytes(),
          'working': (P/'WORKING-lldv-rollback.bin').read_bytes(),
          'new': (P/'EXPERIMENTAL-tvled-transport.bin').read_bytes()}
manifest = json.loads((P/'manifest.json').read_text())
assert hashlib.sha256(IMAGES['new']).hexdigest() == manifest['sha256']
SRC, TV, CAP, SCALER, PKT = 0x200030d8, 0x2000314c, 0x200031c0, 0x20003390, 0x20004800
SV, TVV, CV, TXS, SCS = 0x20004000, 0x20004200, 0x20004400, 0x20004600, 0x20004a00
REGS = (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3)
SAVED = (UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_R6, UC_ARM_REG_R7,
         UC_ARM_REG_R8, UC_ARM_REG_R9, UC_ARM_REG_R10, UC_ARM_REG_R11)


def run(image, fn, tx=6, flags=2, dips=(0,0), tv_direct=True, processed=True,
        depth=8, fmt=0, dst_depth=8, dst_fmt=0, present=True, oui=b'\x46\xd0\x00',
        header=b'\x81\x01\x1b', corrupt=False, same_size=True, enabled=True,
        avi_version=2, avi_length=13, read_failure=False, packet_enum=9, sequence=None):
    u = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
    u.mem_map(0x08000000, 0x40000)
    u.mem_write(0x08004000, IMAGES[image])
    u.mem_map(0x20000000, 0x10000)
    def w(a,v): u.mem_write(a,struct.pack('<I',v))
    def h(a,v): u.mem_write(a,struct.pack('<H',v))
    u.mem_write(0x200003b0, bytes(dips))
    for port, video, ident in ((SRC,SV,0),(TV,TVV,5),(CAP,CV,6)):
        u.mem_write(port+4, bytes([0 if port==SRC else 6]))
        h(port+6,ident)
        w(port+0x3c,video)
        w(port+0x30,TXS if port==CAP else video+0x80)
        w(port+0x2c,video+0xc0)
        w(port+0x40,video+0x100)
        u.mem_write(video+0xa5,b'\x01')
        h(video+0x2a,0x201 if present else 1)
        u.mem_write(video,bytes([3*(depth if port==SRC else dst_depth),fmt if port==SRC else dst_fmt]))
        h(video+8,297)
        h(video+0x14,3840 if same_size or port==SRC else 1920)
        h(video+0x16,2160 if same_size or port==SRC else 1080)
        h(video+0x1c,24)
        u.mem_write(video+0x10,b'\x5d')
    u.mem_write(TV+0x6c,bytes([255 if tv_direct else 0]))
    u.mem_write(CAP+0x6c,bytes([0 if processed else 255]))
    u.mem_write(TXS+0xd,b'\x05')
    u.mem_write(TXS+0x20,bytes([int(enabled)]))
    u.mem_write(TVV+0xa0,bytes([int(enabled)]))
    w(CAP+0x54,SRC)
    w(TV+0x54,SRC)
    w(SCALER+0x44,SCS)
    vendor = bytearray(32)
    vendor[:3],vendor[4:7],vendor[7] = header,oui,flags
    vendor[3] = (-sum(vendor)) & 255
    if corrupt: vendor[3] ^= 1
    avi = bytearray.fromhex('82020d001028005d00000000000000000000000000000000000000000000000000')
    avi[1],avi[2] = avi_version,avi_length
    avi[4] = (avi[4]&31)|(dst_fmt<<5)
    avi[3] = (-sum(avi))&255
    u.mem_write(PKT,bytes(avi if fn in ('avi','avi_forward') else vendor))
    dst = TV if tx==5 else CAP
    writes, buffers, packets, trace, reads = [],[],[],[],[]

    def hook(m,a,size,unused):
        trace.append(a)
        if a not in (0x0800b798,0x08008e60,0x08008f40,0x08008fa8,0x080090b8,0x08008f78,0x0800a940,0x080102a4,0x0800df58):
            return
        args = [m.reg_read(r) for r in REGS]
        st = list(struct.unpack('<IIII',m.mem_read(m.reg_read(UC_ARM_REG_SP),16)))
        if a==0x0800b798:
            assert args[0] == SRC and args[1] in (0,9),args
            reads.append(1)
            if not read_failure: m.mem_write(args[2],bytes(avi if args[1]==0 else vendor))
        elif fn=='filter' and a==0x080102a4:
            packets.append({'op':'write','dst':args[0],'enum':args[1],
                            'packet':bytes(m.mem_read(args[2],32)).hex()})
        elif fn=='filter' and a==0x0800df58:
            packets.append({'op':'enable','dst':args[0],'mask':args[1],'enable':args[2]})
        elif a in (0x080102a4,0x0800df58):
            return  # Execute real writer/enable routines in AVI and integrated cases.
        elif a==0x08008e60: m.mem_write(st[3],struct.pack('<I',0))
        elif a==0x08008f40: m.mem_write(st[0],b'\x00')
        elif a==0x08008f78:
            assert args[2]<=32,args
            buffers.append({'args':args[:3],'bytes':bytes(m.mem_read(args[3],args[2])).hex()})
        elif a!=0x0800a940:
            writes.append({'helper':hex(a),'args':args,'stack':st[:1] if a==0x080090b8 else st})
        m.reg_write(UC_ARM_REG_R0,1 if a==0x0800b798 and read_failure else 0)
        m.reg_write(UC_ARM_REG_PC,m.reg_read(UC_ARM_REG_LR))

    u.hook_add(UC_HOOK_CODE,hook)
    if fn=='route': entry,args = 0x08009619,(SRC,dst,0,0)
    elif fn=='ratio': entry,args = 0x08009463,(SRC,SCALER,dst,0)
    elif fn=='avi': entry,args = 0x080102a5,(dst,0,PKT,1)
    elif fn=='avi_forward': entry,args = 0x0801630d,(SRC,dst,PKT,1)
    else: entry,args = 0x0801630d,(SRC,dst,PKT,0x200)
    records = []
    for mode in ([None] if sequence is None else sequence):
        if mode is not None:
            mode_flags, mode_depth, mode_fmt = mode
            vendor[7] = mode_flags
            vendor[3] = 0
            vendor[3] = (-sum(vendor[:31])) & 255
            for video in (SV, CV, TVV):
                u.mem_write(video, bytes([3*mode_depth, mode_fmt]))
            avi[4] = (avi[4] & 31) | (mode_fmt << 5)
            avi[3] = 0
            avi[3] = (-sum(avi[:17])) & 255
            u.mem_write(PKT, bytes(avi if fn in ('avi','avi_forward') else vendor))
        writes.clear(); buffers.clear(); packets.clear(); trace.clear(); reads.clear()
        for r,v in zip(REGS,args):u.reg_write(r,v)
        for i,r in enumerate(SAVED):u.reg_write(r,0x12345000+i)
        u.reg_write(UC_ARM_REG_SP,0x2000f000)
        u.mem_write(0x2000f000,struct.pack('<III',0 if fn=='avi_forward' else packet_enum,0,0))
        u.reg_write(UC_ARM_REG_LR,0x08003ff1)
        try: u.emu_start(entry,0x08003ff0,count=40000)
        except Exception:
            print('failed',image,fn,[hex(a) for a in trace[-12:]])
            raise
        assert u.reg_read(UC_ARM_REG_PC)==0x08003ff0,hex(u.reg_read(UC_ARM_REG_PC))
        assert u.reg_read(UC_ARM_REG_SP)==0x2000f000
        for i,r in enumerate(SAVED):assert u.reg_read(r)==0x12345000+i,(fn,r)
        record = {'result':u.reg_read(UC_ARM_REG_R0),'writes':writes,'buffers':buffers,'packets':packets,
                'flags':int.from_bytes(u.mem_read((TVV if tx==5 else CV)+0x2a,2),'little'),
                'video':bytes(u.mem_read(CV,0x40)).hex(),'input_packet':bytes(u.mem_read(PKT,32)).hex(),
                'vendor_reads':len(reads),'instructions':len(trace)}
        records.append(json.loads(json.dumps(record)))
    return records[0] if sequence is None else records



def observable(r):
    return {k:v for k,v in r.items() if k not in ('vendor_reads','instructions')}


def main():
    counts = {'route_ratio':0,'filter':0,'avi':0,'integrated_filter':0,'avi_forward':0,'mode_transitions':0}
    # Exhaustive core mode/board combinations, compared with proven LLDV image.
    for tx,flags,dips,tv,depth,fmt in itertools.product((5,6),range(4),((0,0),(1,0),(0,1)),(False,True),(8,10,12),range(4)):
        kw = dict(tx=tx,flags=flags,dips=dips,tv_direct=tv,depth=depth,fmt=fmt)
        std = tx==6 and flags==2 and dips==(0,0) and tv and depth==8 and fmt==0
        for fn in ('route','ratio'):
            old,new = run('working',fn,**kw),run('new',fn,**kw)
            assert new['result']==((3 if fn=='route' else 257) if std else old['result']),(fn,kw,old,new)
            counts['route_ratio']+=1
    guards = [{'present':False},{'oui':b'\x8b\x84\x90'},{'header':b'\x81\x01\x05'},
              {'header':b'\x82\x01\x1b'},{'header':b'\x81\x02\x1b'},
              {'depth':10},{'fmt':1},{'tx':5},{'dips':(1,0)},{'dips':(0,1)},
              {'tv_direct':False},{'corrupt':True},{'read_failure':True}]
    for g in guards:
        for fn in ('route','ratio'):
            assert run('new',fn,**g)['result']==run('stock',fn,**g)['result'],(fn,g)
            counts['route_ratio']+=1
    for flags,tx,processed in itertools.product(range(4),(5,6),(False,True)):
        kw = dict(flags=flags,tx=tx,processed=processed)
        new,old = run('new','filter',**kw),run('working','filter',**kw)
        if flags==2 and tx==6 and processed:
            assert new['packets'][0]['op']=='enable' and new['packets'][0]['enable']==0
            assert new['flags']&0x200==0
        else: assert observable(new)==observable(old),(kw,new,old)
        counts['filter']+=1
    for g in guards+[{'processed':False}]:
        r=run('new','filter',**g)
        # Missing source packet follows stock disable; other rejected valid packets forward.
        assert observable(r)==observable(run('working','filter',**g)),g
        counts['filter']+=1
    for flags in (0,1,3):
        for depth,fmt in itertools.product((8,10,12),range(4)):
            kw=dict(flags=flags,depth=depth,fmt=fmt)
            assert observable(run('new','avi',**kw))==observable(run('working','avi',**kw)),kw
            counts['avi']+=1
    for g in guards+[{'processed':False},{'dst_depth':10},{'dst_fmt':1},{'same_size':False},
                     {'enabled':False},{'avi_version':3},{'avi_length':12}]:
        assert observable(run('new','avi',**g))==observable(run('working','avi',**g)),g
        counts['avi']+=1
    old,new = run('working','avi'),run('new','avi')
    assert old['writes']==new['writes'] and old['video']==new['video']
    assert old['input_packet']==new['input_packet']
    assert len(old['buffers'])==len(new['buffers'])==1
    a,b = [bytes.fromhex(r['buffers'][0]['bytes']) for r in (old,new)]
    assert [i for i in range(len(a)) if a[i]!=b[i]]==[0,1]
    assert (b[1]>>5)&7==1 and (sum(b[:14])+0x82+2+13)%256==0
    counts['avi']+=1
    # Actual packet writer and enable routines, not just forwarder stubs.
    for flags,tx in itertools.product((2,3),(5,6)):
        r=run('new','integrated',flags=flags,tx=tx)
        if tx==5:assert not r['writes'] and not r['buffers']
        else:
            gate=[x for x in r['writes'] if x['helper']=='0x80090b8' and x['args']==[0x1b040,0x50,1,0]]
            assert gate and gate[-1]['stack']==[0],r
        counts['integrated_filter']+=1
    for flags,tx in itertools.product(range(4),(5,6)):
        a=run('working','avi_forward',flags=flags,tx=tx)
        b=run('new','avi_forward',flags=flags,tx=tx)
        if flags==2 and tx==6:
            assert a['writes']==b['writes'] and a['video']==b['video']
            raw=bytes.fromhex(b['buffers'][0]['bytes'])
            assert (raw[1]>>5)&7==1 and (sum(raw[:14])+0x82+2+13)%256==0
        else:assert observable(a)==observable(b),(flags,tx,a,b)
        counts['avi_forward']+=1
    modes = [(0,8,0),(2,8,0),(3,12,1),(2,8,0),(0,8,0),(2,10,0),(2,8,0)]
    for fn in ('avi_forward','filter'):
        before = run('working',fn,sequence=modes)
        after = run('new',fn,sequence=modes)
        for mode,a,b in zip(modes,before,after):
            if mode==(2,8,0):
                if fn=='avi_forward':
                    assert a['writes']==b['writes'] and a['video']==b['video']
                    raw=bytes.fromhex(b['buffers'][0]['bytes'])
                    assert (raw[1]>>5)&7==1
                else: assert b['packets'][0]['op']=='enable' and b['packets'][0]['enable']==0
            else: assert observable(a)==observable(b),(fn,mode,a,b)
            counts['mode_transitions']+=1
    report={'image_sha256':manifest['sha256'],'passed':counts,'total':sum(counts.values()),
            'avi_example':{'before':old,'after':new},
            'scope':'Actual linked ARM; synthetic board state and stubbed hardware I/O; no physical validation'}
    (P/'test-results.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'passed':counts,'total':sum(counts.values())}))


if __name__=='__main__': main()
