"""Latest QS0: native side-view enemies must register P2's punches."""
import ctypes as C
import hashlib
import struct
import zipfile
from native_probe import Probe, ROOT

source = ROOT/'diagnostics/blue-melee-next-qs0.State'
digest = hashlib.sha256(source.read_bytes()).digest()
raw = zipfile.ZipFile(source).read('Core.bin')
state = raw[4:4+struct.unpack_from('<I', raw)[0]]
p = Probe()

def attack(player):
    for frame in range(180):
        button = 2 if frame % 12 < 6 else 0
        p.run(p1=button if player == 1 else 0, p2=button if player == 2 else 0)

def swap_players():
    a = [p.player(1, addr) for addr in range(0x320, 0x500)]
    b = [p.player(2, addr) for addr in range(0x320, 0x500)]
    for i, addr in enumerate(range(0x320, 0x500)):
        p.set_player(1, addr, b[i])
        p.set_player(2, addr, a[i])

try:
    for attacker in (2, 1):
        p.restore(state)
        assert p.word(0x9a) == 2 and p.word(0x576) == 10
        if attacker == 1:
            swap_players()
        base = p.save()
        # Real QS0 positions, facing and attack input; no enemy or hitbox
        # changes. The previous core left this enemy at ten HP for P2.
        attack(attacker)
        assert p.word(0x576) == 0, ('Side-view punches ignored', attacker)
        assert p.status()[7:9] == [80, 80]
        buf = C.create_string_buffer(p.core.br_state_size())
        p.core.br_state_save(buf)
        assert struct.unpack_from('<I', buf.raw, 1484+9*4)[0] == 0
        assert p.status()[2] == 0
        p.screenshot(ROOT/f'diagnostics/side-melee-p{attacker}-fixed.png')
        p.restore(base)
        p.samples.clear()
        attack(attacker)
        expected = p.save(), p.frame, bytes(p.samples)
        p.restore(base)
        p.samples.clear()
        attack(attacker)
        assert (p.save(), p.frame, bytes(p.samples)) == expected
    p.restore(state)
    p.run(180)
    assert p.word(0x576) == 10, 'Idle players damaged the enemy'
    assert hashlib.sha256(source.read_bytes()).digest() == digest
    print('Passed: exact QS0 side-view punches kill enemy for either player, no idle damage, private health/context restoration, state/video/audio replay')
finally:
    p.close()
