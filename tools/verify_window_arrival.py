"""Section 1's native window entrance must keep its original frame timing."""
import ctypes as C
import struct
from native_probe import Probe, ROOT

p = Probe()

def press(button):
    p.run(p1=button)
    p.run()

def arriving():
    buf = C.create_string_buffer(p.core.br_state_size())
    p.core.br_state_save(buf)
    return struct.unpack_from('<I', buf.raw, 1484+12*4)[0]

def player_word(player, addr):
    return p.player(player, addr) | p.player(player, addr+1) << 8

try:
    p.boot()
    press(265)
    for _ in range(9):
        press(32)
    press(128)  # Level 1, subsection 2.
    press(32)
    press(256)
    pause, jump, poses = [], [], set()
    replay = None
    previous_blue = None
    for frame in range(2000):
        p.run()
        if p.word(0x76) != 1 or p.word(0x78) != 4:
            continue
        if arriving() and p.status()[0]:
            for addr in (0x320, 0x324, 0x32c, 0x350, 0x35c):
                assert player_word(1, addr) == player_word(2, addr), hex(addr)
            x = player_word(1, 0x328)
            x = x if x < 32768 else x-65536
            distance = 40-40*max(0, min(208, x+64))//208
            assert (player_word(1, 0x328)-player_word(2, 0x328)) & 65535 == distance
            poses.add(p.word(0x320))
        if p.status()[0]:
            blue = player_word(2, 0x328) + p.word(0x17a0)
            if previous_blue is not None:
                step = (blue-previous_blue+32768) % 65536-32768
                assert abs(step) <= 5, ('Entrance position jumped', frame, step)
            previous_blue = blue
        if not p.word(0x6a) and p.word(0x350) == 0x19:
            timer = p.word(0x19a0)
            assert p.word(0x324) == 0x1898, 'Missing native window entrance flags'
            if timer:
                pause.append(timer)
                assert p.word(0x328) == 0xffc0
                if timer == 80:
                    replay = p.save()
            else:
                jump.append(p.word(0x328))
        if frame > 700 and p.status()[0] and not arriving() and p.word(0x3b0):
            break
    else:
        raise AssertionError('Window entrance did not finish')
    assert pause == list(range(144, 0, -1)), pause
    assert jump == [x & 65535 for x in range(-64, 145, 4)], jump
    assert len(poses) > 1, 'Entrance animation did not advance'
    ready = p.save()
    assert player_word(2, 0x328) >= 128, 'P2 landed outside the window wall'
    assert player_word(2, 0x328) == player_word(1, 0x328), 'P2 missed the native landing'
    p.screenshot(ROOT/'diagnostics/window-arrival-fixed.png')
    for player in (1, 2):
        for direction in (64, 128):
            p.restore(ready)
            if direction == 64:  # Step away from the entrance's left wall first.
                p.run(10, p1=128 if player == 1 else 0, p2=128 if player == 2 else 0)
            before = player_word(player, 0x328) + p.word(0x17a0)
            p.run(10, p1=direction if player == 1 else 0, p2=direction if player == 2 else 0)
            after = player_word(player, 0x328) + p.word(0x17a0)
            assert after < before if direction == 64 else after > before
    assert replay is not None
    p.restore(replay)
    p.samples.clear()
    p.run(250)
    expected = p.save(), p.frame, bytes(p.samples)
    p.restore(replay)
    p.samples.clear()
    p.run(250)
    assert (p.save(), p.frame, bytes(p.samples)) == expected
    assert p.status()[2] == 0
    print('Passed: native window flags, 144-frame pause, 52-frame jump, both arrival animations, independent controls, state/video/audio replay')
finally:
    p.close()
