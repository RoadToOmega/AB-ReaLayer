"""Generate bounded audio-owned sound macros and GUI-to-audio command transport."""
from layout import LIMITER_BASE
from parameters import SOUND, LOCKED, SOUND_DEFAULTS

def audio_refs(code):
 import re
 return re.sub(r'\bslider(\d+)\b',lambda m:f'master_sound[{m[1]}]' if int(m[1]) in SOUND else m[0],code)

def init_code():
 out=[f'''// Control memory occupies the unused part of the M9 master reservation.
master_sound={LIMITER_BASE+16384};master_patch={LIMITER_BASE+16512};master_previous_patch={LIMITER_BASE+16640};
master_commands={LIMITER_BASE+16800};master_voice_tags={LIMITER_BASE+17000};
function master_action_put(p,v) (''']
 for p in SOUND+[64,69,70]:out.append(f'p=={p} && slider{p}!=v ? (slider{p}=v;slider_automate(slider{p},1););')
 out+=[''' );
// Exactly representable 24-bit LCG state survives host float serialization.
function master_macro_random() (
 master_rng=(master_rng*1664525+1013904223)%16777216;master_rng/16777216;
);
function master_action_locked(p) (
 (slider69>=.5 && ('''+' || '.join(f'p=={p}' for p in LOCKED)+''')) || (p==64 && atomic_get(master_protection)>0);
);
// Single GUI producer, single audio consumer; publication happens after payload.
function master_request(op) local(w,r,p) (
 w=atomic_get(master_command_write);r=atomic_get(master_command_read);
 w-r<16 ? (p=master_commands+(w%16)*2;p[0]=op;p[1]=time_precise();atomic_set(master_command_write,w+1);1;) : 0;
);
function master_patch_capture() (''']
 for p in SOUND:out.append(f'master_patch[{p}]=slider{p};')
 out+=[');\nfunction master_patch_commit() (']
 for p in SOUND:out.append(f'master_action_put({p},master_patch[{p}]);')
 out+=[');\nfunction master_sound_snapshot() (\nmaster_phase!=1 || limiter_wet>=1 ? (']
 for p in SOUND:out.append(f'master_sound[{p}]=slider{p};')
 out+=['master_phase==1 ? (master_phase=2;master_chaos_active=1;););\n);', 'function master_patch_generate(chaos) local(u,same) (']
 for p in SOUND:out.append(f'master_previous_patch[{p}]=slider{p};')
 for i in range(4):
  b=7+i*12
  values={b:'chaos ? 6 : floor((-18+21*master_macro_random())*10+.5)/10', b+1:'floor((-1+2*master_macro_random())*100+.5)/100',b+2:'chaos ? (master_macro_random()<.5 ? -24 : 24) : floor((-12+24*master_macro_random())*100+.5)/100',b+9:'chaos ? 12 : floor(6*master_macro_random()*100+.5)/100',b+10:'chaos ? 12 : floor(6*master_macro_random()*10+.5)/10',b+11:'chaos ? 1 : floor(master_macro_random()*100+.5)/100',65+i:'chaos ? (master_macro_random()<.5 ? 0 : 100) : floor(master_macro_random()*101)',55+i*2:f'chaos ? slider{55+i*2} : floor(200*sqr(master_macro_random())+.5)',56+i*2:f'chaos ? slider{56+i*2} : floor(750*sqr(master_macro_random())+.5)'}
  for p,v in values.items():out.append(f'master_patch[{p}]={v};')
 out+=['same=1;']
 for p in SOUND:out.append(f'master_patch[{p}]!=master_previous_patch[{p}] ? same=0;')
 out+=['''same ? (chaos ? master_patch[8]=master_patch[8]>=.99 ? -.99 : master_patch[8]+.01 : master_patch[7]=master_patch[7]>=2.9 ? -18 : master_patch[7]+.1;);
master_patch_commit();master_action_put(70,master_rng);
);
function master_reset_sound() (
''']
 for p in SOUND:out.append(f'master_patch[{p}]={SOUND_DEFAULTS[p]};')
 out+=['master_patch_commit();\n);\nfunction master_chaos_off() (master_chaos_active=0;master_phase=3;master_hold_frames=max(1,srate*.01);master_reset_sound();master_action_put(69,0););','function master_chaos_enforce() (']
 for p in LOCKED:out.append(f'master_action_put({p},master_patch[{p}]);')
 out+=[');\nfunction master_chaos_tails() local(n,i,v) (n=0;']
 from layout import STRIDE
 for l in range(4):out.append(f'i=0;loop(16,v={l*STRIDE+16384}+i*24;v[0] && master_voice_tags[{l*16}+i]>0 ? n+=1;i+=1;);')
 out+=['n;);', 'function master_chaos_normalize() (']
 for i in range(4):
  b=7+i*12
  out.append(f'master_patch[{b}]=6;master_patch[{b+9}]=12;master_patch[{b+10}]=12;master_patch[{b+11}]=1;')
  out.append(f'abs(master_patch[{b+2}])!=24 ? master_patch[{b+2}]=master_macro_random()<.5 ? -24 : 24;')
  out.append(f'master_patch[{65+i}]!=0 && master_patch[{65+i}]!=100 ? master_patch[{65+i}]=master_macro_random()<.5 ? 0 : 100;')
 out+=['master_patch_commit();master_action_put(70,master_rng););', '''
function master_actions_block() local(r,w,p,op,age,steps) (
 // Initialize from recalled values without rerolling a saved Chaos preset.
 !master_actions_started ? (
  master_actions_started=1;master_chaos_seen=slider69>=.5;
  master_rng=max(0,min(16777215,floor(slider70)));
  master_patch_capture();master_chaos_seen ? master_chaos_normalize();master_phase=master_chaos_seen ? 2 : 0;master_chaos_active=master_chaos_seen;
''']
 for p in SOUND:out.append(f'master_sound[{p}]=slider{p};')
 out+=[''' );
 master_play_pending=0;
 // MIDI/host automation may also change the Chaos switch.
 (slider69>=.5)!=master_chaos_seen ? (
  slider69>=.5 ? (master_patch_generate(1);master_phase=1;) : master_chaos_off();
 );
 r=atomic_get(master_command_read);w=atomic_get(master_command_write);steps=0;
 while(r<w && steps<16) (
  p=master_commands+(r%16)*2;op=p[0];age=time_precise()-p[1];
  age>=0 && age<.5 && !master_clearing && !atomic_get(master_panic_request) ? (
   op==1 ? master_patch_generate(slider69>=.5) :
   op==2 ? (slider69>=.5 ? master_chaos_off() : (master_patch_generate(1);master_action_put(69,1);master_phase=1;);) :
   op==3 ? master_play_pending+=1 :
   op==4 ? (slider69>=.5 ? master_chaos_off() : master_reset_sound(););
  );
  r+=1;steps+=1;atomic_set(master_command_read,r);
 );
 master_chaos_seen=slider69>=.5;
 slider69>=.5 ? master_chaos_enforce();
 master_phase==3 ? (
  master_chaos_tails()>0 ? master_hold_frames=max(1,srate*.01) : master_hold_frames-=samplesblock;
  master_hold_frames<=0 ? (master_phase=0;master_action_put(64,0););
 );
 master_phase>0 ? master_action_put(64,1);
 atomic_set(master_protection,master_phase);
 master_limiter_target=slider64>=.5;
);
''']
 return '\n'.join(out)
