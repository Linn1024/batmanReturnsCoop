"""Verify that a native save survives closing/reopening the emulator (ASLR)."""
import hashlib
import json
import subprocess
import sys
from native_probe import Probe, ROOT

if len(sys.argv)==1:
    for mode in ('save','load'):
        subprocess.run([sys.executable,__file__,mode],check=True)
    print('Cross-process save/load: RAM, video and audio match.')
else:
    p=Probe()
    try:
        if sys.argv[1]=='save':
            p.boot()
            p.run(47,p1=128,p2=1)
            (ROOT/'diagnostics/restart.state').write_bytes(p.save())
        else:
            p.restore((ROOT/'diagnostics/restart.state').read_bytes())
        frames=hashlib.sha256()
        p.samples.clear()
        for t in range(100):
            p.run(p1=2 if t%12<6 else 0,p2=256 if t==12 else 0)
            frames.update(p.frame[0])
        result={'ram':hashlib.sha256(bytes(p.ram)).hexdigest(),
                'video':frames.hexdigest(),'audio':hashlib.sha256(p.samples).hexdigest()}
        expected=ROOT/'diagnostics/restart-expected.json'
        if sys.argv[1]=='save':expected.write_text(json.dumps(result))
        else:assert result==json.loads(expected.read_text()),result
    finally:p.close()
