"""Minimal libretro frontend used by opening.py. Reads the ROM into memory."""
import ctypes as c
from pathlib import Path
import struct
import sys

def callback(restype,*args):
    return c.CFUNCTYPE(restype,*args)

lib=c.CDLL(str(Path(sys.argv[2]).resolve()))
lib.retro_reference_memory.restype=c.c_void_p
buttons=0
frame=None
fmt=0
@callback(c.c_bool,c.c_uint,c.c_void_p)
def env(cmd,ptr):
    global fmt
    if cmd==10:
        fmt=c.cast(ptr,c.POINTER(c.c_int))[0]
        return True
    return False

@callback(None,c.c_void_p,c.c_uint,c.c_uint,c.c_size_t)
def video(ptr,w,h,pitch):
    global frame
    if ptr: frame=(w,h,pitch,c.string_at(ptr,h*pitch))

@callback(None,c.c_int16,c.c_int16)
def sample(l,r): pass
@callback(c.c_size_t,c.c_void_p,c.c_size_t)
def batch(buf,count): return count
@callback(None)
def poll(): pass
@callback(c.c_int16,c.c_uint,c.c_uint,c.c_uint,c.c_uint)
def input(port,device,index,id):
    return int(port==0 and device==1 and bool(buttons & (1<<id)))

for n,cb in (('environment',env),('video_refresh',video),('audio_sample',sample),
             ('audio_sample_batch',batch),('input_poll',poll),('input_state',input)):
    getattr(lib,'retro_set_'+n)(cb)
lib.retro_init()
class Game(c.Structure):
    _fields_=[('path',c.c_char_p),('data',c.c_void_p),('size',c.c_size_t),('meta',c.c_char_p)]
rom=Path(sys.argv[1]).read_bytes()
buf=c.create_string_buffer(rom)
assert lib.retro_load_game(c.byref(Game(None,c.addressof(buf),len(rom),None)))
lib.retro_set_controller_port_device(0,1)
def memory(i,n): return c.string_at(lib.retro_reference_memory(i),n)
def run(n,button=None):
    global buttons
    buttons=(1<<button) if button is not None else 0
    for _ in range(n): lib.retro_run()
def status():
    r=memory(0,0x20000)
    return (r[0x100],r[0x13bf],r[0x1f11],r[0x1f17],r[0x1f19],r[0x95],r[0x7f],r[0x192e],r[0x1931])
def snapshot(prefix):
    for i,(label,n) in enumerate((('wram',0x20000),('vram',0x10000),('cgram',512),('bg',12))):
        Path(prefix+'.'+label).write_bytes(memory(i,n))
    if frame:
        w,h,pitch,data=frame
        with open(prefix+'.ppm','wb') as f:
            f.write(f'P6\n{w} {h}\n255\n'.encode())
            for y in range(h):
                words=struct.unpack_from('<'+'H'*w,data,y*pitch)
                f.write(bytes(ch for v in words for ch in (((v>>11)&31)*255//31,((v>>5)&63)*255//63,(v&31)*255//31)))
    print(prefix,fmt,status(),flush=True)
