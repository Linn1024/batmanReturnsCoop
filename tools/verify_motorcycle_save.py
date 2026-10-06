"""Regression for the upper motorcycle being truncated by P2's OAM usage."""
import hashlib
import json
import re
import struct
import zipfile
from native_probe import Probe, ROOT

source = ROOT / 'diagnostics/motorcycle-qs0.State'
before = hashlib.sha256(source.read_bytes()).hexdigest()
with zipfile.ZipFile(source) as z:
    data = z.read('Core.bin')
p = Probe()
try:
    p.restore(data[4:4 + struct.unpack_from('<I', data)[0]])
    trace = ROOT / 'diagnostics/motorcycle-fixed.trace'
    p.core.br_start_trace(str(trace).encode(), 200000, 0)
    p.run()
    p.core.br_stop_trace()
    lines = trace.read_text().splitlines()
    start = next(i for i, line in enumerate(lines)
                 if line.startswith('80947A ') and 'X=0550 ' in line)
    finish = next(line for line in lines[start:] if line.startswith('80947E '))
    first = int(re.search(r'W=([0-9A-F]+)', lines[start])[1], 16)
    last = int(re.search(r'W=([0-9A-F]+)', finish)[1], 16)
    flags = int(re.search(r'P=([0-9A-F]+)', finish)[1], 16)
    assert not flags & 1, 'Upper motorcycle exhausted OAM'
    assert (last-first)//4 > 40, (first, last)
    p.run()
    p.screenshot(ROOT / 'diagnostics/motorcycle-after.png')
    saved = p.save()
    def replay():
        video = hashlib.sha256()
        p.samples.clear()
        for frame in range(120):
            p.run(p1=2 if frame % 12 < 6 else 0,
                  p2=64 if frame < 20 else 0)
            video.update(p.frame[0])
        return bytes(p.ram), video.digest(), bytes(p.samples)
    expected = replay()
    p.restore(saved)
    assert replay() == expected
    p.run(480)
    assert p.status()[2] == 0
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before
    report = {'upper_motorcycle_sprites': (last-first)//4,
              'native_oam_complete': True, 'save_replay': True,
              'continued_gameplay': True, 'original_save_unchanged': True}
    (ROOT / 'diagnostics/motorcycle-verification.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
finally:
    p.close()
