"""Real cheat-menu input: every native subsection with shared graphics loading."""
import ctypes as C
from native_probe import Probe, ROOT

p = Probe()
def press(button, player=1):
    p.run(p1=button if player == 1 else 0, p2=button if player == 2 else 0)
    p.run()
def owners():
    import struct
    buf = C.create_string_buffer(p.core.br_state_size()); p.core.br_state_save(buf)
    return struct.unpack_from('<16I', buf.raw, 1484)
try:
    p.boot(); base = p.save(); checked = []
    for level, (start, count) in enumerate(zip((0, 2, 5, 8, 12, 13, 15), (2, 3, 3, 4, 1, 2, 3))):
        for section in range(count):
            player = 1+section%2
            p.restore(base); press(265, player)
            for _ in range(8): press(32, player)
            for _ in range(level): press(128, player)
            press(32, player)
            # Both directions wrap within this level's valid subsections.
            press(64, player); assert owners()[6] == count-1
            press(128, player); assert owners()[6] == 0
            for _ in range(section): press(128, player)
            assert owners()[5:7] == (level, section)
            if level == 3 and section == 3:
                p.screenshot(ROOT/'diagnostics/cheat-sublevels.png')
            selected = p.save(); p.run(3); p.restore(selected)
            assert owners()[5:7] == (level, section)
            press(32, player); press(256, player)
            for frame in range(6000):
                p.run()
                if (p.word(0x32) == 6 and p.word(0x76) == start+section and
                    p.word(0x78) == 4 and p.status()[0] and not p.word(0x6a) and
                    ((p.word(0x9a) == 0 and not p.word(0x49c)) or
                     (p.word(0x9a) != 0 and p.word(0x3b0) and p.word(0x350) < 3)) and frame > 300 and not owners()[7]):
                    break
            else: raise AssertionError(('Sublevel did not become playable', level+1, section+1, p.status()))
            assert p.word(0x72) == level and p.word(0x74) == section
            assert not owners()[7] and p.status()[2] == 0
            p.run(20)
            p.screenshot(ROOT/f'diagnostics/sublevel-{level+1}-{section+1}.png')
            # Both controllers move independently after the native entrance.
            ready = p.save()
            for player in (1, 2):
                p.restore(ready); before = p.status()[3 if player == 1 else 5]+p.word(0x17a0)
                p.run(45, p1=128 if player == 1 else 0, p2=128 if player == 2 else 0)
                after = p.status()[3 if player == 1 else 5]+p.word(0x17a0)
                if after == before:  # Some starts have terrain directly to the right.
                    p.restore(ready)
                    p.run(45, p1=64 if player == 1 else 0, p2=64 if player == 2 else 0)
                    after = p.status()[3 if player == 1 else 5]+p.word(0x17a0)
                assert after != before, (level+1, section+1, player, before, after)
            p.restore(ready); press(265)
            assert owners()[5:7] == (level, section), 'Menu forgot current sublevel'
            checked.append((level+1, section+1))
    print('Passed: both controllers, valid sublevel bounds/wrap, selection save/restore, all 18 native loads, entrances, independent movement:', checked)
finally:
    p.close()
