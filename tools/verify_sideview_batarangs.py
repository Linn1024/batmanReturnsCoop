"""Native throw input, all three projectile slots, both players/directions."""
import struct
import zipfile
from native_probe import Probe, ROOT

p = Probe()
try:
    with zipfile.ZipFile(ROOT/'diagnostics/nextlevel-qs0.State') as z:
        data = z.read('Core.bin')
    p.restore(data[4:4+struct.unpack_from('<I', data)[0]])
    p.run(40)
    base = p.save()
    def word(player, a):
        return p.player(player, a) | p.player(player, a+1) << 8
    for player in (1, 2):
        for facing in (0, 0x20):
            for slot in (0x460, 0x4b0, 0x500):
                p.restore(base)
                # Keep the trajectory fixture clear of native enemy contacts.
                for enemy in (0x550, 0x640, 0x730):
                    for offset in range(0xf0):
                        p.set_player(1, enemy+offset, 0)
                p.set_word(player, 0x324, facing)
                # Fill earlier slots to exercise the native allocator's full range.
                for earlier in range(0x460, slot, 0x50):
                    p.set_word(player, earlier+0x10, 2)
                    p.set_word(player, earlier+8, 100)
                    p.set_word(player, earlier+0x1b, 0)
                for frame in range(25):
                    p.run(p1=2 if player == 1 and frame == 0 else 0,
                          p2=2 if player == 2 and frame == 0 else 0)
                    if word(player, slot+0x10):
                        break
                else:
                    raise AssertionError(('No throw', player, facing, slot))
                delta = -40 if facing else 40
                assert word(player, slot+8) == (word(player, 0x328)+delta)&65535
                assert word(player, slot+12) == word(player, 0x32c)-56
                assert word(player, slot) != 0, 'Projectile not rendered'
                assert all(word(3-player, a+0x10) == 0 for a in (0x460, 0x4b0, 0x500))
                old_x = word(player, slot+8)
                saved = p.save()
                p.run()
                assert word(player, slot+8) == old_x+(-8 if facing else 8), (player,facing,hex(slot),old_x,word(player,slot+8),word(player,slot+0x10))
                expected = p.save(), p.frame[0]
                p.restore(saved)
                p.run()
                assert (p.save(), p.frame[0]) == expected
    # Same native enemy and throw position: equal damage for either owner,
    # including the third slot. Other slots stay out of the enemy's hitbox.
    damage = []
    for player in (1, 2):
        for slot in (0x460, 0x4b0, 0x500):
            p.restore(base)
            p.set_word(player, 0x328, 100)
            p.set_word(player, 0x324, 0)
            p.set_word(1, 0x666, 32)
            # Keep the target ahead of the thrower; nearest-player AI can
            # otherwise move it behind the muzzle before this fixture starts.
            p.set_word(1, 0x648, 200)
            for earlier in range(0x460, slot, 0x50):
                p.set_word(player, earlier+0x10, 2)
                p.set_word(player, earlier+8, 20)
                p.set_word(player, earlier+0x1b, 0)
            seen_hit = False
            for frame in range(20):
                p.run(p1=2 if player == 1 and frame == 0 else 0,
                      p2=2 if player == 2 and frame == 0 else 0)
                seen_hit |= word(player, slot+0x10) == 3
            assert seen_hit, ('No native hit', player, slot)
            assert word(player, slot+0x10) == 0, 'Hit projectile not consumed'
            assert word(3-player, slot+0x10) == 0, 'Wrong owner consumed'
            damage.append(32-p.word(0x666))
    assert damage[0] > 0 and damage == [damage[0]]*6, damage
    p.restore(base)
    # Repeated simultaneous throws must retire and reuse each owner's slots.
    for frame in range(300):
        p.run(p1=2 if frame % 40 == 0 else 0,
              p2=2 if frame % 40 == 0 else 0)
    assert p.status()[2] == 0
    print('Passed: both owners, both facings, all three slots, motion, native enemy damage/consumption, save replay, repeated simultaneous throws.')
finally:
    p.close()

