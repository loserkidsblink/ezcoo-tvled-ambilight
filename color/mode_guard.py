#!/usr/bin/env python3
"""Select the custom IPT HDR-YUV LUT only for verified TV-led DV on HDMI2.
Does not change the grabber, LED device, TV, Shield, or HDMI configuration.
"""
import hashlib,json,logging,re,signal,subprocess,time,urllib.request,os
from pathlib import Path
URL=os.environ.get('HYPERHDR_URL','http://127.0.0.1:8090/json-rpc')
EXPECTED_LUT=os.environ.get('TVLED_LUT_SHA256','')
SSH=[]  # configured only by main; importing/tests never contact a device
running=True

def is_standard_dv(status):
    patterns=[r'Dolby HDR Info\[2\]',r'Video Format\[R444\]',r'DeepColorMode\[\s*8BIT\]',r'PHY Lock\[1\]',r'is5Vconnected\[1\]',r'isMute\[0\]']
    return all(re.search(p,status) for p in patterns)

def rpc(payload):
    req=urllib.request.Request(URL,data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=3) as r: result=json.load(r)
    if not result.get('success'):raise RuntimeError('HyperHDR rejected request')
    return result

def apply(desired):
    components=rpc({'command':'serverinfo'})['info']['components']
    actual=next(c['enabled'] for c in components if c['name']=='HDR')
    if actual!=desired:
        rpc({'command':'componentstate','componentstate':{'component':'HDR','state':desired}})
        logging.info('Color conversion: %s','TV-led DV IPT' if desired else 'original SDR YUV')

def stop(*_):
    global running
    running=False

def main():
    global SSH
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(message)s')
    host=os.environ.get('TVLED_SSH_HOST','')
    port=os.environ.get('TVLED_LG_PORT','2')
    if not host or host.startswith('-') or not port.isdigit() or not re.fullmatch('[0-9a-f]{64}',EXPECTED_LUT):
        raise RuntimeError('Set TVLED_SSH_HOST, numeric TVLED_LG_PORT, and TVLED_LUT_SHA256; see README')
    SSH=['ssh','-o','BatchMode=yes','-o','ConnectTimeout=2','-o','LogLevel=ERROR',host,
         'cat /proc/lg/hdmi20/port'+port+'/status']
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    lut=Path(os.environ.get('TVLED_LUT_PATH',str(Path.home()/'.hyperhdr/lut_lin_tables.3d')))
    if hashlib.sha256(lut.read_bytes()).hexdigest()!=EXPECTED_LUT:
        apply(False)
        raise RuntimeError('Custom LUT mismatch; refusing to enable IPT')
    positive=0;last_error=None
    try:
        while running:
            try:
                result=subprocess.run(SSH,capture_output=True,text=True,timeout=4,check=True)
                positive=positive+1 if is_standard_dv(result.stdout) else 0
                apply(positive>=2)
                last_error=None
            except Exception as e:
                positive=0
                message=str(e)
                if message!=last_error:logging.warning('Mode detection unavailable: %s',message)
                last_error=message
                try:apply(False)
                except Exception:pass
            for _ in range(20):
                if not running:break
                time.sleep(.1)
    finally:
        try:apply(False)
        except Exception:pass

if __name__=='__main__':main()
