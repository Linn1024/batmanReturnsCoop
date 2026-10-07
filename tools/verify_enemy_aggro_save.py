"""Reported QS0: side-view enemies target either nearer Batman."""
import ctypes as C
import struct
import zipfile
from native_probe import Probe, ROOT

raw = zipfile.ZipFile(ROOT/'diagnostics/enemy-aggro-qs0.State').read('Core.bin')
state = raw[4:4+struct.unpack_from('<I', raw)[0]]
p = Probe()
try:
    for nearer in (2, 1):
        p.restore(state)
        if nearer == 1:
            a = [p.player(1, addr) for addr in range(0x320, 0x500)]
            b = [p.player(2, addr) for addr in range(0x320, 0x500)]
            for i, addr in enumerate(range(0x320, 0x500)):
                p.set_player(1, addr, b[i])
                p.set_player(2, addr, a[i])
        buf = C.create_string_buffer(p.core.br_state_size())
        p.core.br_state_save(buf)
        flags = struct.unpack_from('<I', buf.raw, 1484)[0]
        struct.pack_into('<I', buf, 1484, flags & ~1)
        p.core.br_state_load(buf)
        base = p.save()
        def scenario():
            p.run(40, p1=128 if nearer == 1 else 0,
                  p2=128 if nearer == 2 else 0)
            p.run(40)
            for enemy in (0x640, 0x730):
                assert p.word(enemy+8) >= 150, ('Enemy followed trailing player', nearer, enemy)
                assert not p.word(enemy+4) & 0x20, ('Enemy faces trailing player', nearer, enemy)
            p.run(20)
            hp = p.status()[7:9]
            assert hp[nearer-1] < 80 and hp[2-nearer] == 80, (nearer, hp)
            assert p.status()[2] == 0
        p.samples.clear()
        scenario()
        expected = p.save(), p.frame, bytes(p.samples)
        p.restore(base)
        p.samples.clear()
        scenario()
        assert (p.save(), p.frame, bytes(p.samples)) == expected
    print('Passed: QS0 enemies chase, face and damage either nearer player; state/video/audio replay')
finally:
    p.close()
