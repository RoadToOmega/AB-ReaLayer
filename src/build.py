#!/usr/bin/env python3
"""Build a self-contained JSFX from the verified M3 layer template.

Static namespaces isolate DSP/loader/GUI state; no runtime code generation.
Edit this adapter or the template, then rebuild. Python is not needed by users.
"""
from pathlib import Path
import re
import json
from ui_layout import OPEN_WIDTH,OPEN_HEIGHT

ROOT=Path(__file__).resolve().parents[1]
RELEASE=json.loads((ROOT/'release.json').read_text())
source=(ROOT/'src/layer-template.jsfx').read_text()
init=source.split('@init\n',1)[1].split('@serialize\n')[0]
serial=source.split('@serialize\n',1)[1].split('@slider\n')[0]
block=source.split('@block\n',1)[1].split('@sample\n')[0]
sample=source.split('@sample\n',1)[1].split('@gfx ')[0]
gui=source.split('@gfx 840 640\n',1)[1]
from m6_transform import transform
init,serial,block,sample,gui=transform(init,serial,block,sample,gui)
# Extend the M7 voice reader without copying PCM.
init=init.replace('region_rng.state=seq_seed;', 'reverse_rng.state=1+((seq_seed+7919)%2147483646); audition_rng.state=1+((seq_seed+15485863)%2147483646); region_rng.state=seq_seed;')
init=init.replace('v[6]*=10^(dg/20);', 'v[23]=(audition ? audition_rng.next_random() : reverse_rng.next_random())*100<max(0,min(100,slider24)); v[6]*=10^(dg/20);')
sample=sample.replace('pos_i=floor(v[2]); frac=v[2]-pos_i;', 'read_position=v[23] ? v[3]-1-(v[2]-v[12]) : v[2]; read_position=max(v[12],min(v[3]-1,read_position)); pos_i=floor(read_position); frac=read_position-pos_i;')
from m10_loader import transform as transform_loader
init=transform_loader(init)
init+='\n'+(ROOT/'src/edit-engine.eel').read_text()
from layout import STRIDE, BANK_CAPACITY, MAXMEM, LIMITER_BASE
from m10_actions import init_code as actions_init, audio_refs

# Tokenize comments/literals as opaque spans. Every user symbol (including
# instance field names and function names) receives a static layer namespace.
TOKEN=re.compile(r'//[^\n]*|/\*[\s\S]*?\*/|"(?:\\.|[^"\\])*"|\$[a-zA-Z]+|(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?|#?[A-Za-z_][A-Za-z_0-9]*')
functions=set(re.findall(r'function\s+(\w+)\s*\(',source))
calls=set(re.findall(r'\b(\w+)\s*\(',TOKEN.sub(lambda m:m[0] if not m[0].startswith(('//','/*','"')) else '',source)))
builtins=calls-functions
host={'this','srate','samplesblock','play_state','play_position','spl0','spl1',
      'ext_noinit','ext_tail_size','mouse_x','mouse_y','mouse_cap','mouse_wheel',
      'gfx_w','gfx_h','gfx_x','gfx_y','gfx_dest','gfx_ext_flags','function','local','instance'}

def params(layer):
    b=7+(layer-1)*12
    return {1:b,2:b+1,3:b+2,4:2,5:3,6:4,13:b+7,14:b+8,15:b+5,16:b+6,17:5,18:b+9,19:b+10,20:b+11,21:6,22:55+(layer-1)*2,23:56+(layer-1)*2,24:64+layer}

def ns(text,layer):
    mapping=params(layer)
    def sub(m):
        t=m[0]
        if t.startswith(('//','/*','"','$')) or t[0].isdigit() or t[0]=='.': return t
        if t.startswith('slider') and t[6:].isdigit():
            n=int(t[6:]); return 'slider'+str(mapping[n]) if n in mapping else f'l{layer}_detect{n}'
        if t in builtins or t in host or t.startswith(('master_','#master_')): return t
        if t.startswith('#'): return f'#l{layer}_'+t[1:]
        return f'l{layer}_'+t
    return TOKEN.sub(sub,text)

