#!/usr/bin/env python3
"""M9 directional voice, clear transaction, defaults, and limiter host integration."""
import argparse,base64,hashlib,json,re,struct,subprocess,warnings
from pathlib import Path
import numpy as np
from scipy.io import wavfile
from reference import project,expected_voice,RNG
from edit_checks import state6
from lifecycle_checks import read4

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--reaper',required=True,type=Path);ap.add_argument('--output',required=True,type=Path);a=ap.parse_args()
 root=Path(__file__).resolve().parents[1];out=a.output.resolve();effects=out/'profile/Effects';effects.mkdir(parents=True,exist_ok=True)
 src=root/'AB_ReaSampler.jsfx';source=src.read_text();results=[]
 empty=[dict(path='',frames=0,ch=1,rate=48000,regions=[]) for _ in range(4)]
 def params(reverse=(0,0,0,0),limiter=0):return [-4,0,-1,2,0,-1]+[v for i in range(4) for v in (0,0,0,1,0,4,12345+i*104729,0,1,0,0,0)]+[0]*8+[0,int(limiter)]+list(reverse)
 def render(name,layers,par,events=(),hook='',block='',before='',rate=48000,recall=False):
  code=source
  if hook or block or before:code=source.split('\n@gfx ')[0]+'\n@gfx 1100 720\n'
  code=code.replace('// TEST_M4_SAMPLE_HOOK',hook).replace('// TEST_M4_BLOCK_HOOK',block)
  code=code.replace('limiter_process();\nmaster_peak=',before+'\nlimiter_process();\nmaster_peak=')
  code=code.replace('@slider\n','master_write ? (file_var(0,limiter_guard_count);file_var(0,limiter_delay);file_var(0,slider1);file_var(0,limiter_gain););\n@slider\n')
  plugin=name+'.jsfx';(effects/plugin).write_text(code);output=out/(name+'.wav');output.unlink(missing_ok=True);rpp=out/(name+'.rpp');saved=out/(name+'.saved.rpp');saved.unlink(missing_ok=True)
  rpp.write_text(project(output,plugin,state6(layers),rate,par,events));lua=out/(name+'.lua')
  lua.write_text(f'reaper.Main_openProject([[{rpp}]])\nreaper.Main_OnCommand(42230,0)\nreaper.Main_SaveProjectEx(0,[[{saved}]],0)\nreaper.Main_OnCommand(40004,0)\n')
  common=[str(a.reaper.resolve()),'-newinst','-nosplash','-ignoreerrors','-cfgfile',str(out/'profile/reaper.ini')]
  proc=subprocess.run(common+[str(lua)],capture_output=True,text=True,timeout=90);(out/(name+'.log')).write_text(proc.stdout+proc.stderr)
  assert proc.returncode==0 and saved.exists() and output.exists(),name
  with warnings.catch_warnings():warnings.simplefilter('ignore');_,pcm=wavfile.read(output)
  y=pcm.astype(float)/2**31;raw=base64.b64decode(''.join(re.search(r'<JS_SER\s+([^>]+)>',saved.read_text())[1].split()));meta=struct.unpack('<4f',raw[-16:])
  if recall:
   output.unlink();p=subprocess.run(common+['-renderproject',str(saved)],capture_output=True,text=True,timeout=90);assert p.returncode==0
   with warnings.catch_warnings():warnings.simplefilter('ignore');_,again=wavfile.read(output)
   assert np.array_equal(pcm,again),(name,'recall changed playback')
  return y,meta,saved
 audio=[];layers=[]
 for i in range(4):
  t=np.arange(18000);x=(.02+(t/18000)*.08+.03*np.sin(t*(.027+i*.009))).astype(np.float32)
  if i%2:x=np.column_stack((x,-x*.45))
  p=out/f'layer{i}.wav';wavfile.write(p,96000 if i>=2 else 48000,x);audio.append(x);layers.append(dict(path=p,frames=len(x),ch=1+i%2,rate=96000 if i>=2 else 48000,regions=[[1000,17000]]))
 for name,rev,pitch in [('forward',(0,0,0,0),0),('reverse',(100,100,100,100),0),('mixed',(100,0,100,0),0),('reverse_fractional',(100,100,100,100),5.25),('reverse_down',(100,100,100,100),-11.5),('reverse_whole',(100,100,100,100),0),('reverse_envelopes',(100,100,100,100),0)]:
  par=params(rev);expected=np.zeros((96000,2))
  for i in range(4):
   par[8+i*12]=pitch;par[13+i*12]=int(name=='reverse_whole');par[54+i*2]=50 if name=='reverse_envelopes' else 0;par[55+i*2]=75 if name=='reverse_envelopes' else 0;clip=audio[i] if name=='reverse_whole' else audio[i][1000:17000];clip=clip[::-1] if rev[i] else clip
   expected+=expected_voice(clip,layers[i]['rate'],48000,4800,pitch=pitch,gain_db=-4,attack_ms=par[54+i*2],release_ms=par[55+i*2])
  y,meta,_=render(name,layers,par,[(192,144,60,127)],recall=name=='mixed');error=float(np.max(abs(y-expected)));assert error<3e-6,(name,error);results.append(dict(test=name,status='PASS',max_error=error))
 # Independent seeded Bernoulli decisions, including a MIDI sequence reset.
 for probability in (25,75):
  events=[(i*96,144,60,127) for i in range(1,25)];events.append((1200,176,20,127));events.sort()
  par=params((probability,)*4);par[0]=-24;par[5]=20
  rng=[RNG(1+(12345+i*104729+7919)%2147483646) for i in range(4)]
  expected=np.zeros((96000,2));directions=[]
  for tick,status,_,_ in events:
   if status==176:rng=[RNG(1+(12345+i*104729+7919)%2147483646) for i in range(4)];continue
   for i in range(4):
    reverse=rng[i].draw()*100<probability;directions.append(reverse);clip=audio[i][1000:17000]
    expected+=expected_voice(clip[::-1] if reverse else clip,layers[i]['rate'],48000,tick*25,gain_db=-24)
  y,_,_=render(f'probability_{probability}',layers,par,events)
  assert np.max(abs(y-expected))<3e-6,(probability,np.max(abs(y-expected)))
  assert any(directions) and not all(directions);results.append(dict(test=f'probability_{probability}',status='PASS',reverse_count=sum(directions),triggers=len(directions)))
 # Direction is decided once; a mid-voice probability edit must not reverse a playing voice.
 expected=np.zeros((96000,2))
 for i in range(4):expected+=expected_voice(audio[i][1000:17000][::-1],layers[i]['rate'],48000,4800,gain_db=-4)
 y,_,_=render('reverse_latched',layers,params((100,)*4),[(192,144,60,127)],hook='master_sample_index==0 && play_position>.15 ? (slider65=0;slider66=0;slider67=0;slider68=0;);')
 assert np.max(abs(y-expected))<3e-6;results.append(dict(test='reverse_latched',status='PASS'))
 # Clear at exact audio boundary: all assignments empty, active tails fade, later MIDI stays silent.
 clear='!master_test_clear && play_state==1 && play_position>=.15 ? (master_test_clear=1;atomic_set(master_clear_request,1););'
 y,_,saved=render('clear_all',layers,params(),[(192,144,60,127),(768,144,60,127)],block=clear)
 metadata,_=read4(saved);assert all(x['path']=='' for x in metadata);assert np.max(abs(y[12000:]))<1e-8;assert np.max(abs(y[5000:6500]))>.01;results.append(dict(test='clear_all',status='PASS'))
 # Fixed delay is host compensated for MIDI playback. Exact low-level null confirms bypass.
 for rate in (44100,48000,96000,192000):
  for kind in ('impulse','sine','burst','quiet','bypass'):
   n=rate*2;t=np.arange(n);signal=np.zeros(n)
   if kind=='impulse':signal[np.arange(int(.1*rate),int(1.5*rate),int(.013*rate))]=3
   elif kind=='sine':signal=2.5*np.sin(t*2*np.pi*37/rate)
   elif kind=='burst':signal=((t//max(1,int(rate*.009)))%3==0)*2.2*np.sin(t*2*np.pi*1003/rate)
   else:signal=.2*np.sin(t*2*np.pi*431/rate)
   # Test signal computed from absolute test frame; scheduled only while rendering.
   expr={'impulse':f'(m9_n>={int(.1*rate)} && m9_n<{int(1.5*rate)} && (m9_n-{int(.1*rate)})%{int(.013*rate)}==0)*3', 'sine':'2.5*sin(m9_n*2*$pi*37/srate)','burst':f'(floor(m9_n/{max(1,int(rate*.009))})%3==0)*2.2*sin(m9_n*2*$pi*1003/srate)','quiet':'.2*sin(m9_n*2*$pi*431/srate)','bypass':'.2*sin(m9_n*2*$pi*431/srate)'}[kind]
   driving=f'play_state==1 ? (spl0={expr};spl1=-spl0*.37;m9_n+=1;) : (spl0=0;spl1=0;);'
   y,meta,_=render(f'limiter_{kind}_{rate}',empty,params(limiter=kind!='bypass'),before=driving,rate=rate)
   assert meta[0]==0,(kind,rate,'safety guard',meta);assert meta[1]==int(rate*.002+.5),(rate,meta)
   assert np.max(abs(y[:,1]+y[:,0]*.37))<1e-7,(kind,rate,'stereo link: 24-bit render rounding')
   if kind in ('quiet','bypass'):
    # Render PDC may advance generator relative to timeline: identify using known delay.
    err=min(np.max(abs(y[:,0]-signal)),np.max(abs(y[:,0]-np.r_[np.zeros(int(meta[1])),signal[:-int(meta[1])]])))
    assert err<3e-6,(kind,rate,err)
   else:assert np.max(abs(y))<=10**(-.1/20)+1e-8,(kind,rate,np.max(abs(y)))
   results.append(dict(test=f'limiter_{kind}_{rate}',status='PASS',peak=float(np.max(abs(y))),guard_activations=int(meta[0])))
 # Toggle an overloaded DC signal: smooth transition, stable delay, settled ceiling.
 driving='play_state==1 ? (slider64=m9_n>=9600 && m9_n<28800;spl0=2;spl1=-.74;m9_n+=1;) : (spl0=0;spl1=0;);'
 y,meta,_=render('limiter_toggle',empty,params(),before=driving)
 assert meta[1]==96 and meta[0]==0,meta
 assert np.max(abs(np.diff(y[9000:30500,0])))<.005,'toggle discontinuity'
 assert np.max(abs(y[11000:28000,0]))<=10**(-.1/20)+1e-8
 assert np.max(abs(y[31000:40000,0]-1))<3e-6 # integer render clips bypass overload at full scale
 results.append(dict(test='limiter_toggle',status='PASS',max_step=float(np.max(abs(np.diff(y[9000:30500,0]))))))
 (out/'feature-results.json').write_text(json.dumps(dict(source_sha256=hashlib.sha256(src.read_bytes()).hexdigest(),passed=len(results),results=results),indent=2)+'\n');print('PASS',len(results))
if __name__=='__main__':main()
