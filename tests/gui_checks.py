#!/usr/bin/env python3
"""Run the compiled JSFX @gfx in REAPER on an offscreen LICE surface.

Only test copies override pointer/keyboard input and framebuffer destination.
Production drawing, widgets, parameter setters and editor code are executed.
This is not an operating-system mouse/Retina test.
"""
import argparse,base64,hashlib,json,re,struct,subprocess,time
from pathlib import Path
import numpy as np
from PIL import Image
from scipy.io import wavfile
from edit_checks import state6
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from layout import TEST_GFX_BASE
from ui_layout import WIDTH,HEIGHT,OPEN_WIDTH,OPEN_HEIGHT,RECTS,WORK_DY,card_rect,card_fields

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--reaper',required=True,type=Path);ap.add_argument('--output',required=True,type=Path);ap.add_argument("--case");args=ap.parse_args()
    root=Path(__file__).resolve().parents[1];out=args.output.resolve();effects=out/'profile/Effects';effects.mkdir(parents=True,exist_ok=True)
    source=(root/'AB_ReaSampler.jsfx').read_text();report=[]
    # Contract and cross-thread ownership guard, including the M7 right-click regression.
    headers=re.findall(r'^slider\d+:[^\n]+',source,re.M)
    contract=json.loads((root/'src/parameter-contract.json').read_text())
    assert [re.sub(r'>-', '>', x, count=1) for x in headers[:62]]==[x.replace("slider1:-12<","slider1:-4<") for x in contract]
    assert all(re.search(r'>-',x) for x in headers) and 'slider_show(' not in source
    audio=source.split('\n@block\n')[1].split('\n@gfx ')[0];gfx=source.split('\n@gfx ')[1]
    writes=lambda s:set(re.findall(r'\b(master_\w+)\s*[+*/-]?=(?!=)',s))
    assert not writes(audio)&writes(gfx),(writes(audio)&writes(gfx))
    report.append({'test':'parameter_contract_and_thread_ownership','status':'PASS','parameters':len(headers)})
    rng=np.random.default_rng(7);x=np.zeros(230400,np.float32);bounds=[]
    for j in range(6):
        start=int((.1+j*.8)*48000);n=16800;t=np.arange(n)/48000
        x[start:start+n]=(.5*np.sin(t*(410+j*54)*2*np.pi)+rng.normal(0,.15,n))*np.exp(-t*17)*np.minimum(1,t/.002)
        bounds.append([start,start+n])
    wav=out/'Stone_steps_variations.wav';wavfile.write(wav,48000,x)
    layers=[dict(path=wav,frames=len(x),ch=1,rate=48000,regions=bounds,flags=[1]*6) for i in range(4)]
    params=[-4,0,-1,2,0,-1]+[v for i in range(4) for v in (0,0,0,1,0,0,12345+i*104729,0,1,0,0,0)]+[0]*8
    def center(rect):
        x,y,w,h=rect;return x+w/2,y+h/2
    def click(name,cap=1):
        x,y=center(RECTS[name]);return f'master_probe_cap={cap};master_probe_x={x};master_probe_y={y};'
    checks=[]
    actions={2:'master_probe_cap=1;master_probe_x=928;master_probe_y=412;',3:'master_probe_cap=1;master_probe_x=928;master_probe_y=367;',
             5:'master_probe_cap=1;master_probe_x=420;master_probe_y=155;',
             7:'master_probe_cap=2;master_probe_x=1040;master_probe_y=412;',8:'master_probe_char=55;',9:'master_probe_char=46;',10:'master_probe_char=53;',11:'master_probe_char=13;',
             13:'master_probe_cap=2;master_probe_x=952;master_probe_y=576;',14:'master_probe_char=55;',15:'master_probe_char=53;',16:'master_probe_char=48;',17:'master_probe_char=13;',
             19:'master_probe_cap=1;master_probe_x=1040;master_probe_y=412;',21:'master_probe_cap=1;master_probe_x=1040;master_probe_y=412;',
             23:'master_probe_cap=1;master_probe_x=928;master_probe_y=412;',24:'master_probe_cap=9;master_probe_x=928;master_probe_y=367;',
             27:'master_probe_cap=2;master_probe_x=928;master_probe_y=412;',28:'master_probe_char=45;',29:'master_probe_char=13;',30:'master_probe_char=27;',
             32:'master_probe_cap=2;master_probe_x=928;master_probe_y=412;',33:'master_probe_char=57;',34:'master_probe_char=57;',35:'master_probe_char=13;'}
    for frame,expr in [(4,'abs(slider16-3)<.001 && slider28==0'),(6,'master_selected==1'),(12,'abs(slider29-7.5)<.001 && slider17==0'),(18,'slider57==750 && slider55==0'),(22,'slider29==0'),(25,'abs(slider28-.3)<.001'),(29,'master_focus==28 && strlen(#master_input_error)>0'),(31,'master_focus==0 && abs(slider28-.3)<.001'),(36,'slider28==12 && master_focus==0')]:
        checks.append(f'master_probe_frame=={frame} ? (master_probe_checks+=1; !({expr}) ? master_probe_failed+={frame};);')
    for name,w,h in [('play',OPEN_WIDTH,OPEN_HEIGHT),('edit',OPEN_WIDTH,OPEN_HEIGHT),('detect',OPEN_WIDTH,OPEN_HEIGHT),('settings',OPEN_WIDTH,OPEN_HEIGHT),('numeric',OPEN_WIDTH,OPEN_HEIGHT),('small',1100,720),('compact',880,576),('large',1860,1200),('interactions',OPEN_WIDTH,OPEN_HEIGHT),('edit_actions',OPEN_WIDTH,OPEN_HEIGHT),('m9_controls',OPEN_WIDTH,OPEN_HEIGHT),('m10_controls',OPEN_WIDTH,OPEN_HEIGHT),('chaos',OPEN_WIDTH,OPEN_HEIGHT),('reset_sound',OPEN_WIDTH,OPEN_HEIGHT),('path_tooltip',OPEN_WIDTH,OPEN_HEIGHT)]:
        if args.case and name!=args.case:continue
        n=w*h;capture=38 if name in ('interactions','edit_actions','m9_controls') else 8
        setup=''
        if name in ('edit','detect','settings'):
            setup='master_probe_frame==2 ? ('+click(name.upper())+');'
        if name=='edit':setup+='master_probe_frame==4 ? (master_probe_cap=1;master_probe_x=100;master_probe_y=520;);'
        if name=='m9_controls':
            setup='master_probe_frame==2 ? (master_probe_cap=2;master_probe_x=1175;master_probe_y=215;);'
            setup+='master_probe_frame==3 ? master_probe_char=49;master_probe_frame==4 ? master_probe_char=48;master_probe_frame==5 ? master_probe_char=48;master_probe_frame==6 ? master_probe_char=13;'
            setup+='master_probe_frame==8 ? (master_probe_cap=1;master_probe_x=784;master_probe_y=34;);'
            setup+='master_probe_frame==10 || master_probe_frame==12 ? (master_probe_cap=1;master_probe_x=1145;master_probe_y=104;);'
            setup+='master_probe_frame==14 || master_probe_frame==16 ? (master_probe_cap=1;master_probe_x=630;master_probe_y=36;);'
        if name=='m10_controls':setup='master_probe_frame==2 ? (master_probe_cap=1;master_probe_x=100;master_probe_y=104;);master_probe_frame==4 ? (master_probe_cap=1;master_probe_x=425;master_probe_y=104;);master_probe_frame==6 ? (master_probe_cap=1;master_probe_x=1118;master_probe_y=772;);'
        if name=='reset_sound':setup='master_probe_frame==2 ? ('+click('RANDOM')+');master_probe_frame==4 ? ('+click('RESET_SOUND')+');master_probe_frame==6 ? ('+click('PLAY_SAMPLER')+');'
        if name=='path_tooltip':setup='master_probe_x=120;master_probe_y=174;'
        if name=='numeric':setup='master_probe_frame==2 ? (master_probe_cap=2;master_probe_x=630;master_probe_y=36;);'
        if name=='interactions':setup='\n'.join(f'master_probe_frame=={f} ? ({s});' for f,s in actions.items())
        if name=='edit_actions':
            setup='master_probe_frame==2 ? (master_probe_cap=1;master_probe_x=200;master_probe_y=300;);master_probe_frame==4 ? (master_probe_cap=1;master_probe_x=100;master_probe_y=520;);'
            setup+='master_probe_frame==6 ? (master_probe_cap=1;master_probe_x=100;master_probe_y=630;);'
            setup+='master_probe_frame==8 ? (master_probe_cap=1;master_probe_x=220;master_probe_y=630;);'
            setup+='master_probe_frame==10 ? (master_probe_cap=1;master_probe_x=375;master_probe_y=630;);'
            setup+='master_probe_frame==12 ? (master_probe_cap=1;master_probe_x=520;master_probe_y=630;);'
        code=source.replace('@slider\n',f'master_write ? (file_var(0,master_probe_checks);file_var(0,master_probe_failed);file_var(0,master_probe_done);master_probe_done ? file_mem(0,{TEST_GFX_BASE},{n}););\n@slider\n')
        prefix=f'''function master_probe_key() local(c) (c=master_probe_char;master_probe_char=0;c;);
master_probe_frame+=1;master_probe_char=0;master_probe_cap=0;master_probe_x=-100;master_probe_y=-100;
{setup}
gfx_w={w};gfx_h={h};mouse_x=({w}-{WIDTH}*min({w}/{WIDTH},{h}/{HEIGHT}))/2+master_probe_x*min({w}/{WIDTH},{h}/{HEIGHT});mouse_y=({h}-{HEIGHT}*min({w}/{WIDTH},{h}/{HEIGHT}))/2+master_probe_y*min({w}/{WIDTH},{h}/{HEIGHT});mouse_cap=master_probe_cap;
master_probe_frame==1 ? gfx_setimgdim(100,{w},{h});
'''
        # Prefix after all functions, before the frame loop.
        code=code.replace('master_visible=!(gfx_ext_flags&2);',prefix+'master_visible=1;')
        code=code.replace('gfx_getchar();','master_probe_key();').replace('gfx_dest=-1;','gfx_dest=100;')
        code=code.replace('time_precise()','(master_probe_frame*.03)')
        tail='\n'+('\n'.join(checks) if name=='interactions' else '')
        if name=='m9_controls':
            for frame,expr in [(7,'slider68==100'),(9,'slider64==1'),(11,'master_clear_until>master_probe_frame*.03 && atomic_get(master_clear_request)==0'),(13,'master_clear_until==0 && l1_gui_loader.l1_status==0 && l4_gui_loader.l4_status==0'),(18,'slider1==-4')]:
                tail+=f'master_probe_frame=={frame} ? (master_probe_checks+=1; !({expr}) ? master_probe_failed+={frame};);'
        if name=='edit_actions':
            for frame,expr in [(7,'l1_edit_count==7'),(9,'l1_edit_count==6'),(11,'l1_edit_flags[0]==0')]:
                tail+=f'master_probe_frame=={frame} ? (master_probe_checks+=1; !({expr}) ? master_probe_failed+={frame};);'
        tail+=f''' \nmaster_probe_frame=={capture} ? (
  test_y=0;loop({h},test_x=0;loop({w},gfx_x=test_x;gfx_y=test_y;gfx_getpixel(test_r,test_g,test_b);
    ({TEST_GFX_BASE})[test_y*{w}+test_x]=floor(test_r*255+.5)*65536+floor(test_g*255+.5)*256+floor(test_b*255+.5);test_x+=1;);test_y+=1;);
  master_probe_done=1;slider71=1;
);'''
        code=code.replace('\n@init\n','\nslider71:0<0,1,1>-Test capture complete\n@init\n')+tail
        (effects/(name+'.jsfx')).write_text(code)
        # Rendering first activates restored banks; the deferred callback waits for @gfx capture.
        render=out/(name+'.wav');render.unlink(missing_ok=True)
        from reference import project
        fixture_params=params.copy()
        if name=='m9_controls':fixture_params[0]=-12
        if name=='chaos':
            fixture_params+=[0,1]+[100,0,100,0]+[1,1357911]
            for i in range(4):
                b=6+i*12;fixture_params[b]=6;fixture_params[b+1]=[-.8,.5,-.3,.9][i];fixture_params[b+2]=[-24,24,24,-24][i];fixture_params[b+9:b+12]=[12,12,1]
        rpp=out/(name+'.rpp');rpp.write_text(project(render,name+'.jsfx',state6(layers),48000,fixture_params,[]))
        saved=out/(name+'.saved.rpp');saved.unlink(missing_ok=True);ready=out/(name+'.done');ready.unlink(missing_ok=True)
        after_capture=f'os.remove([[{render}]])\nreaper.Main_OnCommand(42230,0)\n' if name in ('edit_actions','m9_controls','m10_controls','reset_sound') else ''
        lua=out/(name+'.lua');lua.write_text(f'''reaper.Main_openProject([[{rpp}]])
reaper.Main_OnCommand(42230,0)
local tr=reaper.GetTrack(0,0)
function finish()
 if reaper.TrackFX_GetParam(tr,0,70)<0.5 then reaper.defer(finish) else
 {after_capture}
 reaper.Main_SaveProjectEx(0,[[{saved}]],0)
 local f=io.open([[{ready}]],"w");f:write("done");f:close()
 end
end
finish()
''')
        log=open(out/(name+'.log'),'w');p=subprocess.Popen([str(args.reaper.resolve()),'-newinst','-nosplash','-ignoreerrors','-cfgfile',str(out/'profile/reaper.ini'),str(lua)],stdout=log,stderr=log)
        deadline=time.monotonic()+35
        while not ready.exists() and time.monotonic()<deadline and p.poll() is None:time.sleep(.1)
        p.terminate()
        try:p.wait(timeout=3)
        except subprocess.TimeoutExpired:p.kill();p.wait()
        log.close();assert ready.exists(),(name,'GUI capture did not finish')
        raw=base64.b64decode(''.join(re.search(r'<JS_SER\s+([^>]+)>',saved.read_text())[1].split()))
        count,failed,done=struct.unpack('<3f',raw[-n*4-12:-n*4]);assert done==1 and failed==0,(name,count,failed,done)
        if name=='interactions':assert count==len(checks),(count,len(checks))
        if name=='m10_controls':
            host_fields=re.search(r'<JS [^\n]+\n([^\n]+)',saved.read_text())[1].split();host_fields.pop(64);host_params=[float(x) for x in host_fields]
            assert host_params[68]==1 and host_params[63]==1 and host_params[6]==6,host_params
        if name=='reset_sound':
            from parameters import SOUND_DEFAULTS
            host_fields=re.search(r'<JS [^\n]+\n([^\n]+)',saved.read_text())[1].split();host_fields.pop(64);host_params=[float(x) for x in host_fields]
            assert all(host_params[p-1]==default for p,default in SOUND_DEFAULTS.items()),host_params
            assert host_params[0]==-4 and host_params[68]==0
        if name=='edit_actions':
            from lifecycle_checks import read4
            actual,_=read4(saved)
            assert count==3 and actual[0]['flags']==[0,1,1,1,1,1] and actual[0]['regions']==bounds,(count,actual[0])
        if name=='m9_controls':
            from lifecycle_checks import read4
            actual,_=read4(saved);assert count==5 and all(x['path']=='' for x in actual)
        values=np.frombuffer(raw[-n*4:],dtype='<f4').astype(np.uint32).reshape(h,w)
        assert len(np.unique(values))>100,name
        rgb=np.stack([(values>>16)&255,(values>>8)&255,values&255],axis=-1).astype('uint8')
        Image.fromarray(rgb).save(out/(name+'.png'))
        report.append({'test':name,'status':'PASS','dimensions':[w,h],'interaction_assertions':int(count),'image':name+'.png'})
        print(name,'PASS',flush=True)
    (out/'gui-results.json').write_text(json.dumps({'host':'REAPER 7.79 Linux, offscreen JSFX graphics','source_sha256':hashlib.sha256(source.encode()).hexdigest(),'passed':len(report),'results':report},indent=2)+'\n')
if __name__=='__main__':main()
