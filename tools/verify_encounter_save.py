"""Regression for the reported opening-stage encounter deadlock in BizHawk QS0.

Usage: python tools/verify_encounter_save.py "path/to/QuickSave0.State"
Uses controlled player positions/invincibility and native attacks to verify the
waiting encounter can finish, release its camera lock, and permit scrolling.
"""
import hashlib
import json
from pathlib import Path
import struct
import sys
import zipfile

from native_probe import Probe, ROOT

source = Path(sys.argv[1])
digest = hashlib.sha256(source.read_bytes()).hexdigest()
with zipfile.ZipFile(source) as archive:
    data = archive.read('Core.bin')
size = struct.unpack_from('<I', data)[0]
p = Probe()
try:
    p.restore(data[4:4+size])
    assert p.word(0xa0) and p.word(0x76) == 0
    assert p.word(0x17a0) > 0x302
    pointer = p.word(0xba)
    p.run(3)
    assert p.word(0xba) != pointer, 'Event allocation remains blocked'
    for frame in range(7000):
        targets = [s for s in (0x550, 0x640, 0x730)
                   if p.word(s) and p.word(s+0x26) > 0]
        if targets and frame % 15 == 0:
            target = targets[0]
            for player in (1, 2):
                p.set_word(player, 0x328,
                           max(28, min(230, p.word(target+8)+35+player*5)))
                p.set_word(player, 0x338, p.word(target+0x18))
                p.set_word(player, 0x324, 0x20)
                p.set_word(player, 0x3f8, 120)
        attack = 2 if frame % 12 < 6 else 0
        p.run(p1=attack, p2=attack)
        assert p.status()[2] == 0
        if not p.word(0xa0):
            break
    else:
        raise AssertionError('Encounter never released the camera lock')
    camera = p.word(0x17a0)
    p.run(180, p1=128, p2=128)
    assert p.word(0x17a0) > camera, 'Camera cannot advance after encounter'
    p.screenshot(ROOT/'diagnostics/encounter-recovered.png')
    report = {'frames_to_clear': frame, 'camera_before': camera,
              'camera_after': p.word(0x17a0), 'hook_errors': p.status()[2],
              'validation': 'Controlled combat fixture; not a manual playthrough'}
    (ROOT/'diagnostics/encounter-verification.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report))
finally:
    p.close()
assert hashlib.sha256(source.read_bytes()).hexdigest() == digest
