"""Latest QS0: elevator camera locks must survive either player's movement."""
import hashlib
import struct
import zipfile
from native_probe import Probe, ROOT

source = ROOT/'diagnostics/left-camera-next-qs0.State'
digest = hashlib.sha256(source.read_bytes()).digest()
raw = zipfile.ZipFile(source).read('Core.bin')
state = raw[4:4+struct.unpack_from('<I', raw)[0]]
p = Probe()

try:
    for player in (1, 2, 0):
        for direction in (64, 128):
            p.restore(state)
            assert p.word(0x76) == 5 and p.word(0xa0) & 3 == 3
            x = p.word(0x17a0)
            y = p.word(0x17b0)
            for frame in range(300):
                p.run(p1=direction if player in (0, 1) else 0,
                      p2=direction if player in (0, 2) else 0)
                assert p.word(0x17a0) == x, ('Lift camera moved horizontally', player, direction, frame)
                assert p.word(0x17b0) <= y
                y = p.word(0x17b0)
                assert p.status()[2] == 0
            assert y < 1514, 'Native elevator stopped ascending'
    p.restore(state)
    p.samples.clear()
    p.run(300, p1=64, p2=64)
    expected = p.save(), p.frame, bytes(p.samples)
    p.screenshot(ROOT/'diagnostics/elevator-camera-lock-fixed.png')
    p.restore(state)
    p.samples.clear()
    p.run(300, p1=64, p2=64)
    assert (p.save(), p.frame, bytes(p.samples)) == expected
    assert hashlib.sha256(source.read_bytes()).digest() == digest
    print('Passed: latest elevator QS0, either/both players left/right, native horizontal lock and upward motion, falls/respawns without camera drift, state/video/audio replay')
finally:
    p.close()
