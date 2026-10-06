#ifndef BATMAN_COOP_H
#define BATMAN_COOP_H
/* Batman Returns USA, CRC32 E87DFDF6. Included once by cpuexec.c.
 * Native player routines run with private context and no extra emulated time.
 * World updates remain timed. All game-specific state lives in the BR suffix.
 * See ../../DEVELOPMENT.md for the mapped routines and verification limits.
 */
#include <stdio.h>
#include <string.h>
#include "pixform.h"
static FILE *br_trace;
static unsigned br_trace_left, br_watch_addr=0x328, br_prev_pc, br_last;
typedef struct { unsigned char obj[0x1e0], hp,weapon,timer[2],face[2]; } BRPlayer;
static struct {
 unsigned version,active,frames,errors,stage;
 BRPlayer p2,ai_saved,spawn;
 unsigned ai,owner[16];
 unsigned char tiles[65536],visible_tiles[65536],gray[131072],visible_gray[131072],pending[128],live[128];
 unsigned short buttons,previous;
} br;
/* Separate player OAM, appended to saves without changing the legacy BR layout. */
typedef struct { unsigned count; SOBJ obj[128]; unsigned char anchor[128],blue[128]; } BRExtraOAM;
static struct { BRExtraOAM pending,live; unsigned char third[0x50];
 unsigned terrain_stage,terrain_key[32768];unsigned char terrain[32768];
} br_extra;
static unsigned char br_draw_blue[256];
unsigned br_extra_size(void){return sizeof(br_extra);}
unsigned br_extra_old_size(void){return sizeof(BRExtraOAM)*2+0x50;}
void br_extra_save(void*p){memcpy(p,&br_extra,sizeof(br_extra));}
void br_extra_load(const void*p,unsigned n){memset(&br_extra,0,sizeof(br_extra));if(p && n<=sizeof(br_extra))memcpy(&br_extra,p,n);}
unsigned br_build_objs(SOBJ*out){
 unsigned i,j=0,n=0,count=br.active?br_extra.live.count:0;
 if(count>128)count=0;
 for(i=0;i<=128;i++){
  while(j<count && br_extra.live.anchor[j]==i){out[n]=br_extra.live.obj[j];br_draw_blue[n++]=br_extra.live.blue[j++];}
  if(i<128){out[n]=PPU.OBJ[i];br_draw_blue[n++]=br.active&&br.live[i];}
 }
 return n;
}
unsigned char br_tile_cache[131072],br_tile_cached[2048];
unsigned char br_effect_cache[131072],br_effect_cached[2048];
int br_render;
static int br_inside;
static int br_second;
static int br_supported;
static void br_cheat_opcode(unsigned pc);
static void br_cheat_load_level(void);
static void br_prepare_arrival(void);
static void br_prepare_vehicle(void);
static unsigned br_vehicle_word(unsigned a);
static void br_vehicle_set(unsigned a,unsigned v);
int br_identify(void){
 unsigned i,k,crc=~0u;br_supported=0;
 if(Memory.CalculatedSize!=1048576)return 0;
 for(i=0;i<1048576;i++){crc^=Memory.ROM[i];for(k=0;k<8;k++)crc=(crc>>1)^(0xedb88320u&-(int)(crc&1));}
 br_supported=(~crc)==0xe87dfdf6u;return br_supported;
}
static unsigned short br_colors[32];
unsigned short *br_player_colors(void){
 unsigned i,b=PPU.Brightness;
 /* Preserve the native black shadow/outline ink; recolour body shading. */
 static const unsigned char blue[8][3]={{0,0,0},{0,0,0},{2,4,10},{3,8,17},{5,13,24},{8,18,28},{15,24,30},{24,29,31}};
 for(i=0;i<16;i++)br_colors[i]=IPPU.ScreenColors[128+i];
 for(i=1;i<8;i++)br_colors[i]=BUILD_PIXEL(blue[i][0]*b/15,blue[i][1]*b/15,blue[i][2]*b/15);
 memcpy(br_colors+16,br_colors,16*sizeof(*br_colors));
 br_colors[18]=BUILD_PIXEL(0,0,0);
 return br_colors;
}
static unsigned br_r16(unsigned a){return Memory.RAM[a]|Memory.RAM[a+1]<<8;}
static void br_w16(unsigned a,unsigned v){Memory.RAM[a]=v;Memory.RAM[a+1]=v>>8;}
static unsigned br_map_buttons(unsigned raw){
 unsigned low=raw&255,high=raw>>8,type=br_r16(0x1fb8),a,b;
 if(type==2){a=(low&0x80)|((high&0x80)>>1);b=((high&0x40)<<1)|(low&0x70);return(raw&0x3f00)|(a<<8)|b;}
 if(type==4){a=((high&0x80)>>1)|((high&0x40)<<1);return(raw&0x3f00)|(a<<8)|low;}
 if(type==6){a=((low&0x80)?0xc0:0)|high;b=(low&0x30)|((low&0x40)<<1);if(br.buttons&0x30)b|=high&0x40;return(raw&0x3f00)|(a<<8)|b;}
 return raw;
}
static void br_capture(BRPlayer*p){
 memcpy(p->obj,Memory.RAM+0x320,sizeof(p->obj));p->hp=Memory.RAM[0x8a];p->weapon=Memory.RAM[0x8e];
 memcpy(p->timer,Memory.RAM+0x9c,2);p->face[0]=Memory.RAM[0xa8];p->face[1]=Memory.RAM[0xd4];
}
static void br_install(const BRPlayer*p){
 memcpy(Memory.RAM+0x320,p->obj,sizeof(p->obj));Memory.RAM[0x8a]=p->hp;Memory.RAM[0x8e]=p->weapon;
 memcpy(Memory.RAM+0x9c,p->timer,2);Memory.RAM[0xa8]=p->face[0];Memory.RAM[0xd4]=p->face[1];
}
static void br_jump(unsigned pc){ICPU.Registers.PB=pc>>16;ICPU.ShiftedPB=pc&0xff0000;S9xSetPCBase(pc);}
static unsigned br_terrain_key(int x,int y){return ((unsigned)(y>>4)<<16)|((x>>4)&65535);}
static unsigned br_terrain_slot(unsigned key){return (key*2654435761u^(key>>16)*40503u)&32767;}
static void br_remember_terrain(void){
 int x,y,cx=br_r16(0x17a0)&~15,cy=br_r16(0x17b0)&~15;
 if(br_extra.terrain_stage!=br.stage+1){memset(br_extra.terrain_key,0,sizeof(br_extra.terrain_key));br_extra.terrain_stage=br.stage+1;}
 /* Only the native collision window contains freshly loaded terrain.
  * Remember it before scrolling overwrites the 512-pixel ring buffer. */
 for(y=cy-48;y<cy+320;y+=16)for(x=cx-48;x<cx+320;x+=16)if(x>=0 && y>=0){
  unsigned key=br_terrain_key(x,y),slot=br_terrain_slot(key),n=0;
  unsigned addr=0x19000+((x&0x100)<<2)+((y&0x100)<<3)+((y&0xf0)<<2)+((x&0xf0)>>3);
  while(br_extra.terrain_key[slot] && br_extra.terrain_key[slot]!=key+1 && ++n<32768)slot=(slot+1)&32767;
  if(n<32768){br_extra.terrain_key[slot]=key+1;br_extra.terrain[slot]=Memory.RAM[addr];}
 }
}
static int br_free_camera(void){
 int x1=(short)br_r16(0x328),x2=(short)(br.p2.obj[8]|br.p2.obj[9]<<8);
 return br.active && br_r16(0x9a)==2 && !br_r16(0xd6) &&
  (br_r16(0x40e) || (br.p2.obj[0xee]|br.p2.obj[0xef]) ||
   (br.owner[10] && (x1<16 || x1>240 || x2<16 || x2>240)));
}
static int br_fire_corridor(void){
 /* Native vertical follow moves a few pixels during swings in this room. */
 return br.active && br.stage==3 && br_r16(0x9a)==2 &&
  br_r16(0x17b0)>=240 && br_r16(0x17b0)<=288 &&
  br_r16(0x17a0)>=2304 && br_r16(0x17a0)<=3584 && !br_r16(0xd6);
}
static void br_shift_grappler(unsigned char *body,int shift){
 int addr;
 for(addr=8;addr<=0x38;addr+=0x30){
  unsigned v=(body[addr]|body[addr+1]<<8)+shift;body[addr]=v;body[addr+1]=v>>8;
 }
 if(body[0xee] || body[0xef]){
  unsigned v=(body[0xf8]|body[0xf9]<<8)+shift;body[0xf8]=v;body[0xf9]=v>>8;
 }
}
static void br_fire_keep_visible(void){
 unsigned player;
 if(!br_fire_corridor())return;
 for(player=0;player<2;player++){
  unsigned char *body=player?br.p2.obj:Memory.RAM+0x320;
  int x=(short)(body[8]|body[9]<<8);
  if(x<48)br_shift_grappler(body,48-x);
  else if(x>240)br_shift_grappler(body,240-x);
 }
}
static void br_grapple_catch_up(void){
 int dx=(signed char)Memory.RAM[0x188c];
 int x1=(short)br_r16(0x328),x2=(short)(br.p2.obj[8]|br.p2.obj[9]<<8),shift;
 unsigned char *body;
 /* Assist only this upper fire corridor, after the actual camera shift.
  * Keep the trailing player inside the left margin, never
  * copying the leader's pose, velocity, inventory or grapple state. */
 if(!br_fire_corridor())return;
 /* Visibility is required even when a backward pan, a small separation,
  * or an already offscreen save bypasses the gentle forward assist. */
 if(dx<0 || abs(x1-x2)<=96){br_fire_keep_visible();return;}
 body=x1<x2?Memory.RAM+0x320:br.p2.obj;
 shift=(dx>0?72:48)-(x1<x2?x1:x2);
 if(shift<=0){br_fire_keep_visible();return;}
 /* Swing recoil can exceed the camera speed. Allow enough correction to
  * counter it, including the last swing after the camera reaches the end. */
 if(shift>dx+8)shift=dx+8;
 if(shift>abs(x1-x2)-96)shift=abs(x1-x2)-96;
 br_shift_grappler(body,shift);
 br_fire_keep_visible();
}
static void br_death(unsigned pc){
 br_cheat_opcode(pc);
 if(br_second && br.owner[13]){
  if(pc==0x84fd56)br_w16(2,0);
  /* Project into the shared road view, while spawning from P2's lane. */
  if(pc==0x84fd65){ICPU.Registers.A.W=0x200-(br.ai_saved.obj[8]|br.ai_saved.obj[9]<<8);br_jump(0x84fd68);}
  /* Only the timed P1 pass owns engine audio. */
  if(pc==0x84e5c7)br_jump(0x84e5ca);
  if(pc==0x84e7fd)br_jump(0x84e80f);
 }
 if(pc==0x80bebe && br_free_camera()){
  int sx=(short)br_r16(8),wx=(short)sx+br_r16(0x17a0),wy=(short)br_r16(10)+br_r16(0x17b0);
  if(sx< -48 || sx>=320){
   unsigned key=br_terrain_key(wx,wy),slot=br_terrain_slot(key),n=0;
   while(br_extra.terrain_key[slot] && br_extra.terrain_key[slot]!=key+1 && ++n<32768)slot=(slot+1)&32767;
   if(br_extra.terrain_key[slot]==key+1){ICPU.Registers.A.W=br_extra.terrain[slot];br_jump(0x80bf23);return;}
  }
  br_jump(0x80becc);return;
 }
 if(br.active && br_r16(0x9a)==2 && ICPU.Registers.X.W==0x320){
  /* The native screen X is an eight-bit integer with a fractional byte.
   * Extend both movement and camera subtraction into the signed high byte. */
  if(pc==0x80bd2b)Memory.RAM[0x329]+=(short)br_r16(0x1a)<0?ICPU._Carry-1:ICPU._Carry;
  if(pc==0x80be4e)Memory.RAM[0x329]-=Memory.RAM[0x00]+(ICPU._Carry?0:1);
  /* Hook range is measured from the player, not the shared viewport. */
  if(pc==0x80e0f7 && br_free_camera()){br_jump(0x80e105);return;}
  if(pc==0x80bcaa && br_free_camera()){
   int x=(short)br_r16(0x328),left=(short)br_r16(0x1a)<0;
   /* Preserve true level boundaries, but the viewport edge is not terrain. */
   if(left?(!(Memory.RAM[0x9e]&2)||x>=16):(!(Memory.RAM[0x9e]&1)||x<241)){
    br_jump(0x80bcc6);return;
   }
   /* Do not let an already offscreen coordinate bypass the true level
    * boundary through the native low-byte comparison. */
   Memory.RAM[0x3e6]++;br_jump(0x80bd81);return;
  }
 }

 if(pc==0x80c97e && br.active && Memory.RAM[0x8c]>1){
  BRPlayer old,partner;unsigned i; br_capture(&old);
  partner=br_second?br.ai_saved:br.p2;
  Memory.RAM[0x8c]--;br_install(&br.spawn);
  for(i=7;i<0x1b;i++)Memory.RAM[0x320+i]=partner.obj[i];
  br_w16(0x334,0);br_w16(0x33f,0);br_w16(0x343,0);br_w16(0x33b,0);
  br_w16(0x35c,2);br_w16(0x3b0,1);br_w16(0x3f8,120);Memory.RAM[0x8a]=80;
  Memory.RAM[0x8e]=old.weapon;
  br_jump(0x80c9a5);
 }
}
static unsigned br_run(unsigned start,unsigned end){
 SICPU saved=ICPU;SCPUState cpu=CPU;unsigned count=0,carry;unsigned char stack[256];
 memcpy(stack,Memory.RAM+0x1f00,256);br_inside=1;br_jump(start);
 while(ICPU.ShiftedPB+(unsigned)(CPU.PC-CPU.PCBase)!=end && count++<100000){
  br_death(ICPU.ShiftedPB+(unsigned)(CPU.PC-CPU.PCBase));
  CPU.PCAtOpcodeStart=CPU.PC;
  (*ICPU.S9xOpcodes[*CPU.PC++].S9xOpcode)();
 }
 if(count>=100000)br.errors++;
 carry=ICPU._Carry;
 memcpy(Memory.RAM+0x1f00,stack,256);ICPU=saved;CPU=cpu;br_inside=0;
 return carry;
}
static void br_upload(void){
 static const unsigned srcs[]={0x3a8,0x3b2,0x3ba},banks[]={0x3aa,0x3b8,0x3b9},dsts[]={0x3ac,0x3b4,0x3bc},lens[]={0x3ae,0x3b6,0x3be};
 unsigned k,i;
 for(k=0;k<3;k++){
  unsigned n=br_r16(lens[k]),s=br_r16(srcs[k])|(Memory.RAM[banks[k]]<<16),d=br_r16(dsts[k])*2;
  if(n && n<0x4000 && d+n<=65536){for(i=0;i<n;i++)br.tiles[d+i]=S9xGetByte(s+i);}
 }
 memset(br_tile_cached,0,sizeof(br_tile_cached));memset(br_effect_cached,0,sizeof(br_effect_cached));
}
__declspec(dllexport) unsigned br_state_size(void){return sizeof(br);}
__declspec(dllexport) void br_state_save(void*p){memcpy(p,&br,sizeof(br));}
__declspec(dllexport) void br_state_load(const void*p){memcpy(&br,p,sizeof(br));memset(br_tile_cached,0,sizeof(br_tile_cached));memset(br_effect_cached,0,sizeof(br_effect_cached));}
__declspec(dllexport) void br_reset(void){memset(&br,0,sizeof(br));memset(&br_extra,0,sizeof(br_extra));br.version=2;}
__declspec(dllexport) void br_input(unsigned v){br.buttons=v;}
__declspec(dllexport) void br_sprite_stats(unsigned*v){
 unsigned y,n;v[0]=v[1]=0;
 for(y=0;y<SNES_HEIGHT_EXTENDED;y++){
  for(n=0;n<256 && GFX.OBJLines[y].OBJ[n].Sprite>=0;n++);
  if(n>v[0])v[0]=n;
  if((unsigned)(2048-GFX.OBJLines[y].Tiles)>v[1])v[1]=2048-GFX.OBJLines[y].Tiles;
 }
}
__declspec(dllexport) void br_status(unsigned*v){v[0]=br.active;v[1]=br.frames;v[2]=br.errors;v[3]=br_r16(0x328);v[4]=br_r16(0x32c);v[5]=br.p2.obj[8]|br.p2.obj[9]<<8;v[6]=br.p2.obj[12]|br.p2.obj[13]<<8;v[7]=Memory.RAM[0x8a];v[8]=br.p2.hp;v[9]=Memory.RAM[0x8c];}
__declspec(dllexport) unsigned br_read(unsigned player,unsigned a){
 if(player==2){if(a>=0x500 && a<0x550)return br_extra.third[a-0x500];if(a>=0x320&&a<0x500)return br.p2.obj[a-0x320];if(a==0x8a)return br.p2.hp;if(a==0x8e)return br.p2.weapon;}
 return Memory.RAM[a&0x1ffff];
}
__declspec(dllexport) void br_write(unsigned player,unsigned a,unsigned v){
 if(player==2){if(a>=0x500 && a<0x550){br_extra.third[a-0x500]=v;return;}if(a>=0x320&&a<0x500){br.p2.obj[a-0x320]=v;return;}if(a==0x8a){br.p2.hp=v;return;}if(a==0x8e){br.p2.weapon=v;return;}}
 Memory.RAM[a&0x1ffff]=v;
}
static unsigned short br_output[512*544];
static void br_text(unsigned w,unsigned x,unsigned y,const char*s,unsigned color){
 static const unsigned char glyphs[][5]={
  {62,81,73,69,62},{0,66,127,64,0},{98,81,73,73,70},{34,65,73,73,54},{24,20,18,127,16},{39,69,69,69,57},{60,74,73,73,48},{1,113,9,5,3},{54,73,73,73,54},{6,73,73,41,30},
  {126,9,9,9,126},{127,73,73,73,54},{62,65,65,65,34},{127,65,65,34,28},{127,73,73,73,65},{127,9,9,9,1},{62,65,73,73,122},{127,8,8,8,127},{0,65,127,65,0},{32,64,65,63,1},{127,8,20,34,65},{127,64,64,64,64},{127,2,12,2,127},{127,4,8,16,127},{62,65,65,65,62},{127,9,9,9,6},{62,65,81,33,94},{127,9,25,41,70},{38,73,73,73,50},{1,1,127,1,1},{63,64,64,64,63},{31,32,64,32,31},{63,64,56,64,63},{99,20,8,20,99},{3,4,120,4,3},{97,81,73,69,67}};
 for(;*s;s++,x+=6){int n=*s>='0'&&*s<='9'?*s-'0':*s>='A'&&*s<='Z'?*s-'A'+10:-1;unsigned a,b;if(n<0)continue;for(a=0;a<5;a++)for(b=0;b<7;b++)if(glyphs[n][a]&(1<<b))if(x+a<w)br_output[(y+b)*w+x+a]=color;}
}
#include "batman_cheats.h"
int br_relocate_hud(void){return br_supported && br.active && br_r16(0x32)==6;}
static void br_boss_bar(unsigned w,unsigned h){
 unsigned hp=br_r16(0x19ae),kind=br_r16(0x19ac),layer,fill,x,y,scale=w/256,b=PPU.Brightness;
 static const unsigned char colors[5][2][3]={
  {{31,15,0},{31,11,0}}, /* Original final layer: orange, two tones. */
  {{31,27,8},{26,19,2}}, {{10,31,13},{3,23,6}},
  {{10,21,31},{4,12,25}}, {{28,16,31},{20,8,26}}
 };
 unsigned top,under;
 if(!br_supported || !br.active || br_r16(0x32)!=6 || kind<0x12 || kind>0x40 || h<40 || !scale)return;
 /* The ROM treats exactly 80 HP as a full green bar. Keep that boundary
  * in the final orange layer, then retain native depletion/transparency. */
 if(hp<80)return;
 /* Each colour is 80 HP. The shrinking top layer reveals the full next
  * layer, making every hit visible even while total health exceeds 80. */
 layer=hp?(hp-1)/80:0;fill=hp?(hp-1)%80+1:0;
 if(layer>4)layer=4;
 for(y=25;y<31;y++){
  unsigned tone=y<28?0:1;
  top=BUILD_PIXEL(colors[layer][tone][0]*b/15,colors[layer][tone][1]*b/15,colors[layer][tone][2]*b/15);
  under=BUILD_PIXEL(colors[layer?layer-1:0][tone][0]*b/15,colors[layer?layer-1:0][tone][1]*b/15,colors[layer?layer-1:0][tone][2]*b/15);
  for(x=0;x<80*scale;x++)br_output[y*w+168*scale+x]=x<fill*scale?top:under;
 }
}
static void br_top_hud(unsigned w){
 unsigned x,y,scale=w/256,b=PPU.Brightness;
 if(!br.active || !scale)return;
 /* Reuse the original BG3 HUD tiles, fonts, portrait, borders and palette.
  * Decode onto a black strip so transparent HUD pixels reveal no scenery. */
 for(y=16;y<40;y++)for(x=0;x<256;x++){
  unsigned map=(PPU.BG[2].SCBase*2+((y/8)*32+x/8)*2)&65535;
  unsigned tile=Memory.VRAM[map]|Memory.VRAM[(map+1)&65535]<<8;
  unsigned px=x&7,py=y&7,addr,ink,color,i;
  if(x>=112 && x<144)continue; /* P2's complete item frame is drawn below. */
  if(y>=32 && x>=24 && x<104){
   unsigned hp=br.p2.hp>80?80:br.p2.hp;
   tile=(tile&0xff00)|Memory.ROM[0x9c10+hp-((x-24)/8)*8];
  }
  if(tile&0x4000)px=7-px;
  if(tile&0x8000)py=7-py;
  addr=(PPU.BG[2].NameBase*2+(tile&1023)*16+py*2)&65535;
  ink=((Memory.VRAM[addr]>>(7-px))&1)|(((Memory.VRAM[(addr+1)&65535]>>(7-px))&1)<<1);
  if(!ink)continue;
  color=IPPU.ScreenColors[((tile>>10)&7)*4+ink];
  /* Blue portrait and name distinguish the partner while retaining the
   * native silhouettes, lettering and orange two-tone health gauge. */
  if(x>=8 && x<24 && y>=24 && color!=BUILD_PIXEL(0,0,0)){
   static const unsigned char blue[4][3]={{0,0,0},{2,4,10},{5,13,24},{18,25,31}};
   color=BUILD_PIXEL(blue[ink][0]*b/15,blue[ink][1]*b/15,blue[ink][2]*b/15);
  }
  if(x>=24 && x<104 && y>=24 && y<32){
   /* Ink 1 is the lettering's shadow, not another foreground tone. */
   color=ink==1?BUILD_PIXEL(0,0,0):ink==2?
    BUILD_PIXEL(5*b/15,17*b/15,31*b/15):BUILD_PIXEL(10*b/15,26*b/15,31*b/15);
  }
  for(i=0;i<scale;i++)br_output[(y-8)*w+x*scale+i]=color;
 }
}
static void br_hud_weapon(unsigned w,unsigned weapon,unsigned y0){
 unsigned x,y,scale=w/256;
 if(weapon>2)weapon=0;
 for(y=0;y<16;y++)for(x=0;x<16;x++){
  /* Native item descriptors are 2Dxx: character page 1, palette 3. */
  unsigned tile=0x100+Memory.ROM[0x9c61+weapon]+x/8+(y/8)*2;
  unsigned addr=(PPU.BG[2].NameBase*2+tile*16+(y&7)*2)&65535;
  unsigned bit=7-(x&7),ink=((Memory.VRAM[addr]>>bit)&1)|(((Memory.VRAM[(addr+1)&65535]>>bit)&1)<<1),i;
  if(ink)for(i=0;i<scale;i++)br_output[(y0+y)*w+(120+x)*scale+i]=IPPU.ScreenColors[12+ink];
 }
}
static void br_p2_weapon_hud(unsigned w){
 unsigned x,y,scale=w/256,b=PPU.Brightness;
 unsigned white=BUILD_PIXEL(31*b/15,31*b/15,31*b/15);
 if(!br.active || !scale)return;
 /* Match the original 26x26 border and its five-pixel icon inset. */
 for(y=11;y<37;y++)for(x=115*scale;x<141*scale;x++)
  br_output[y*w+x]=(x<116*scale || x>=140*scale || y==11 || y==36)?white:0;
 br_hud_weapon(w,br.p2.weapon,16);
}
unsigned short *br_video(const unsigned short*src,unsigned w,unsigned h,unsigned pitch){
 unsigned y;if(w>512 || h>512)return (unsigned short*)src;
 for(y=0;y<h;y++)memcpy(br_output+y*w,(const unsigned char*)src+y*pitch,w*2);
 if(BR_LOAD){
  memset(br_output,0,w*(h+32)*2);
  br_text(w,72,h/2,"LOADING LEVEL",BUILD_PIXEL(25,28,31));
  return br_output;
 }
 if(br.active){
  unsigned blue=BUILD_PIXEL(5,17,31),white=BUILD_PIXEL(25,28,31);
  if(br_r16(0x9a)==2){
   int a=(short)br_r16(0x328),b=(short)(br.p2.obj[8]|br.p2.obj[9]<<8);
   if(a<0 || a>255)br_text(w,a<0?4:w-48,40,a<0?"P1 LEFT":"P1 RIGHT",white);
   if(b<0 || b>255)br_text(w,b<0?4:w-48,50,b<0?"P2 LEFT":"P2 RIGHT",blue);
  }
 }
 memmove(br_output+32*w,br_output,h*w*2);
 memset(br_output,0,w*32*2);
 if(br.active && h>=40)memset(br_output+32*w,0,w*16*2);
 br_top_hud(w);
 br_boss_bar(w,h);
 br_p2_weapon_hud(w);
 br_menu_draw(w,h);
 return br_output;
}
unsigned char* br_graphics(void){return br.visible_tiles;}
/* Grounded poses contain their oval shadow in the body tiles (ink 2).
 * Reuse the saved pixel mask only for that ink at the ground line, never
 * for a rectangular suit region. Airborne shadows keep native rendering. */
