"""Reported boss QS0: native damage and projectile ownership for both cars."""
import ctypes as C
import hashlib
import struct
import zipfile
from native_probe import Probe, ROOT

source = ROOT/'diagnostics/batmobile-boss-qs0.State'
digest = hashlib.sha256(source.read_bytes()).digest()
data = zipfile.ZipFile(source).read('Core.bin')
p = Probe()
def word(player, a): return p.player(player, a) | p.player(player, a+1) << 8
def cheats(value):
    suffix = C.create_string_buffer(p.core.br_state_size())
    p.core.br_state_save(suffix)
    struct.pack_into('<I', suffix, 1484, value)
    p.core.br_state_load(suffix)
def shot(player, slot):
    for owner in (1, 2):
        for s in (0x4b0, 0x500): p.set_word(owner, s+16, 0)
    # A missile approaching the existing native boss, including perspective.
    for a, value in ((slot, 0x3e00), (slot+6, p.word(0x646)),
                     (slot+8, p.word(0x648)), (slot+14, p.word(0x64e)+128),
                     (slot+16, 1), (slot+27, 0)):
        p.set_word(player, a, value)
def replay():
    video = hashlib.sha256(); p.samples.clear()
    for frame in range(180):
        p.run(p2=(128 if frame % 80 < 40 else 64) | (2 if frame % 12 == 0 else 0))
        video.update(p.frame[0])
    return p.save(), video.digest(), bytes(p.samples)
try:
    p.restore(data[4:4+struct.unpack_from('<I', data)[0]])
    cheats(5)  # Invulnerability/lives remain; one-hit is disabled.
    base = p.save(); damage = []
    for player in (1, 2):
        for slot in (0x4b0, 0x500):
            p.restore(base); shot(player, slot); p.set_word(1, 0x68a, 0)
            hp = p.word(0x666)
            for frame in range(8):
                p.run()
                if p.word(0x666) < hp: break
            else: raise AssertionError(('Boss did not register missile', player, slot))
            damage.append(hp-p.word(0x666))
            assert word(player, slot+16) == 0
            assert word(3-player, slot+16) == 0
            assert p.word(0x68a) == 7  # Native hit cooldown, not a custom damage write.
            assert p.status()[2] == 0
            saved = p.save(); expected = replay()
            p.restore(saved); assert replay() == expected
            p.restore(base); shot(player, slot); p.set_word(1, 0x68a, 7)
            p.run(3)
            assert p.word(0x666) == hp, 'Native boss cooldown bypassed'
            assert word(player, slot+16) == 1, 'Invulnerable boss consumed missile'
            p.restore(base); cheats(7); shot(player, slot)
            for frame in range(8):
                p.run()
                if not p.word(0x666): break
            assert not p.word(0x666) and p.word(0x67c) == 9
            assert word(player, slot+16) == 0
    assert damage == [4]*4, damage
    # Use actual P2 controller steering/fire without injecting any missile.
    p.restore(base); hp = p.word(0x666)
    for frame in range(1000):
        world = p.word(0x646)
        if world >= 32768: world -= 65536
        target = world+512; lane = word(2, 0x328)
        steer = 128 if lane < target-4 else 64 if lane > target+4 else 0
        p.run(p2=steer | (2 if frame % 12 == 0 else 0))
        assert p.status()[2] == 0
        assert not word(1, 0x4c0) and not word(1, 0x510)
        if p.word(0x666) < hp: break
    else: raise AssertionError('Actual P2 firing never damaged boss')
    p.screenshot(ROOT/'diagnostics/batmobile-boss-fixed.png')
    assert hashlib.sha256(source.read_bytes()).digest() == digest
    print('Passed: both cars/slots damage boss equally, owner consumption, native cooldown, one-hit defeat, save/video/audio replay, actual P2 steering/fire from QS0.')
finally:
    p.close()
