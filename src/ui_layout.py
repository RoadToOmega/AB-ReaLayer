"""Logical GUI geometry, separate from PCM memory. Shared by drawing/input/tests."""
import re
WIDTH,HEIGHT=1240,800
OPEN_WIDTH,OPEN_HEIGHT=1550,1000
WORK_DY=70
CARD_X,CARD_Y,CARD_W,CARD_H,CARD_STEP=20,140,291,132,303
RECTS={
 'RANDOM':(20,90,170,28),'RESET_SOUND':(202,90,148,28),'CHAOS':(362,90,130,28),
 'CLEAR_ALL':(1070,90,150,28),'MASTER':(570,14,120,44),'LIMITER':(710,20,148,28),
 'SETTINGS':(1110,20,110,28),'VARIATIONS':(20,286,130,28),'EDIT':(158,286,86,28),'DETECT':(252,286,94,28),
 'STOP_ALL':(892,755,112,34),'PLAY_SAMPLER':(1016,752,204,40),
 'SOUND_PANEL':(860,286,360,438),'RANDOM_PITCH':(878,372,100,108),
 'RANDOM_GAIN':(990,372,100,108),'RANDOM_PAN':(1102,372,100,108),
 'ATTACK':(878,536,148,108),'RELEASE':(1052,536,148,108),
 'MODAL':(355,310,530,185),'NUM_APPLY':(379,449,126,28),'NUM_CANCEL':(519,449,126,28),
}
CONSTANTS=dict(UI_W=WIDTH,UI_H=HEIGHT,UI_WORK_DY=WORK_DY,UI_CARD_X=CARD_X,UI_CARD_Y=CARD_Y,UI_CARD_W=CARD_W,UI_CARD_H=CARD_H,UI_CARD_STEP=CARD_STEP,UI_WAVE_W=788,UI_WORK_W=824)
def card_rect(i):return (CARD_X+i*CARD_STEP,CARD_Y,CARD_W,CARD_H)
def card_fields(i):
 x=card_rect(i)[0]
 return [(x+12,190,65,44),(x+77,190,65,44),(x+142,190,71,44),(x+213,190,66,44)]
def expand(code):
 for name,r in RECTS.items():
  code=code.replace('@'+name+'@',','.join(map(str,r[:3])))
  code=code.replace('@'+name+'_RECT@',','.join(map(str,r)))
 for name,value in CONSTANTS.items():code=re.sub(r'\b'+name+r'\b',str(value),code)
 assert not re.search(r'@[A-Z_]+@',code),'Unexpanded GUI rectangle'
 return code
