"""Check recovery and continued gameplay from a supplied BizHawk freeze save.

Usage: python tools/verify_freeze_save.py "path/to/QuickSave0.State"
The original save is read only. No ROM or user save is checked into the repo.
"""
import hashlib
import json
from pathlib import Path
import struct
import sys
import zipfile

from native_probe import Probe, ROOT

source = Path(sys.argv[1])
original_hash = hashlib.sha256(source.read_bytes()).hexdigest()
with zipfile.ZipFile(source) as archive:
    wrapped = archive.read('Core.bin')
size = struct.unpack_from('<I', wrapped)[0]
p = Probe()
try:
    assert len(wrapped) >= 4 + size
    p.restore(wrapped[4:4 + size])
    before = p.status()
    assert before[0], 'Expected an active co-op gameplay save'
    # Recovery must complete promptly, without Start or other input.
    p.run(3)
    assert p.status()[1] > before[1], 'Saved freeze did not recover'
    previous = p.status()[1]
    images = set()
    for frame in range(600):
        p.run(p1=2 if frame % 24 < 12 else 0,
              p2=128 if frame < 60 else 2 if frame % 30 < 15 else 0)
        images.add(hashlib.sha256(p.frame[0]).digest())
        if frame % 60 == 59:
            status = p.status()
            assert status[0] and status[1] > previous + 30, status
            assert status[2] == before[2], status
            previous = status[1]
    assert len(images) > 60, 'Video stopped updating'
    p.screenshot(ROOT / 'diagnostics/freeze-regression.png')
    print(json.dumps({'source': str(source), 'before': before,
                      'after': p.status(), 'distinct_frames': len(images)}))
finally:
    p.close()
assert hashlib.sha256(source.read_bytes()).hexdigest() == original_hash