def adapt_init(layer):
    offset=(layer-1)*STRIDE
    t=init.replace('loop(memory_ok ? 3 : 0','loop(memory_ok ? 2 : 0').replace('bank_capacity=8388608',f'bank_capacity={BANK_CAPACITY}')
    t=t.replace('pcm_base+3*bank_capacity','pcm_base+2*bank_capacity')
    for key,value in [('bank_meta',1024),('bank_paths',8192),('region_base',12288),
                      ('saved_regions',4096),('saved_settings',4700),('shuffle_base',7000),
                      ('voice_base',16384),('event_base',32768),('pcm_base',65536),('saved_flags',5000),('edit_regions',48000),('edit_flags',48512),('edit_settings',49000)]:
        t=t.replace(f'{key}={value}',f'{key}={value+offset}')
    t=t.replace('booted=1;', 'booted=1; slider7=-36; slider8=6; slider9=80; slider10=10; slider11=3; slider12=20;')
    t=t.replace('setup();\next_noinit=1;','ext_noinit=1;')
    t+='''
function has_room() local(i,v,room) (
  room=0; i=0; loop(voice_limit,v=voice_base+i*voice_stride; !v[0] ? room=1; i+=1;); room;
);
function participates() local(m) (
  m=bank_meta+token_bank(active_token)*bank_stride;
  layer_audible && active_token>0 && (slider13>=.5 || (m[16]>0 &&
    (seq_mode!=4 || (region_base+token_bank(active_token)*region_stride)[512+max(0,min(m[7]-1,floor(slider14)-1))]>0)));
);
'''
    t=t.replace('v[0]=1;',f'master_voice_tags[{(layer-1)*16}+(v-voice_base)/voice_stride]=master_chaos_active;v[0]=1;')
    return audio_refs(ns(t,layer))

def adapt_serial(layer):
    # M4 wraps four complete v3 bank descriptors. Host parameters are separate.
    t=serial.replace('setup();','')
    t=t.replace('ss_token=ss_restore_pending ? -2 : ss.pin_active();',
                'ss_token=(atomic_get(clear_request)>0 || atomic_get(master_clear_request)>0) ? -1 : ss_restore_pending ? -2 : ss.pin_active();')
    t+='\n'+''.join(f'file_var(0,slider{i});\n' for i in range(7,13))
    return ns(t,layer)

def adapt_block(layer):
    t=block.split('// Queue kind:')[0]
    t=t.replace('loop(3,','loop(2,')
    # Clearing detaches the bank but leaves its voices fading on retired PCM.
    t=t.replace('// New-bank adoption', '''
(atomic_setifequal(clear_request,1,0)==1 || master_clearing) ? (
  release_all();
  active_token>0 ? (a_meta=bank_meta+token_bank(active_token)*bank_stride; atomic_set(a_meta[0],4););
  atomic_set(active_token,0);
);
// New-bank adoption''')
    t=t.replace('a_meta[4]==audio_request ?', 'a_meta[4]==audio_request && !master_clearing ?')
    t=t.replace('target_gain=10^','target_gain=layer_audible*10^')
    t+='\nblock_peak=0; block_voices=0;\n'
    return audio_refs(ns(t,layer))

def adapt_sample(layer):
    t=sample[sample.index('smooth_gain+='):]
    t=t.replace('spl0=out_l; spl1=out_r;','master_left+=out_l; master_right+=out_r;')
    t=t.replace('sample_index+=1;','').replace('sample_index>=samplesblock','master_sample_index+1>=samplesblock')
    return ns(t,layer)

