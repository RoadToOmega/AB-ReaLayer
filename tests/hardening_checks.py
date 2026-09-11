#!/usr/bin/env python3
"""Actual REAPER checks for work-conserving scheduling and stale-load rejection."""
import argparse,base64,hashlib,json,re,struct,subprocess,warnings
from pathlib import Path
import numpy as np
from scipy.io import wavfile
from reference import project
from layer_checks import state4
from lifecycle_checks import read4

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--reaper',required=True,type=Path); ap.add_argument('--output',required=True,type=Path)
    args=ap.parse_args(); out=args.output.resolve(); effects=out/'profile/Effects'; effects.mkdir(parents=True,exist_ok=True)
    src=Path(__file__).resolve().parents[1]/'VariationSampler-M11.jsfx'; code=src.read_text()
    common=[str(args.reaper.resolve()),'-newinst','-nosplash','-ignoreerrors','-cfgfile',str(out/'profile/reaper.ini')]
    wav=out/'source.wav'; wavfile.write(wav,48000,np.full(96000,.05,np.float32))
    empty=[dict(path='',frames=0,ch=1,rate=48000,regions=[]) for _ in range(4)]
    params=[-12,0,-1,2,0,-1]+[v for i in range(4) for v in (0,0,0,1,0,0,12345+i*104729,1,1,0,0,0)]
    results=[]

    def run(name,variant,state,render=False):
        plugin=name+'.jsfx'; (effects/plugin).write_text(variant)
        output=out/(name+'.wav'); rpp=out/(name+'.rpp'); saved=out/(name+'.saved.rpp'); lua=out/(name+'.lua')
        rpp.write_text(project(output,plugin,state,48000,params,[(192,0x90,60,127)]))
        render_action='reaper.Main_OnCommand(42230,0)\n' if render else ''
        lua.write_text(f'reaper.Main_openProject([[{rpp}]])\n{render_action}reaper.Main_SaveProjectEx(0,[[{saved}]],0)\nreaper.Main_OnCommand(40004,0)\n')
        p=subprocess.run(common+[str(lua)],capture_output=True,text=True,timeout=90)
        (out/(name+'.log')).write_text(p.stdout+p.stderr)
        assert p.returncode==0 and saved.exists(),name
        return saved,output

    for mask in range(1,16):
        hook=[]
        for i in range(1,5):
            if mask&(1<<(i-1)):
                hook.append(f'l{i}_gui_loader.l{i}_begin_load("{wav}",atomic_add(l{i}_latest_request,1),0,0,0);')
        hook.append('loop(4,master_pump_one(););')
        for i in range(1,5): hook.append(f'master_test{i}=l{i}_gui_loader.l{i}_read_items; l{i}_gui_loader.l{i}_cancel_load();')
        variant=code.replace('// TEST_M4_INIT_HOOK','\n'.join(hook))
        variant=variant.replace('@slider\n',''.join(f'file_var(0,master_test{i});\n' for i in range(1,5))+'@slider\n')
        saved,_=run('scheduler_mask_'+str(mask),variant,state4(empty))
        raw=base64.b64decode(''.join(re.search(r'<JS_SER\s+([^>]+)>',saved.read_text())[1].split()))
        actual=list(struct.unpack('<4f',raw[-16:])); expected=[0]*4; cursor=0
        for _ in range(4):
            for __ in range(4):
                cursor=(cursor+1)%4
                if mask&(1<<cursor): expected[cursor]+=16384; break
        assert actual==expected,(mask,actual,expected)
        results.append(dict(test='scheduler_mask_'+str(mask),status='PASS',decoded_items=actual))

    # Pre-stage READY banks before the host attempts an invalid state restore.
    # If rejection does not advance request generations, audio can adopt them.
    hook=[]
    for i in range(1,5):
        hook.append(f'''l{i}_gui_loader.l{i}_begin_load("{wav}",atomic_add(l{i}_latest_request,1),0,0,0);
loop(20,(l{i}_gui_loader.l{i}_status==1 || l{i}_gui_loader.l{i}_status==3) ? l{i}_gui_loader.l{i}_load_step(););''')
    variant=code.replace('// TEST_M4_INIT_HOOK','\n'.join(hook))
    for name,raw in [('invalid_magic',struct.pack('<ff',999,4)),('unsupported_version',struct.pack('<ff',73104,99)),('truncated_header',struct.pack('<f',73104))]:
        saved,output=run(name,variant,base64.b64encode(raw).decode(),True)
        layers,_=read4(saved)
        assert all(x['path']=='' and x['count']==0 and x['frames']==0 for x in layers),name
        with warnings.catch_warnings():
            warnings.simplefilter('ignore'); _,pcm=wavfile.read(output)
        assert np.count_nonzero(pcm)==0,name
        results.append(dict(test=name,status='PASS',nonzero_samples=0))
    report=dict(host='REAPER 7.79 Linux x86_64',source_sha256=hashlib.sha256(src.read_bytes()).hexdigest(),passed=len(results),results=results)
    (out/'hardening-results.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=len(results),report=str(out/'hardening-results.json')),indent=2))

if __name__=='__main__': main()
