"""QS2: restore native fire gaps without changing the collision map."""
import ctypes as C
import hashlib
import struct
import zipfile
from native_probe import Probe, ROOT

source = ROOT/'diagnostics/falling-fire-qs2.State'
digest = hashlib.sha256(source.read_bytes()).digest()
raw = zipfile.ZipFile(source).read('Core.bin')
state = raw[4:4+struct.unpack_from('<I', raw)[0]]
p = Probe()
try:
    p.restore(state)
    terrain = bytes(p.ram[0x19000:0x1a000])
    p.run(p1=8)  # QS2 was paused.
    p.run(3)
    assert p.word(0x17c0) == p.word(0x17a0)-1024
    assert bytes(p.ram[0x19000:0x1a000]) == terrain
    p.screenshot(ROOT/'diagnostics/falling-fire-fixed.png')
    # The visible safe strip is 2880..3007 in native world coordinates.
    # Its fire-background metatiles must come from native RAM definitions.
    vram = C.string_at(p.core.retro_get_memory_data(3), 65536)
    native = (ROOT/'diagnostics/fire-fresh-native-qs2.core.vram').read_bytes()
    for y in range(192, 256, 8):
        for x in range(1856, 1952, 8):
            address = 2*(0x1000+((x&256)<<2)+((y&256)<<3)
                         +((y&248)<<2)+((x&248)>>3))
            assert vram[address:address+2] == native[address:address+2], (x,y)
    start = p.save()
    def replay():
        video = hashlib.sha256()
        p.samples.clear()
        for f in range(240):
            p.run(p1=128 if f<120 else 64,
                  p2=256 if f%20==0 else 0)
            video.update(p.frame[0])
            assert not p.status()[2]
        return p.save(), video.digest(), bytes(p.samples)
    expected = replay()
    p.restore(start)
    assert replay() == expected
    p.restore(start)
    # Isolate standing damage from the nearby fire-breathing enemy.
    for slot in range(0x820, 0xeb0, 0x50):
        if p.word(slot+0x10) >= 128:
            p.ram[slot:slot+0x50] = bytes(80)
    for player, x in ((1,112), (2,144)):
        for address, value in ((0x328,x), (0x358,x), (0x350,0),
                               (0x3b0,24), (0x3f8,0)):
            p.set_word(player, address, value)
    hp = p.status()[7:9]
    p.run(150)
    assert p.status()[7:9] == hp, 'Safe platform caused fire damage'
    assert hashlib.sha256(source.read_bytes()).digest() == digest
    print('Passed: QS2 native safe-gap graphics, unchanged collision, movement and state/video/audio replay')
finally:
    p.close()
