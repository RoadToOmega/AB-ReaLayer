"""Shared parameter specifications for GUI controls and sound reset macros."""
PARAMS={1:(-60,6,.1,-4,'dB'),2:(0,16,1,0,'ch'),3:(-1,127,1,-1,'note'),4:(.1,10,.1,2,'ms'),5:(0,1,1,0,''),6:(-1,119,1,-1,'CC')}
for layer in range(4):
    base=7+12*layer
    for j,entry in enumerate([(-60,6,.1,0,'dB'),(-1,1,.01,0,'pan'),(-24,24,.01,0,'st'),(0,1,1,1,''),(0,1,1,0,''),(0,4,1,0,''),(1,16777215,1,12345+layer*104729,'seed'),(0,1,1,0,''),(1,256,1,1,'region'),(0,12,.01,0,'st'),(0,12,.1,0,'dB'),(0,1,.01,0,'pan')]): PARAMS[base+j]=entry
    PARAMS[55+2*layer]=(0,2000,1,0,'ms')
    PARAMS[56+2*layer]=(0,5000,1,0,'ms')
    for j,entry in enumerate([(-80,-6,.5,-36,'dB'),(1,24,.5,6,'dB'),(1,1000,1,80,'ms'),(1,1000,1,10,'ms'),(0,100,.5,3,'ms'),(0,500,1,20,'ms')]): PARAMS[110+layer*10+j]=entry

PARAMS[64]=(0,1,1,0,'')
PARAMS[69]=(0,1,1,0,'')
PARAMS[70]=(0,16777215,1,1357911,'')
for i in range(4): PARAMS[65+i]=(0,100,1,0,'%')

SOUND=[]
LOCKED=[]
for i in range(4):
    b=7+i*12
    SOUND.extend([b,b+1,b+2,b+9,b+10,b+11,55+i*2,56+i*2,65+i])
    LOCKED.extend([b,b+1,b+2,b+9,b+10,b+11,65+i])
SOUND_DEFAULTS={p:PARAMS[p][3] for p in SOUND}
