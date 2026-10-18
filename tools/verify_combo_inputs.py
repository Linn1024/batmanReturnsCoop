"""Each Batman's buffered circle attack must use only that controller."""
import hashlib
from native_probe import Probe, ROOT

p=Probe()
try:
    p.boot()
    base=p.save()
    for control,attack,jump in ((0,2,1),(2,1,256),(4,1,2),(6,2,1)):
        for player in (1,2):
            def run(own=0,other=0):
                p.run(p1=own if player==1 else other,
                      p2=own if player==2 else other)
            p.restore(base)
            p.set_word(1,0x1fb8,control)
            run(attack)
            p.run(7)
            # Reported case: one is already punching, partner uses jump+hit.
            run(attack,attack|jump)
            assert p.player(player,0x350)==9, (control,player,'Borrowed circle attack')
            assert p.player(3-player,0x350)==24
            if player==2:
                assert p.word(0xec)&0xc000==0xc000, 'P1 input buffer was not restored'
            p.restore(base)
            p.set_word(1,0x1fb8,control)
            run(attack)
            p.run(6)
            run(jump)
            # Native buffered combo: own jump then own hit on adjacent frames.
            buffered=p.save()
            run(attack)
            assert p.player(player,0x350)==24, (control,player,'Own buffered combo broken')
            assert p.player(3-player,0x350)==0
            expected=p.save(),p.frame[0]
            p.restore(buffered)
            run(attack)
            assert (p.save(),p.frame[0])==expected
    p.restore(base)
    p.run(p1=2,p2=2)
    p.run(6)
    p.run(p1=1,p2=1)
    buffered=p.save()
    def replay():
        video=hashlib.sha256()
        p.samples.clear()
        for frame in range(120):
            p.run(p1=2 if frame%12==0 else 0,
                  p2=2 if frame%17==0 else 0)
            video.update(p.frame[0])
            assert not p.status()[2]
            if frame==0:
                assert p.player(1,0x350)==24 and p.player(2,0x350)==24
                p.screenshot(ROOT/'diagnostics/independent-circle-attacks.png')
        return p.save(),video.digest(),bytes(p.samples)
    expected=replay()
    p.restore(buffered)
    assert replay()==expected
    print('Passed: independent punch/circle inputs on both controllers, all four control types, own buffered combos, simultaneous circles and state/video/audio replay')
finally:
    p.close()
