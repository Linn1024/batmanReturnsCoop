"""Reported QS0: scripted belt walk mirrors native pose without respawning."""
import ctypes as C
import hashlib
import struct
import zipfile
from native_probe import Probe, ROOT

source = ROOT/'diagnostics/script-walk-qs0.State'
digest = hashlib.sha256(source.read_bytes()).digest()
data = zipfile.ZipFile(source).read('Core.bin')
p = Probe()
def word(player, address):
    return p.player(player, address) | p.player(player, address+1) << 8
def signed(value):
    return value if value < 32768 else value-65536
try:
    p.restore(data[4:4+struct.unpack_from('<I', data)[0]])
    poses = set(); positions = set(); count = 0; replay_base = None
    for frame in range(260):
        p.run(p2=64)  # The scene must own movement despite opposite P2 input.
        if p.word(0xd6) and p.word(0x9a) == 1:
            assert p.status()[0], 'Partner deactivated during the script'
            assert signed(word(1, 0x328))-signed(word(2, 0x328)) == 40
            for address in (0x320, 0x32c, 0x338, 0x350, 0x35c, 0x3b0):
                assert word(1, address) == word(2, address), (frame, hex(address))
            poses.add(word(2, 0x320)); positions.add(word(2, 0x328)); count += 1
            if replay_base is None: replay_base = p.save()
            if frame in (80, 120, 150):
                p.screenshot(ROOT/f'diagnostics/script-walk-fixed-{frame}.png')
        assert p.status()[2] == 0
    assert count > 80 and len(poses) >= 5 and len(positions) > 40
    assert not p.word(0xd6) and not p.word(0x6a), 'Native scene did not finish'
    ready = p.save()
    for player in (1, 2):
        p.restore(ready); before = word(player, 0x328)+p.word(0x17a0)
        p.run(12, p1=128 if player == 1 else 0, p2=128 if player == 2 else 0)
        assert word(player, 0x328)+p.word(0x17a0) > before
    def replay():
        video = hashlib.sha256(); p.samples.clear()
        for frame in range(200):
            p.run(p2=128 if frame % 20 < 10 else 64); video.update(p.frame[0])
        return p.save(), video.digest(), bytes(p.samples)
    p.restore(replay_base); expected = replay()
    p.restore(replay_base); assert replay() == expected
    assert hashlib.sha256(source.read_bytes()).digest() == digest
    print('Passed: QS0 native walking animation, constant trailing offset, no respawn/flash, scene completion, independent controls, save/video/audio replay.')
finally:
    p.close()
