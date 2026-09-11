#!/usr/bin/env python3
"""Actual REAPER checks for atomic sound actions, Chaos lifecycle and internal notes."""
import argparse,base64,hashlib,json,re,struct,subprocess,warnings,sys
from pathlib import Path
import numpy as np
from scipy.io import wavfile
from reference import project
from edit_checks import state6
from lifecycle_checks import read4
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from parameters import SOUND,LOCKED,SOUND_DEFAULTS

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--reaper',required=True,type=Path);ap.add_argument('--output',required=True,type=Path);a=ap.parse_args()
 root=Path(__file__).resolve().parents[1];out=a.output.resolve();effects=out/'profile/Effects';effects.mkdir(parents=True,exist_ok=True)
 source=(root/'AB_ReaSampler.jsfx').read_text();reports=[]
 par=[-4,0,-1,2,0,-1]+[v for i in range(4) for v in (0,0,0,1,0,0,12345+i*104729,0,1,3,3,.2)]+[v for _ in range(4) for v in (10,20)]+[0,0]+[50]*4+[0,1357911]
 layers=[]
 for i in range(4):
  rate=48000 if i<2 else 96000;t=np.arange(rate)/rate;x=(.05*np.sin((117+i*31)*t*2*np.pi)*(1+t)).astype(np.float32)
  if i%2:x=np.column_stack((x,-.6*x))
  wav=out/f'source{i}.wav';wavfile.write(wav,rate,x);layers.append(dict(path=wav,frames=len(x),ch=1+i%2,rate=rate,regions=[[0,rate//2],[rate//2,rate]]))
 def run(name,events=(),pre='',post='',sample='',params=None,recall=False):
  code=source.split('\n@gfx ')[0]+'\n@gfx 1100 720\n'
  code=code.replace('master_actions_block();limiter_configure();master_sound_snapshot();',pre+'\nmaster_actions_block();limiter_configure();master_sound_snapshot();\n'+post)
  code=code.replace('// TEST_M4_SAMPLE_HOOK',sample)
  extra='master_write ? ('+''.join(f'file_var(0,slider{p});' for p in range(1,71))+''.join(f'file_var(0,{p});' for p in ['master_phase','master_chaos_active','master_test_failed','master_test_checks','master_rejected','master_event_count','master_command_read','master_command_write'])+');\n'
  code=code.replace('@slider\n',extra+'@slider\n');plugin=name+'.jsfx';(effects/plugin).write_text(code)
  output=out/(name+'.wav');saved=out/(name+'.saved.rpp');output.unlink(missing_ok=True);saved.unlink(missing_ok=True)
  rpp=out/(name+'.rpp');rpp.write_text(project(output,plugin,state6(layers),48000,params or par,events));lua=out/(name+'.lua')
  lua.write_text(f'reaper.Main_openProject([[{rpp}]])\nreaper.Main_OnCommand(42230,0)\nreaper.Main_SaveProjectEx(0,[[{saved}]],0)\nreaper.Main_OnCommand(40004,0)\n')
  common=[str(a.reaper.resolve()),'-newinst','-nosplash','-ignoreerrors','-cfgfile',str(out/'profile/reaper.ini')]
  p=subprocess.run(common+[str(lua)],capture_output=True,text=True,timeout=90);(out/(name+'.log')).write_text(p.stdout+p.stderr);assert p.returncode==0 and saved.exists() and output.exists(),name
  with warnings.catch_warnings():warnings.simplefilter('ignore');_,pcm=wavfile.read(output)
  raw=base64.b64decode(''.join(re.search(r'<JS_SER\s+([^>]+)>',saved.read_text())[1].split()));values=struct.unpack('<78f',raw[-312:]);assert values[72]==0,(name,values[-8:])
  if recall:
   output.unlink();p=subprocess.run(common+['-renderproject',str(saved)],capture_output=True,text=True,timeout=90);assert p.returncode==0
   with warnings.catch_warnings():warnings.simplefilter('ignore');_,again=wavfile.read(output)
   assert np.array_equal(pcm,again),(name,'recall audio differs')
  return pcm.astype(float)/2**31,values,saved
 once=lambda action:f'play_state==1 && !master_test_once ? (master_test_once=1;{action});'
 def check(expr):return f'master_test_checks+=1;!({expr}) ? master_test_failed+=1;'
 # Equivalent MIDI and button notes share random sequences and admission.
 midi,_,_=run('physical_midi',events=[(0,144,60,100)])
 button,_,_=run('button_note',pre=once('master_request(3);'))
 assert np.array_equal(midi,button);reports.append(dict(test='button_matches_midi',status='PASS'))
 for name,changes,events in [('solo',{10:1},[(0,144,60,100)]),('filtered',{1:7,2:83},[(0,150,83,100)]),('muted',{9:0,21:0,33:0,45:0},[(0,144,60,100)])]:
  p=par.copy()
  for k,v in changes.items():p[k]=v
  m,_,_=run('midi_'+name,events=events,params=p);b,_,_=run('button_'+name,params=p,pre=once('master_request(3);'))
  assert np.array_equal(m,b),name;reports.append(dict(test='button_'+name,status='PASS'))
 # Sixteen occupied slots reject the following click as a whole four-layer trigger.
 pre='play_state==1 && master_test_stage<2 ? (master_test_stage==0 ? loop(16,master_request(3);) : master_request(3);master_test_stage+=1;);'
 _,v,_=run('voice_exhaustion',pre=pre)
 assert v[74]==1;reports.append(dict(test='button_voice_exhaustion',status='PASS'))
 y,_,_=run('clear_discards_button',pre=once('master_request(3);master_clearing=1;'))
 assert np.max(abs(y))==0;reports.append(dict(test='clear_discards_button',status='PASS'))
 # Full queue preserves 16 presses; excess request fails instead of overwriting.
 _,v,_=run('queue_bound',pre=once('loop(16,master_request(3););'+check('master_request(3)==0')))
 assert v[76]==16 and v[77]==16;reports.append(dict(test='queue_bound',status='PASS'))
 _,v,_=run('stale_button',pre=once('master_request(3);master_commands[1]=time_precise()-2;'))
 assert v[76]==1;reports.append(dict(test='stale_button',status='PASS'))
 y,_,_=run('panic_discards_button',pre=once('master_request(3);atomic_set(master_panic_request,1);'))
 assert np.max(abs(y))==0;reports.append(dict(test='panic_discards_button',status='PASS'))
 # Many randomisations exercise all ranges, uniqueness, unchanged unrelated controls.
 expressions=[]
 for i in range(4):
  b=7+i*12
  for p,lo,hi in [(b,-18,3),(b+1,-1,1),(b+2,-12,12),(b+9,0,6),(b+10,0,6),(b+11,0,1),(55+i*2,0,200),(56+i*2,0,750),(65+i,0,100)]:expressions.append(f'slider{p}>={lo} && slider{p}<={hi}')
  expressions.extend([f'slider{b+3}==1',f'slider{b+4}==0',f'slider{b+6}=={12345+i*104729}'])
 hook=once('loop(100,master_patch_generate(0);'+check(' && '.join(expressions))+check('slider1==-4 && slider64==0')+');')
 _,v,saved=run('random_ranges',pre=hook)
 assert v[73]==200;meta,_=read4(saved);assert all(x['path'] for x in meta);reports.append(dict(test='random_ranges_100_patches',status='PASS',assertions=int(v[73])))
 # Saved generated values, independent of transient RNG progression, restore exactly.
 _,v,_=run('random_save',pre=once('master_request(1);'))
 p=[round(x,2) if i+1 in SOUND else x for i,x in enumerate(v[:70])];run('random_recall',events=[(0,144,60,100),(960,144,60,100)],params=p,recall=True);reports.append(dict(test='random_recall',status='PASS'))
 # Enable, then wait for full wet protection before adopting loud settings.
 condition='master_phase==1 ? ('+check('master_sound[7]==0')+') : master_phase==2 ? ('+check('limiter_wet==1 && master_sound[7]==6 && slider64==1')+');'
 _,v,_=run('chaos_enable',pre='play_state==1 && !master_test_once && play_position>.1 ? (master_test_once=1;master_request(2););',post=condition)
 assert v[68]==1 and v[63]==1 and v[70]==2 and v[73]>0
 for i in range(4):
  b=6+i*12;assert v[b]==6 and abs(v[b+2])==24 and v[b+9]==12 and v[b+10]==12 and v[b+11]==1 and v[64+i] in (0,100) and v[54+i*2]==10 and v[55+i*2]==20
 reports.append(dict(test='chaos_enable_and_protection',status='PASS'))
 p=[round(x,2) if i+1 in SOUND else x for i,x in enumerate(v[:70])];run('chaos_recall',events=[(0,144,60,100),(960,144,60,100)],params=p,recall=True);reports.append(dict(test='chaos_recall',status='PASS'))
 _,v,_=run('chaos_reroll',params=p,pre=once('master_request(1);'))
 assert any(v[k-1]!=p[k-1] for k in [8,9,65,20,21,66,32,33,67,44,45,68]);reports.append(dict(test='chaos_reroll',status='PASS'))
 # Off resets sound parameters, retains master/assignments, holds limiter on tails.
 pre='play_state==1 && play_position>.1 && !master_test_once ? (master_test_once=1;master_request(2););'
 post='master_phase==3 && master_chaos_tails()>0 ? ('+check('slider64==1 && master_chaos_active==0')+');'
 _,v,saved=run('chaos_off',params=p,events=[(0,144,60,100)],pre=pre,post=post)
 assert all(v[k-1]==0 for k in SOUND);assert v[0]==-4 and v[68]==0 and v[63]==0 and v[73]>0
 meta,_=read4(saved);assert all(x['path'] for x in meta);reports.append(dict(test='chaos_off_defaults_and_tail_hold',status='PASS'))
 p=par.copy();p[68]=1
 _,v,_=run('chaos_initial_on',params=p)
 assert v[6]==6 and abs(v[8])==24 and v[15]==12 and v[64] in (0,100);reports.append(dict(test='chaos_initial_on_normalized',status='PASS'))
 p=[round(x,2) if i+1 in SOUND else x for i,x in enumerate(v[:70])]
 # Host automation cannot defeat max settings/limiter while Chaos is active.
 _,v,_=run('chaos_lock',params=p,pre='play_state==1 && master_actions_started ? (slider7=-50;slider16=0;slider64=0;);',post=check('slider7==6 && slider16==12 && slider64==1'))
 reports.append(dict(test='chaos_parameter_lock',status='PASS'))
 # M11: Reset Sound shares factory values and preserves unrelated state.
 for limiter in (0,1):
  p=par.copy();p[0]=-7.3;p[63]=limiter;p[9]=0;p[22]=1;p[11]=2
  original_layers=[dict(x) for x in layers]
  layers[0]['flags']=[0,1];layers[0]['regions']=[[120,22000],[25000,45000]]
  pre=once('master_request(1);master_request(4);')
  _,v,saved=run('reset_preserves_'+str(limiter),params=p,pre=pre)
  assert all(v[k-1]==default for k,default in SOUND_DEFAULTS.items())
  assert abs(v[0]-p[0])<.00001 and v[63]==limiter and v[9]==0 and v[22]==1 and v[11]==2 and v[68]==0
  assert v[69]!=p[69], 'Reset must preserve advanced macro RNG state'
  meta,_=read4(saved)
  for i,m in enumerate(meta):
   assert m['path']==str(layers[i]['path']) and m['regions']==layers[i]['regions']
  assert meta[0]['flags']==[0,1]
  layers[:]=original_layers
  reports.append(dict(test='reset_preserves_state_limiter_'+str(limiter),status='PASS'))
 p=par.copy()
 for k,value in SOUND_DEFAULTS.items():p[k-1]=value
 baseline,_,_=run('reset_default_baseline',params=p,events=[(0,144,60,100)])
 actual,v,_=run('reset_before_trigger',pre=once('master_request(4);master_request(3);'))
 assert np.array_equal(baseline,actual)
 reports.append(dict(test='reset_next_trigger_matches_defaults',status='PASS'))
 # Repeated reset is idempotent and does not rewind either RNG.
 _,v,_=run('reset_repeated',pre=once('master_request(4);master_request(4);'))
 assert all(v[k-1]==default for k,default in SOUND_DEFAULTS.items()) and v[69]==par[69]
 reports.append(dict(test='reset_idempotent_rng_unchanged',status='PASS'))
 p=[round(x,2) if i+1 in SOUND else x for i,x in enumerate(v[:70])]
 run('reset_recall',params=p,events=[(0,144,60,100),(960,144,60,100)],recall=True)
 reports.append(dict(test='reset_saved_state_recall',status='PASS'))
 p=par.copy();p[68]=1
 _,v,saved=run('reset_chaos_tail',params=p,events=[(0,144,60,100)],
  pre='play_state==1 && play_position>.1 && !master_test_once ? (master_test_once=1;master_request(4););',
  post='master_phase==3 && master_chaos_tails()>0 ? ('+check('slider64==1 && master_chaos_active==0')+');')
 assert all(v[k-1]==default for k,default in SOUND_DEFAULTS.items()) and v[68]==0 and v[63]==0 and v[73]>0
 reports.append(dict(test='reset_exits_chaos_with_protected_tails',status='PASS'))
 (out/'macro-results.json').write_text(json.dumps(dict(source_sha256=hashlib.sha256(source.encode()).hexdigest(),passed=len(reports),results=reports),indent=2)+'\n');print('PASS',len(reports))
if __name__=='__main__':main()