void br_material(unsigned tile,unsigned char*cache){
 unsigned i;for(i=0;i<64;i++)if(cache[i]==2 && br.visible_gray[(tile>>5)*64+i])cache[i]=18;
}
static void br_ground_shadow(unsigned last){
 unsigned s,x,y;int feet=(short)(br.p2.obj[12]|br.p2.obj[13]<<8);
 int center=(short)(br.p2.obj[8]|br.p2.obj[9]<<8);
 memset(br.gray,0,sizeof(br.gray));
 if((br_r16(0x9a)!=1 && br_r16(0x9a)!=2) || !(br.p2.obj[0x90]|br.p2.obj[0x91]))return;
 for(s=0;s<last && s<128;s++){
  unsigned a=0x100+s*4,attr=Memory.RAM[a+3],name=Memory.RAM[a+2]|((attr&1)<<8);
  unsigned hi=(Memory.RAM[0x300+s/4]>>((s%4)*2))&3,size=(hi&2)?16:8;
  int px=Memory.RAM[a]-(hi&1?256:0),py=Memory.RAM[a+1];
  for(y=0;y<size;y++)for(x=0;x<size;x++){
   int xx=px+x,yy=(py+y)&255;
   unsigned tx,ty,tile,addr,k,ink;
   if(yy<feet-3 || yy>feet || xx<center-24 || xx>center+32)continue;
   tx=(attr&0x40)?size-1-x:x;ty=(attr&0x80)?size-1-y:y;
   tile=(name&0x100)|((name+(ty/8)*16)&0xf0)|((name+tx/8)&15);
   addr=(PPU.OBJNameBase+tile*32+(tile>=256?PPU.OBJNameSelect:0))&65535;
   k=7-(tx&7);
   ink=((br.tiles[addr+(ty&7)*2]>>k)&1)|(((br.tiles[addr+(ty&7)*2+1]>>k)&1)<<1)|
       (((br.tiles[addr+(ty&7)*2+16]>>k)&1)<<2)|(((br.tiles[addr+(ty&7)*2+17]>>k)&1)<<3);
   if(ink==2)br.gray[(addr>>5)*64+(ty&7)*8+(tx&7)]=1;
  }
 }
 memset(br_tile_cached,0,sizeof(br_tile_cached));
}
int br_sprite(unsigned s){return br.active && s<256 ? br_draw_blue[s] : 0;}
void br_commit_oam(void){br_extra.live=br_extra.pending;IPPU.OBJChanged=true;memcpy(br.live,br.pending,128);memcpy(br.visible_tiles,br.tiles,65536);memcpy(br.visible_gray,br.gray,131072);memset(br_tile_cached,0,sizeof(br_tile_cached));memset(br_effect_cached,0,sizeof(br_effect_cached));}
static void br_draw_player(unsigned marker){
 BRPlayer p1;unsigned i;
   unsigned anchor=(br_r16(0)-0x100)/4,last,carry,slot=marker>=0x10000?(marker&0xffff):marker==0xff04?0x410:(marker==0x320 || marker==0xff00)?0x320:(marker==0xff01 || marker==0xff05)?0x460:marker==0xff03?0x500:0x4b0;
   unsigned char oam[544],work[32],third[0x50];
   memcpy(third,Memory.RAM+0x500,0x50);if(marker==0xff03)memcpy(Memory.RAM+0x500,br_extra.third,0x50);
   memcpy(oam,Memory.RAM+0x100,sizeof(oam));memcpy(work,Memory.RAM,32);
   br_w16(0,0x100);br_w16(2,0x300);Memory.RAM[0x1e]=0x80;
   br_capture(&p1);if(marker!=0x320)br_install(&br.p2);
   if(!br_r16(slot) || (br_r16(0x9a)==2 && ((short)br_r16(slot+8)<-96 || (short)br_r16(slot+8)>352))){br_install(&p1);memcpy(Memory.RAM,work,32);memcpy(Memory.RAM+0x500,third,0x50);return;}
   ICPU.Registers.X.W=slot;ICPU.Registers.Y.W=br_r16(slot);ICPU._Negative=(br_r16(slot)&0x8000)?0x80:0;
   carry=br_run(0x80947a,0x80947e);br_install(&p1);memcpy(Memory.RAM+0x500,third,0x50);
   last=carry?128:(br_r16(0)-0x100)/4;
   /* Finish the builder's partial high-OAM byte before decoding it. */
   if(!carry && Memory.RAM[0x1e]!=0x80){unsigned v=Memory.RAM[0x1e];while(v && !(v&2))v>>=2;Memory.RAM[br_r16(2)]=v>>2;}
   if(marker==0xff00)br_ground_shadow(last);
   for(i=0;i<last && br_extra.pending.count<128;i++){
    unsigned n=br_extra.pending.count++,a=0x100+i*4,attr=Memory.RAM[a+3],hi=(Memory.RAM[0x300+i/4]>>((i%4)*2))&3;
    SOBJ*o=&br_extra.pending.obj[n];memset(o,0,sizeof(*o));
    o->HPos=Memory.RAM[a]-(hi&1?256:0);o->VPos=Memory.RAM[a+1];o->Name=Memory.RAM[a+2]|((attr&1)<<8);
    o->Palette=(attr>>1)&7;o->Priority=(attr>>4)&3;o->HFlip=(attr>>6)&1;o->VFlip=attr>>7;o->Size=(hi>>1)&1;
    br_extra.pending.anchor[n]=anchor;br_extra.pending.blue[n]=(marker==0xff00 || marker==0xff05)?1:(marker==0xff04 || marker>=0x10000)?2:0;
   }
   memcpy(Memory.RAM+0x100,oam,sizeof(oam));memcpy(Memory.RAM,work,32);

}
/* Rope segments are generated by the ROM into shared effect slots. Build
 * P2's segments only while drawing, then restore P1's original effect list. */
