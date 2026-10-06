"""Escalator QS0: shared vertical follow must not oscillate between players."""
import hashlib
import struct
import zipfile
from native_probe import Probe, ROOT

source = ROOT/'diagnostics/shake-qs0.State'
digest = hashlib.sha256(source.read_bytes()).hexdigest()
with zipfile.ZipFile(source) as z:
    data = z.read('Core.bin')
p = Probe()
try:
    p.restore(data[4:4+struct.unpack_from('<I', data)[0]])
    ys = []
    for _ in range(180):
        p.run()
        ys.append(p.word(0x17b0))
        assert all(32 <= p.status()[i] <= 224 for i in (4, 6))
    steps = [b-a for a, b in zip(ys, ys[1:])]
    assert all(-2 <= step <= 0 for step in steps), steps
    assert ys[-1] < ys[0]-30, 'Camera stopped following the escalator'
    p.screenshot(ROOT/'diagnostics/vertical-camera-fixed.png')
    saved = p.save()
    p.run(90)
    expected = p.save(), p.frame[0]
    p.restore(saved)
    p.run(90)
    assert (p.save(), p.frame[0]) == expected
    assert p.status()[2] == 0
    assert hashlib.sha256(source.read_bytes()).hexdigest() == digest
    print('Passed: continuous upward follow, no camera reversals, both players visible, save replay, original QS0 unchanged.')
finally:
    p.close()
