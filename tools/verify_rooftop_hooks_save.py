"""Latest QS0: both hooks receive camera displacement exactly once."""
import hashlib
import struct
import zipfile
from native_probe import Probe, ROOT

source = ROOT/'diagnostics/grapple-latest-qs0.State'
digest = hashlib.sha256(source.read_bytes()).digest()
raw = zipfile.ZipFile(source).read('Core.bin')
state = raw[4:4+struct.unpack_from('<I', raw)[0]]
p = Probe()

def word(player, address):
    return p.player(player, address) | p.player(player, address+1) << 8

try:
    p.restore(state)
    p.run(p1=256, p2=256)
    p.run(17)
    # Attached anchors stay fixed in world space while the camera pans.
    for player in (1, 2):
        assert word(player, 0x40e) == 3 and word(player, 0x420) == 1
        for address in (0x328, 0x358, 0x418):
            p.set_word(player, address, word(player, address)+40)
    camera = p.word(0x17a0)
    anchors = [word(player, 0x418)+camera for player in (1, 2)]
    p.run()
    assert p.word(0x17a0) > camera
    assert [word(player, 0x418)+p.word(0x17a0) for player in (1, 2)] == anchors

    timings = ((20,20,0), (24,24,0), (30,30,0), (20,24,0),
               (24,20,0), (18,32,0), (20,28,0), (20,24,40))
    for swapped in (False, True):
        for first, second, delay in timings:
            p.restore(state)
            if swapped:
                bodies = [bytes(p.player(pl, a) for a in range(0x320, 0x500)) for pl in (1,2)]
                for pl in (1,2):
                    for offset, value in enumerate(bodies[2-pl]):
                        p.set_player(pl, 0x320+offset, value)
            lives = p.status()[9]
            for frame in range(420):
                p.run(p1=256 if frame % first == 0 else 0,
                      p2=256 if frame >= delay and (frame-delay) % second == 0 else 0)
                status = p.status()
                assert status[2] == 0 and status[9] == lives, (swapped, first, second, frame, status)
                assert all(32 <= status[a] <= 224 for a in (3,5)), ('Offscreen swing', frame, status)
                assert all(status[a] <= 240 for a in (4,6)), ('Fall', swapped, first, second, delay, frame, status)
                if p.word(0x17a0) >= 3800:
                    break
            else:
                raise AssertionError(('Traversal stalled', swapped, first, second, delay))
    p.restore(state)
    p.run(100, p1=0, p2=0)
    saved = p.save()
    def replay():
        p.samples.clear()
        for frame in range(180):
            p.run(p1=256 if frame % 20 == 0 else 0,
                  p2=256 if frame % 24 == 0 else 0)
        return p.save(), p.frame, bytes(p.samples)
    expected = replay()
    p.restore(saved)
    assert replay() == expected
    assert hashlib.sha256(source.read_bytes()).digest() == digest
    print('Passed: one camera shift per hook, QS0 traversal with eight timings and either ownership, no offscreen falls/life loss, state/video/audio replay')
finally:
    p.close()