static void br_draw_side_hook(void){
 BRPlayer p1;unsigned char effects[0x640],work[32];unsigned slot;
 br_draw_player(0xff04);
 if(!br.p2.obj[0xca] && !br.p2.obj[0xcb])return;
 memcpy(effects,Memory.RAM+0xeb0,sizeof(effects));memcpy(work,Memory.RAM,32);
 br_capture(&p1);br_install(&br.p2);
 /* Preserve native tile/palette metadata in each effect slot. The rope
  * builder only writes geometry; zeroing whole slots selects Batman tiles. */
 for(slot=0xeb0;slot<0x14f0;slot+=0x50)br_w16(slot,0);
 {unsigned db=ICPU.Registers.DB,shifted=ICPU.ShiftedDB;ICPU.Registers.DB=0x81;ICPU.ShiftedDB=0x810000;
  br_run(0x80aeda,0x80aede);ICPU.Registers.DB=db;ICPU.ShiftedDB=shifted;}
 br_capture(&br.p2);br_install(&p1);
 memcpy(Memory.RAM,work,32);
 for(slot=0xeb0;slot<0x14f0;slot+=0x50)if(br_r16(slot))br_draw_player(0x10000+slot);
 memcpy(Memory.RAM+0xeb0,effects,sizeof(effects));
}
/* Swap projectile ownership without a transient, unsaved backup. */
static void br_swap_side_projectiles(void){
 unsigned i;unsigned char v;
 for(i=0;i<0xa0;i++){v=Memory.RAM[0x460+i];Memory.RAM[0x460+i]=br.p2.obj[0x140+i];br.p2.obj[0x140+i]=v;}
 for(i=0;i<0x50;i++){v=Memory.RAM[0x500+i];Memory.RAM[0x500+i]=br_extra.third[i];br_extra.third[i]=v;}
}
static void br_arrival_begin(void){
 br.active=0;br.owner[12]=1;br.stage=br_r16(0x76);
 memset(&br_extra.pending,0,sizeof(br_extra.pending));memset(&br_extra.live,0,sizeof(br_extra.live));
 memset(br.pending,0,sizeof(br.pending));memset(br.live,0,sizeof(br.live));
 memset(br_extra.third,0,sizeof(br_extra.third));br.owner[10]=br.owner[11]=0;br_extra.terrain_stage=0;
 IPPU.OBJChanged=true;
}
static void br_prepare_arrival(void){
 /* A saved transition may spend several frames waiting without executing
  * the normal player or draw loops. Remove stale private OAM immediately. */
 if(br_supported && !br.owner[12] && br_r16(0x32)==6 && br_r16(0x6a)==1 &&
    br_r16(0x35c)==2 && br_r16(0x350)==0x19 && !br_r16(0x3b0))br_arrival_begin();
}
static void br_arrival_pose(void){
 /* Reuse the native arrival pose, but never run its world/script effects
  * twice. P2 becomes independently controlled when the arrival has landed. */
 br_capture(&br.p2);
 if(br_r16(0x9a)==2)br_shift_grappler(br.p2.obj,-40);
 else {unsigned x=br_r16(0x328)-40;br.p2.obj[8]=x;br.p2.obj[9]=x>>8;}
 br.p2.obj[0x58]=br.p2.obj[8];
 br_upload();br.active=br_r16(0x320)!=0;
}
static int br_scripted_walk(void){
 return br_supported && br_r16(0x32)==6 && br_r16(0x9a)==1 &&
  br_r16(0xd6) && br_r16(0x35c)==2 && br_r16(0x320);
}
static void br_scripted_pose(void){
 unsigned x=br_r16(0x328)-40;
 /* The timed native script owns movement and animation. Keep inventory,
  * health and projectile contexts private; mirror only the actor pose. */
 memcpy(br.p2.obj,Memory.RAM+0x320,0x140);
 br.p2.obj[8]=x;br.p2.obj[9]=x>>8;br.p2.obj[0x58]=x;
 br_upload();
}
static unsigned br_vehicle_word(unsigned a){return br.p2.obj[a-0x320]|br.p2.obj[a-0x31f]<<8;}
static void br_vehicle_set(unsigned a,unsigned v){br.p2.obj[a-0x320]=v;br.p2.obj[a-0x31f]=v>>8;}
static void br_vehicle_position(void){
 int lane=br_vehicle_word(0x328),view=br_r16(0x328);
 if(lane<view-80)lane=view-80;
 if(lane>view+80)lane=view+80;
 if(lane<400)lane=400;
 if(lane>624)lane=624;
 br_vehicle_set(0x328,lane);
 br_vehicle_set(0x468,128+lane-view);
}
static void br_prepare_vehicle(void){
 if(!br_supported)return;
 if(br_r16(0x32)!=6 || br_r16(0x9a)!=0 || br_r16(0x76)!=12){
  br.owner[13]=0;return;
 }
 if(!br_r16(0x460))return;
 if(!br.owner[13]){
  br_capture(&br.p2);br.p2.hp=80;br.spawn=br.p2;
  br_vehicle_set(0x328,br_r16(0x328)+72);
  memset(br.p2.obj+0x190,0,0x50);memset(br_extra.third,0,0x50);
  memset(&br_extra.pending,0,sizeof(br_extra.pending));memset(&br_extra.live,0,sizeof(br_extra.live));
  memset(br.pending,0,128);memset(br.live,0,128);memset(br.gray,0,sizeof(br.gray));
  br.owner[12]=br.owner[14]=br.owner[15]=0;br.owner[13]=1;br.stage=12;br.active=1;
 }
 /* Fresh races have a native vehicle entrance before driving state zero.
  * Follow that shared script, then release P2 to independent control. */
 if(br_vehicle_word(0x49c)>=6)
  memcpy(br.p2.obj+0x140,Memory.RAM+0x460,0x50);
 if(!br_r16(0x49c))memcpy(br.spawn.obj+0x140,Memory.RAM+0x460,0x50);
 br_vehicle_position();
}
static void br_vehicle_update(void){
 BRPlayer p1;unsigned char globals[256],third[0x50],thunk[4];
 unsigned held=br.buttons,edge=held&~br.previous;
 br.previous=held;br_capture(&p1);br.ai_saved=p1;
 memcpy(globals,Memory.RAM,256);memcpy(third,Memory.RAM+0x500,0x50);
 memcpy(thunk,Memory.RAM+0x1ef0,4);
 br_install(&br.p2);memcpy(Memory.RAM+0x500,br_extra.third,0x50);
 br_w16(0xb2,br.p2.obj[0x20]);
 /* Road ring cursors and speed are shared, unlike walking timers. */
 memcpy(Memory.RAM+0x9c,globals+0x9c,2);
 br_w16(0xd8,held);br_w16(0xda,edge);br_second=1;
 br_run(0x84dfa9,0x84dfac);
 Memory.RAM[0x1ef0]=0x22;Memory.RAM[0x1ef1]=0x54;
 Memory.RAM[0x1ef2]=0xe5;Memory.RAM[0x1ef3]=0x84;
 if(br_r16(0x49c)<3)br_run(0x7e1ef0,0x7e1ef4);
 Memory.RAM[0x340]=Memory.RAM[0xb2];
 br_capture(&br.p2);memcpy(br_extra.third,Memory.RAM+0x500,0x50);
 br_second=0;br_install(&p1);memcpy(Memory.RAM,globals,256);
 memcpy(Memory.RAM+0x500,third,0x50);memcpy(Memory.RAM+0x1ef0,thunk,4);
 /* Respawn only the destroyed car; the shared race keeps running. */
 if(!br.p2.hp && br_r16(0x8c)>1){
  unsigned lane=br_vehicle_word(0x328);br_w16(0x8c,br_r16(0x8c)-1);
  br.p2=br.spawn;br.p2.hp=80;br_vehicle_set(0x328,lane);
  br_vehicle_set(0x49c,2);br_vehicle_set(0x490,32);
  memset(br_extra.third,0,0x50);
 }
 br_vehicle_position();br.frames++;
}
static void br_vehicle_swap_shots(void){
 unsigned i;unsigned char v;
 for(i=0;i<0x50;i++){
  v=Memory.RAM[0x4b0+i];Memory.RAM[0x4b0+i]=br.p2.obj[0x190+i];br.p2.obj[0x190+i]=v;
  v=Memory.RAM[0x500+i];Memory.RAM[0x500+i]=br_extra.third[i];br_extra.third[i]=v;
 }
}
/* Enemy reads of the native tube phase must see either player's blast.
 * Observe the completed LDA so its emulated timing and private state remain
 * native. Ordinary attacks and the nearer-player AI context are untouched. */
