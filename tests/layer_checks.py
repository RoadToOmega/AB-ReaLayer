#!/usr/bin/env python3
"""Four-layer integration checks against real REAPER offline audio."""
import argparse, base64, hashlib, json, struct, subprocess, warnings
from pathlib import Path
import numpy as np
from scipy.io import wavfile
from reference import project, expected_voice, state2, SETTINGS, Sequence

def state4(layers):
    blob=struct.pack('<ff',73104,4)
    for layer in layers:
        raw=bytearray(base64.b64decode(state2(layer['path'],layer['frames'],layer['ch'],layer['rate'],layer['regions'])))
        struct.pack_into('<f',raw,4,3)
        blob+=raw+struct.pack('<6f',*layer.get('settings',SETTINGS))
    return base64.b64encode(blob).decode()

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--reaper',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True); ap.add_argument('--smoke',action='store_true')
    args=ap.parse_args(); out=args.output.resolve(); effects=out/'profile/Effects'
    effects.mkdir(parents=True,exist_ok=True)
    src=Path(__file__).resolve().parents[1]/'AB_ReaSampler.jsfx'
    code=src.read_text(); (effects/src.name).write_text(code)
    common=[str(args.reaper.resolve()),'-newinst','-nosplash','-ignoreerrors','-cfgfile',str(out/'profile/reaper.ini')]
    results=[]

    def run(name,configs=None,events=None,cc=-1,channel=0,note=-1,master=0,recall=False,hook='',expected_override=None,detect=False):
        configs=configs or [{} for _ in range(4)]
        layers=[]; clips=[]; seqs=[]; lp=[]; live=[[] for _ in range(4)]
        for i,c in enumerate(configs):
            n=c.get('count',5); rate=c.get('rate',48000); ch=c.get('ch',1)
            duration=c.get('duration',.015)
            cs=[np.full(round(rate*duration),.002*(r+1)*(i+1),np.float32) for r in range(n)]
            if ch==2: cs=[np.column_stack((x,-x*.6)) for x in cs]
            x=np.concatenate(cs) if cs else np.zeros(480,np.float32)
            path=out/(name+f'-layer{i+1}.wav'); wavfile.write(path,rate,x)
            path='' if c.get('empty') else str(path)
            if c.get('missing'): path=str(out/'missing-source.wav')
            bounds=[] if c.get('empty') else [(r*len(cs[0]),(r+1)*len(cs[0])) for r in range(n)]
            layers.append(dict(path=path,frames=0 if c.get('empty') else len(x),ch=ch,rate=rate,regions=bounds,settings=c.get('settings',SETTINGS)))
            clips.append(cs)
            seed=c.get('seed',12345+i*104729); mode=c.get('mode',0)
            seqs.append(Sequence(seed,mode,n,fixed=c.get('fixed',1)-1))
            lp.extend([c.get('volume',0),c.get('pan',0),c.get('pitch',0),c.get('enabled',1),c.get('solo',0),mode,seed,
                       c.get('whole',0),c.get('fixed',1),*c.get('amounts',(0,0,0))])
        params=[int(v) if isinstance(v,bool) else v for v in [master,channel,note,2,0,cc]+lp]
        if events is None: events=[(96+j*96,0x90,60,127) for j in range(24)]
        expected=np.zeros((96000,2)); picks=[[] for _ in range(4)]; rejected=0
        anysolo=any(c.get('solo',0) for c in configs)
        for tick,status,key,velocity in sorted(events,key=lambda e:(e[0],0 if e[1]&240==176 else 1)):
            if channel and (status&15)+1!=channel: continue
            if status&240==176:
                if key==cc and velocity>=64:
                    for s in seqs: s.reset()
                continue
            if status&240!=144 or velocity==0 or (note>=0 and key!=note): continue
            onset=tick*25
            participants=[i for i,c in enumerate(configs) if c.get('enabled',1) and (not anysolo or c.get('solo',0)) and not c.get('empty') and not c.get('missing') and (clips[i] or c.get('whole'))]
            for i in range(4): live[i]=[end for end in live[i] if end>onset]
            if any(len(live[i])>=16 for i in participants): rejected+=1; continue
            for i in participants:
                c=configs[i]; seq=seqs[i]
                if c.get('whole'):
                    clip=np.concatenate(clips[i]) if clips[i] else np.zeros(480,np.float32)
                    draws=[seq.v.draw()*2-1 for _ in range(3)]; r=-1
                else:
                    r,draws=seq.next(); clip=clips[i][r]
                picks[i].append(r+1)
                dp,dg,db=[a*b for a,b in zip(c.get('amounts',(0,0,0)),draws)]
                pitch=c.get('pitch',0)+dp
                expected+=expected_voice(clip,layers[i]['rate'],48000,onset,pitch=pitch,
                    gain_db=master+c.get('volume',0)+dg,pan=max(-1,min(1,c.get('pan',0)+db)),velocity=velocity)
                live[i].append(onset+int(np.ceil(len(clip)/(layers[i]['rate']/48000*2**(pitch/12)))))
        if expected_override is not None: expected=expected_override(expected,clips)
        plugin=src.name
        if hook or detect:
            plugin=name+'.jsfx'
            variant=code.replace('// TEST_M4_SAMPLE_HOOK',hook)
            if detect:
                for i in range(1,5): variant=variant.replace(f'l{i}_restore_loader.l{i}_mode=2;',f'l{i}_restore_loader.l{i}_mode=0;')
            (effects/plugin).write_text(variant)
        output=out/(name+'.wav'); rpp=out/(name+'.rpp')
        rpp.write_text(project(output,plugin,state4(layers),48000,params,events))
        p=subprocess.run(common+['-renderproject',str(rpp)],capture_output=True,text=True,timeout=90)
        (out/(name+'.log')).write_text(p.stdout+p.stderr)
        assert p.returncode==0 and output.exists(),(name,p.stdout,p.stderr)
        with warnings.catch_warnings():
            warnings.simplefilter('ignore'); rate,pcm=wavfile.read(output)
        assert rate==48000 and pcm.shape==(96000,2),name
        actual=pcm.astype(float)/2**31; error=float(np.max(np.abs(actual-expected)))
        assert error<3e-6,(name,error,float(np.max(np.abs(actual))))
        if recall:
            saved=out/(name+'.saved.rpp'); lua=out/(name+'.lua'); output.unlink()
            lua.write_text(f'reaper.Main_openProject([[{rpp}]])\nreaper.Main_OnCommand(42230,0)\nreaper.Main_SaveProjectEx(0,[[{saved}]],0)\nreaper.Main_OnCommand(40004,0)\n')
            p=subprocess.run(common+[str(lua)],capture_output=True,text=True,timeout=90)
            assert p.returncode==0 and saved.exists(),name
            output.unlink()
            p=subprocess.run(common+['-renderproject',str(saved)],capture_output=True,text=True,timeout=90)
            assert p.returncode==0 and output.exists(),name
            with warnings.catch_warnings():
                warnings.simplefilter('ignore'); _,reopened=wavfile.read(output)
            assert np.array_equal(pcm,reopened),(name,'recall changed audio')
        results.append(dict(test=name,status='PASS',max_absolute_error=error,regions=picks,rejected_notes=rejected))
        return actual

    run('four_layers_default')
    if not args.smoke:
        for i in range(4):
            run('only_layer_'+str(i+1),configs=[{} if j==i else {'empty':True} for j in range(4)])
        run('four_independent_modes',configs=[{'mode':i,'seed':887+i*31} for i in range(4)])
        run('four_fixed_regions',configs=[{'mode':4,'fixed':i+1} for i in range(4)])
        run('layer_mix_controls',configs=[{'volume':-i*3,'pan':(-1,-.4,.4,1)[i],'pitch':(-12,-3,5,12)[i],'ch':1+i%2,'rate':(22050,44100,48000,96000)[i]} for i in range(4)])
        run('independent_modulation',configs=[{'amounts':(3+i,2+i,.2*i),'ch':1+i%2,'pan':.4,'seed':16777215-i} for i in range(4)])
        run('master_gain',master=-12)
        run('mute_two_layers',configs=[{'enabled':i%2} for i in range(4)])
        run('single_solo',configs=[{'solo':i==2} for i in range(4)])
        run('multiple_solo',configs=[{'solo':i%2} for i in range(4)])
        run('muted_solo_is_silent',configs=[{'enabled':0,'solo':1},{},{},{}])
        run('missing_layer_does_not_block_others',configs=[{}, {'missing':True},{},{}])
        run('different_counts',configs=[{'count':n} for n in (1,2,7,256)],master=-18)
        run('empty_detection',configs=[{'count':0},{},{'count':0},{}])
        run('mixed_whole_and_variations',configs=[{'whole':i%2} for i in range(4)])
        notes=[(96+i*96,0x90,60,127) for i in range(20)]
        run('reset_all_cc',cc=20,events=notes+[(1000,0xb0,20,127)])
        run('reset_cc_wrong_channel',cc=20,channel=1,events=notes+[(1000,0xb1,20,127)])
        run('note_channel_filters',channel=1,note=60,events=notes+[(70,0x91,60,127),(80,0x90,61,127),(90,0x90,60,0)])
        run('group_reject_at_64_voices',events=[(96,0x90,60,127)]*17+[(288,0x90,60,127)],master=-12)
        run('one_full_layer_rejects_entire_group',configs=[{'duration':.5},{},{},{}],
            events=[(96,0x90,60,127)]*16+[(192,0x90,60,127),(1200,0x90,60,127)],master=-12)
        run('four_layer_recall',configs=[{'mode':i,'amounts':(3,4,.7),'fixed':i+1} for i in range(4)],recall=True)
        # Exact sample driver uses the same audio audition method as the GUI.
        run('layer_four_audition_isolated',hook='test_samples==1200 ? l4_start_voice(100,1); test_samples+=1;',
            expected_override=lambda e,c:e+expected_voice(c[3][0],48000,48000,1200,velocity=100))
        run('four_empty_layers',configs=[{'empty':True} for _ in range(4)],recall=True)
    report=dict(host='REAPER 7.79 Linux x86_64',source_sha256=hashlib.sha256(src.read_bytes()).hexdigest(),passed=len(results),results=results)
    (out/'layer-results.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=len(results),report=str(out/'layer-results.json')),indent=2))

if __name__=='__main__': main()
