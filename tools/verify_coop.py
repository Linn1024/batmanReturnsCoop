"""Cold-boot opening-stage regression, including controlled combat/death fixtures."""
import hashlib
import json
from native_probe import Probe, ROOT

report = {}
rom = ROOT / 'Batman Returns (U) [!].smc'
rom_hash = hashlib.sha256(rom.read_bytes()).hexdigest()
p = Probe()
try:
    p.boot()
    assert p.status()[0] == 1 and p.status()[2] == 0
    base = p.save()
    report['cold_boot'] = p.status()
    p.screenshot(ROOT / 'diagnostics/verified-boot.png')

    for player in (1, 2):
        p.restore(base)
        x0 = p.status()[3 if player == 1 else 5] + p.word(0x17a0)
        other0 = p.status()[5 if player == 1 else 3] + p.word(0x17a0)
        p.run(16, p1=64 if player == 1 else 0, p2=64 if player == 2 else 0)
        x1 = p.status()[3 if player == 1 else 5] + p.word(0x17a0)
        other1 = p.status()[5 if player == 1 else 3] + p.word(0x17a0)
        assert x1 < x0-15 and abs(other1-other0) <= 1, (player, x0, x1, other0, other1)
        p.restore(base)
        p.run(12, p1=1 if player == 1 else 0, p2=1 if player == 2 else 0)
        assert p.status()[4 if player == 1 else 6] < 195
        assert p.status()[6 if player == 1 else 4] == 208
    report['independent_movement_and_jump'] = True

    # Scripted encounters must hold the shared camera even when both players
    # push right. Test from cold boot so old-save recovery cannot mask a bug.
    p.restore(base)
    p.set_player(1, 0xa0, 1)
    p.set_word(1, 0x328, 180)
    p.set_word(2, 0x328, 190)
    camera = p.word(0x17a0)
    p.run(20, p1=128, p2=128)
    assert p.word(0x17a0) == camera
    assert p.status()[3] > 180 and p.status()[5] > 190
    report['scripted_camera_lock'] = True

    # Native enemy attack-box contact: only the overlapping Batman loses health.
    for player in (1, 2):
        p.restore(base)
        p.set_word(player, 0x328, 100)
        p.set_word(3-player, 0x328, 220)
        for a, v in [(0x60a, 1), (0x5f8, 100), (0x604, 0),
                     (0x608, p.player(player, 0x338)), (0x618, 10),
                     (0x61a, 80), (0x61c, 10), (0x616, 8)]:
            p.set_word(1, a, v)
        p.run()
        assert p.status()[7 if player == 1 else 8] == 72
        assert p.status()[8 if player == 1 else 7] == 80
    report['independent_native_damage'] = True

    # Reach a spawned native clown through movement, then position the fixture.
    p.restore(base)
    p.run(450, p1=128, p2=128)
    fight = p.save()
    assert p.word(0x650) == 8 and p.word(0x666) == 40
    for player in (1, 2):
        p.restore(fight)
        # Arrival timing can change encounter reactions. Normalize these
        # along with positions for the controlled native-combat fixture.
        for pl in (1,2):
            for addr in (0x350,0x334,0x33b,0x33f,0x343,0x3f8):p.set_word(pl,addr,0)
        p.set_word(player, 0x328, 180)
        p.set_word(player, 0x338, 40)
        p.set_word(player, 0x324, 0x20)
        p.set_word(3-player, 0x328, 28)
        p.set_word(3-player, 0x338, 10)
        for a,v in [(0x560,0),(0x648,140),(0x658,40),(0x67c,16)]:
            p.set_word(1,a,v)
        for t in range(90):
            p.run(p1=2 if player == 1 and t%12<6 else 0,
                  p2=2 if player == 2 and t%12<6 else 0)
        assert p.word(0x666) < 40, (player, p.word(0x666))
        report[f'p{player}_enemy_health_after_attacks'] = p.word(0x666)
        p.screenshot(ROOT / f'diagnostics/verified-p{player}-combat.png')

    # Each player produces a separate native projectile.
    for player in (1,2):
        p.restore(base)
        p.run(p1=256 if player==1 else 0,p2=256 if player==2 else 0)
        p.run(20)
        assert p.player(player,0x470) == 2
        assert p.player(3-player,0x470) == 0
    report['independent_batarangs'] = True

    for player in (1, 2):
        p.restore(base)
        p.set_word(player, 0x35c, 3)  # Native completed death state.
        p.set_word(player, 0x3a4, 0)
        p.set_player(player, 0x8a, 0)
        p.run()
        assert p.status()[9] == 2 and p.status()[7:9] == [80, 80]
        assert abs(p.status()[3]-p.status()[5]) <= 2
        p.run(150)
        assert p.status()[9] == 2 and p.status()[2] == 0
        p.restore(base)
        p.set_player(1,0x8c,1)
        p.set_word(player,0x35c,3)
        p.set_word(player,0x3a4,0)
        p.set_player(player,0x8a,0)
        p.run(300)
        assert p.read(0x8c)==0 and p.word(0x32)==7 and not p.status()[0]
    report['shared_life_respawn_and_game_over'] = True

    p.restore(base)
    p.run(1,p2=8)
    p.run(5)
    frame=p.status()[1]
    p.run(30)
    assert p.status()[1] == frame
    p.run(1,p2=8)
    p.run(30)
    assert p.status()[1] > frame+20
    report['p2_pause_resume'] = True

    p.restore(fight)
    p.run(19,p1=2,p2=1)
    saved=p.save()
    def replay():
        p.samples.clear()
        video=hashlib.sha256()
        for t in range(100):
            p.run(p1=2 if t%12<6 else 0,p2=64 if t<20 else 256 if t==30 else 0)
            video.update(p.frame[0])
        return (bytes(p.ram),p.save(),video.hexdigest(),bytes(p.samples))
    a=replay()
    p.restore(saved)
    b=replay()
    report['save_replay'] = dict(zip(('ram','full_state','video','audio'),(x==y for x,y in zip(a,b))))
    assert all(report['save_replay'].values()), report['save_replay']
    assert p.status()[2] == 0
    assert hashlib.sha256(rom.read_bytes()).hexdigest() == rom_hash
    report['rom_sha256'] = rom_hash
    report['scope'] = 'Opening-stage checks; combat and death include controlled injected fixtures. Not a campaign playthrough.'
finally:
    p.close()
(ROOT / 'diagnostics/verification.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
