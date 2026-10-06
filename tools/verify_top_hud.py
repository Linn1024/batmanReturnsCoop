"""Native-style P2 HUD above an intact game frame, with private HP/weapon."""
import hashlib
from PIL import Image
from native_probe import Probe, ROOT

p = Probe()
def screenshot(name):
    file = ROOT/f'diagnostics/{name}.png'; p.screenshot(file)
    return Image.open(file).convert('RGB')
try:
    p.boot(); base = p.save(); im = screenshot('top-hud')
    assert im.size == (256, 256)
    # Full health is the exact native bar, with the same border and two tones.
    assert im.crop((24, 24, 104, 32)).tobytes() == im.crop((24, 64, 104, 72)).tobytes()
    assert im.crop((144, 24, 256, 32)).getbbox() is None, 'Duplicated native enemy HUD'
    assert any(im.getpixel((x, y)) != im.getpixel((x, y+40))
               for y in range(8, 16) for x in range(144, 248)
               if im.getpixel((x, y)) != (0, 0, 0)), 'Score still duplicated in the game frame'
    assert im.crop((8, 16, 24, 32)).tobytes() != im.crop((8, 56, 24, 72)).tobytes()
    assert im.crop((24, 16, 104, 24)).getcolors() and len(im.crop((24, 16, 104, 24)).getcolors()) == 3
    assert all(im.getpixel((x, y)) == (0, 0, 0)
               for y in range(32, 48) for x in range(256) if not (115 <= x < 141 and y < 37))
    assert all(im.getpixel((115, y)) == im.getpixel((140, y)) == (255, 250, 255)
               for y in range(11, 37))
    assert all(im.getpixel((x, y)) == (255, 250, 255) for y in (11, 36) for x in range(115, 141))
    assert all(im.getpixel((x, y)) == im.getpixel((x, y+40))
               for y in range(11, 37) for x in range(115, 141)
               if x in (115, 140) or y in (11, 36)), 'P2 frame differs from native dimensions'
    assert im.crop((116, 12, 140, 16)).getbbox() is None
    assert im.crop((116, 32, 140, 36)).getbbox() is None
    assert all(im.getpixel((x, y)) == im.getpixel((x, y+40))
               for y in range(16, 32) for x in range(120, 136)
               if im.getpixel((x, y)) != (0, 0, 0)), 'P2 item uses wrong native tiles'
    health = {}; weapon = {}
    for hp in (0, 1, 40, 79, 80):
        p.restore(base); p.set_player(2, 0x8a, hp); p.run()
        current = screenshot(f'top-hud-hp-{hp}')
        health[hp] = current.crop((24, 24, 104, 32)).tobytes()
        assert p.read(0x8a) == 80, 'P2 HUD altered native P1 health'
        assert current.crop((24, 64, 104, 72)).tobytes() == im.crop((24, 64, 104, 72)).tobytes()
        assert current.crop((24, 24, 104, 25)).tobytes() == im.crop((24, 24, 104, 25)).tobytes()
    assert len(set(health.values())) == 5
    for item in (0, 1, 2):
        p.restore(base); p.set_player(2, 0x8e, item); p.run()
        current = screenshot(f'top-hud-weapon-{item}')
        weapon[item] = current.crop((120, 16, 136, 32)).tobytes()
        assert current.crop((112, 48, 144, 80)).tobytes() == im.crop((112, 48, 144, 80)).tobytes()
        assert current.crop((116, 12, 140, 16)).getbbox() is None
        assert current.crop((116, 32, 140, 36)).getbbox() is None
        assert p.read(0x8e) == 1
        # Verify all four icon tiles against the native P1 rendering, not
        # merely that changing the index produces different pixels.
        p.restore(base); p.set_player(1, 0x8e, item); p.run(2)
        native = screenshot(f'top-hud-native-weapon-{item}')
        assert all(current.getpixel((x, y)) == native.getpixel((x, y+40))
                   for y in range(16, 32) for x in range(120, 136)
                   if current.getpixel((x, y)) != (0, 0, 0))
    assert len(set(weapon.values())) == 3
    p.restore(base); p.run(p2=4); p.run()
    assert p.read(0x8e) == 1 and p.player(2, 0x8e) == 2, 'P2 selection changed both players'
    screenshot('top-hud-different-weapons')
    p.restore(base); saved = p.save()
    def replay():
        video = hashlib.sha256(); p.samples.clear()
        for frame in range(180):
            p.run(p2=(128 if frame < 25 else 0) | (1 if frame == 30 else 0))
            video.update(p.frame[0])
        return p.save(), video.digest(), bytes(p.samples)
    expected = replay(); p.restore(saved); assert replay() == expected
    assert p.status()[2] == 0
    p.restore(base); p.run(450, p1=128, p2=128); p.run(p1=2)
    assert p.word(0x19a4) and not p.word(0x19ac), 'No ordinary enemy HUD'
    enemy = screenshot('ordinary-enemy-top-hud')
    assert enemy.crop((152, 16, 248, 32)).getbbox() is not None
    assert any(enemy.getpixel((x, y)) != enemy.getpixel((x, y+40))
               for y in range(16, 32) for x in range(152, 248)
               if enemy.getpixel((x, y)) != (0, 0, 0)), 'Enemy HUD still duplicated'
    print('Passed: separate HUD icons, full native item tiles on correct page, complete frame and unclipped margins for all items, unchanged P1 icon, readable name, black separator, independent selection, save/video/audio replay.')
finally:
    p.close()
