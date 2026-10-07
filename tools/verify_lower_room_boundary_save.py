"""QS0: backtracking after the collapse must not enter hidden fire tiles."""
import ctypes as C
import hashlib
import struct
import zipfile
from native_probe import Probe, ROOT

source = ROOT/'diagnostics/window-left-boundary-qs0.State'
digest = hashlib.sha256(source.read_bytes()).digest()
raw = zipfile.ZipFile(source).read('Core.bin')
state = raw[4:4+struct.unpack_from('<I', raw)[0]]
p = Probe()

try:
    p.restore(state)
    assert p.word(0x76) == 3 and p.word(0x17b0) == 512
    # Disable invulnerability: this must fix access to the invalid terrain,
    # rather than conceal the damage with a cheat.
    buf = C.create_string_buffer(p.core.br_state_size())
    p.core.br_state_save(buf)
    C.c_uint.from_buffer(buf, 1484).value &= ~1
    p.core.br_state_load(buf)
    base = p.save()
    for player in (1, 2, 0):
        p.restore(base)
        for frame in range(1200):
            p.run(p1=64 if player in (0, 1) else 0,
                  p2=64 if player in (0, 2) else 0)
            assert p.word(0x17a0) >= 3584, 'Camera returned outside the lower room'
            assert p.status()[7:9] == [80, 80], ('Invisible damage', player, frame, p.status())
            assert p.status()[4] == p.status()[6] == 208, 'Walked out of the floor'
        assert p.status()[2] == 0
    assert p.word(0x17a0) >= 3584
    assert p.status()[3] <= 16 and p.status()[5] <= 16
    p.screenshot(ROOT/'diagnostics/lower-room-left-boundary-fixed.png')
    ready = p.save()
    p.samples.clear()
    p.run(120, p1=128, p2=128)
    assert p.word(0x17a0) > 3625, 'Boundary also blocked forward movement'
    expected = p.save(), p.frame, bytes(p.samples)
    p.restore(ready)
    p.samples.clear()
    p.run(120, p1=128, p2=128)
    assert (p.save(), p.frame, bytes(p.samples)) == expected
    for frame in range(500):
        p.run(p1=128, p2=128)
        if p.word(0x76) == 4:
            break
    else:
        raise AssertionError('Lower room no longer exits to the next section')
    assert hashlib.sha256(source.read_bytes()).digest() == digest
    print('Passed: full leftward backtracking for either/both players without invulnerability, no hidden damage or falls, room boundary, forward movement, next section, state/video/audio replay')
finally:
    p.close()
