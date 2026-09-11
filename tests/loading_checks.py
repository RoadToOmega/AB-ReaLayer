#!/usr/bin/env python3
"""Real @gfx callback benchmark and M9/M10 native-rate detection equivalence."""
import argparse,base64,hashlib,json,re,struct,subprocess,time,sys
from pathlib import Path
import numpy as np
from scipy.io import wavfile
from reference import project
from edit_checks import state6
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from layout import LIMITER_BASE

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--reaper',required=True,type=Path);ap.add_argument('--output',required=True,type=Path);ap.add_argument('--baseline',type=Path);ap.add_argument('--seconds',type=float,default=60);a=ap.parse_args()
 root=Path(__file__).resolve().parents[1];baseline=a.baseline or root/'tests/baseline-M9.jsfx'
 assert baseline.exists(),'Pass --baseline pointing to the original M9 JSFX for speed/equivalence comparison'
 out=a.output.resolve();out.mkdir(parents=True,exist_ok=True);wav=out/'large_96k_stereo.wav';rate=96000;n=int(a.seconds*rate);t=np.arange(n)/rate
 x=(.1*np.sin(t*2*np.pi*439)*((t%1.5)<.4)).astype(np.float32);wavfile.write(wav,rate,np.column_stack((x,-.6*x)))
 reports=[];stats={};snapshots={};base=LIMITER_BASE+20000;stride=3078;length=4*stride
 empty=[dict(path='',frames=0,ch=1,rate=48000,regions=[]) for _ in range(4)]
 params=[-4,0,-1,2,0,-1]+[v for i in range(4) for v in (0,0,0,1,0,0,12345+i*104729,0,1,0,0,0)]+[0]*16
 for version,src in [('M9',baseline),('M10',root/'VariationSampler-M11.jsfx')]:
  source=src.read_text()
  for count in [1,4]:
   name=f'{version}_{count}';work=out/name;effects=work/'profile/Effects';effects.mkdir(parents=True,exist_ok=True)
   extra='' if 'slider69:' in source else 'slider69:0<0,1,1>-Test padding\nslider70:0<0,1,1>-Test padding\n'
   code=source.replace('\n@init\n','\n'+extra+'slider71:0<0,1,1>-Benchmark complete\n@init\n')
   code=code.replace('@slider\n',f'master_write ? (file_var(0,bench_seconds);file_var(0,bench_callbacks);file_mem(0,{base},{length}););\n@slider\n')
   tail='\nbench_callbacks+=1;!bench_started ? (bench_started=1;bench_start=time_precise();'
   for i in range(1,count+1):tail+=f'l{i}_gui_loader.l{i}_mode=0;l{i}_gui_loader.l{i}_begin_load("{wav}",atomic_add(l{i}_latest_request,1),0,0,0);'
   tail+=');\n!bench_done && '+ ' && '.join(f'l{i}_gui_loader.l{i}_status==2' for i in range(1,count+1))+' ? (bench_done=1;bench_seconds=time_precise()-bench_start;'
   for i in range(1,count+1):
    at=base+(i-1)*stride
    tail+=f'''bench_m=l{i}_bank_meta+l{i}_gui_loader.l{i}_bank*l{i}_bank_stride;
memcpy({at},bench_m+1,3);({at})[3]=bench_m[7];({at})[4]=bench_m[8];({at})[5]=l{i}_gui_loader.l{i}_read_items;
memcpy({at+6},l{i}_region_base+l{i}_gui_loader.l{i}_bank*l{i}_region_stride,512);
memcpy({at+518},bench_m+32,512);
bench_i=0;loop(2048,({at+1030})[bench_i]=(l{i}_gui_loader.l{i}_base)[floor(bench_i*(bench_m[6]-1)/2047)];bench_i+=1;);
'''
   tail+='slider71=1;);\n';(effects/'probe.jsfx').write_text(code+tail)
   rpp=work/'probe.rpp';render=work/'render.wav';rpp.write_text(project(render,'probe.jsfx',state6(empty),48000,params,[]));saved=work/'saved.rpp';done=work/'done';done.unlink(missing_ok=True);saved.unlink(missing_ok=True)
   lua=work/'run.lua';lua.write_text(f'''reaper.Main_openProject([[{rpp}]])
reaper.Main_OnCommand(42230,0)
local tr=reaper.GetTrack(0,0)
function check()
 if reaper.TrackFX_GetParam(tr,0,70)>.5 then
 reaper.Main_SaveProjectEx(0,[[{saved}]],0)
 local f=io.open([[{done}]],'w');f:write('done');f:close()
 else reaper.defer(check) end
end
check()
''')
   with (work/'host.log').open('w') as log:
    proc=subprocess.Popen([str(a.reaper.resolve()),'-newinst','-nosplash','-ignoreerrors','-cfgfile',str(work/'profile/reaper.ini'),str(lua)],stdout=log,stderr=log)
    try:
     deadline=time.monotonic()+240
     while not done.exists() and proc.poll() is None and time.monotonic()<deadline:time.sleep(.1)
     assert done.exists(),(name,'GUI loader failed to complete')
    finally:
     proc.terminate()
     try:proc.wait(timeout=3)
     except subprocess.TimeoutExpired:proc.kill();proc.wait()
   raw=base64.b64decode(''.join(re.search(r'<JS_SER\s+([^>]+)>',saved.read_text())[1].split()));data=np.frombuffer(raw[-(length+2)*4:],dtype='<f4');seconds,callbacks=data[:2];snap=data[2:2+count*stride].copy()
   for i in range(count):assert snap[i*stride]==n and snap[i*stride+1]==2 and snap[i*stride+2]==rate and snap[i*stride+3]>0 and snap[i*stride+5]==n*2
   stats[name]=dict(seconds=float(seconds),callbacks=int(callbacks));snapshots[name]=snap
   print(name,stats[name],flush=True)
 for count in [1,4]:
  assert np.array_equal(snapshots[f'M9_{count}'],snapshots[f'M10_{count}']),(count,'PCM/peaks/region mismatch')
  ratio=stats[f'M9_{count}']['seconds']/stats[f'M10_{count}']['seconds'];assert ratio>1,(count,'No measured speedup')
  reports.append(dict(test=f'native_load_{count}_layers',status='PASS',duration_seconds=a.seconds,speedup=ratio,baseline=stats[f'M9_{count}'],updated=stats[f'M10_{count}']))
 (out/'loading-results.json').write_text(json.dumps(dict(source_sha256=hashlib.sha256((root/'VariationSampler-M11.jsfx').read_bytes()).hexdigest(),baseline_sha256=hashlib.sha256(baseline.read_bytes()).hexdigest(),passed=len(reports),results=reports),indent=2)+'\n');print('PASS',len(reports))
if __name__=='__main__':main()
