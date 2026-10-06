"""QS0 side-view transition: both heroes, controls, cheats and save replay."""
import hashlib
import json
import struct
import zipfile
from native_probe import Probe, ROOT

source = ROOT / 'diagnostics/nextlevel-qs0.State'
original = hashlib.sha256(source.read_bytes()).hexdigest()
data = zipfile.ZipFile(source).read('Core.bin')
p = Probe()
try:
    p.restore(data[4:4 + struct.unpack_from('<I', data)[0]])
    p.run(3)
    assert p.word(0x9a) == 2 and p.status()[0]
    base = p.save()
    def word(player, address):
        return p.player(player, address) | p.player(player, address+1) << 8
    for player in (1, 2):
        other = 3-player
        for button in (128, 1, 2):
            p.restore(base)
            camera0 = p.word(0x17a0)
            x, ox = word(player, 0x328)+camera0, word(other, 0x328)+camera0
            p.run(8, p1=button if player == 1 else 0,
                  p2=button if player == 2 else 0)
            assert word(player, 0x320) and word(other, 0x320)
            if button == 128:
                assert word(player, 0x328)+p.word(0x17a0) > x+8
                assert word(other, 0x328)+p.word(0x17a0) == ox
            if button == 1:
                assert word(player, 0x32c) < 190
                assert word(other, 0x32c) == 208
            if button == 2:
                assert p.player(player, 0x350) == 0x12, 'Invulnerability blocked attack'
                assert p.player(other, 0x350) != 0x12
    # Either player can lead in either direction. The idle partner keeps a
    # fixed world position, never wrapping across the 8-bit screen coordinate.
    for lead in (1, 2):
        p.restore(base)
        for direction in (128, 64):
            for _ in range(300):
                previous = p.status()
                camera0 = p.word(0x17a0)
                p.run(p1=direction if lead == 1 else 0,
                      p2=direction if lead == 2 else 0)
                current = p.status()
                other = 5 if lead == 1 else 3
                assert all(14 <= current[a] <= 242 for a in (3, 5)), current
                assert abs(current[other]-previous[other]) <= 3
                assert current[other]+p.word(0x17a0) == previous[other]+camera0
    p.restore(base)
    for _ in range(30):
        p.run()
        assert word(1, 0x320) and word(2, 0x320), 'Permanent blink frame'
    p.screenshot(ROOT / 'diagnostics/sideview-fixed.png')
    saved = p.save()
    camera = p.word(0x17a0)
    def replay():
        video = hashlib.sha256()
        p.samples.clear()
        for i in range(120):
            p.run(p1=128, p2=128)
            video.update(p.frame[0])
        return p.save(), video.digest(), bytes(p.samples)
    result = replay()
    assert p.word(0x17a0) > camera
    p.restore(saved)
    assert replay() == result
    assert p.status()[2] == 0
    assert hashlib.sha256(source.read_bytes()).hexdigest() == original
    report = dict(both_heroes_visible=True, either_player_leads_without_wrap=True, independent_movement_jump_attack=True,
                  invulnerability_allows_attacks=True, shared_camera=True,
                  deterministic_save_replay=True, original_save_unchanged=True)
    (ROOT / 'diagnostics/sideview-verification.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
finally:
    p.close()
