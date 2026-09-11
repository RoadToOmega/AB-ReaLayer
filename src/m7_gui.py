"""M7-derived presentation generator, extended with M9/M10 controls."""
from pathlib import Path
from layout import STRIDE
ROOT=Path(__file__).resolve().parent
from parameters import PARAMS
from ui_layout import expand, WIDTH, HEIGHT

def build(ns,gui):
    registry=['function master_notify(p,finish) (']
    for p in range(1,71): registry.append(f'p=={p} ? slider_automate(slider{p},finish);')
    registry.append(');\nfunction master_spec(p) (')
    for p,(lo,hi,step,default,unit) in PARAMS.items():
        registry.append(f'p=={p} ? (master_lo={lo};master_hi={hi};master_step={step};master_default={default};#master_unit="{unit}";);')
    registry.append(');\nfunction master_get(p) local(v) (v=0; p<100 ? v=slider(p);')
    for i in range(4):
        for j in range(6): registry.append(f'p=={110+i*10+j} ? v=l{i+1}_detect{j+7};')
    registry.append('v;);\nfunction master_put(p,v,finish) (!master_action_locked(p) ? (master_spec(p); v=max(master_lo,min(master_hi,master_lo+floor((v-master_lo)/master_step+.5)*master_step)); p<100 ? (slider(p)=v; master_notify(p,finish);) : (')
    for i in range(4):
        for j in range(6): registry.append(f'p=={110+i*10+j} ? l{i+1}_detect{j+7}=v;')
    registry.append('sliderchange(-1););););')
    common=expand((ROOT/'gui-controls.eel').read_text())
    # Snapshot remains identical to M6, with separate buffers per layer.
    snapshot=gui[gui.index('// Snapshot the active immutable table.'):gui.index('g_visible ? (')]
    layer=expand((ROOT/'gui-layer.eel').read_text())
    parts=['\n'.join(registry),common]
    for i in range(1,5):
        s=snapshot
        import re
        for v in (9000,10000,10700,11000): s=re.sub(rf'\b{v}\b',str(v+(i-1)*STRIDE),s)
        body=layer.replace('LAYER_NUMBER',str(i)).replace('LAYER_INDEX',str(i-1)).replace('BASE_PARAMETER',str(7+12*(i-1))).replace('DETECT_PARAMETER',str(110+10*(i-1)))
        for v in (9000,10000,10700,11000): body=re.sub(rf'\b{v}\b',str(v+(i-1)*STRIDE),body)
        parts.append(ns('function snapshot() (\n'+s+'\n);\n'+body,i))
    frame=expand((ROOT/'gui-frame.eel').read_text())
    frame=frame.replace('// SNAPSHOTS','\n'.join(f'l{i}_snapshot();' for i in range(1,5)))
    frame=frame.replace('// CARDS','\n'.join(f'l{i}_card();' for i in range(1,5)))
    frame=frame.replace('// SELECTED','\n'.join(f'master_selected=={i-1} ? l{i}_workspace();' for i in range(1,5)))
    frame=frame.replace('// SOUND_SELECTED','\n'.join(f'master_selected=={i-1} ? l{i}_sound_panel();' for i in range(1,5)))
    frame=frame.replace('// STATUS_SELECTED','\n'.join(f'master_selected=={i-1} ? l{i}_status_line();' for i in range(1,5)))
    frame=frame.replace('// SERVICE','\n'.join(f'l{i}_gui_loader.l{i}_status==4 && l{i}_gui_loader.l{i}_request!=atomic_get(l{i}_latest_request) ? l{i}_gui_loader.l{i}_cancel_load(); l{i}_edit_service();' for i in range(1,5)))
    frame=frame.replace('// DROP','\n'.join(f'''master_drop_layer=={i-1} ? (l{i}_edit_discard(); l{i}_g_request=atomic_add(l{i}_latest_request,1); l{i}_gui_loader.l{i}_mode=0; l{i}_gui_loader.l{i}_begin_load(#master_drop,l{i}_g_request,0,0,0); #l{i}_ui_message="";);''' for i in range(1,5)))
    clear='function master_clear_layers() (\n'
    for i in range(1,5): clear+=f'l{i}_edit_discard(); l{i}_gui_loader.l{i}_cancel_load(); atomic_add(l{i}_latest_request,1); l{i}_gui_loader.l{i}_status=0; l{i}_restore_failed=0; #l{i}_ui_message="";\n'
    clear+='atomic_set(master_clear_request,1);sliderchange(-1););\n'
    return '\n'.join(parts+[clear,frame])
