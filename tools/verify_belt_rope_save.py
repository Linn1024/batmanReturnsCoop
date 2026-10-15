"""Reported belt-level QS0: P2 rope is visible and shared effects stay intact."""
import hashlib
import struct
import zipfile
from native_probe import Probe, ROOT

source = ROOT/'diagnostics/belt-missing-rope-qs0.State'
digest = hashlib.sha256(source.read_bytes()).digest()
raw = zipfile.ZipFile(source).read('Core.bin')
state = raw[4:4+struct.unpack_from('<I', raw)[0]]
p = Probe()
try:
    p.restore(state)
    assert p.word(0x9a) == 1 and p.player(2, 0x40e) == 3
    p.run(2)
    shown, _, _, pitch = p.frame
    effects = bytes(p.ram[0x11d0:0x14f0])
    p.screenshot(ROOT/'diagnostics/belt-rope-visible.png')
    p.restore(state)
    p.set_word(2, 0x3ea, 0)  # Hide only the private rope's drawing state.
    p.run(2)
    hidden = p.frame[0]
    assert sum(shown[i:i+2] != hidden[i:i+2]
               for i in range(64*pitch, 100*pitch, 2)) > 30, 'Missing rope above Batman'
    assert bytes(p.ram[0x11d0:0x14f0]) == effects

    p.restore(state)
    for address in range(0x320, 0x500):
        p.set_player(1, address, p.player(2, address))
    both = p.save()
    p.run(2)
    effects = bytes(p.ram[0x11d0:0x14f0])
    assert any(effects)
    p.restore(both)
    p.set_word(2, 0x3ea, 0)
    p.run(2)
    assert bytes(p.ram[0x11d0:0x14f0]) == effects, 'P2 drawing changed P1 rope'

    def replay():
        video = hashlib.sha256()
        p.samples.clear()
        for frame in range(180):
            p.run(p1=128 if frame < 40 else 0,
                  p2=256 if frame % 30 == 0 else 0)
            video.update(p.frame[0])
            assert not p.status()[2]
        return p.save(), video.digest(), bytes(p.samples)
    p.restore(both)
    expected = replay()
    p.restore(both)
    assert replay() == expected
    assert hashlib.sha256(source.read_bytes()).digest() == digest
    print('Passed: QS0 belt rope visible, simultaneous ropes isolated, movement and state/video/audio replay')
finally:
    p.close()
