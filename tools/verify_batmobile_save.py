"""Reported racing save: private car, native missiles/hits and save replay."""
import ctypes as C
import hashlib
import struct
import zipfile
from native_probe import Probe, ROOT

source = ROOT/'diagnostics/batmobile-qs0.State'
digest = hashlib.sha256(source.read_bytes()).digest()
data = zipfile.ZipFile(source).read('Core.bin')
p = Probe()
def word(player, a):
    return p.player(player, a) | p.player(player, a+1) << 8
def clear_traffic():
    for a in range(0x640, 0xc80, 0x50):
        if a != 0x730:
            p.set_word(1, a, 0)
            p.set_word(1, a+16, 0)
def replay():
    video = hashlib.sha256()
    p.samples.clear()
    for frame in range(180):
        p.run(p1=2 if frame % 20 == 0 else 0,
              p2=(64 if frame % 80 < 40 else 128) | (2 if frame % 22 == 0 else 0))
        video.update(p.frame[0])
    return p.save(), video.digest(), bytes(p.samples)
try:
    p.restore(data[4:4+struct.unpack_from('<I', data)[0]])
    p.run(p1=8); p.run(14)
    assert p.status()[0] and p.status()[2] == 0
    assert word(1, 0x460) and word(2, 0x460)
    assert word(2, 0x468) - word(1, 0x468) == 72
    p.screenshot(ROOT/'diagnostics/batmobile-coop.png')
    base = p.save()
    for a in range(0x640, 0xc80, 0x50):
        p.set_word(1, a, 0); p.set_word(1, a+16, 0)
    steering_base = p.save()
    p.run(30)
    reference = bytes(p.ram[0x320:0x4b0]), p.word(0x9c), p.word(0xb4), bytes(p.ram[0x11000:0x12000])
    for button, direction in ((64, -1), (128, 1)):
        p.restore(steering_base); x = word(2, 0x468)
        p.run(30, p2=button)
        assert (word(2, 0x468)-x)*direction > 0
        # P2 cannot advance road generation, enemies or P1's car twice.
        assert (bytes(p.ram[0x320:0x4b0]), p.word(0x9c), p.word(0xb4), bytes(p.ram[0x11000:0x12000])) == reference
        assert 48 <= word(2, 0x468) <= 208
    for player in (1, 2):
        p.restore(base)
        for frame in range(12):
            p.run(p1=2 if player == 1 else 0, p2=2 if player == 2 else 0)
            if word(player, 0x4c0): break
        else: raise AssertionError(('No native missile', player))
        assert word(3-player, 0x4c0) == 0
        assert abs((word(player, 0x4b6)+512 & 65535)-word(player, 0x328)) <= 32
        p.run(3)
        assert word(player, 0x4b0) != 0
        assert abs(word(player, 0x4b8)-word(player, 0x468)) < 40
    damage = []
    for player in (1, 2):
        for slot in (0x4b0, 0x500):
            p.restore(base); clear_traffic()
            for owner in (1, 2):
                for s in (0x4b0, 0x500): p.set_word(owner, s+16, 0)
            p.set_word(1, 0x756, 32)
            for a, v in ((slot, 0x3e00), (slot+6, p.word(0x736)),
                         (slot+14, p.word(0x73e)), (slot+16, 1), (slot+27, 0)):
                p.set_word(player, a, v)
            p.run()
            damage.append(32-p.word(0x756))
            assert word(player, slot+16) == 0
            assert word(3-player, slot+16) == 0
    assert damage[0] > 0 and damage == [damage[0]]*4, damage
    for player in (1, 2):
        p.restore(base); clear_traffic()
        # Disable saved invulnerability for this native contact fixture.
        suffix = C.create_string_buffer(p.core.br_state_size())
        p.core.br_state_save(suffix)
        struct.pack_into('<I', suffix, 1484, 0)
        p.core.br_state_load(suffix)
        p.set_word(1, 0x736, word(player, 0x328)-512)
        p.set_word(1, 0x73e, 0x760)
        p.run(12)
        assert word(player, 0x49c) == 2
        assert word(3-player, 0x49c) == 0
        assert p.status()[6+player] < 80
        assert p.status()[6+3-player] == 80
    p.restore(base); saved = p.save(); expected = replay()
    p.restore(saved); assert replay() == expected
    p.restore(base)
    for frame in range(1800):
        p.run(p1=2 if frame % 12 == 0 else 0,
              p2=(64 if frame % 100 < 50 else 128) | (2 if frame % 14 == 0 else 0))
        assert p.status()[2] == 0
        if p.word(0x32) == 6 and p.word(0x9a) == 0 and p.word(0x76) == 12:
            assert 48 <= word(2, 0x468) <= 208
    assert hashlib.sha256(source.read_bytes()).digest() == digest
    # A fresh vehicle entrance uses additional lifecycle states absent in QS0.
    p.close(); p = Probe(); p.boot()
    def press(button): p.run(p1=button); p.run()
    press(265)
    for _ in range(8): press(32)
    for _ in range(4): press(128)
    press(32); press(32); press(256)
    for frame in range(2000):
        p.run()
        if frame > 500 and p.word(0x32) == 6 and p.word(0x76) == 12 and p.status()[0] and not word(1, 0x49c) and not word(2, 0x49c):
            before = word(2, 0x328); p.run(20, p2=64)
            assert word(2, 0x328) < before
            break
    else: raise AssertionError('Fresh blue vehicle entrance never released controls')
    assert p.status()[2] == 0
    print('Passed: blue car, independent steering, shared road, both native missile slots/owners, correct contact damage, save/video/audio replay, 1800-frame race, fresh vehicle entrance.')
finally:
    p.close()
