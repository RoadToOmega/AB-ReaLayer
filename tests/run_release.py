#!/usr/bin/env python3
"""Required release gate: GUI failures are failures, never waived by audio passes."""
import argparse,hashlib,json,subprocess,sys
from pathlib import Path
SUITES=('startup','gui','feature','macro','capacity','layer','lifecycle','hardening','edit','loading')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--reaper',required=True,type=Path);ap.add_argument('--output',required=True,type=Path);a=ap.parse_args()
    root=Path(__file__).resolve().parents[1];out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
    src=root/'AB_ReaSampler.jsfx';before=src.read_bytes()
    subprocess.run([sys.executable,str(root/'src/build.py')],check=True)
    assert before==src.read_bytes(),'Distributed JSFX differs from the deterministic source build'
    digest=hashlib.sha256(before).hexdigest();reports=[]
    for name in SUITES:
        work=out/name
        with (out/(name+'.log')).open('w') as log:
            subprocess.run([sys.executable,str(root/'tests'/(name+'_checks.py')),'--reaper',str(a.reaper.resolve()),'--output',str(work)],stdout=log,stderr=subprocess.STDOUT,check=True)
        result=json.loads((work/(name+'-results.json')).read_text())
        assert result['source_sha256']==digest,name
        assert all(x['status']=='PASS' for x in result['results']),name
        reports.append({'suite':name,'passed':result['passed']});print(name,result['passed'],'PASS',flush=True)
    assert hashlib.sha256(src.read_bytes()).hexdigest()==digest,'Source changed during verification'
    final={'source_sha256':digest,'passed':sum(x['passed'] for x in reports),'suites':reports}
    (out/'release-results.json').write_text(json.dumps(final,indent=2)+'\n')
if __name__=='__main__':main()