header='''desc:AB_ReaLayer
author:Original implementation for Multi Layer Sampler
version:0.11.1
about:
  AB ReaLayer - Multilayer Random Variation Sampler for REAPER.
  Designed for game audio and sound design workflows.
tags:instrument sampler
// Generated by src/build.py. Four isolated layers, two 96 MiB PCM banks each.
options:maxmem=67371008 prealloc=* gfx_idle
in_pin:none
out_pin:Left
out_pin:Right
slider1:-4<-60,6,0.1>Master output (dB)
slider2:0<0,16,1>MIDI channel (0 = all)
slider3:-1<-1,127,1>Trigger note (-1 = all)
slider4:2<0.1,10,0.1>Edge fade (ms)
slider5:0<0,1,1{Transport start and manual,Manual only}>Sequence reset policy
slider6:-1<-1,119,1>Sequence reset MIDI CC (-1 = off)
'''
for layer in range(1,5):
    b=7+(layer-1)*12
    defs=['0<-60,6,0.1>Volume (dB)','0<-1,1,0.01>Pan / stereo balance',
          '0<-24,24,0.01>Pitch (semitones)','1<0,1,1{Muted,Enabled}>Enable',
          '0<0,1,1{Off,Solo}>Solo','0<0,4,1{Random no repeat,Shuffle bag,Round robin,Random,Fixed}>Selection',
          f'{12345+(layer-1)*104729}<1,16777215,1>Seed','0<0,1,1{Variations,Whole WAV}>Playback',
          '1<1,256,1>Audition / fixed region','0<0,12,0.01>Random pitch (+/- st)',
          '0<0,12,0.1>Random gain (+/- dB)','0<0,1,0.01>Random pan (+/-)']
    for j,d in enumerate(defs):
        value,label=d.rsplit('>',1); header+=f'slider{b+j}:{value}>Layer {layer}: {label}\n'

for layer in range(1,5):
    header+=f'slider{55+(layer-1)*2}:0<0,2000,1>Layer {layer}: Attack (ms)\n'
    header+=f'slider{56+(layer-1)*2}:0<0,5000,1>Layer {layer}: End release (ms)\n'
header=header.replace('maxmem=67371008',f'maxmem={MAXMEM}')
header+='slider63:0<0,1,1>Reserved for future history\nslider64:0<0,1,1{Off,On}>Master limiter\n'
for layer in range(1,5): header+=f'slider{64+layer}:0<0,100,1>Layer {layer}: Reverse chance (%)\n'
header+='slider69:0<0,1,1{Off,On}>Chaos mode\nslider70:1357911<0,16777215,1>Macro random state\n'
init_parts=[adapt_init(i) for i in range(1,5)]
init_parts.append(actions_init())
init_parts.append('function master_pump_one() ( master_pumped=0; loop(4, !master_pumped ? ( master_pump=(master_pump+1)%4;')
for i in range(1,5):
    init_parts.append(f'''master_pump=={i-1} && (l{i}_gui_loader.l{i}_status==1 || l{i}_gui_loader.l{i}_status==3) ? (
      master_pumped=1; l{i}_gui_loader.l{i}_load_step();
    );''')
init_parts.append(');); master_pumped; );')
init_parts.append('function master_pump_loaders() local(start,j,worked) (start=time_precise();j=0;worked=1;while(worked && j<16 && (j==0 || time_precise()-start<.004)) (worked=master_pump_one();j+=1;););')
init_parts.append('function master_reject_state() (')
for i in range(1,5):
    init_parts.append(f'''l{i}_restore_failed=1; l{i}_restore_loader.l{i}_status=-8;
      #l{i}_saved_path=""; l{i}_saved_frames=0; l{i}_saved_channels=0; l{i}_saved_rate=0;
      l{i}_saved_count=0; l{i}_saved_overflow=0;
      atomic_set(l{i}_restore_request,atomic_add(l{i}_latest_request,1));
      atomic_set(l{i}_clear_request,1);
    ''')
