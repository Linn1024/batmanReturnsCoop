"""Saved P2 grapple: native rope isolation, simultaneous hooks and replay."""
import hashlib
import struct
import zipfile
from native_probe import Probe, ROOT

source = ROOT/'diagnostics/hook-qs0.State'
digest = hashlib.sha256(source.read_bytes()).hexdigest()
with zipfile.ZipFile(source) as z:
    data = z.read('Core.bin')
raw = data[4:4+struct.unpack_from('<I', data)[0]]
p = Probe()
try:
    p.restore(raw)
    p.run(2)
    assert p.player(2, 0x410) | p.player(2, 0x411) << 8
    assert p.player(2, 0x3ea)
    assert p.status()[2] == 0
    p.screenshot(ROOT/'diagnostics/hook-fixed.png')
    def rope_pixels():
        data, width, height, pitch = p.frame
        return b''.join(data[y*pitch+10*2:y*pitch+80*2] for y in range(48,128))
    blue_rope = rope_pixels()
    # Give P1 the same live hook context, then compare P1's effect slots with
    # and without a P2 rope. Drawing the private rope must not overwrite them.
    p.restore(raw)
    for a in range(0x320, 0x460):
        p.set_player(1, a, p.player(2, a))
    both = p.save()
    p.run(2)
    effects = bytes(p.ram[0xeb0:0x14f0])
    assert any(effects)
    p.restore(both)
    p.set_word(2, 0x3ea, 0)
    p.set_word(2, 0x40e, 0)
    p.set_word(2, 0x410, 0)
    p.run(2)
    assert bytes(p.ram[0xeb0:0x14f0]) == effects
    # Compare the isolated rope region against the original P1 rendering.
    # This catches selecting idle Batman tiles instead of the hook pose tiles.
    assert rope_pixels() == blue_rope, "P2 rope differs from native P1 rope"
    p.restore(both)
    p.run(30)
    saved = p.save()
    p.run(90)
    expected = p.save(), p.frame[0]
    p.restore(saved)
    p.run(90)
    assert (p.save(), p.frame[0]) == expected
    assert p.status()[2] == 0
    assert hashlib.sha256(source.read_bytes()).hexdigest() == digest
    print('Passed: hook context, simultaneous rope isolation, save replay, no hook errors, original QS0 unchanged.')
finally:
    p.close()
