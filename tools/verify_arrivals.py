"""Synchronised arrivals: reported entrance save and all seven level starts."""
import hashlib, struct, zipfile, ctypes as C
from native_probe import Probe, ROOT

source=ROOT/'diagnostics/arrival-qs0.State'
digest=hashlib.sha256(source.read_bytes()).hexdigest()
d=zipfile.ZipFile(source).read('Core.bin')
p=Probe()
def word(pl,a):return p.player(pl,a)|p.player(pl,a+1)<<8
def signed(v):return v if v<32768 else v-65536
def pose():
    assert signed(word(1,0x328))-signed(word(2,0x328))==40
    for a in (0x320,0x32c,0x350,0x35c,0x3b0):
        assert word(1,a)==word(2,a),(hex(a),word(1,a),word(2,a))
def arriving():
    # Legacy BR prefix: 20-byte header, three 486-byte player contexts,
    # alignment padding, AI word, then owner[16].
    data=C.create_string_buffer(p.core.br_state_size())
    p.core.br_state_save(data)
    return struct.unpack_from('<I',data.raw,1484+12*4)[0]!=0
def press(button):p.run(p1=button);p.run()
try:
    p.restore(d[4:4+struct.unpack_from('<I',d)[0]])
    for frame in range(70):
        p.run()
        if p.status()[0] and arriving():pose()
        assert p.status()[2]==0
    saved=p.save();p.run(80);expected=p.save(),p.frame[0]
    p.restore(saved);p.run(80);assert (p.save(),p.frame[0])==expected
    p.screenshot(ROOT/'diagnostics/arrival-fixed.png')
    ready=p.save()
    for pl in (1,2):
        p.restore(ready);before=word(pl,0x328)
        p.run(8,p1=128 if pl==1 else 0,p2=128 if pl==2 else 0)
        assert word(pl,0x328)>before
    p.close();p=Probe();p.boot();base=p.save()
    mirrored=[];vehicle=[]
    for level,stage in enumerate((0,2,5,8,12,13,15)):
        p.restore(base);press(265)
        for _ in range(8):press(32)
        for _ in range(level):press(128)
        press(32);press(32);press(256)
        count=0
        for frame in range(1600):
            p.run()
            if p.word(0x76)!=stage or p.word(0x32)!=6:continue
            if p.word(0x9a) not in (1,2):
                vehicle.append(level+1);break
            if p.status()[0] and arriving():
                pose();count+=1
            if frame>100 and p.status()[0] and not arriving() and p.word(0x3b0) and not p.word(0x6a):break
        else:raise AssertionError(('Entrance did not finish',level+1,p.status()))
        mirrored.append((level+1,count))
        assert p.status()[2]==0
    assert hashlib.sha256(source.read_bytes()).hexdigest()==digest
    print('Passed: saved arrival poses match, no stale partner, controls after landing, save replay, level arrivals',mirrored,'vehicle starts',vehicle)
finally:p.close()