init_parts.append(');')
for i in range(1,5): init_parts.append(f'l{i}_setup();')
init_parts.append('master_event_base=40000; master_event_limit=2048; master_editor_y=176; ext_noinit=1; ext_tail_size=-1;\n// TEST_M4_INIT_HOOK')

serial_parts=['master_write=file_avail(0)<0; master_magic=master_write ? 73104 : 0; master_version=master_write ? 6 : 0; file_var(0,master_magic); file_var(0,master_version);',
              'master_magic==73104 && (master_version==4 || master_version==6) ? (']
for i in range(1,5): serial_parts.append(adapt_serial(i))
serial_parts.append(') : (')
serial_parts.append('master_reject_state();')
serial_parts.append(');')

blocks=['master_clearing=atomic_setifequal(master_clear_request,1,0)==1;', 'master_any_solo=slider11>=.5 || slider23>=.5 || slider35>=.5 || slider47>=.5;']
for i in range(1,5):
    b=7+(i-1)*12
    blocks.append(f'l{i}_layer_audible=slider{b+3}>=.5 && (!master_any_solo || slider{b+4}>=.5);')
    blocks.append(adapt_block(i))
blocks.append('''
master_target=10^(max(-60,min(6,slider1))/20);
master_smoothing=1-exp(-1/(.005*srate));
!master_started ? (master_gain=master_target; master_started=1;);
master_event_count=0; master_event_index=0; master_sample_index=0;
// Button-generated notes share the MIDI queue and all-or-none admission path.
loop(master_play_pending,
 master_e=master_event_base+master_event_count*3;master_e[0]=0;master_e[1]=0;master_e[2]=100;master_event_count+=1;
);

while(midirecv(master_offset,master_status,master_data1,master_data2)) (
  master_type=master_status&240; master_channel=(master_status&15)+1;
  master_matches=slider2==0 || master_channel==floor(slider2);
  master_note=master_type==144 && master_data2>0 && master_matches && (slider3<0 || master_data1==floor(slider3));
  master_panic=master_type==176 && master_matches && (master_data1==120 || master_data1==123);
  master_reset=master_type==176 && master_matches && slider6>=0 && master_data1==floor(slider6) && master_data2>=64;
  master_note || master_panic || master_reset ? (
    master_event_count<master_event_limit ? (
      master_e=master_event_base+master_event_count*3;
      master_e[0]=max(0,min(samplesblock-1,master_offset));
      master_e[1]=master_reset ? 2 : master_panic; master_e[2]=master_data2;
      master_event_count+=1;
    ) : (
      master_overflows+=1;
      master_panic ? (l1_release_all(); l2_release_all(); l3_release_all(); l4_release_all(););
    );
  ) : (
    !((master_type==128 || (master_type==144 && master_data2==0)) && master_matches && (slider3<0 || master_data1==floor(slider3))) ?
      midisend(master_offset,master_status,master_data1,master_data2);
  );
);
atomic_setifequal(master_panic_request,1,0)==1 ? (l1_release_all(); l2_release_all(); l3_release_all(); l4_release_all(););
atomic_setifequal(master_reset_request,1,0)==1 ? (l1_reset_sequence(); l2_reset_sequence(); l3_reset_sequence(); l4_reset_sequence(););
// TEST_M4_BLOCK_HOOK
''')

