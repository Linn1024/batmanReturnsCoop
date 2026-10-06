"""Recover the reported stuck side-view boss introduction without input."""
import hashlib
import struct
import zipfile
from native_probe import Probe, ROOT

source = ROOT/'diagnostics/broken-qs0.State'
original = hashlib.sha256(source.read_bytes()).hexdigest()
with zipfile.ZipFile(source) as z:
    wrapped = z.read('Core.bin')
p = Probe()
try:
    p.restore(wrapped[4:4+struct.unpack_from('<I', wrapped)[0]])
    assert p.word(0xd6) and p.word(0x58) == 0xffff
    for frame in range(600):
        p.run()
        assert all(14 <= p.status()[a] <= 242 for a in (3, 5))
        if p.word(0xd6) == 0 and p.word(0x6a) == 0:
            break
    else:
        raise AssertionError('Script never released control')
    assert p.word(0x17a0) >= 0x7fe, 'Native scripted pan did not finish'
    p.run(90)
    p.screenshot(ROOT/'diagnostics/scripted-pan-recovered.png')
    saved = p.save()
    for player in (1, 2):
        p.restore(saved)
        index = 3 if player == 1 else 5
        before = p.status()[index]+p.word(0x17a0)
        p.run(12, p1=128 if player == 1 else 0, p2=128 if player == 2 else 0)
        assert p.status()[index]+p.word(0x17a0) > before+10
    p.restore(saved)
    p.run(120)
    expected = p.save(), p.frame[0]
    p.restore(saved)
    p.run(120)
    assert (p.save(), p.frame[0]) == expected
    assert p.status()[2] == 0
    assert hashlib.sha256(source.read_bytes()).hexdigest() == original
    print(f'Passed: script released after {frame+1} frames, both controls, no wrap, save replay, original QS0 unchanged.')
finally:
    p.close()
