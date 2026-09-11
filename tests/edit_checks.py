#!/usr/bin/env python3
"""Real REAPER edit publication, exclusions, envelopes and recall checks."""
import argparse,base64,hashlib,json,struct,subprocess,warnings
from pathlib import Path
import numpy as np
from scipy.io import wavfile
from reference import project,expected_voice,Sequence,SETTINGS
from lifecycle_checks import read4

def state6(layers):
    blob=struct.pack('<ff',73104,6)
    for l in layers:
        path=str(l['path']).encode(); regions=l['regions']; flags=l.get('flags',[1]*len(regions))
        blob+=struct.pack('<ffI',73101,4,len(path))+path+b'\0'*(-len(path)%4)
        blob+=struct.pack('<5f',l['frames'],l['ch'],l['rate'],len(regions),0)+struct.pack('<6f',*SETTINGS)
        blob+=struct.pack('<'+'f'*len(regions)*2,*np.asarray(regions).flatten())
        blob+=struct.pack('<'+'f'*len(flags),*flags)+struct.pack('<6f',*SETTINGS)
    return base64.b64encode(blob).decode()

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--reaper',required=True,type=Path); ap.add_argument('--output',required=True,type=Path)
    args=ap.parse_args(); out=args.output.resolve(); effects=out/'profile/Effects'; effects.mkdir(parents=True,exist_ok=True)
    src=Path(__file__).resolve().parents[1]/'AB_ReaSampler.jsfx'; code=src.read_text()
    # These deterministic hooks temporarily call GUI-owned routines from @block.
    # Disable the idle GUI in these copies so there is exactly one test owner.
    driver_code=code.split('\n@gfx ')[0]+'\n@gfx 1100 720\n// GUI routines are owned by the deterministic test driver.\n'
    common=[str(args.reaper.resolve()),'-newinst','-nosplash','-ignoreerrors','-cfgfile',str(out/'profile/reaper.ini')]
    audio=[]; layers=[]; bounds=[[0,24000],[28000,52000],[56000,80000]]
    for i in range(4):
        x=(.005*(i+1)+.003*np.sin(np.arange(96000)*.008)).astype(np.float32)
        if i%2: x=np.column_stack((x,-x*.7))
        path=out/f'layer{i+1}.wav'; wavfile.write(path,48000,x); audio.append(x)
        layers.append(dict(path=path,frames=len(x),ch=1+i%2,rate=48000,regions=bounds,flags=[1,1,1]))
    results=[]
    def render(name,state_layers,params,events,expected,hook='',expected_tables=None,recall=False,sample_hook=''):
        plugin=name+'.jsfx'; (effects/plugin).write_text(driver_code.replace('// TEST_M4_BLOCK_HOOK',hook).replace('// TEST_M4_SAMPLE_HOOK',sample_hook))
        output=out/(name+'.wav'); rpp=out/(name+'.rpp'); saved=out/(name+'.saved.rpp'); lua=out/(name+'.lua')
        rpp.write_text(project(output,plugin,state6(state_layers),48000,params,events))
        lua.write_text(f'reaper.Main_openProject([[{rpp}]])\nreaper.Main_OnCommand(42230,0)\nreaper.Main_SaveProjectEx(0,[[{saved}]],0)\nreaper.Main_OnCommand(40004,0)\n')
        proc=subprocess.run(common+[str(lua)],capture_output=True,text=True,timeout=90)
        (out/(name+'.log')).write_text(proc.stdout+proc.stderr)
        assert proc.returncode==0 and saved.exists() and output.exists(),name
        metadata,_=read4(saved)
        if expected_tables:
            for i,(table,flags) in enumerate(expected_tables):
                assert metadata[i]['regions']==table and metadata[i]['flags']==flags,(name,i,metadata[i])
        with warnings.catch_warnings():
            warnings.simplefilter('ignore'); _,pcm=wavfile.read(output)
        err=float(np.max(np.abs(pcm.astype(float)/2**31-expected)))
        assert err<3e-6,(name,err)
        if recall:
            # Remove test driver from reopened plugin so saved applied edits alone
            # drive playback; compare against a fresh render of the saved state.
            (effects/plugin).write_text(code); output.unlink()
            proc=subprocess.run(common+['-renderproject',str(saved)],capture_output=True,text=True,timeout=90)
            assert proc.returncode==0 and output.exists(),name
            with warnings.catch_warnings():
                warnings.simplefilter('ignore'); _,reopened=wavfile.read(output)
            assert np.array_equal(pcm,reopened),(name,'recall PCM mismatch')
        results.append(dict(test=name,status='PASS',max_absolute_error=err,layers=metadata))
    def parameters(mode=2,attack=0,release=0,fixed=1,whole=0):
        return [-12,0,-1,2,0,-1]+[v for i in range(4) for v in (0,0,0,1,0,mode,12345+i*104729,whole,fixed,0,0,0)]+[v for i in range(4) for v in (attack,release)]

    for target in range(4):
        p=f'l{target+1}_'
        for action in ('trim','split','merge','exclude','discard','hold','clamp'):
            table=[r[:] for r in bounds]; flags=[1,1,1]
            ops={
                'trim':f'{p}edit_boundary(1,1000); {p}edit_boundary(2,12000);',
                'split':f'{p}edit_cursor=12000; {p}edit_split();',
                'merge':f'{p}edit_merge();',
                'exclude':f'{p}edit_toggle();',
                'discard':f'{p}edit_boundary(1,1000); {p}edit_discard();',
                'hold':f'{p}edit_boundary(1,1000);',
                'clamp':f'{p}edit_select(1); {p}edit_boundary(1,-999); {p}edit_boundary(2,999999);',
            }[action]
            if action=='trim': table[0]=[1000,12000]
            if action=='split': table=[[0,12000],[12000,24000]]+table[1:]; flags=[1]*4
            if action=='merge': table=[[0,52000],table[2]]; flags=[1,1]
            if action=='exclude': flags[0]=0
            if action=='clamp': table[1]=[24000,56000]
            apply=action not in ('hold','discard')
            cmd=f'{p}edit_apply(); loop(32, ({p}gui_loader.{p}status==1 || {p}gui_loader.{p}status==3) ? {p}gui_loader.{p}load_step(); {p}edit_service(););' if apply else ''
            hook=f'!master_test_done && play_state==1 && play_position>=.1 ? ({p}edit_begin(); {ops} {cmd} master_test_done=1;);'
            expected=np.zeros((96000,2)); tables=[]
            for i,x in enumerate(audio):
                expected+=expected_voice(x[:24000],48000,48000,0,gain_db=-12)
                selected=next(j for j,f in enumerate(flags) if f) if i==target and apply else 1
                tab=table if i==target else bounds
                expected+=expected_voice(x[tab[selected][0]:tab[selected][1]],48000,48000,19200,gain_db=-12)
                tables.append((tab,flags if i==target else [1,1,1]))
            render(f'layer{target+1}_{action}',layers,parameters(),[(0,0x90,60,127),(768,0x90,60,127)],expected,hook,tables)

    for mode in range(5):
        for flags in ([1,0,1],[0,0,1],[0,0,0]):
            states=[dict(l,flags=flags) for l in layers]; events=[(96+j*96,0x90,60,40) for j in range(20)]
            expected=np.zeros((96000,2)); enabled=[j for j,f in enumerate(flags) if f]
            for i,x in enumerate(audio):
                seq=Sequence(12345+i*104729,mode,len(enabled),fixed=0)
                for tick,*_ in events:
                    if not enabled or mode==4 and not flags[0]: continue
                    j=0 if mode==4 else enabled[seq.next()[0]]
                    expected+=expected_voice(x[bounds[j][0]:bounds[j][1]],48000,48000,tick*25,gain_db=-12,velocity=40)
            render(f'exclusions_mode{mode}_'+''.join(map(str,flags)),states,parameters(mode=mode),events,expected,
                   expected_tables=[(bounds,flags)]*4,recall=mode==1 and flags==[1,0,1])
    for attack,release in [(50,0),(0,100),(100,250),(2000,5000)]:
        expected=sum(expected_voice(x[:24000],48000,48000,4800,gain_db=-12,attack_ms=attack,release_ms=release) for x in audio)
        render(f'envelope_{attack}_{release}',layers,parameters(attack=attack,release=release),[(192,0x90,60,127)],expected,recall=True)
    # A parameter change after note-on must affect only subsequent voices.
    expected=np.zeros((96000,2))
    for x in audio:
        expected+=expected_voice(x[:24000],48000,48000,0,gain_db=-12,attack_ms=50,release_ms=100)
        expected+=expected_voice(x[28000:52000],48000,48000,19200,gain_db=-12,attack_ms=200,release_ms=300)
    hook='!master_test_done && play_state==1 && play_position>=.1 ? ('+''.join(f'slider{55+i*2}=200; slider{56+i*2}=300;' for i in range(4))+'master_test_done=1;);'
    render('envelope_captured_per_voice',layers,parameters(attack=50,release=100),[(0,0x90,60,127),(768,0x90,60,127)],expected,hook)
    # Region and flag edits loaded directly from an M6 state must recall exactly.
    states=[dict(l,regions=[[1000,12000],[12000,24000],[28000,52000]],flags=[1,0,1]) for l in layers]
    expected=sum(expected_voice(x[1000:12000],48000,48000,4800,gain_db=-12) for x in audio)
    render('edited_table_recall',states,parameters(),[(192,0x90,60,127)],expected,expected_tables=[(s['regions'],s['flags']) for s in states],recall=True)
    states=[dict(l,flags=[0,0,0]) for l in layers]
    expected=expected_voice(audio[3][:24000],48000,48000,4800,gain_db=-12,velocity=100)
    render('excluded_take_manual_audition',states,parameters(),[(192,0x90,60,127)],expected,
           sample_hook='master_test_frames==4800 ? l4_start_voice(100,1); master_test_frames+=1;')
    expected=sum(expected_voice(x,48000,48000,4800,gain_db=-12) for x in audio)
    render('whole_wav_bypasses_exclusions',states,parameters(whole=1),[(192,0x90,60,127)],expected)
    par=parameters(attack=50,release=100); expected=np.zeros((96000,2))
    for i,x in enumerate(audio):
        pitch=(-12,-3,5,12)[i]; par[6+i*12+2]=pitch
        expected+=expected_voice(x[:24000],48000,48000,4800,gain_db=-12,pitch=pitch,attack_ms=50,release_ms=100)
    render('envelopes_with_varispeed',layers,par,[(192,0x90,60,127)],expected)
    many=[[i*300,(i+1)*300] for i in range(256)]
    states=[dict(l,regions=many,flags=[1]*256) for l in layers]
    hook='''!master_test_done && play_state==1 && play_position>=.1 ? (
l4_edit_begin(); l4_edit_select(255); l4_edit_cursor=76650; l4_edit_split(); l4_edit_merge();
l4_edit_apply(); loop(32,l4_gui_loader.l4_status==1 ? l4_gui_loader.l4_load_step(); l4_edit_service(););
master_test_done=1;);'''
    expected=np.zeros((96000,2))
    for i,x in enumerate(audio):
        expected+=expected_voice(x[:300],48000,48000,0,gain_db=-12)
        expected+=expected_voice(x[:300] if i==3 else x[300:600],48000,48000,19200,gain_db=-12)
    render('split_limit_and_merge_last_are_safe',states,parameters(),[(0,0x90,60,127),(768,0x90,60,127)],expected,hook,[(many,[1]*256)]*4)
    hook=f'''!master_test_done && play_state==1 && play_position>=.1 ? (
l1_edit_begin(); l1_edit_boundary(1,1000);
test_spare.l1_mode=1; test_spare.l1_begin_load("{layers[0]['path']}",atomic_add(l1_latest_request,1),0,0,0);
l1_edit_apply(); master_test_done=1;);
'''
    expected=np.zeros((96000,2))
    for x in audio:
        expected+=expected_voice(x[:24000],48000,48000,0,gain_db=-12)
        expected+=expected_voice(x[28000:52000],48000,48000,19200,gain_db=-12)
    render('busy_edit_apply_preserves_applied_audio',layers,parameters(),[(0,0x90,60,127),(768,0x90,60,127)],expected,hook,[(bounds,[1,1,1])]*4,
        sample_hook='master_test_done && (l1_gui_loader.l1_status!=-4 || !l1_edit_active || l1_edit_pending) ? master_gain=1000;')
    report=dict(host='REAPER 7.79 Linux x86_64',source_sha256=hashlib.sha256(src.read_bytes()).hexdigest(),passed=len(results),results=results)
    (out/'edit-results.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=len(results),report=str(out/'edit-results.json')),indent=2))

if __name__=='__main__': main()
