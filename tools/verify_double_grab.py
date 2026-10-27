"""Native one/two enemy grab eligibility and co-op ownership."""
import ctypes as C
import hashlib
import struct
from native_probe import Probe, ROOT

def setup(p,base,player=1,partner=145,second=140):
    p.restore(base)
    enemy=bytes(p.ram[0x640:0x730])
    for slot in range(0x550,0xeb0,0xf0):p.ram[slot:slot+0xf0]=bytes(0xf0)
    for slot,x in ((0x550,120),(0x640,second)):
        p.ram[slot:slot+0xf0]=enemy
        for off,value in ((8,x),(0x18,40),(0x14,0),(0x3c,50),(0x3e,0),
                          (0x40,20),(0x44,0),(0x4e,int(x>130)),(0x26,40)):
            p.ram[slot+off]=value&255;p.ram[slot+off+1]=value>>8
    for who,x in ((player,130),(3-player,partner)):
        for addr,value in ((0x328,x),(0x338,40),(0x350,0),(0x334,0),
                           (0x3f8,0),(0x33b,0),(0x33f,0),(0x343,0)):
            p.set_word(who,addr,value)

def sequence(p,player,frames=35):
    result=[]
    for frame in range(frames):
        p.run(p1=128 if player==1 else 0,p2=128 if player==2 else 0)
        result.append((p.player(player,0x350),p.word(0x58c),p.word(0x67c)))
    return result

p=Probe()
try:
    p.boot();p.run(450,p1=128,p2=128);base=p.save()
    # This diagnostic DLL disables co-op simulation and cheats; only the
    # original game executes. Build locally when auditing native behavior.
    reference=ROOT/'diagnostics/grab-original-reference.dll'
    if reference.exists():
        ns={'__file__':str(ROOT/'tools/native_probe.py'),'__name__':'native_reference'}
        exec((ROOT/'tools/native_probe.py').read_text().replace(
            "ROOT/'engine/snes9x2005_libretro.dll'",
            "ROOT/'diagnostics/grab-original-reference.dll'"),ns)
        q=ns['Probe']()
        try:
            for second in (140,200):
                setup(q,base[:-56],second=second)
                original=sequence(q,1)
                setup(p,base,partner=10,second=second)
                actual=sequence(p,1)
                assert actual[:12]==original[:12], (second,[(i,a,b) for i,(a,b) in enumerate(zip(actual,original)) if a!=b][:5])
                if second==140:assert any(row[0]==15 for row in original[:12])
                else:assert all(row[0]!=15 for row in original[:12])
            print('Passed: exact native single/double grab initiation sequences')
        finally:q.close()
    for player in (1,2):
        for partner in (10,130,145,160):
            setup(p,base,player=player,partner=partner)
            actual=sequence(p,player)
            assert any(row[0]==15 for row in actual), (player,partner,actual[:5])
            assert p.player(3-player,0x350)==0, (player,partner,'Idle partner stole grab')
            assert not p.status()[2]
        setup(p,base,player=player,second=200)
        assert all(row[0]!=15 for row in sequence(p,player)[:12]), 'Grab range widened'
    # Independent simultaneous holds: one enemy each must not become a
    # fake two-enemy move; two enemies each must allow two real clashes.
    for double in (False,True):
        setup(p,base)
        template=bytes(p.ram[0x550:0x640])
        for slot in range(0x550,0xeb0,0xf0):p.ram[slot:slot+0xf0]=bytes(0xf0)
        targets=((0x550,80),(0x640,100),(0x730,180),(0x820,200)) if double else ((0x550,100),(0x640,200))
        for slot,x in targets:
            p.ram[slot:slot+0xf0]=template
            p.ram[slot+8]=x;p.ram[slot+9]=0
            p.ram[slot+0x4e]=int(x in (100,200))
        for player,x in ((1,90),(2,190)):
            p.set_word(player,0x328,x);p.set_word(player,0x358,x)
        p.run(4,p1=128,p2=128)
        assert p.player(1,0x350)==(15 if double else 13)
        assert p.player(2,0x350)==(15 if double else 13)
    setup(p,base,player=2,partner=145)
    p.run(3,p2=128)
    captured=p.save()
    def replay():
        video=hashlib.sha256();p.samples.clear()
        for frame in range(120):
            p.run(p2=128 if frame<45 else 2 if frame%12==0 else 0)
            video.update(p.frame[0]);assert not p.status()[2]
        return p.save(),video.digest(),bytes(p.samples)
    expected=replay();p.restore(captured);assert replay()==expected
    print('Passed: both owners, nearby/overlapping idle partner, native range, held-enemy ownership and save/state/video/audio replay')
finally:p.close()
