"""Exercise the cheat UI through real controller input, plus combat/OAM fixtures."""
import ctypes as C
import json
from native_probe import Probe, ROOT

p = Probe()
report = {}
CHORD = (1 << 3) | (1 << 8) | 1  # SNES Start+A+B, libretro button IDs.

def press(button, player=0):
    p.run(p1=button if player == 0 else 0, p2=button if player == 1 else 0)
    p.run()

def select(row, player=0):
    press(CHORD, player)
    for _ in range(row):
        press(32, player)

try:
    p.boot()
    base = p.save()
    initial_camera = p.word(0x17a0)
    for player in (0, 1):
        p.restore(base)
        before = p.status()[1]
        p.run(30, p1=CHORD if player == 0 else 0, p2=CHORD if player == 1 else 0)
        p.run(30)
        assert p.status()[1] == before, 'Menu did not pause gameplay'
        p.screenshot(ROOT/'diagnostics/cheat-menu.png')
        # Closing with B must not leak a jump into the game while B is held.
        p.run(10, p1=1 if player == 0 else 0, p2=1 if player == 1 else 0)
        assert p.status()[4] == 208 and p.status()[6] == 208
        assert p.word(0x6c) == 0, 'Opening chord leaked Start into native pause'
    report['both_controllers_menu_pause_and_input_capture'] = True

    # Invulnerability against the same native contact box used by verify_coop.
    for player in (1, 2):
        p.restore(base)
        select(0); press(256); press(1)
        p.set_word(player, 0x328, 100)
        p.set_word(3-player, 0x328, 220)
        for address, value in [(0x60a, 1), (0x5f8, 100), (0x604, 0),
                               (0x608, p.player(player, 0x338)), (0x618, 10),
                               (0x61a, 80), (0x61c, 10), (0x616, 8)]:
            p.set_word(1, address, value)
        p.run()
        assert p.status()[7:9] == [80, 80]
    enabled = p.save()
    p.restore(base); p.restore(enabled)
    p.set_player(1, 0x8a, 10); p.run()
    assert p.read(0x8a) == 80
    report['invulnerability_both_players_and_save_restore'] = True

    for row, address, expected in [(2, 0x8c, 99), (3, 0x90, 9)]:
        p.restore(base); select(row); press(256); press(1)
        p.set_word(1, address, 1); p.run()
        assert p.word(address) == expected
    report['infinite_lives_and_ammo'] = True
    for row in (4, 5, 6, 7):
        p.restore(base)
        if row == 4:
            p.set_player(1, 0x8a, 10); p.set_player(2, 0x8a, 5)
        select(row); press(256); press(1)
        if row == 4: assert p.status()[7:9] == [80, 80]
        if row == 5: assert p.read(0x8c) == 8
        if row == 6: assert p.read(0x90) == 9
        if row == 7: assert abs(p.status()[3]-p.status()[5]) <= 25
    report['heal_lives_refill_regroup'] = True

    p.restore(base); idle=[bytes(p.player(pl,a) for a in range(0x320,0x460)) for pl in (1,2)]
    p.run(450,p1=128,p2=128); fight=p.save()
    for player in (1, 2):
        p.restore(fight); select(1); press(256); press(1)
        # Restore idle bodies so an encounter reaction cannot consume the
        # single attack edge in this controlled one-hit fixture.
        for pl in (1,2):
            for off,v in enumerate(idle[pl-1]):p.set_player(pl,0x320+off,v)
        p.set_word(player, 0x328, 180); p.set_word(player, 0x338, 40)
        p.set_word(player, 0x324, 0x20)
        p.set_word(3-player, 0x328, 28); p.set_word(3-player, 0x338, 10)
        for address, value in [(0x560, 0), (0x648, 140), (0x658, 40), (0x67c, 16)]:
            p.set_word(1, address, value)
        # One held attack, no second button edge. Native death animation remains.
        p.run(30, p1=2 if player == 1 else 0, p2=2 if player == 2 else 0)
        assert p.word(0x666) == 0, (player, p.word(0x666))
    report['one_hit_kills_both_players'] = True

    # Put all hardware sprites on one scanline via the game's real OAM DMA.
    p.restore(base)
    for index in range(128):
        for offset, value in enumerate([16*(index % 16), 80, 0, 0x30]):
            p.write(0x100+4*index+offset, value)
    for index in range(32): p.write(0x300+index, 0xaa)
    p.run()
    stats = (C.c_uint*2)(); p.core.br_sprite_stats(stats)
    assert list(stats) == [128, 256], list(stats)
    report['scanline_capacity'] = {'sprites': stats[0], 'tile_segments': stats[1]}

    report['level_starts'] = []
    for level, stage in enumerate((0, 2, 5, 8, 12, 13, 15)):
        p.restore(base); select(8)
        for _ in range(level): press(128)
        press(32); press(32); press(256)
        for frame in range(2000):
            p.run()
            if p.word(0x76) == stage and p.word(0x78) == 4 and p.word(0x32) == 6:
                break
        else: raise AssertionError(('Level did not load', level+1, p.status()))
        assert p.word(0x72) == level and p.word(0x74) == 0
        assert p.status()[2] == 0
        p.run(15)
        p.screenshot(ROOT/f'diagnostics/verified-level-{level+1}.png')
        report['level_starts'].append(level+1)
    p.restore(base); p.run(120, p1=128, p2=128)
    select(11); press(256)
    for frame in range(1200):
        p.run()
        if frame > 100 and p.status()[0] and p.word(0x78) == 4: break
    assert p.word(0x72) == 0 and p.status()[0] and p.word(0x17a0) == initial_camera
    report['restart_level'] = True
finally:
    p.close()
(ROOT/'diagnostics/cheat-verification.json').write_text(json.dumps(report, indent=2))
print(json.dumps(report, indent=2))
