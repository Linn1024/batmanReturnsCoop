"""Reported QS0: Stungun combat must not retain its introduction input lock."""
import ctypes as C
import hashlib
import struct
import zipfile
from native_probe import Probe, ROOT

source=ROOT/'diagnostics/movement-blocked-qs0.State'
digest=hashlib.sha256(source.read_bytes()).digest()
wrapped=zipfile.ZipFile(source).read('Core.bin')
state=wrapped[4:4+struct.unpack_from('<I',wrapped)[0]]
p=Probe()
try:
    p.restore(state)
    assert p.word(0x76)==1 and p.word(0xd6)==1 and p.word(0x6a)==1
    assert p.word(0x560)==0xae and p.word(0x58c)==15
    p.run(2)
    assert p.word(0xd6)==0 and p.word(0x6a)==0
    assert p.word(0x576)>0 and p.word(0x74)==1, 'Recovery skipped live boss'
    for player in (1,2):
        p.restore(state)
        p.run(2)
        index=3 if player==1 else 5
        before=p.status()[index]+p.word(0x17a0)
        p.run(12,p1=128 if player==1 else 0,p2=128 if player==2 else 0)
        assert p.status()[index]+p.word(0x17a0)>before+10, player
    # Protect health to isolate independent left/right movement from the
    # boss attack already in flight beside P2 in the reported save.
    p.restore(state)
    n=p.core.br_state_size()
    buf=C.create_string_buffer(n)
    p.core.br_state_save(buf)
    private=bytearray(buf.raw)
    struct.pack_into('<I',private,1484,struct.unpack_from('<I',private,1484)[0]|1)
    p.core.br_state_load(C.create_string_buffer(bytes(private)))
    p.run(2)
    ready=p.save()
    for player in (1,2):
        for direction in (64,128):
            p.restore(ready)
            # Both players start away from the true left boundary.
            p.set_word(player,0x328,120)
            p.set_word(player,0x358,120)
            before=120+p.word(0x17a0)
            p.run(12,p1=direction if player==1 else 0,
                  p2=direction if player==2 else 0)
            index=3 if player==1 else 5
            change=p.status()[index]+p.word(0x17a0)-before
            assert change>10 if direction==128 else change<-10, (player,direction,change)
    def replay():
        video=hashlib.sha256();p.samples.clear()
        for frame in range(180):
            p.run(p1=128 if frame<80 else 64,
                  p2=128 if frame<110 else 2 if frame%20==0 else 0)
            video.update(p.frame[0])
            assert not p.word(0xd6) and not p.word(0x6a)
            assert not p.status()[2]
        return p.save(),video.digest(),bytes(p.samples)
    p.restore(ready);expected=replay()
    p.restore(ready);assert replay()==expected
    assert hashlib.sha256(source.read_bytes()).digest()==digest
    p.screenshot(ROOT/'diagnostics/boss-control-lock-fixed.png')
    print('Passed: exact QS0 unlock, live boss retained, independent left/right movement, no relock, state/video/audio replay and original save preserved')
finally:
    p.close()
