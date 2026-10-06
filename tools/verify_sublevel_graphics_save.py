"""Reload the reported rooftop-room QS0 through the real menu."""
import ctypes as C
import hashlib
import struct
import zipfile
from PIL import Image
from native_probe import Probe, ROOT

source = ROOT/'diagnostics/sublevel-graphics-qs0.State'
digest = hashlib.sha256(source.read_bytes()).digest()
p = Probe()
def owners():
    buf = C.create_string_buffer(p.core.br_state_size()); p.core.br_state_save(buf)
    return struct.unpack_from('<16I', buf.raw, 1484)
def press(button):
    p.run(p1=button); p.run()
try:
    data = zipfile.ZipFile(source).read('Core.bin')
    p.restore(data[4:4+struct.unpack_from('<I', data)[0]])
    press(265)
    assert owners()[5:7] == (3, 3)
    while owners()[2] != 10: press(32)
    press(256)
    sections = set(); replay_base = None
    for frame in range(6000):
        p.run()
        if p.word(0x32) == 6: sections.add(p.word(0x76))
        if owners()[7] and p.word(0x76) == 9 and replay_base is None:
            replay_base = p.save()
        if (not owners()[7] and p.word(0x76) == 11 and p.word(0x78) == 4
            and not p.word(0x6a) and p.word(0x3b0) and p.status()[0]): break
    else: raise AssertionError('Selected room did not load')
    assert {8, 9, 10, 11} <= sections
    p.run(20); p.screenshot(ROOT/'diagnostics/sublevel-graphics-fixed.png')
    fixed = Image.open(ROOT/'diagnostics/sublevel-graphics-fixed.png').convert('RGB')
    expected = Image.open(ROOT/'diagnostics/sublevel-4-4.png').convert('RGB')
    fixed = fixed.crop((0, 32, fixed.width, fixed.height))
    expected = expected.crop((0, 32, expected.width, expected.height))
    before = Image.open(ROOT/'diagnostics/sublevel-graphics-before.png').convert('RGB')
    region = (0, 48, 64, 96)
    assert fixed.crop(region).tobytes() == expected.crop(region).tobytes()
    assert fixed.crop(region).tobytes() != before.crop(region).tobytes()
    assert p.word(0x19ac) == 23 and p.word(0x19ae) == 256, 'Native rooftop boss HUD missing'
    assert p.status()[2] == 0
    def replay():
        video = hashlib.sha256(); p.samples.clear()
        for _ in range(1400):
            p.run(); video.update(p.frame[0])
        return p.save(), video.digest(), bytes(p.samples)
    assert replay_base is not None
    p.restore(replay_base); expected = replay()
    p.restore(replay_base); assert replay() == expected
    assert hashlib.sha256(source.read_bytes()).digest() == digest
    print('Passed: reported QS0 reload, all prerequisite sections, correct background tiles, native boss HUD, mid-load save/video/audio replay, original QS0 unchanged.')
finally:
    p.close()
