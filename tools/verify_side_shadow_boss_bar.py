"""Reported 2D QS0: black shadow and boss health colour-layer depletion."""
import hashlib
import struct
import zipfile
from PIL import Image
from native_probe import Probe, ROOT

source = ROOT/'diagnostics/side-shadow-boss-qs0.State'
digest = hashlib.sha256(source.read_bytes()).digest()
data = zipfile.ZipFile(source).read('Core.bin')
p = Probe()
try:
    p.restore(data[4:4+struct.unpack_from('<I', data)[0]])
    p.run(2)
    assert p.word(0x9a) == 2
    p.screenshot(ROOT/'diagnostics/side-shadow-boss-fixed.png')
    before = Image.open(ROOT/'diagnostics/side-shadow-boss-before.png').convert('RGB')
    after = Image.open(ROOT/'diagnostics/side-shadow-boss-fixed.png').convert('RGB')
    before = before.crop((0, 0, before.width, before.height-32))
    after = after.crop((0, 32, after.width, after.height))
    feet = p.player(2, 0x32c) | p.player(2, 0x32d) << 8
    changed = [(x, y) for y in range(40, after.height) for x in range(after.width)
               if before.getpixel((x, y)) != after.getpixel((x, y))]
    assert len(changed) == 61
    assert all(feet-3 <= y <= feet and after.getpixel((x, y)) == (0, 0, 0)
               for x, y in changed), 'Altered blue body outside ground shadow'
    base = p.save(); solid = {}
    top = Image.open(ROOT/'diagnostics/side-shadow-boss-fixed.png').convert('RGB')
    assert top.crop((152, 16, 248, 32)).getbbox() is not None
    assert top.crop((168, 25, 248, 31)).tobytes() != top.crop((168, 65, 248, 71)).tobytes(), 'Boss bar still duplicated in game frame'
    def render(hp):
        p.restore(base)
        for address in (0x666, 0x19ae, 0x19a6):
            p.set_word(1, address, hp)
        p.set_word(1, 0x19a8, 128)  # Request the native HUD redraw.
        p.run(4)
        file = ROOT/f'diagnostics/boss-bar-{hp}.png'; p.screenshot(file)
        im = Image.open(file).convert('RGB')
        return im
    # Native final-layer tones; transparent empty pixels now reveal black.
    native = Image.open(ROOT/'diagnostics/boss-bar-native-79.png').convert('RGB')
    solid[80] = [native.getpixel((168, y)) for y in range(33, 39)]
    for hp in (0, 1, 40, 79):
        im = render(hp)
        for y in range(25, 31):
            assert [im.getpixel((x, y)) for x in range(168, 248)] == [solid[80][y-25]]*hp + [(0, 0, 0)]*(80-hp)
    im = render(80)
    for y in range(25, 31):
        assert [im.getpixel((x, y)) for x in range(168, 248)] == [solid[80][y-25]]*80
    for hp in (160, 240, 320, 400):
        im = render(hp); solid[hp] = []
        for y in range(25, 31):
            row = [im.getpixel((x, y)) for x in range(168, 248)]
            assert len(set(row)) == 1
            solid[hp].append(row[0])
        assert solid[hp][0] == solid[hp][2] != solid[hp][3] == solid[hp][5]
    assert len({tuple(value) for value in solid.values()}) == 5
    for hp in (399, 319, 288, 241, 161, 81):
        im = render(hp)
        layer = (hp-1)//80; fill = (hp-1)%80+1
        for y in range(25, 31):
            row = [im.getpixel((x, y)) for x in range(168, 248)]
            assert row == [solid[(layer+1)*80][y-25]]*fill + [solid[layer*80][y-25]]*(80-fill)
        # Preserve the original native bar border and boss portrait/name.
        assert [im.getpixel((x, 24)) for x in range(168, 248)] == [before.getpixel((x, 32)) for x in range(168, 248)]
    p.restore(base); saved = p.save()
    def replay():
        video = hashlib.sha256(); p.samples.clear()
        for frame in range(120):
            p.run(p2=256 if frame % 24 == 0 else 0)
            video.update(p.frame[0])
        return p.save(), video.digest(), bytes(p.samples)
    expected = replay(); p.restore(saved); assert replay() == expected
    assert p.status()[2] == 0
    assert hashlib.sha256(source.read_bytes()).digest() == digest
    # Reported exact-80-HP QS0 must not fall through to native solid green.
    latest = ROOT/'diagnostics/boss-green-qs0.State'
    latest_digest = hashlib.sha256(latest.read_bytes()).digest()
    data = zipfile.ZipFile(latest).read('Core.bin')
    p.restore(data[4:4+struct.unpack_from('<I', data)[0]])
    p.run(3); assert p.word(0x19ae) == 80
    file = ROOT/'diagnostics/boss-green-fixed.png'; p.screenshot(file)
    im = Image.open(file).convert('RGB')
    for y in range(25, 31):
        assert [im.getpixel((x, y)) for x in range(168, 248)] == [solid[80][y-25]]*80
    assert hashlib.sha256(latest.read_bytes()).digest() == latest_digest
    print('Passed: black 2D shadow, original final bar/transparency unchanged, two-tone added layers and depletion boundaries, native border, save/video/audio replay.')
finally:
    p.close()
