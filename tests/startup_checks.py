#!/usr/bin/env python3
"""Real @gfx startup heartbeat, with the reported 0.8.0 bug as negative control."""
import argparse,hashlib,json,subprocess,time,sys
from pathlib import Path
from reference import project
from edit_checks import state6

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--reaper',required=True,type=Path);ap.add_argument('--output',required=True,type=Path);a=ap.parse_args()
    root=Path(__file__).resolve().parents[1];out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
    source=(root/'AB_ReaSampler.jsfx').read_text();report=[]
    sys.path.insert(0,str(root/'src'));from eel_syntax import validate_literals
    validate_literals(source)
    broken=source+'\nstartup_invalid=1e10;\n'
    assert broken!=source
    try:validate_literals(broken)
    except ValueError:pass
    else:raise AssertionError('Build preflight accepted the regression')
    params=[-12,0,-1,2,0,-1]+[v for i in range(4) for v in (0,0,0,1,0,0,12345+i*104729,0,1,0,0,0)]+[0]*8+[0]*7
    empty=[dict(path='',frames=0,ch=1,rate=48000,regions=[]) for _ in range(4)]
    for name,code,expected in [('broken_negative_control',broken,0),('fixed_startup',source,1)]:
        work=out/name;effects=work/'profile/Effects';effects.mkdir(parents=True,exist_ok=True)
        # Retain every production section, including the complete @gfx. Only append a heartbeat.
        code=code.replace('\n@init\n','\nslider71:0<0,1,1>-Test GUI heartbeat\n@init\n')+'\nslider71=1;\n'
        (effects/'probe.jsfx').write_text(code);done=work/'done.txt';done.unlink(missing_ok=True)
        render=work/'render.wav';render.unlink(missing_ok=True);rpp=work/'probe.rpp';rpp.write_text(project(render,'probe.jsfx',state6(empty),48000,params,[]))
        lua=work/'run.lua';lua.write_text(f'''reaper.Main_openProject([[{rpp}]])
reaper.Main_OnCommand(42230,0)
local start=reaper.time_precise()
local tr=reaper.GetTrack(0,0)
function check()
 local value=reaper.TrackFX_GetParam(tr,0,70)
 if value>0.5 or reaper.time_precise()-start>2 then
  local f=io.open([[{done}]],'w');f:write(tostring(value));f:close()
 else reaper.defer(check) end
end
check()
''')
        with open(work/'host.log','w') as log:
            proc=subprocess.Popen([str(a.reaper.resolve()),'-newinst','-nosplash','-ignoreerrors','-cfgfile',str(work/'profile/reaper.ini'),str(lua)],stdout=log,stderr=log)
            try:
                deadline=time.monotonic()+12
                while not done.exists() and time.monotonic()<deadline and proc.poll() is None:time.sleep(.05)
                assert done.exists(),(name,'Host did not complete startup probe; this is a failure, not a waived gate')
                actual=float(done.read_text());assert actual==expected,(name,actual,expected)
            finally:
                proc.terminate()
                try:proc.wait(timeout=3)
                except subprocess.TimeoutExpired:proc.kill();proc.wait()
        report.append(dict(test=name,status='PASS',gui_heartbeat=actual));print(name,'PASS',flush=True)
    (out/'startup-results.json').write_text(json.dumps(dict(source_sha256=hashlib.sha256(source.encode()).hexdigest(),passed=len(report),results=report),indent=2)+'\n')
if __name__=='__main__':main()
