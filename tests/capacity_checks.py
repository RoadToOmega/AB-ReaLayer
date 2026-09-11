#!/usr/bin/env python3
"""Load exact-limit and one-frame-oversized 96 kHz files through all four real banks."""
import argparse,base64,hashlib,json,re,struct,subprocess,sys
from pathlib import Path
from reference import project
from edit_checks import state6
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from layout import BANK_CAPACITY,STRIDE,MAXMEM

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--reaper',required=True,type=Path);ap.add_argument('--output',required=True,type=Path);a=ap.parse_args()
 root=Path(__file__).resolve().parents[1];src=root/'AB_ReaSampler.jsfx';source=src.read_text();out=a.output.resolve();effects=out/'profile/Effects';effects.mkdir(parents=True,exist_ok=True);results=[]
 assert MAXMEM<128000000
 for ch in (1,2):
  for over in (0,1):
   name=f'channels{ch}_'+('over_limit' if over else 'exact_limit');frames=BANK_CAPACITY//ch+over;data=frames*ch*4;wav=out/(name+'.wav')
   with wav.open('wb') as f:
    f.write(b'RIFF'+struct.pack('<I',36+data)+b'WAVEfmt '+struct.pack('<IHHIIHH',16,3,ch,96000,96000*ch*4,ch*4,32)+b'data'+struct.pack('<I',data));f.write(struct.pack('<f',.125)*ch);f.seek(44+data-4);f.write(struct.pack('<f',-.25))
   layers=[dict(path=wav,frames=frames,ch=ch,rate=96000,regions=[[0,frames]]) for _ in range(4)]
   fields=[]
   for i in range(1,5):
    p=f'l{i}_';fields+=['file_var(0,'+p+'restore_failed);','file_var(0,'+p+'restore_loader.'+p+'status);','file_var(0,'+p+'active_token);',f'test_p={p}pcm_base+{p}token_bank({p}active_token)*{p}bank_capacity;test_last=test_p[{BANK_CAPACITY-1}];file_var(0,test_last);']
   code=source.replace('@slider\n','master_write ? ('+''.join(fields)+');\n@slider\n');plugin=name+'.jsfx';(effects/plugin).write_text(code)
   render=out/(name+'-render.wav');render.unlink(missing_ok=True);rpp=out/(name+'.rpp');saved=out/(name+'.saved.rpp');rpp.write_text(project(render,plugin,state6(layers),96000,[-4,0,-1,2,0,-1]+[v for i in range(4) for v in (0,0,0,1,0,4,12345+i*104729,0,1,0,0,0)]+[0]*14,[]))
   lua=out/(name+'.lua');lua.write_text(f'reaper.Main_openProject([[{rpp}]])\nreaper.Main_OnCommand(42230,0)\nreaper.Main_SaveProjectEx(0,[[{saved}]],0)\nreaper.Main_OnCommand(40004,0)\n')
   p=subprocess.run([str(a.reaper.resolve()),'-newinst','-nosplash','-ignoreerrors','-cfgfile',str(out/'profile/reaper.ini'),str(lua)],capture_output=True,text=True,timeout=150);(out/(name+'.log')).write_text(p.stdout+p.stderr);assert p.returncode==0 and saved.exists(),name
   raw=base64.b64decode(''.join(re.search(r'<JS_SER\s+([^>]+)>',saved.read_text())[1].split()));v=struct.unpack('<16f',raw[-64:])
   for i in range(4):
    failed,status,token,last=v[i*4:i*4+4]
    if over:assert failed==1 and status==-3 and token==0,(name,i,v)
    else:assert failed==0 and token>0 and last==-.25,(name,i,v)
   results.append(dict(test=name,status='PASS',channels=ch,frames=frames,layers_checked=4));print(name,'PASS',flush=True)
 (out/'capacity-results.json').write_text(json.dumps(dict(source_sha256=hashlib.sha256(src.read_bytes()).hexdigest(),passed=len(results),results=results),indent=2)+'\n')
if __name__=='__main__':main()
