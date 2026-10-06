"""QS0 test-tube blasts must affect enemies targeting either Batman."""
import ctypes as C
import hashlib
import struct
import zipfile
from native_probe import Probe, ROOT

source = ROOT/'diagnostics/test-tube-qs0.State'
digest = hashlib.sha256(source.read_bytes()).digest()
data = zipfile.ZipFile(source).read('Core.bin')
p = Probe()
def word(player, a): return p.player(player, a) | p.player(player, a+1) << 8
def cheats(value):
    suffix = C.create_string_buffer(p.core.br_state_size())
    p.core.br_state_save(suffix); struct.pack_into('<I', suffix, 1484, value)
    p.core.br_state_load(suffix)
def throw(players):
    p.run(p1=1024 if 1 in players else 0, p2=1024 if 2 in players else 0)
    p.run(p1=1536 if 1 in players else 0, p2=1536 if 2 in players else 0)
def replay():
    video = hashlib.sha256(); p.samples.clear(); defeated = [False, False]
    for _ in range(220):
        p.run(); video.update(p.frame[0])
        for i, a in enumerate((0x550, 0x640)):
            defeated[i] |= p.word(a+0x10) == 0 or p.word(a+0x26) == 0
    return p.save(), video.digest(), bytes(p.samples), defeated
try:
    p.restore(data[4:4+struct.unpack_from('<I', data)[0]])
    cheats(5)  # Native damage, finite shared tubes, invulnerable players.
    base = p.save()
    for swapped in (False, True):
        for player in (1, 2):
            p.restore(base)
            if swapped:
                # Change the AI's nearer-player choice without changing the tube.
                p.set_word(1, 0x328, 230); p.set_word(2, 0x328, 80)
            throw((player,))
            p.run(25)
            assert word(player, 0x402) == 1
            assert word(3-player, 0x402) == 0, 'Copied blast state into partner'
            assert p.word(0x90) == 8
            # Both reported clown enemies start the original tube reaction.
            assert [p.word(a+0x3c) for a in (0x550, 0x640)] == [0x15, 0x15]
            saved = p.save(); expected = replay()
            assert all(expected[3]), ('Enemy survived tube', swapped, player)
            p.restore(saved); assert replay() == expected
            assert p.status()[2] == 0
    # Separate enemies select opposite nearer players, yet the same blast hits both.
    p.restore(base)
    p.set_word(1, 0x328, 64); p.set_word(2, 0x328, 192)
    p.set_word(1, 0x558, 64); p.set_word(1, 0x648, 192)
    throw((2,)); p.run(25)
    assert [p.word(a+0x3c) for a in (0x550, 0x640)] == [0x15, 0x15]
    p.restore(base); throw((1, 2)); p.run(25)
    assert p.word(0x90) == 7 and word(1, 0x402) == word(2, 0x402) == 1
    assert [p.word(a+0x3c) for a in (0x550, 0x640)] == [0x15, 0x15]
    saved = p.save(); expected = replay(); p.restore(saved)
    assert replay() == expected
    assert p.status()[2] == 0
    assert hashlib.sha256(source.read_bytes()).digest() == digest
    print('Passed: either player blasts both enemies, swapped/split AI targets, private animation states, native defeat, finite shared stock, simultaneous tubes, save/video/audio replay.')
finally:
    p.close()