static void br_tube_enemy_read(unsigned pc){
 unsigned own,other,phase;
 switch(pc){
  case 0x80f17b:case 0x80f2a7:case 0x80f2dc:case 0x82b413:case 0x82b422:
  case 0x82b5ed:case 0x82b5fb:case 0x82b613:case 0x82b621:case 0x82b6d4:
  case 0x82c015:case 0x82c02b:case 0x82c438:case 0x82c4af:case 0x82c526:
  case 0x82c5ce:case 0x82c969:case 0x82cc29:case 0x82cc47:case 0x82cc86:
  case 0x82ce2b:case 0x82ce50:case 0x82ce99:case 0x82ced3:case 0x82cef4:
  case 0x82d0bc:case 0x82da58:case 0x82db4c:case 0x82dbdd:case 0x82dc25:
  case 0x82de09:case 0x82eec7:case 0x82f31b:case 0x82f5b2:case 0x839031:
  case 0x839073:case 0x839287:case 0x8397f8:case 0x83982b:case 0x839f53:
  case 0x83a21d:case 0x83ab25:case 0x83af4e:case 0x83b1ca:case 0x83b324:
  case 0x83b394:case 0x83c360:case 0x83c47c:case 0x83c494:case 0x83cecd:
  case 0x83ceea:case 0x83d3e1:case 0x83d44b:case 0x83e975:case 0x83ea4e:
  case 0x83f6c1:case 0x83f816:case 0x83f8f1:case 0x83f925:case 0x83f9fc:
  case 0x83fa5e:case 0x83faa6:case 0x83fadc:case 0x83fb22:case 0x83fb42:
  case 0x83fb4f:case 0x8481f5:case 0x848526:case 0x84942d:case 0x849940:
  case 0x849f42:case 0x84a206:case 0x84a35b:case 0x84a3f6:case 0x84a45d:
  case 0x84a4af:case 0x84a52a:case 0x84a593:case 0x84a6e8:case 0x84af6a:
  case 0x84b4f7:case 0x84b88f:case 0x84bd0e:case 0x84bf4b:case 0x84c705:
  case 0x84ce53:case 0x87f3a5:case 0x87fb52:case 0x87fbcc:case 0x87fc5e:
  break;
  default:return;
 }
 own=br_r16(0x402);
 other=br.ai?(br.ai_saved.obj[0xe2]|br.ai_saved.obj[0xe3]<<8):
             (br.p2.obj[0xe2]|br.p2.obj[0xe3]<<8);
 /* The one-frame initial blast starts native enemy reactions. Afterwards
  * keep checks active until the last player's explosion has finished. */
 phase=own==1 || other==1?1:!own?other:!other?own:own<other?own:other;
 if(ICPU.Registers.P.W&0x20){
  ICPU.Registers.A.B.l=phase;ICPU._Zero=(unsigned char)phase;ICPU._Negative=(unsigned char)phase;
 }else{
  ICPU.Registers.A.W=phase;ICPU._Zero=phase!=0;ICPU._Negative=phase>>8;
 }
}
static void br_game_hook(unsigned pc){
 BRPlayer p1;unsigned char scratch[32],inputs[4];unsigned i;
 if(br_inside || !br_supported)return;
 if(pc==0x808492)br_cheat_load_level();
 br_cheat_stage_hook(pc);
 if(pc==0x808492 || pc==0x80ae91 || pc==0x80944e)br_prepare_vehicle();
 if(br.owner[13]){
  if(pc==0x80ae91 && !br_r16(0x6a))br_vehicle_update();
  if((BR_CHEATS&BR_ONEHIT) && (pc==0x84ee95 || pc==0x84eeeb || pc==0x84fa57 || pc==0x84faab))
   br_w16(ICPU.Registers.X.W+0x26,1);
  /* Native traffic checks use a centred car. Translate the same check
   * for P2 only after P1 misses; retain the native enemy response. */
  if(pc==0x84ee4f || pc==0x84f441 || pc==0x84f229 || pc==0x84f4d9){
   int x=(short)br_r16(ICPU.Registers.X.W+8),width=pc==0x84f229?16:pc==0x84f4d9?24:32;
   br.owner[15]=0;
   if((br_r16(0x49c) || x<128-width || x>128+width) &&
      !br_vehicle_word(0x49c) && abs(x-(int)br_vehicle_word(0x468))<=width){
    br.owner[15]=1;ICPU.Registers.A.W=0;ICPU._Zero=0;ICPU._Negative=0;br_jump(pc+3);
   }
  }
  if(br.owner[15] && (pc==0x84ee57 || pc==0x84f449 || pc==0x84f231 || pc==0x84f4e1))
   ICPU.Registers.A.W+=128-br_vehicle_word(0x468);
  if(pc==0x84e810 && br.owner[15]){
   br_vehicle_set(0x49c,1);br.owner[15]=0;br_jump(0x84e818);return;
  }
  /* On a native missile miss, run the same hit response for P2's pair.
   * Restore ownership at either return, including saves inside the scan. */
  if((br.owner[14]==1 && (pc==0x84eeca || pc==0x84ef20)) ||
     (br.owner[14]==2 && (pc==0x84fa88 || pc==0x84fadc))){
   br_vehicle_swap_shots();br.owner[14]=0;
  }else if((pc==0x84ef20 || pc==0x84fadc) && !br.owner[14] &&
           (br_vehicle_word(0x4c0) || (br_extra.third[16]|br_extra.third[17]<<8))){
   br_vehicle_swap_shots();br.owner[14]=pc==0x84fadc?2:1;
   br_jump(pc==0x84fadc?0x84fa35:0x84ee75);return;
  }
  if(pc==0x80944e){
   br_extra.pending.count=0;memset(br.pending,0,128);
   memcpy(br.tiles,Memory.VRAM,65536);memset(br_tile_cached,0,sizeof(br_tile_cached));
  }
  if(pc==0x809474 && br_r16(ICPU.Registers.Y.W)==0x460){
   SICPU saved=ICPU;br_draw_player(0xff05);br_draw_player(0xff02);br_draw_player(0xff03);ICPU=saved;
  }
  return;
 }
 if(pc==0x80bf33 || pc==0x80c8d8)br_arrival_begin();
 /* Older saves can already be inside a scripted entrance with a stale P2. */
 if((pc==0x808492 || pc==0x80af04 || pc==0x80aebe || pc==0x80944e) && br_r16(0x32)==6 && br_r16(0x6a)==1 &&
    br_r16(0x35c)==2 && br_r16(0x350)==0x19 && !br_r16(0x3b0) && !br.owner[12])br_arrival_begin();
 /* Old co-op saves can be inside the OAM tail's sentinel-shift loop after
  * a discarded sprite-builder carry. The final high-OAM byte was already
  * written; take the same full-buffer exit that the builder requested. */
 if(br.active && pc>=0x8094ae && pc<=0x8094b0 &&
    !ICPU.Registers.A.B.l && !Memory.RAM[0x1e] && br_r16(2)==0x31f){
  br_jump(0x8094cf);return;
 }
 if(pc==0x808492 && (br_r16(0x32)!=6 || (br_r16(0x6a)>=8 && !br_scripted_walk())))br.active=0;
 if(br.owner[12] && (pc==0x80af08 || pc==0x80aec2 || pc==0x80af18 ||
    pc==0x80aeca || pc==0x80aece || pc==0x80944e)){
  br_arrival_pose();
  if((pc==0x80af08 || pc==0x80aec2) && br_r16(0x35c)==2 &&
     br_r16(0x3b0) && !br_r16(0x6a) && br_r16(0x350)<0x14){
   br.owner[12]=0;br_capture(&br.spawn);
  }else if(pc!=0x80944e)return;
 }
 if(pc==0x80af04 || pc==0x80aebe){
  if(pc==0x80aebe)br_fire_keep_visible();
  if(br.active && br.stage!=br_r16(0x76))br.active=0;
  if(!br.owner[12] && !br.active && br_r16(0x35c)==2 && br_r16(0x3b0)){
   br.active=1;br.stage=br_r16(0x76);br_capture(&br.p2);memset(br_extra.third,0,0x50);
   br.owner[10]=br.owner[11]=0;br_extra.terrain_stage=0;
   br.spawn=br.p2;
   br.p2.obj[8]=Memory.RAM[0x328]>80?Memory.RAM[0x328]-40:Memory.RAM[0x328]+40;
   br.p2.obj[0x58]=br.p2.obj[8];
   memcpy(br.tiles,Memory.VRAM,65536);
  }
 }
 if(!br.active)return;
 if(br_scripted_walk() && !br.owner[12] && !br.ai){
  if(pc==0x80944e)br_scripted_pose();
  /* Do not replay the native script or replace its forced movement with
   * controller input. Only private sprite construction runs for P2. */
  else if(pc!=0x809474 && pc!=0x8094d8)return;
 }
 if(!br.owner[12])br_tube_enemy_read(pc);
 if(br.owner[12] && pc!=0x80944e && pc!=0x809474 && pc!=0x8094d8)return;
 /* The native section-three controller owns the vertical floor collapse.
  * Record its allocated slot rather than assuming a fixed object address. */
 if(pc==0x83a3de && br.stage==3){
  unsigned slot=ICPU.Registers.X.W;
  br.owner[11]=br_r16(slot+0x42)==2?slot:0;
 }
 /* Elevator/platform sections can leave one player below the shared view.
  * Rejoin a grounded partner using their valid native platform context. Keep
  * each player's inventory, health and projectile slots independent. */
 if(pc==0x80aebe && br_r16(0x9a)==2){
  int y1=(short)br_r16(0x32c),y2=(short)(br.p2.obj[12]|br.p2.obj[13]<<8);
  if(br_r16(0x76)==3 && Memory.RAM[0x350]==0x18 && y1>256 && y2>=32 && y2<=224 && br.p2.obj[0x90] && br.p2.obj[0x30]<3){
   memcpy(Memory.RAM+0x320,br.p2.obj,0x140);
   {int dx=br_r16(0x328)<216?24:-24;br_w16(0x328,br_r16(0x328)+dx);br_w16(0x358,br_r16(0x358)+dx);}
  }else if(br_r16(0x76)==3 && br.p2.obj[0x30]==0x18 && y2>256 && y1>=32 && y1<=224 && Memory.RAM[0x3b0] && Memory.RAM[0x350]<3){
   memcpy(br.p2.obj,Memory.RAM+0x320,0x140);memcpy(br.tiles,Memory.VRAM,65536);
   {int dx=br_r16(0x328)>40?-24:24,x=br_r16(0x328)+dx,a=br_r16(0x358)+dx;br.p2.obj[8]=x&255;br.p2.obj[9]=x>>8;br.p2.obj[0x38]=a&255;br.p2.obj[0x39]=a>>8;}
  }
  /* Older invulnerability builds zeroed the terminal fall countdown. */
  if(Memory.RAM[0x350]==0x18 && !br_r16(0x3f8))br_w16(0x3f8,2);
  if(br.p2.obj[0x30]==0x18 && !br.p2.obj[0xd8] && !br.p2.obj[0xd9])br.p2.obj[0xd8]=2;
 }
 /* The enemy's native scan checks P1 first, then P2 on a miss. Keep the
  * real hit response and consume only the projectile belonging to its owner. */
 if(br_r16(0x9a)==2){
  if(pc==0x80f01e && !br.owner[9]){br_swap_side_projectiles();br.owner[9]=1;br_jump(0x80efe2);return;}
  if(br.owner[9] && (pc==0x80f012 || pc==0x80f020)){br_swap_side_projectiles();br.owner[9]=0;}
 }
 if(pc==0x838c86 && br_r16(0x9a)==2){
  unsigned char hook[0x50];
  memcpy(hook,Memory.RAM+0x410,0x50);memcpy(Memory.RAM+0x410,br.p2.obj+0xf0,0x50);
  br_swap_side_projectiles();memcpy(scratch,Memory.RAM,32);
  {unsigned x=ICPU.Registers.X.W;ICPU.Registers.X.W=0x3c0;br_run(0x838c7b,0x838c86);ICPU.Registers.X.W=x;}
  memcpy(Memory.RAM,scratch,32);br_swap_side_projectiles();
  memcpy(br.p2.obj+0xf0,Memory.RAM+0x410,0x50);memcpy(Memory.RAM+0x410,hook,0x50);
 }
 /* Earlier midpoint-camera builds could pass the first encounter lock and
  * fill all three event slots with mutually waiting scripts. These spare
  * slots are already visited by the native event-update loop. */
 if(pc==0x828547 && br.version<2 && br.stage==0 && Memory.RAM[0xa0] && br_r16(0x17a0)>0x302){
  unsigned slot;
  for(slot=0x1090;slot<0x11d0;slot+=0x50)if(!br_r16(slot+0x10)){
   ICPU.Registers.X.W=slot;br_jump(0x828527);return;
  }
 }
 if(pc==0x80af08 || pc==0x80aec2){
  if(pc==0x80aec2){br.owner[10]=br_free_camera();br_remember_terrain();}
  unsigned char third[0x50];unsigned scroll=br_r16(0x17a4),vertical=br_r16(0x17b4),vertical2=0;br_capture(&p1);br.ai_saved=p1;memcpy(scratch,Memory.RAM,32);memcpy(inputs,Memory.RAM+0xd8,4);
  br_install(&br.p2);
  /* Scripted side-view scenes supply their own shared controller input. */
  if(!(pc==0x80aec2 && br_r16(0xd6))){br_w16(0xd8,br_map_buttons(br.buttons));br_w16(0xda,br_map_buttons(br.buttons&~br.previous));}
  br.previous=br.buttons;
  if(pc==0x80aec2){br_w16(0x17b4,0);memcpy(third,Memory.RAM+0x500,0x50);memcpy(Memory.RAM+0x500,br_extra.third,0x50);}
  br_second=1;br_run(pc==0x80aec2?0x80aebe:0x80af04,pc);br_second=0;br_upload();br_capture(&br.p2);
  if(pc==0x80aec2){vertical2=br_r16(0x17b4);memcpy(br_extra.third,Memory.RAM+0x500,0x50);memcpy(Memory.RAM+0x500,third,0x50);}
  br_install(&p1);memcpy(Memory.RAM,scratch,32);memcpy(Memory.RAM+0xd8,inputs,4);br_w16(0x17a4,scroll);br.frames++;
  if(pc==0x80aec2){
   int dy=(short)vertical;
   if(!br_r16(0xd6) && !(Memory.RAM[0xa0]&0x0c) &&
      !(br.stage==3 && br_r16(0x17a0)==0xe00 && br.owner[11] && br_r16(br.owner[11]+0x42)==2)){
    int y1=(short)br_r16(0x32c),y2=(short)(br.p2.obj[12]|br.p2.obj[13]<<8),mid=(y1+y2)/2;
    dy=0;
    /* One shared vertical target, with a dead band. Reusing P1's request
     * during the P2 pass made the native five-pixel corrections alternate. */
    if(mid<172 && ((short)vertical<0 || (short)vertical2<0))dy=mid<170?-2:mid-172;
    if(mid>180 && ((short)vertical>0 || (short)vertical2>0))dy=mid>182?2:mid-180;
   }
   br_w16(0x17b4,dy);
  }

  {int x1=(short)br_r16(0x328),x2=(short)(br.p2.obj[8]|br.p2.obj[9]<<8);
   int free=pc==0x80aec2 && br_free_camera(),mid=(x1+x2)/2,delta=0;
   if(free){
    /* Fit both players when possible. When separated, follow the player
     * advancing beyond the viewport without moving their partner's body. */
    int left=x1<x2?x1:x2,right=x1>x2?x1:x2;
    if(right-left>184){
     if(right>200)mid=right-72;
     else if(left<56 && right<120)mid=left+72;
     else mid=128;
    }
   }
   if(mid>136 && !(Memory.RAM[0x9e]&1))delta=mid-136>(free?8:2)?(free?8:2):mid-136;
   if(mid<120 && !(Memory.RAM[0x9e]&2))delta=mid-120<-(free?8:2)?-(free?8:2):mid-120;
   if(!free && ((delta>0 && (x1<26 || x2<26)) || (delta<0 && (x1>230 || x2>230))))delta=0;
   /* Native encounter/cutscene locks own the camera while A0 is nonzero.
    * Preserve the native scripted displacement instead of scrolling past
    * actors which must finish before the next event can be allocated. */
   /* Side-view A0 bit 1 is its normal mode, not a camera lock.
    * Only the belt-scrolling path uses any nonzero A0 as a lock. */
   if(br_r16(0x9a)==1 && Memory.RAM[0xa0])delta=(short)scroll;
   if(br_r16(0x9a)==2 && ((Memory.RAM[0xa0]&0x30) || br_r16(0xd6)))delta=(short)scroll;
   if(br_r16(0x9a)==2 && br_r16(0xd6)){
    /* Scripted pans must finish even when a co-op player starts near an edge.
     * Carry edge players with the pan rather than stopping the scene or wrapping. */
    int x,shift;
    if(br_r16(0x19c0))delta=(short)br_r16(0x19c0);
    else {
     /* Walk-off scripts use forced input, not the automatic-pan register.
      * Recover a saved player already at the edge by following the walk. */
     unsigned held=inputs[0]|inputs[1]<<8;
     if((held&0x0100) && br_r16(0x328)>136 && !(Memory.RAM[0x9e]&1))delta=2;
     if((held&0x0200) && br_r16(0x328)<120 && !(Memory.RAM[0x9e]&2))delta=-2;
    }
    x=br_r16(0x328);shift=x-delta<16?16+delta-x:x-delta>240?240+delta-x:0;
    br_w16(0x328,x+shift);br_w16(0x358,br_r16(0x358)+shift);
    x=br.p2.obj[8]|br.p2.obj[9]<<8;shift=x-delta<16?16+delta-x:x-delta>240?240+delta-x:0;
    br.p2.obj[8]=(x+shift)&255;br.p2.obj[9]=(x+shift)>>8;
    x=(br.p2.obj[0x38]|br.p2.obj[0x39]<<8)+shift;br.p2.obj[0x38]=x&255;br.p2.obj[0x39]=x>>8;
   }
   br_w16(0x17a4,delta);
  }
 }
 if(pc==0x84828b || pc==0x8482d1 || pc==0x848317){
  int ex=(short)br_r16(ICPU.Registers.X.W+8),ey=(short)br_r16(ICPU.Registers.X.W+0x18);
  int x1=(short)br_r16(0x328)-ex,y1=(short)br_r16(0x338)-ey;
  int x2=(short)(br.p2.obj[8]|br.p2.obj[9]<<8)-ex,y2=(short)(br.p2.obj[0x18]|br.p2.obj[0x19]<<8)-ey;
  if(x2*x2+y2*y2<x1*x1+y1*y1){br_capture(&br.ai_saved);br_install(&br.p2);br.ai=1;}
 }
 if(br.ai && (pc==0x84828f || pc==0x8482d5 || pc==0x84831b)){
  br_capture(&br.p2);br_install(&br.ai_saved);br.ai=0;
 }
 if(pc==0x80aeca){
  br_capture(&p1);memcpy(scratch,Memory.RAM,32);br_install(&br.p2);
  br_run(0x80aec6,0x80aeca);br_capture(&br.p2);br_install(&p1);memcpy(Memory.RAM,scratch,32);
  br_grapple_catch_up();
 }
 if(pc==0x80aece){
  unsigned char third[0x50];
  br_capture(&p1);memcpy(scratch,Memory.RAM,32);memcpy(third,Memory.RAM+0x500,0x50);
  br_install(&br.p2);memcpy(Memory.RAM+0x500,br_extra.third,0x50);
  br_run(0x80aeca,0x80aece);br_capture(&br.p2);memcpy(br_extra.third,Memory.RAM+0x500,0x50);
  br_install(&p1);memcpy(Memory.RAM,scratch,32);memcpy(Memory.RAM+0x500,third,0x50);
 }
 if(pc==0x80af18){
  unsigned char shadow[0x50];memcpy(shadow,Memory.RAM+0x4b0,0x50);
  br_capture(&p1);memcpy(scratch,Memory.RAM,32);br_install(&br.p2);
  br_run(0x80af0c,0x80af18);br_capture(&br.p2);br_install(&p1);memcpy(Memory.RAM,scratch,32);memcpy(Memory.RAM+0x4b0,shadow,0x50);
 }
 if(pc==0x848279){br_capture(&p1);memcpy(scratch,Memory.RAM,32);br_install(&br.p2);br_run(0x848243,0x848279);br_capture(&br.p2);br_install(&p1);memcpy(Memory.RAM,scratch,32);}
 if(pc==0x80944e){
  /* Shared object updates can still displace a swinging body after the
   * player/camera passes. Enforce visibility before building either OAM. */
  br_fire_keep_visible();
  unsigned count=0,j,k;unsigned entries[48],depths[48];
  memset(br.pending,0,128);br_extra.pending.count=0;
  while(count<48 && br_r16(0x15b0+count*2)){entries[count]=br_r16(0x15b0+count*2);depths[count]=br_r16(entries[count]+14);count++;}
  if((br_r16(0x58)&0x8000) && br_r16(0x9a)==1 && !br.owner[12]){
   for(k=0;k<3;k++){
    unsigned off=k==0?0:k==1?0x140:0x190;
    if(!br.p2.obj[off]&&!br.p2.obj[off+1])continue;
    if(count==48)break;
    {unsigned depth=br.p2.obj[off+14]|br.p2.obj[off+15]<<8;
     for(j=count;j>0 && depths[j-1]<depth;j--){entries[j]=entries[j-1];depths[j]=depths[j-1];}
     entries[j]=0xff00+k;depths[j]=depth;count++;
    }
   }
   for(j=0;j<48;j++)br_w16(0x15b0+j*2,j<count?entries[j]:0);
  }
 }
 if(pc==0x8094d8 && br_r16(0x9a)==2 && ICPU.Registers.Y.W>=0x15b0 && ICPU.Registers.Y.W<0x1622 && br_r16(ICPU.Registers.Y.W)==0x320){
  if(br.owner[12]){SICPU saved=ICPU;br_draw_player(0xff00);br_draw_side_hook();ICPU=saved;return;}
  br_draw_player(0x320);br_draw_player(0xff00);
  br_draw_player(0xff01);br_draw_player(0xff02);br_draw_player(0xff03);br_draw_side_hook();
  br_jump(0x8094e6);
 }
 if(pc==0x809474 && ICPU.Registers.Y.W>=0x15b0 && ICPU.Registers.Y.W<0x1610){
  unsigned marker=br_r16(ICPU.Registers.Y.W);
  if(br.owner[12] && marker==0x320){SICPU saved=ICPU;br_draw_player(0xff00);if(br_r16(0x9a)==2)br_draw_side_hook();ICPU=saved;return;}
  if(marker==0x320 || (marker>=0xff00 && marker<=0xff02)){
   br_draw_player(marker);
   if(marker==0x320 && br_r16(0x9a)==2){br_draw_player(0xff00);br_draw_player(0xff01);br_draw_player(0xff02);br_draw_player(0xff03);br_draw_side_hook();}
   br_jump(0x80947e);ICPU._Carry=0;
  }
 }

}
__declspec(dllexport) void br_start_trace(const char *path,unsigned n,unsigned watch){
 if(br_trace)fclose(br_trace);
 br_trace=fopen(path,"w");br_trace_left=n;br_watch_addr=watch;br_last=0xffffffff;
}
__declspec(dllexport) void br_stop_trace(void){if(br_trace)fclose(br_trace);br_trace=0;}
__declspec(dllexport) unsigned char *br_vram(void){return Memory.VRAM;}
__declspec(dllexport) unsigned short *br_palette(void){return PPU.CGDATA;}
static void br_hook(void){
 unsigned pc=ICPU.ShiftedPB+(unsigned)(CPU.PC-CPU.PCBase);
 br_game_hook(pc);
 br_death(pc);
 if(br_trace && br_trace_left){
  unsigned v=Memory.RAM[br_watch_addr]|Memory.RAM[br_watch_addr+1]<<8;
  if(br_watch_addr==0 || v!=br_last){
   S9xPackStatus();
   fprintf(br_trace,"%06X %02X %02X %02X %02X A=%04X X=%04X Y=%04X D=%04X S=%04X P=%03X DB=%02X W=%04X prev=%06X\n",pc,CPU.PC[0],CPU.PC[1],CPU.PC[2],CPU.PC[3],ICPU.Registers.A.W,ICPU.Registers.X.W,ICPU.Registers.Y.W,ICPU.Registers.D.W,ICPU.Registers.S.W,ICPU.Registers.P.W,ICPU.Registers.DB,v,br_prev_pc);
  }
  br_last=v;br_prev_pc=pc;
  if(!--br_trace_left)br_stop_trace();
 }
}
#endif
