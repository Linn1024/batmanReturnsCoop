"""Reported blue ground shadow: only floor pixels change, with save replay."""
import hashlib
import struct
import zipfile
from PIL import Image
from native_probe import Probe, ROOT

source = ROOT/'diagnostics/blue-shadow-qs0.State'
digest = hashlib.sha256(source.read_bytes()).digest()
data = zipfile.ZipFile(source).read('Core.bin')
p = Probe()
try:
    p.restore(data[4:4+struct.unpack_from('<I', data)[0]])
    p.run(2)
    feet = p.player(2, 0x32c) | p.player(2, 0x32d) << 8
    p.screenshot(ROOT/'diagnostics/blue-shadow-fixed.png')
    before = Image.open(ROOT/'diagnostics/blue-shadow-before.png').convert('RGB')
    after = Image.open(ROOT/'diagnostics/blue-shadow-fixed.png').convert('RGB')
    before = before.crop((0, 0, before.width, before.height-32))
    after = after.crop((0, 32, after.width, after.height))
    changed = [(x, y) for y in range(40, after.height) for x in range(after.width)
               if before.getpixel((x, y)) != after.getpixel((x, y))]
    assert len(changed) > 32
    assert all(feet-3 <= y <= feet and after.getpixel((x, y)) == (0, 0, 0)
               for x, y in changed), 'Changed pixels outside the black ground shadow'
    # Body pixels above the floor are identical, including blue shading.
    assert any(b > r+40 for r, g, b in after.crop((120, 80, 175, feet-8)).getdata())
    saved = p.save()
    def replay():
        video = hashlib.sha256(); p.samples.clear()
        for frame in range(180):
            p.run(p2=(128 if frame < 30 else 0) | (1 if frame == 40 else 0))
            video.update(p.frame[0])
        return p.save(), video.digest(), bytes(p.samples)
    expected = replay(); p.restore(saved)
    assert replay() == expected
    assert p.status()[2] == 0
    assert hashlib.sha256(source.read_bytes()).digest() == digest
    print('Passed: QS0 shadow pixels black, blue body unchanged, movement/jump/save/video/audio replay, original save unchanged.')
finally:
    p.close()
