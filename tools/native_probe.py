"""Headless tests of the compiled core; no Lua or emulator UI."""
import ctypes as C
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]

class Game(C.Structure):
    _fields_ = [('path', C.c_char_p), ('data', C.c_void_p), ('size', C.c_size_t), ('meta', C.c_char_p)]

class Variable(C.Structure):
    _fields_ = [('key', C.c_char_p), ('value', C.c_char_p)]

class Probe:
    def __init__(self, options=None):
        (ROOT / "diagnostics").mkdir(exist_ok=True)
        self.core = C.CDLL(str(ROOT/'engine/snes9x2005_libretro.dll'))
        self.buttons = [0, 0]
        self.options = {}
        if options: self.options.update(options)
        self.root_bytes = str(ROOT).encode()
        self.frame = None
        self.samples = bytearray()
        self.format = 0
        def env(cmd, data):
            if cmd in (9, 31):
                C.cast(data, C.POINTER(C.c_char_p))[0] = self.root_bytes
                return True
            if cmd == 10:
                self.format = C.cast(data, C.POINTER(C.c_int))[0]
                return True
            if cmd == 16:
                arr = C.cast(data, C.POINTER(Variable)); i = 0
                while arr[i].key:
                    self.options.setdefault(arr[i].key, arr[i].value.split(b'; ', 1)[-1].split(b'|')[0]); i += 1
                return True
            if cmd == 15:
                var = C.cast(data, C.POINTER(Variable)).contents
                var.value = self.options.get(var.key)
                return bool(var.value)
            if cmd in (3, 17):
                C.cast(data, C.POINTER(C.c_bool))[0] = cmd == 3
                return True
            if cmd == 52:
                C.cast(data, C.POINTER(C.c_uint))[0] = 0
                return True
            return cmd in (11, 35, 37)
        def video(data, w, h, pitch):
            if data: self.frame = (C.string_at(data, h*pitch), w, h, pitch)
        def audio(data, n):
            self.samples.extend(C.string_at(data, n*4)); return n
        signatures = {
            'environment': (C.CFUNCTYPE(C.c_bool, C.c_uint, C.c_void_p), env),
            'video_refresh': (C.CFUNCTYPE(None, C.c_void_p, C.c_uint, C.c_uint, C.c_size_t), video),
            'audio_sample_batch': (C.CFUNCTYPE(C.c_size_t, C.c_void_p, C.c_size_t), audio),
            'audio_sample': (C.CFUNCTYPE(None, C.c_int16, C.c_int16), lambda l,r: None),
            'input_poll': (C.CFUNCTYPE(None), lambda: None),
            'input_state': (C.CFUNCTYPE(C.c_int16, C.c_uint, C.c_uint, C.c_uint, C.c_uint),
                            lambda p,d,i,b: int(p<2 and bool(self.buttons[p] & (1<<b)))),
        }
        self.callbacks = []
        for name, (sig, fn) in signatures.items():
            cb = sig(fn); self.callbacks.append(cb); getattr(self.core, 'retro_set_'+name)(cb)
        self.core.retro_init()
        path = ROOT/'Batman Returns (U) [!].smc'
        data = path.read_bytes(); self.rom = C.create_string_buffer(data)
        game = Game(str(path).encode(), C.addressof(self.rom), len(data), None)
        self.core.retro_load_game.argtypes = [C.POINTER(Game)]
        self.core.retro_load_game.restype = C.c_bool
        assert self.core.retro_load_game(C.byref(game))
        for p in (0,1): self.core.retro_set_controller_port_device(p, 1)
        self.core.retro_serialize_size.restype = C.c_size_t
        for name in ('retro_serialize', 'retro_unserialize'):
            fn = getattr(self.core, name); fn.argtypes = [C.c_void_p, C.c_size_t]; fn.restype = C.c_bool
        self.core.retro_get_memory_data.restype = C.c_void_p
        self.ram = (C.c_ubyte*131072).from_address(self.core.retro_get_memory_data(2))

    def run(self, n=1, p1=0, p2=0):
        self.buttons[:] = p1, p2
        for _ in range(n): self.core.retro_run()

    def read(self, addr): return self.ram[addr & 0x1ffff]
    def word(self, addr): return self.read(addr) | self.read(addr+1)<<8
    def write(self, addr, value): self.ram[addr & 0x1ffff] = value
    def save(self):
        n = self.core.retro_serialize_size(); buf = C.create_string_buffer(n)
        assert self.core.retro_serialize(buf, n); return buf.raw
    def restore(self, data):
        buf = C.create_string_buffer(data); assert self.core.retro_unserialize(buf, len(data))
    def status(self):
        data=(C.c_uint*10)();self.core.br_status(data);return list(data)
    def player(self, p, addr): return self.core.br_read(p, addr)
    def set_player(self, p, addr, value): self.core.br_write(p,addr,value)
    def set_word(self,p,addr,value):
        self.set_player(p,addr,value&255);self.set_player(p,addr+1,(value>>8)&255)
    def boot(self):
        for frame in range(3000):
            self.run(p1=8 if frame%120==0 and not self.status()[0] else 0)
            if self.status()[1]>20:
                self.run(30);return
        raise AssertionError(('cold boot failed',self.status()))
    def screenshot(self, path):
        data,w,h,pitch = self.frame
        if self.format == 1:
            im=Image.frombytes('RGB', (w,h), data, 'raw', 'BGRX', pitch)
        else:
            import numpy as np
            a=np.frombuffer(data,dtype='<u2').reshape(h,pitch//2)[:,:w].astype('uint32')
            if self.format==2: rgb=np.stack((((a>>11)&31)*255//31,((a>>5)&63)*255//63,(a&31)*255//31),axis=-1)
            else: rgb=np.stack((((a>>10)&31)*255//31,((a>>5)&31)*255//31,(a&31)*255//31),axis=-1)
            im=Image.fromarray(rgb.astype('uint8'))
        im.save(path)
    def close(self):
        self.core.retro_unload_game(); self.core.retro_deinit()

if __name__ == '__main__':
    p=Probe()
    try:
        p.boot()
        print('Cold boot:',p.status())
        p.screenshot(ROOT/'diagnostics/boot.png')
        (ROOT/'diagnostics/boot.state').write_bytes(p.save())
    finally:
        p.close()
