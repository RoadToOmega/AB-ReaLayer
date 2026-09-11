"""Native-rate single-pass load/validate/peaks/detect transform."""
def transform(code):
 start=code.index('function load_step()')
 end=code.index('// Audio-only deterministic generator.',start)
 replacement='''function load_step()
instance(handle,bank,meta,status,request,channels,rate,items,read_items,
 base,n,i,j,chunk,got,x,frame,bin,peakoff,expected_frames,expected_ch,expected_rate,mode,
 scan,window_count,energy,window_size,is_open,last_loud,x0,x1,pointer) (
 status==1 ? (
  request!=atomic_get(latest_request) ? this.cancel_load() : (
   read_items==0 && mode!=2 ? this.detector_begin();
   chunk=min(16384,items-read_items);
   got=file_mem(handle,base+read_items,chunk);
   got!=chunk ? status=-5 : (
    i=0;
    loop(got/channels,
     pointer=base+read_items+i*channels;x0=pointer[0];x1=channels==2 ? pointer[1] : x0;
     !(abs(x0)<1000000) || !(abs(x1)<1000000) ? status=-5;
     frame=read_items/channels+i;bin=min(255,floor(frame*256/meta[1]));peakoff=meta+32+bin*2;
     peakoff[0]=min(peakoff[0],min(x0,x1));peakoff[1]=max(peakoff[1],max(x0,x1));
     mode!=2 ? (
      energy+=max(x0*x0,x1*x1);window_count+=1;scan+=1;
      window_count>=window_size ? this.detector_window();
     );
     i+=1;
    );
    read_items+=got;
   );
   status<0 ? (file_close(handle);handle=-1;atomic_set(meta[0],0);) : read_items==items ? (
    file_close(handle);handle=-1;
    request==atomic_get(latest_request) ? (
     mode==2 ? status=4 : (
      window_count>0 ? this.detector_window();
      is_open ? (this.detector_append(last_loud);is_open=0;);
      this.finish_detection();
     );
    ) : (atomic_set(meta[0],0);status=-6;);
   );
  );
 );
 status==3 ? this.detector_step();
 status;
);

'''
 return code[:start]+replacement+code[end:]
