"""Title-screen partner colors through actual input on either controller."""
import hashlib
import struct
from native_probe import Probe, ROOT

p = Probe()
def press(button, controller=0):
    p.run(p1=button if controller==0 else 0, p2=button if controller==1 else 0)
    p.run()
def extra():
    return struct.unpack_from('<4I', p.save(), len(p.save())-76)
try:
    for frame in range(380):
        p.run(p1=8 if frame in (120,240) else 0)
    assert (p.word(0x32),p.word(0x34)) == (2,1)
    title = p.save()
    for controller in (0,1):
        p.restore(title)
        press(32,controller)  # Native Options remains the second row.
        assert p.word(0x33b)==1
        press(8,controller)
        p.run(150)
        assert p.word(0x32)==8, 'Original Options no longer opens'
        p.restore(title)
        press(16,controller)  # Wrap upward to the added third row.
        assert extra()[2]==2 and p.word(0x32c)==212
        # The added OPTIONS word exactly matches native OPTIONS pixels.
        video,_,_,pitch=p.frame
        for y in range(8):
            native=(224+y)*pitch+104*2
            added=(240+y)*pitch+144*2
            assert video[native:native+56*2]==video[added:added+56*2], 'Menu font/alignment mismatch'
        p.screenshot(ROOT/'diagnostics/coop-title-native-font.png')
        press(8,controller)
        assert extra()[1]==1
        frozen=p.word(0x3a)
        p.run(60)
        assert p.word(0x3a)==frozen, 'Co-op menu did not pause native title'
        previews=set()
        for color in range(6):
            assert extra()[0]==color
            previews.add(hashlib.sha256(p.frame[0]).digest())
            press(128,controller)
        assert extra()[0]==0 and len(previews)==6
        press(64,controller)
        assert extra()[0]==5
        press(128,controller)
        press(128,controller)
        assert extra()[0]==1
        selected=p.save()
        press(128,controller)
        p.restore(selected)
        assert extra()[0:2]==(1,1)
        p.run()
        p.screenshot(ROOT/'diagnostics/coop-colors-red.png')
        press(1,controller)
        assert extra()[1]==0 and p.word(0x34)==1
        press(32,controller)  # Third row wraps to Game Start.
        assert extra()[2]==0
        press(8,controller)
        p.boot()
        assert extra()[0]==1 and p.status()[0]
    gameplay=p.save()
    p.run()
    red=p.frame[0];pitch=p.frame[3]
    p.screenshot(ROOT/'diagnostics/coop-color-red-gameplay.png')
    blue=bytearray(gameplay)
    struct.pack_into('<I',blue,len(blue)-76,0)
    p.restore(bytes(blue));p.run()
    original=p.frame[0]
    # Only partner material/HUD pixels change; P1 remains native.
    for y in range(145,208):
        assert red[y*pitch+120*2:y*pitch+156*2] == original[y*pitch+120*2:y*pitch+156*2]
    assert red!=original
    # Older color saves retain the choice; pre-color saves default to blue.
    p.restore(gameplay[:-60]); assert extra()[0]==1
    p.restore(gameplay[:-76]); assert extra()[0]==0
    p.restore(selected)
    def replay():
        video=hashlib.sha256();p.samples.clear()
        for i in range(60):
            p.run(p2=128 if i%10==0 else 0)
            video.update(p.frame[0])
        return p.save(),video.digest(),bytes(p.samples)
    expected=replay();p.restore(selected);assert replay()==expected
    print('Passed: native Options, both controllers, six previews, wrap/back, game start, P1 unchanged, old saves and state/video/audio replay')
finally:
    p.close()
