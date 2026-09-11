#!/usr/bin/env python3
"""Bank lifecycle and per-layer analysis checks in actual REAPER.

Temporary test drivers stage loads outside DSP and publish at audio boundaries.
Production code is unchanged; GUI drag/drop and real-time scheduling need
workstation acceptance separately.
"""
import argparse,base64,hashlib,json,re,struct,subprocess,warnings
from pathlib import Path
import numpy as np
from scipy.io import wavfile
from reference import project,expected_voice,SETTINGS
from layer_checks import state4

def read4(path):
    match=re.search(r'<JS_SER\s+([^>]+)>',path.read_text())
    raw=base64.b64decode(''.join(match[1].split())); pos=0
    def numbers(n):
        nonlocal pos
        vals=struct.unpack_from('<'+'f'*n,raw,pos); pos+=4*n; return vals
    magic,version=numbers(2); assert magic==73104 and version in (4,6)
    layers=[]
    for _ in range(4):
        magic,inner=numbers(2); assert magic==73101 and inner in (3,4)
        length=struct.unpack_from('<I',raw,pos)[0]; pos+=4
        text=raw[pos:pos+length].decode(); pos+=length+(-length%4)
        frames,ch,rate,count,overflow=numbers(5)
        settings=numbers(6); bounds=numbers(int(count)*2)
        flags=list(numbers(int(count))) if inner==4 else [1]*int(count)
        controls=numbers(6)
        layers.append(dict(path=text,frames=int(frames),ch=int(ch),rate=int(rate),count=int(count),overflow=int(overflow),
            settings=list(settings),flags=flags,controls=list(controls),regions=[list(map(int,bounds[i:i+2])) for i in range(0,len(bounds),2)]))
    extra=numbers(1)[0] if len(raw)-pos>=4 else 0
    return layers,round(extra)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--reaper',required=True,type=Path); ap.add_argument('--output',required=True,type=Path)
    args=ap.parse_args(); out=args.output.resolve(); effects=out/'profile/Effects'; effects.mkdir(parents=True,exist_ok=True)
    src=Path(__file__).resolve().parents[1]/'VariationSampler-M11.jsfx'; code=src.read_text()
    common=[str(args.reaper.resolve()),'-newinst','-nosplash','-ignoreerrors','-cfgfile',str(out/'profile/reaper.ini')]
    paths=[]; audio=[]; layers=[]
    for i in range(4):
        x=np.zeros(96000,np.float32)
        for start,end,amp in [(.1,.2,.03),(.5,.65,.04),(1,1.15,.02)]: x[round(start*48000):round(end*48000)]=amp*(i+1)
        if i%2: x=np.column_stack((x,-x*.7))
        path=out/f'layer{i+1}.wav'; wavfile.write(path,48000,x)
        paths.append(path); audio.append(x)
        layers.append(dict(path=str(path),frames=len(x),ch=1+i%2,rate=48000,regions=[(0,len(x))]))
    bounds=[[4656,10560],[23856,32160],[47856,56160]]
    results=[]

    def run(name,target,action):
        layer=target+1; p=f'l{layer}_'
        # Test hooks drive GUI-owned loader functions. Disable idle GUI to avoid
        # two owners in the instrumented copy; production code is unchanged.
        variant=code.split('\n@gfx ')[0]+'\n@gfx 1100 720\n// Deterministic test-driver ownership.\n' 
        params=[-12,0,-1,2,0,-1]
        for i in range(4): params.extend([0,0,0,1,0,4,12345+i*104729,0,2,0,0,0])
        first=[expected_voice(x,48000,48000,0,gain_db=-12) for x in audio]
        second=[expected_voice(x,48000,48000,19200,gain_db=-12) for x in audio]
        expected_regions=[[[0,96000]] for _ in range(4)]
        if action=='detect':
            variant=variant.replace(f'{p}restore_loader.{p}mode=2;',f'{p}restore_loader.{p}mode=0;')
            clip=audio[target][bounds[1][0]:bounds[1][1]]
            first[target]=expected_voice(clip,48000,48000,0,gain_db=-12)
            second[target]=expected_voice(clip,48000,48000,19200,gain_db=-12)
            expected_regions[target]=bounds
        elif action in ('hold','discard','apply','busy'):
            init=f'''
test_loader.{p}mode=1;
test_request=atomic_add({p}latest_request,1);
test_loader.{p}begin_load("{paths[target]}",test_request,0,0,0);
loop(1026,(test_loader.{p}status==1 || test_loader.{p}status==3) ? test_loader.{p}load_step(););
'''
            variant=variant.replace('// TEST_M4_INIT_HOOK',init)
            command={'hold':'','discard':f'test_loader.{p}cancel_load();',
                'apply':f'test_loader.{p}request=atomic_add({p}latest_request,1); test_loader.{p}meta[4]=test_loader.{p}request; test_loader.{p}publish_bank();',
                'busy':f'test_busy.{p}begin_load("{paths[target]}",atomic_add({p}latest_request,1),0,0,0);'}[action]
            hook=f'''
!master_test_done && play_state==1 && play_position>=.25 ? (
  {command}
  master_test_action_frame=play_position*srate; master_test_done=1;
);
'''
            variant=variant.replace('// TEST_BLOCK_HOOK (temporary test copies only; no production I/O here).',hook,1)
            if action=='apply':
                clip=audio[target][bounds[1][0]:bounds[1][1]]
                second[target]=expected_voice(clip,48000,48000,19200,gain_db=-12)
                expected_regions[target]=bounds
            if action=='busy':
                # A wrong status adds an audible diagnostic, verified below.
                variant=variant.replace('// TEST_M4_SAMPLE_HOOK',f'master_test_done && test_busy.{p}status!=-4 ? master_gain=1000;')
        elif action=='clear':
            command=f'atomic_add({p}latest_request,1); atomic_set({p}clear_request,1);'
            hook=f'!master_test_done && play_state==1 && play_position>=.15 ? ({command} master_test_action_frame=play_position*srate; master_test_done=1;);'
            variant=variant.replace('// TEST_BLOCK_HOOK (temporary test copies only; no production I/O here).',hook,1)
            second[target]=np.zeros((96000,2)); expected_regions[target]=[]
        elif action=='reset_layer':
            # Use round robin with three saved spans, and reset only this layer.
            for i in range(4): params[6+i*12+5]=2
            command=f'atomic_set({p}reset_request,1);'
            hook=f'!master_test_done && play_state==1 && play_position>=.25 ? ({command} master_test_action_frame=play_position*srate; master_test_done=1;);'
            variant=variant.replace('// TEST_BLOCK_HOOK (temporary test copies only; no production I/O here).',hook,1)
            for i,x in enumerate(audio):
                first[i]=expected_voice(x[bounds[0][0]:bounds[0][1]],48000,48000,0,gain_db=-12)
                selected=0 if i==target else 1
                second[i]=expected_voice(x[bounds[selected][0]:bounds[selected][1]],48000,48000,19200,gain_db=-12)
                expected_regions[i]=bounds
        variant=variant.replace('@slider\n','file_var(0,master_test_action_frame);\n@slider\n')
        plugin=name+'.jsfx'; (effects/plugin).write_text(variant)
        state_layers=[dict(x) for x in layers]
        for i,x in enumerate(state_layers): x['settings']=(-36+i,6+i,80+i*10,10+i,3+i,20+i)
        if action=='reset_layer':
            for x in state_layers: x['regions']=bounds
        output=out/(name+'.wav'); rpp=out/(name+'.rpp'); saved=out/(name+'.saved.rpp'); lua=out/(name+'.lua')
        rpp.write_text(project(output,plugin,state4(state_layers),48000,params,[(0,0x90,60,127),(768,0x90,60,127)]))
        lua.write_text(f'reaper.Main_openProject([[{rpp}]])\nreaper.Main_OnCommand(42230,0)\nreaper.Main_SaveProjectEx(0,[[{saved}]],0)\nreaper.Main_OnCommand(40004,0)\n')
        proc=subprocess.run(common+[str(lua)],capture_output=True,text=True,timeout=90)
        (out/(name+'.log')).write_text(proc.stdout+proc.stderr)
        assert proc.returncode==0 and output.exists() and saved.exists(),name
        metadata,action_frame=read4(saved)
        for i,m in enumerate(metadata):
            assert m['regions']==expected_regions[i],(name,i,m)
            assert m['controls']==list(state_layers[i]['settings']),(name,'detector controls',i,m)
        if action=='clear':
            first[target]=expected_voice(audio[target],48000,48000,0,gain_db=-12,release=action_frame)
            assert metadata[target]['path']=='',name
        expected=sum(first)+sum(second)
        with warnings.catch_warnings():
            warnings.simplefilter('ignore'); _,pcm=wavfile.read(output)
        error=float(np.max(np.abs(pcm.astype(float)/2**31-expected)))
        assert error<3e-6,(name,error,action_frame)
        results.append(dict(test=name,status='PASS',max_absolute_error=error,action_frame=action_frame,layers=metadata))

    for target in range(4):
        for action in ('detect','hold','discard','apply','busy','clear','reset_layer'):
            run(f'layer{target+1}_{action}',target,action)
    report=dict(host='REAPER 7.79 Linux x86_64',source_sha256=hashlib.sha256(src.read_bytes()).hexdigest(),passed=len(results),results=results)
    (out/'lifecycle-results.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=len(results),report=str(out/'lifecycle-results.json')),indent=2))

if __name__=='__main__': main()
