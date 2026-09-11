"""Independent reference math and REAPER fixture formatting inherited from M1–M3 tests."""
import base64, struct
import numpy as np
SETTINGS=(-36,6,80,10,3,20)


def project(output, plugin, serialized, rate, params, events):
    # JS state retains a reserved field after legacy sliders 1-64.
    params=list(params)+[0]*max(0,70-len(params))
    params.insert(64,0)
    midi, last = [], 0
    for tick, status, data1, data2 in sorted(events, key=lambda e: e[0]):
        midi.append(f'E {tick-last} {status:02x} {data1:02x} {data2:02x}')
        last = tick
    midi.append(f'E {3840-last} b0 7b 00')
    return f'''<REAPER_PROJECT 0.1 "7.79" 0
TEMPO 120 4 4
SAMPLERATE {rate} 1 0
RENDER_FILE "{output}"
RENDER_FMT 0 2 0
RENDER_RANGE 0 0 2 0 1000
RENDER_STEMS 0
RENDER_DITHER 0
<RENDER_CFG
ZXZhdxgAAA==
>
MASTER_VOLUME 1 0 -1 -1 1
<TRACK
NAME "M1 integration test"
VOLPAN 1 0 -1 -1 1
NCHAN 2
MAINSEND 1 0
<FXCHAIN
SHOW -1
BYPASS 0 0 0
<JS {plugin} ""
{' '.join(map(str, params))}
>
<JS_SER
{chr(10).join(serialized[i:i+76] for i in range(0,len(serialized),76))}
>
WAK 0 0
>
<ITEM
POSITION 0
LENGTH 2
VOLPAN 1 0 1 -1
PLAYRATE 1 1 0 -1 0 0.0025
<SOURCE MIDI
HASDATA 1 960 QN
{chr(10).join(midi)}
IGNTEMPO 0 120 4 4
>
>
>
>
'''

def expected_voice(source, source_rate, host_rate, onset, pitch=0,
                   gain_db=0, pan=0, velocity=127, release=None, attack_ms=0, release_ms=0):
    result = np.zeros((host_rate*2, 2))
    step = source_rate / host_rate * 2**(pitch/12)
    length = int(np.ceil(len(source)/step))
    positions = np.arange(length)*step
    ids = np.floor(positions).astype(int)
    next_ids = np.minimum(ids+1, len(source)-1)
    frac = positions-ids
    if source.ndim == 1:
        mono = source[ids] + (source[next_ids]-source[ids])*frac
        values = np.column_stack((mono*np.cos((pan+1)*np.pi/4),
                                  mono*np.sin((pan+1)*np.pi/4)))
    else:
        values = source[ids] + (source[next_ids]-source[ids])*frac[:, None]
        values[:, 0] *= np.cos(max(pan, 0)*np.pi/2)
        values[:, 1] *= np.cos(min(pan, 0)*np.pi/2)
    attack_fade = host_rate*max(2,attack_ms)*.001
    release_fade = host_rate*max(2,release_ms)*.001
    env = np.minimum(1, np.arange(length)/attack_fade)
    env *= np.clip((len(source)-1-positions)/(step*release_fade), 0, 1)
    if release is not None:
        rel = np.maximum(0, np.arange(length)-(release-onset)+1)
        env *= np.maximum(0, 1-rel/(host_rate*.005))
    values *= (env*10**(gain_db/20)*velocity/127)[:, None]
    count = min(length, len(result)-onset)
    if count > 0:
        result[onset:onset+count] = values[:count]
    return result

def state2(path, frames, channels, rate, regions=(), settings=SETTINGS, overflow=0):
    path=str(path).encode()
    blob=struct.pack('<ffI',73101,2,len(path))+path+b'\0'*(-len(path)%4)
    blob+=struct.pack('<fffff',frames,channels,rate,len(regions),overflow)
    blob+=struct.pack('<6f',*settings)
    if regions: blob+=struct.pack('<'+'f'*len(regions)*2,*np.asarray(regions).flatten())
    return base64.b64encode(blob).decode()

class RNG:
    def __init__(self, seed): self.state=seed
    def draw(self):
        self.state=self.state*48271%2147483647
        return (self.state-1)/2147483646

class Sequence:
    def __init__(self, seed, mode, count, fixed=2):
        self.seed,self.mode,self.count,self.fixed=seed,mode,count,fixed
        self.reset()
    def reset(self):
        self.r=RNG(self.seed); self.v=RNG(1+(self.seed+104729)%2147483646)
        self.last=-1; self.bag=[]
    def next(self):
        n=self.count
        if self.mode==4: i=min(n-1,self.fixed)
        elif n==1: i=0
        elif self.mode==0:
            i=int(self.r.draw()*(n if self.last<0 else n-1))
            if self.last>=0 and i>=self.last: i+=1
        elif self.mode==1:
            if not self.bag:
                self.bag=list(range(n))
                for j in range(n-1,0,-1):
                    k=int(self.r.draw()*(j+1)); self.bag[j],self.bag[k]=self.bag[k],self.bag[j]
                if self.bag[0]==self.last:
                    k=1+int(self.r.draw()*(n-1)); self.bag[0],self.bag[k]=self.bag[k],self.bag[0]
            i=self.bag.pop(0)
        elif self.mode==2: i=(self.last+1)%n
        else: i=int(self.r.draw()*n)
        self.last=i
        return i,[(self.v.draw()*2-1) for _ in range(3)]
