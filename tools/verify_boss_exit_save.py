"""Latest QS0: boss defeat must finish and reach playable next stage."""
import hashlib
import struct
import zipfile
from native_probe import Probe, ROOT

source = ROOT/'diagnostics/freeze-latest-qs0.State'
digest = hashlib.sha256(source.read_bytes()).hexdigest()
with zipfile.ZipFile(source) as z:
    data = z.read('Core.bin')
p = Probe()
try:
    p.restore(data[4:4+struct.unpack_from('<I', data)[0]])
    assert p.word(0x76) == 1 and p.word(0xd6) == 1
    for frame in range(800):
        p.run()
        if p.word(0x76) == 2:
            break
    else:
        raise AssertionError('Boss exit never advanced the stage')
    exit_frames = frame+1
    for frame in range(3000):
        p.run(p1=8 if frame % 120 == 0 else 0)
        if p.word(0x32) == 6 and p.status()[0] and p.word(0x3b0) and not p.word(0x6a):
            break
    else:
        raise AssertionError('Next stage never became playable')
    p.run(30)
    base = p.save()
    for player in (1, 2):
        p.restore(base)
        index = 3 if player == 1 else 5
        before = p.status()[index]+p.word(0x17a0)
        p.run(12, p1=128 if player == 1 else 0, p2=128 if player == 2 else 0)
        assert p.status()[index]+p.word(0x17a0) > before+10
    assert p.status()[2] == 0
    assert hashlib.sha256(source.read_bytes()).hexdigest() == digest
    p.screenshot(ROOT/'diagnostics/boss-exit-next-stage.png')
    print(f'Passed: boss exit completed in {exit_frames} frames; next stage playable with both controllers; QS0 unchanged.')
finally:
    p.close()
