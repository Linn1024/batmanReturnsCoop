"""Reported QS0: blue Batman trapped outside the window after landing."""
import hashlib
import struct
import zipfile
from native_probe import Probe, ROOT

source = ROOT/'diagnostics/window-controls-qs0.State'
digest = hashlib.sha256(source.read_bytes()).digest()
raw = zipfile.ZipFile(source).read('Core.bin')
state = raw[4:4+struct.unpack_from('<I', raw)[0]]
p = Probe()

def world_x(player):
    return (p.player(player, 0x328) | p.player(player, 0x329) << 8) + p.word(0x17a0)

try:
    p.restore(state)
    assert p.word(0x76) == 1 and p.status()[5] == 104
    inventory = p.player(2, 0x8a), p.player(2, 0x8e), p.word(0x8c)
    black_x = world_x(1)
    p.run()
    assert world_x(1) == black_x, 'Recovery moved black Batman in the world'
    assert p.status()[5] >= 128, 'P2 remains outside the room'
    assert (p.player(2, 0x8a), p.player(2, 0x8e), p.word(0x8c)) == inventory
    ready = p.save()
    for direction in (64, 128):
        p.restore(ready)
        if direction == 64:  # Left is the room wall at the landing position.
            p.run(20, p2=128)
        before = world_x(2)
        p.run(20, p2=direction)
        assert world_x(2) < before if direction == 64 else world_x(2) > before
        assert world_x(1) == black_x, 'P2 input moved black Batman'
        assert p.status()[6] == 208, 'P2 walked out of the floor'
    p.restore(ready)
    p.run(8, p2=1)
    assert p.status()[6] < 208, 'P2 cannot jump'
    p.restore(state)
    p.samples.clear()
    p.run(120, p2=128)
    expected = p.save(), p.frame, bytes(p.samples)
    p.screenshot(ROOT/'diagnostics/window-controls-fixed.png')
    p.restore(state)
    p.samples.clear()
    p.run(120, p2=128)
    assert (p.save(), p.frame, bytes(p.samples)) == expected
    assert p.status()[2] == 0
    assert hashlib.sha256(source.read_bytes()).digest() == digest
    print('Passed: existing QS0 recovers, private inventory preserved, independent left/right movement and jump, no floor fall, state/video/audio replay')
finally:
    p.close()
