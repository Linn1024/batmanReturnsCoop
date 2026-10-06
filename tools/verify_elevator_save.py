"""Elevator QS0 recovery, mirrored ownership, controls and fall countdown."""
import hashlib
import struct
import zipfile
from native_probe import Probe, ROOT

source = ROOT/'diagnostics/elevator-qs0.State'
digest = hashlib.sha256(source.read_bytes()).hexdigest()
with zipfile.ZipFile(source) as z:
    data = z.read('Core.bin')
raw = data[4:4+struct.unpack_from('<I', data)[0]]
p = Probe()
try:
    for fallen in (1, 2):
        p.restore(raw)
        if fallen == 2:
            bodies = [bytes(p.player(pl, a) for a in range(0x320, 0x460)) for pl in (1, 2)]
            for pl in (1, 2):
                for offset, value in enumerate(bodies[2-pl]):
                    p.set_player(pl, 0x320+offset, value)
        p.run(30)
        status = p.status()
        assert all(32 <= status[a] <= 224 for a in (4, 6)), status
        assert abs(status[3]-status[5]) == 24, status
        assert status[7:10] == [80, 80, 99]
        saved = p.save()
        for player in (1, 2):
            p.restore(saved)
            idx = 3 if player == 1 else 5
            before = p.status()[idx]+p.word(0x17a0)
            p.run(12, p1=128 if player == 1 else 0, p2=128 if player == 2 else 0)
            assert p.status()[idx]+p.word(0x17a0) > before+10
        p.restore(saved)
        p.run(90)
        expected = p.save(), p.frame[0]
        p.restore(saved)
        p.run(90)
        assert (p.save(), p.frame[0]) == expected
    # With no grounded partner, an old zeroed fall countdown must still finish.
    p.restore(raw)
    p.set_word(2, 0x3b0, 0)
    p.set_word(2, 0x32c, 300)
    p.run(2)
    assert p.word(0x35c) != 2 or p.word(0x350) != 0x18
    assert p.status()[2] == 0
    assert hashlib.sha256(source.read_bytes()).hexdigest() == digest
    print('Passed: both elevator recovery directions, independent controls, save replay, native fall countdown, original QS0 unchanged.')
finally:
    p.close()
