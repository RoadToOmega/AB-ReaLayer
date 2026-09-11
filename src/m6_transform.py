"""M6 additions to the reusable single-layer source before static namespacing."""
def transform(init,serial,block,sample,gui):
    def change(s,a,b):
        assert a in s,a
        return s.replace(a,b)
    init=change(init,'shuffle_base=7000;', '''shuffle_base=7000; saved_flags=5000;
    edit_regions=48000; edit_flags=48512; edit_settings=49000;''')
    init=change(init,'// Reader count is NOT reset:', '''memset(region_base+bank*region_stride+512,1,256);
          // Reader count is NOT reset:''')
    init=change(init,'function publish_bank() instance(meta,status,request)',
                'function publish_bank() instance(meta,status,request,bank,pi,pn,pr)')
    init=change(init,'atomic_set(meta[0],2); status=2;', '''
    pr=region_base+bank*region_stride; pi=0; pn=0;
    loop(meta[7], pr[512+pi]>0 ? (pr[768+pn]=pi; pn+=1;); pi+=1;);
    meta[16]=pn;
    atomic_set(meta[0],2); status=2;''')
    init=change(init,'seq_last=-1; seq_triggers=0;', 'last_region=0; seq_last=-1; seq_triggers=0;')
    init=change(init,'(!use_region || m[7]>0)', '''(!use_region || (audition ? m[7]>0 :
      (m[16]>0 && (seq_mode!=4 || (region_base+b*region_stride)[512+max(0,min(m[7]-1,floor(slider14)-1))]>0))))''')
    init=change(init,'ri=audition ? max(0,min(m[7]-1,floor(slider14)-1)) : select_region(m[7]);', '''
        ri=audition || seq_mode==4 ? max(0,min(m[7]-1,floor(slider14)-1)) :
          (region_base+b*region_stride)[768+select_region(m[16])];''')
    init=change(init,'seq_triggers+=1;', 'seq_triggers+=1; last_region=ri+1;')
    init=change(init,'v[6]*=10^(dg/20);', '''v[6]*=10^(dg/20);
      v[21]=max(v[9],srate*max(0,min(2000,slider22))*.001);
      v[22]=max(v[9],srate*max(0,min(5000,slider23))*.001);''')
    serial=change(serial,'ss_version=3;', 'ss_version=4;')
    serial=change(serial,'ss_version==3)', 'ss_version==3 || ss_version==4)')
    serial=change(serial,'memcpy(saved_settings,ss_meta+10,6);', '''memcpy(saved_settings,ss_meta+10,6);
    memcpy(saved_flags,region_base+token_bank(ss_token)*region_stride+512,saved_count);''')
    serial=change(serial,'file_mem(0,saved_settings,6); file_mem(0,saved_regions,saved_count*2);', '''file_mem(0,saved_settings,6); file_mem(0,saved_regions,saved_count*2);
  file_mem(0,saved_flags,saved_count);''')
    serial=change(serial,'ss_i=0; ss_end=0;', '''ss_version>=4 ? (
          saved_count>0 && file_mem(0,saved_flags,saved_count)!=saved_count ? ss_valid=0;
        ) : memset(saved_flags,1,saved_count);
        ss_i=0; ss_end=0;''')
    serial=change(serial,'ss_end=ss_stop; ss_i+=1;', '''(saved_flags[ss_i]!=0 && saved_flags[ss_i]!=1) ? ss_valid=0;
          ss_end=ss_stop; ss_i+=1;''')
    serial=change(serial,'saved_regions[0]=0; saved_regions[1]=saved_frames; slider13=1;',
                  'saved_regions[0]=0; saved_regions[1]=saved_frames; saved_flags[0]=1; slider13=1;')
    serial=change(serial,'memcpy(ss_m+10,saved_settings,6);', '''memcpy(ss_m+10,saved_settings,6);
        memcpy(region_base+restore_loader.bank*region_stride+512,saved_flags,saved_count);''')
    block=change(block,'last_audio_rate>0 ? a_voice[9]*=srate/last_audio_rate;', '''last_audio_rate>0 ? (
      a_voice[9]*=srate/last_audio_rate;
      a_voice[21]*=srate/last_audio_rate; a_voice[22]*=srate/last_audio_rate;
    );''')
    sample=change(sample,'attack=min(1,v[11]/max(1,v[9]));','attack=min(1,v[11]/max(1,v[21]));')
    sample=change(sample,'rate_step*v[9]','rate_step*v[22]')
    sample=change(sample,'atomic_set(meter_variation,seq_last+1);','atomic_set(meter_variation,last_region);')
    gui=change(gui,'gfx_set(enabled ? .16', 'enabled=enabled && !edit_active;\n  gfx_set(enabled ? .16')
    gui=change(gui,'g_click && !g_preview && mouse_y>=152','g_click && !g_preview && !edit_active && mouse_y>=152')
    gui=change(gui,'memcpy(10700,g_meta+10,6);','memcpy(10700,g_meta+10,6); memcpy(11000,region_base+token_bank(g_token)*region_stride+512,g_count);')
    gui=change(gui,'memcpy(10000,region_base+gui_loader.bank*region_stride,g_count*2);\n  memcpy(10700,g_meta+10,6); memcpy(11000,region_base+token_bank(g_token)*region_stride+512,g_count);',
               'memcpy(10000,region_base+gui_loader.bank*region_stride,g_count*2);\n  memcpy(10700,g_meta+10,6); memcpy(11000,region_base+gui_loader.bank*region_stride+512,g_count);')
    gui=change(gui,'sprintf(#region_label,"%d",g_idx+1);','sprintf(#region_label,11000[g_idx]>0 ? "%d" : "%d off",g_idx+1);')
    return init,serial,block,sample,gui
