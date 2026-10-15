/* Included by batman_coop.h. Reserved owner words preserve old save layouts. */
#define BR_CHEATS br.owner[0]
#define BR_MENU br.owner[1]
#define BR_ROW br.owner[2]
#define BR_KEYS br.owner[3]
#define BR_CHORD br.owner[4]
#define BR_LEVEL br.owner[5]
#define BR_SECTION br.owner[6]
#define BR_LOAD br.owner[7]
#define BR_BLOCK br.owner[8]
enum { BR_INVUL=1, BR_ONEHIT=2, BR_LIVES=4, BR_AMMO=8 };
static unsigned br_sublevels(unsigned level){
 /* The ROM's native level-select bounds, bank 81:80A7. */
 return Memory.ROM[0x80a7+level%7];
}

static void br_heal(void){
 if(br_r16(0x32)==6){br_w16(0x8a,80);if(br.active)br.p2.hp=80;}
}
static int br_appearance_tick(unsigned held,unsigned edge);
int br_menu_tick(unsigned p1,unsigned p2){
 unsigned held=p1|p2,edge=held&~BR_KEYS,was=BR_MENU;
 unsigned chord=((p1&0x9080)==0x9080)||((p2&0x9080)==0x9080);
 BR_KEYS=held;
 BR_BLOCK&=held;
 if(br_appearance_tick(held,edge))return 1;
 if(chord && !BR_CHORD){
  BR_MENU=!BR_MENU;
  if(BR_MENU){BR_LEVEL=br_r16(0x72)%7;BR_SECTION=br_r16(0x74)%br_sublevels(BR_LEVEL);BR_ROW%=13;}
 }
 BR_CHORD=chord;
 if(!BR_MENU){if(was || chord)BR_BLOCK=held;return was || chord;}
 BR_BLOCK=held;
 if(chord)return 1;
 if(edge&0x0800)BR_ROW=(BR_ROW+12)%13;
 if(edge&0x0400)BR_ROW=(BR_ROW+1)%13;
 if(edge&0x8000){BR_MENU=0;return 1;}
 if(edge&(0x0300|0x0080)){
  int direction=(edge&0x0200)?-1:1;
  if(BR_ROW<4)BR_CHEATS^=1u<<BR_ROW;
  else if(BR_ROW==8){BR_LEVEL=(BR_LEVEL+7+direction)%7;BR_SECTION=0;}
  else if(BR_ROW==9){unsigned count=br_sublevels(BR_LEVEL);BR_SECTION=(BR_SECTION+count+direction)%count;}
  else if(edge&0x0080){
   if(BR_ROW==4)br_heal();
   if(BR_ROW==5)br_w16(0x8c,br_r16(0x8c)>94?99:br_r16(0x8c)+5);
   if(BR_ROW==6)br_w16(0x90,9);
   if(BR_ROW==7 && br.active){
    if(br.owner[13]){
     unsigned lane=br_r16(0x328)+72;
     br.p2.obj[8]=lane;br.p2.obj[9]=lane>>8;
    }else{
     memcpy(br.p2.obj+7,Memory.RAM+0x327,0x14);
     br.p2.obj[8]=Memory.RAM[0x328]>48?Memory.RAM[0x328]-24:Memory.RAM[0x328]+24;
     br.p2.obj[9]=0;
    }
   }
   if(BR_ROW==10 || BR_ROW==11){
    if(BR_ROW==11){BR_LEVEL=br_r16(0x72)%7;BR_SECTION=0;}
    BR_LOAD=1;BR_MENU=0;
   }
   if(BR_ROW==12)BR_MENU=0;
  }
 }
 return 1;
}
unsigned br_filter_pad(unsigned pad){return pad&~BR_BLOCK;}
void br_cheat_frame(void){
 br_prepare_vehicle();
 br_prepare_arrival();
 if(br_r16(0x32)!=6)return;
 if(BR_CHEATS&BR_INVUL){
  br_heal();
  if(br_r16(0x35c)==2 && (br_r16(0x9a)!=2 || Memory.RAM[0x350]<0x14))br_w16(0x3f8,br_r16(0x9a)==2?0:121);
  if(br.active && br.p2.obj[0x3c]==2 && (br_r16(0x9a)!=2 || br.p2.obj[0x30]<0x14)){br.p2.obj[0xd8]=br_r16(0x9a)==2?0:121;br.p2.obj[0xd9]=0;}
 }
 if(BR_CHEATS&BR_LIVES)br_w16(0x8c,99);
 if(BR_CHEATS&BR_AMMO)br_w16(0x90,9);
}
static void br_cheat_opcode(unsigned pc){
 /* Side-view invulnerability uses contact rejection: its blink timer also
  * suppresses attacks, so pinning that timer prevents normal combat. */
 if(br_supported && (BR_CHEATS&BR_INVUL) && (pc==0x80c06f || pc==0x80c0a9))ICPU._Carry=1;
 if(br_supported && (BR_CHEATS&BR_ONEHIT) &&
    (pc==0x87f5cc || pc==0x87f634)){
  unsigned enemy=ICPU.Registers.X.W;
  if(enemy>=0x550 && enemy<0x14f0){
   if(br_r16(enemy+0x26))br_w16(enemy+0x26,1);
   ICPU.Registers.A.W=127;
  }
 }
}
static void br_cheat_load_level(void){
 if(BR_LOAD!=1)return;
 br.active=0;memset(br.pending,0,128);memset(br.live,0,128);
 /* Later sections inherit tiles from earlier sections of the same level. */
 br_w16(0x72,BR_LEVEL);br_w16(0x74,0);
 br_w16(0x78,0);br_w16(0x7a,0);br_w16(0x7c,0);br_w16(0x6a,0);br_w16(0x6c,0);
 /* Use the ROM's own level-select dispatcher and VRAM reset, with normal
  * emulated timing. Merely changing the gameplay state leaves stale tiles. */
 br_w16(0x32,5);br_w16(0x34,1);br_w16(0x36,0);
 if(!br_r16(0x8c))br_w16(0x8c,3);
 BR_LOAD=2;
}
static void br_cheat_stage_hook(unsigned pc){
 if(BR_LOAD==2 && pc==0x808613){BR_LOAD=3;br_jump(0x8085ed);}
 if(BR_LOAD==3 && pc==0x808492 && br_r16(0x32)==6 && br_r16(0x78)==4 && !br_r16(0x159a)){
  if(br_r16(0x74)>=BR_SECTION)BR_LOAD=0;
  else{
   br_w16(0x74,br_r16(0x74)+1);br_w16(0x76,br_r16(0x76)+1);
   /* Take the ROM's actual subsection transition. Special transitions
    * (including the rooftop boss room) have their own graphics loaders. */
   br_w16(0x159a,0x11);br_w16(0x159c,0);br_w16(0xbe,0);
   br_w16(0x6a,0);br_w16(0x6c,0);br_w16(0xd6,0);
   br.active=0;br.owner[12]=0;
  }
 }
}
static void br_menu_draw(unsigned w,unsigned h){
 static const char*rows[]={"INVULNERABILITY","ONE HIT KILLS","INFINITE LIVES","INFINITE TEST TUBES","HEAL BOTH PLAYERS","ADD 5 LIVES","REFILL TEST TUBES","BRING P2 TO P1","LEVEL","SUBLEVEL","LOAD SELECTED LEVEL","RESTART LEVEL","RESUME"};
 unsigned x,y,r,white=BUILD_PIXEL(31,31,31),blue=BUILD_PIXEL(8,22,31),gold=BUILD_PIXEL(31,24,6);
 char label[16];
 if(!BR_MENU || w<256 || h<224)return;
 for(y=8;y<224;y++)for(x=6;x<w-6;x++)br_output[y*w+x]=BUILD_PIXEL(1,2,5);
 br_text(w,18,16,"BATMAN COOP CHEATS",gold);
 for(r=0;r<13;r++){
  unsigned yy=34+r*12,color=r==BR_ROW?gold:white;
  if(r==BR_ROW)for(y=yy-2;y<yy+9;y++)for(x=12;x<w-12;x++)br_output[y*w+x]=BUILD_PIXEL(3,7,11);
  br_text(w,18,yy,rows[r],color);
  if(r<4)br_text(w,210,yy,(BR_CHEATS&(1u<<r))?"ON":"OFF",color);
  if(r==8){snprintf(label,sizeof(label),"%u",BR_LEVEL+1);br_text(w,222,yy,label,color);}
  if(r==9){snprintf(label,sizeof(label),"%u OF %u",BR_SECTION+1,br_sublevels(BR_LEVEL));br_text(w,198,yy,label,color);}
 }
 br_text(w,18,198,"UP DOWN SELECT   A APPLY   B BACK",blue);
 br_text(w,18,212,"LATER STAGES COOP INCOMPLETE",blue);
}
