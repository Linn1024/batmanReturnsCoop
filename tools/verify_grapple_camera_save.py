"""Repeated hook input from user QS0 must cross the fire without camera-edge falls."""
import hashlib, struct, zipfile
from native_probe import Probe, ROOT
source=ROOT/'diagnostics/grapple-camera-qs0.State'
digest=hashlib.sha256(source.read_bytes()).hexdigest()
with zipfile.ZipFile(source) as z: data=z.read('Core.bin')
raw=data[4:4+struct.unpack_from('<I',data)[0]]
p=Probe()
try:
    for swapped in (False,True):
        for timing in ((20,20),(20,24),(24,20)):
            p.restore(raw)
            if swapped:
                bodies=[bytes(p.player(pl,a) for a in range(0x320,0x460)) for pl in (1,2)]
                for pl in (1,2):
                    for off,v in enumerate(bodies[2-pl]):p.set_player(pl,0x320+off,v)
            previous=None
            for frame in range(420):
                p.run(p1=256 if frame%timing[0]==0 else 0,
                      p2=256 if frame%timing[1]==0 else 0)
                state=p.status()
                assert all(0<=state[a]<=242 for a in (4,6)), (swapped,timing,frame,state)
                assert state[2]==0
                xs=[v if v<32768 else v-65536 for v in (state[3],state[5])]
                assert all(48<=x<=240 for x in xs), ('partner left viewport',swapped,timing,frame,xs)
                world=[x+p.word(0x17a0) for x in xs]
                if previous:
                    assert all(abs(a-b)<=16 for a,b in zip(world,previous)), ('catch-up jump',swapped,timing,frame,world,previous)
                previous=world
                for pl in (1,2):
                    def word(a):return p.player(pl,a)|p.player(pl,a+1)<<8
                    if word(0x40e)==3 and word(0x420)==1:
                        assert (word(0x328)-word(0x418))&65535==word(0x36a), ('hook shifted independently',pl,frame)
            assert p.word(0x17a0)>=3580, (swapped,timing,p.word(0x17a0))
    # Loading an already offscreen body must recover immediately, even
    # when both players are together outside the viewport (small gap).
    for players in ((1,),(2,),(1,2)):
        for shift in (-400,400):
            p.restore(raw)
            p.run(12,p1=256,p2=256)
            for pl in players:
                for a in (0x328,0x358,0x418):
                    v=p.player(pl,a)|p.player(pl,a+1)<<8
                    p.set_word(pl,a,v+shift)
            p.restore(p.save())
            p.run()
            assert all(48<=p.status()[a]<=240 for a in (3,5)), ('offscreen saved body',players,shift,p.status())
            assert p.status()[2]==0
    # Backward camera motion cannot opt either body out of visibility.
    p.restore(raw)
    for i in range(240):
        p.run(p1=64|(256 if i%20==0 else 0),p2=256 if i%24==0 else 0)
        if 2304<=p.word(0x17a0)<=3584 and 240<=p.word(0x17b0)<=288:
            assert all(48<=p.status()[a]<=240 for a in (3,5)), ('backward pan',i,p.status())
    p.restore(raw)
    for i in range(360):p.run(p1=256 if i%20==0 else 0,p2=256 if i%24==0 else 0)
    p.screenshot(ROOT/'diagnostics/grapple-camera-fixed.png')
    saved=p.save()
    p.run(40)
    expected=p.save(),p.frame[0]
    p.restore(saved);p.run(40)
    assert (p.save(),p.frame[0])==expected
    assert hashlib.sha256(source.read_bytes()).hexdigest()==digest
    print('Passed: repeated hooks with equal/staggered timing and swapped bodies, traversal completed, both players visible, smooth displacement and aligned hooks without falls, save replay, original QS0 unchanged.')
finally: p.close()
