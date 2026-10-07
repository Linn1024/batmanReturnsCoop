"""Reported scene-clear QS0: mirrored blue pose uses current native tiles."""
import ctypes as C
import hashlib
import struct
import zipfile
from native_probe import Probe, ROOT

source = ROOT/'diagnostics/corrupt-blue-qs0.State'
digest = hashlib.sha256(source.read_bytes()).digest()
raw = zipfile.ZipFile(source).read('Core.bin')
state = raw[4:4+struct.unpack_from('<I', raw)[0]]
p = Probe()
try:
    p.restore(state)
    health, weapon = p.player(2, 0x8a), p.player(2, 0x8e)
    buf = C.create_string_buffer(p.core.br_state_size())
    checked = 0
    for frame in range(350):
        p.run(p2=64 if frame % 20 < 10 else 2)
        if frame and p.status()[0] and p.word(0xd6):
            p.core.br_state_save(buf)
            # Legacy BR layout: private tile cache then committed tile cache.
            tiles = buf.raw[1548+65536:1548+131072]
            native = C.string_at(p.core.retro_get_memory_data(3), 65536)
            assert tiles[0xc000:0xcc00] == native[0xc000:0xcc00], ('Stale body tiles', frame)
            assert p.player(2, 0x8a) == health and p.player(2, 0x8e) == weapon
            checked += 1
        assert not p.status()[2]
        if frame == 2:
            p.screenshot(ROOT/'diagnostics/scene-clear-blue-fixed.png')
    assert checked > 200
    p.restore(state)
    p.run(2)
    saved = p.save()
    def replay():
        video = hashlib.sha256()
        p.samples.clear()
        for _ in range(200):
            p.run()
            video.update(p.frame[0])
        return p.save(), video.digest(), bytes(p.samples)
    expected = replay()
    p.restore(saved)
    assert replay() == expected
    assert hashlib.sha256(source.read_bytes()).digest() == digest
    print('Passed: QS0 scene-clear blue tiles match native pose, private health/weapon intact, state/video/audio replay')
finally:
    p.close()
