"""QS0: punches from either Batman hit an enemy targeting their partner."""
import ctypes as C
import hashlib
import struct
import zipfile
from native_probe import Probe, ROOT

source = ROOT/'diagnostics/blue-melee-qs0.State'
digest = hashlib.sha256(source.read_bytes()).digest()
raw = zipfile.ZipFile(source).read('Core.bin')
state = raw[4:4+struct.unpack_from('<I', raw)[0]]
p = Probe()

def attack(player):
    for frame in range(180):
        button = 2 if frame % 12 < 6 else 0
        p.run(p1=button if player == 1 else 0, p2=button if player == 2 else 0)

def swap_players():
    # Keep the real encounter, mirroring player ownership to exercise both
    # directions of the nearest-player context swap.
    a = [p.player(1, addr) for addr in range(0x320, 0x500)]
    b = [p.player(2, addr) for addr in range(0x320, 0x500)]
    for i, addr in enumerate(range(0x320, 0x500)):
        p.set_player(1, addr, b[i])
        p.set_player(2, addr, a[i])

try:
    for attacker in (2, 1):
        p.restore(state)
        if attacker == 1:
            swap_players()
        assert p.word(0x666) == 16
        # Move down into the enemy's lane using actual input. The idle
        # partner is still nearer; no enemy state or hit box is injected.
        p.run(30, p1=32 if attacker == 1 else 0, p2=32 if attacker == 2 else 0)
        aligned = p.save()
        attack(attacker)
        assert p.word(0x666) < 16, ('Partner-targeted enemy ignored attack', attacker)
        assert p.status()[2] == 0
        buf = C.create_string_buffer(p.core.br_state_size())
        p.core.br_state_save(buf)
        assert struct.unpack_from('<I', buf.raw, 1484+9*4)[0] == 0
        p.screenshot(ROOT/f'diagnostics/melee-target-p{attacker}-fixed.png')
        p.restore(aligned)
        p.samples.clear()
        attack(attacker)
        expected = p.save(), p.frame, bytes(p.samples)
        p.restore(aligned)
        p.samples.clear()
        attack(attacker)
        assert (p.save(), p.frame, bytes(p.samples)) == expected
    p.restore(state)
    p.run(210)
    assert p.word(0x666) == 16, 'Idle players damaged an enemy'
    assert hashlib.sha256(source.read_bytes()).digest() == digest
    print('Passed: real QS0 movement/punches damage partner-targeted enemy, swapped player ownership, no idle damage, context restoration, state/video/audio replay')
finally:
    p.close()
