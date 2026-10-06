"""Reported QS0: floor collapse reaches the lower room and the next section."""
import hashlib
import struct
import zipfile
from native_probe import Probe, ROOT

source=ROOT/'diagnostics/script-latest-qs0.State'
digest=hashlib.sha256(source.read_bytes()).hexdigest()
data=zipfile.ZipFile(source).read('Core.bin')
raw=data[4:4+struct.unpack_from('<I',data)[0]]
p=Probe()
try:
    p.restore(raw)
    assert p.word(0x76)==3 and p.word(0x17a0)==3584
    for frame in range(300):
        p.run()
        assert p.status()[2]==0
        if frame==110:fall_save=p.save()
        if p.word(0x17b0)==512:break
    else:raise AssertionError(('Collapse never reached the lower room',p.status(),p.word(0x17b0)))
    descent_frames=frame+1
    p.run(80)
    assert p.word(0x17b0)==512
    assert all(160<=p.status()[a]<=224 for a in (4,6)),p.status()
    landed=p.save()
    for player in (1,2):
        p.restore(landed)
        index=3 if player==1 else 5
        before=p.status()[index]+p.word(0x17a0)
        p.run(8,p1=128 if player==1 else 0,p2=128 if player==2 else 0)
        assert p.status()[index]+p.word(0x17a0)>before+5
    p.restore(fall_save);p.run(100)
    expected=p.save(),p.frame[0]
    p.restore(fall_save);p.run(100)
    assert (p.save(),p.frame[0])==expected
    p.screenshot(ROOT/'diagnostics/floor-collapse-fixed.png')
    p.restore(landed)
    for frame in range(400):
        p.run(p1=128,p2=128)
        if p.word(0x76)==4:break
    else:raise AssertionError('Lower room cannot exit to the next section')
    assert hashlib.sha256(source.read_bytes()).hexdigest()==digest
    print(f'Passed: collapse reached lower room in {descent_frames} frames, both landed, independent controls, save replay, next section reached, QS0 unchanged.')
finally:p.close()