samples=['''
while(master_event_index<master_event_count && master_event_base[master_event_index*3]<=master_sample_index) (
  master_e=master_event_base+master_event_index*3;
  master_e[1]==2 ? (l1_reset_sequence(); l2_reset_sequence(); l3_reset_sequence(); l4_reset_sequence();) :
  master_e[1]==1 ? (l1_release_all(); l2_release_all(); l3_release_all(); l4_release_all();) : (
''']
for i in range(1,5): samples.append(f'master_p{i}=l{i}_participates();')
samples.append('master_reject='+ ' || '.join(f'(master_p{i} && !l{i}_has_room())' for i in range(1,5))+';')
samples.append('master_reject ? master_rejected+=1 : (')
for i in range(1,5): samples.append(f'master_p{i} ? l{i}_start_voice(master_e[2],0);')
samples.append('''
    );
  );
  master_event_index+=1;
);
// TEST_M4_SAMPLE_HOOK
master_left=0; master_right=0;
''')
samples.extend(adapt_sample(i) for i in range(1,5))
samples.append('''
master_gain+=(master_target-master_gain)*master_smoothing;
spl0=master_left*master_gain; spl1=master_right*master_gain;
master_peak=max(master_peak,max(abs(spl0),abs(spl1)));
master_peak_left=max(master_peak_left,abs(spl0));master_peak_right=max(master_peak_right,abs(spl1));
master_sample_index+=1;
master_sample_index>=samplesblock ? (
  atomic_set(master_meter_peak,master_peak); master_peak=0;
  atomic_set(master_meter_left,master_peak_left);atomic_set(master_meter_right,master_peak_right);master_peak_left=0;master_peak_right=0;
  atomic_set(master_meter_rejected,master_rejected); atomic_set(master_meter_overflow,master_overflows);
);
''')


# The M7-derived GUI remains a separate presentation module. M10 action and
# loader modules extend the engine while retaining its immutable bank protocol.
from m7_gui import build as build_gui
builtins.update({'slider','str_getchar','strcpy_substr','strcmp','strcpy_from','time_precise','gfx_circle','gfx_arc','sin','cos'})
init_parts.append((ROOT/'src/limiter.eel').read_text().replace('LIMITER_BASE',str(LIMITER_BASE)))
blocks.insert(1,'master_actions_block();limiter_configure();master_sound_snapshot();')
samples=[s.replace('master_peak=max(master_peak','limiter_process();\nmaster_peak=max(master_peak') for s in samples]
header=re.sub(r'^(slider\d+:[^\n]*?>)',r'\1-',header,flags=re.M)
header=header.replace('gfx_idle','gfx_idle no_meter')
init_parts.append("gfx_ext_retina=1; // Request native Retina rendering; layout uses actual framebuffer dimensions.")
gui_output=build_gui(ns,gui)
output=header+'\n@init\n'+'\n'.join(init_parts)+'\n@serialize\n'+'\n'.join(serial_parts)+'\n@slider\n// Native parameters are sampled at audio block boundaries.\n@block\n'+'\n'.join(blocks)+'\n@sample\n'+'\n'.join(samples)+f'\n@gfx {OPEN_WIDTH} {OPEN_HEIGHT}\n'+gui_output
# Release metadata is shared by the host header, GUI subtitle and ReaPack package.
output=output.replace('desc:AB_ReaLayer (0.11.1)',f'desc:AB_ReaLayer ({RELEASE["version"]})')
output=output.replace('version:0.11.1',f'version:{RELEASE["version"]}')
output=output.replace('V0.11.1',f'V{RELEASE["version"]}')
output=output.replace('author:Original implementation for Multi Layer Sampler',f'author:{RELEASE["author"]}')
from eel_syntax import validate_literals
validate_literals(output)
(ROOT/'VariationSampler-M11.jsfx').write_text(output)
print('Built',ROOT/'VariationSampler-M11.jsfx',len(output),'bytes')

# Only this category folder is indexed. The root copy serves existing test runners.
package=ROOT/'Instruments/VariationSampler-M11.jsfx'
package.parent.mkdir(exist_ok=True)
meta='// @description '+RELEASE['description']+'\n// @version '+RELEASE['version']+'\n// @author '+RELEASE['author']+'\n'
meta+='// @about\n//   AB ReaLayer - Multilayer Random Variation Sampler for REAPER.\n//   Designed for game audio and sound design workflows.\n// @changelog\n'
meta+=''.join('//   '+line+'\n' for line in RELEASE['changelog'])
package.write_text(meta+'\n'+output)
print('Packaged',package)
