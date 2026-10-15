/* Title-screen COOP OPTIONS, separate from the debug cheat menu. */
#include "batman_portrait.h"
static int br_appearance_tick(unsigned held,unsigned edge){
 if(!br_extra.appearance)return 0;
 BR_BLOCK=held;
 if(edge&0x0c00)br_extra.appearance_row^=1;
 if(edge&0x8000){br_extra.appearance=0;return 1;}
 if(!br_extra.appearance_row && (edge&0x0300)){
  unsigned previous=br_extra.color;
  br_extra.color=(previous+BR_COLOR_COUNT+((edge&0x0200)?-1:1))%BR_COLOR_COUNT;
 }
 if(edge&(0x0080|0x1000)){
  if(br_extra.appearance_row)br_extra.appearance=0;
  else br_extra.color=(br_extra.color+1)%BR_COLOR_COUNT;
 }
 return 1;
}
static void br_appearance_opcode(unsigned pc){
 if(!br_supported)return;
 if(pc==0x80b0ba)br_extra.title_row=br_extra.appearance=br_extra.appearance_row=0;
 if(pc==0x80b132){
  unsigned edge=br_r16(0x2e);
  br_extra.title_row%=3;
  if(edge&0x2c00){
   br_extra.title_row=(br_extra.title_row+((edge&0x0800)?2:1))%3;
   br_w16(0x66,384);
  }
  br_w16(0x33b,br_extra.title_row<2?br_extra.title_row:0);
  edge&=~0x2c00;
  if(br_extra.title_row==2 && (edge&0x1000)){
   br_extra.appearance=1;br_extra.appearance_row=0;
   BR_BLOCK=BR_KEYS;edge&=~0x1000;
  }
  br_w16(0x2e,edge);
 }
 if(pc==0x80b153 && br_extra.title_row==2){
  br_w16(0x32c,212);br_jump(0x80b15f);
 }
}
/* Decode the same 8x8 BG3 glyphs and CGRAM palette as GAME START / OPTIONS.
 * ROM text uses 0B..24 for A..Z, 01..0A for digits and 2A for spaces. */
static void br_option_text(unsigned w,unsigned x,unsigned y,const char *text){
 unsigned scale=w/256;
 for(;*text;text++,x+=8){
  unsigned glyph=*text>='A'&&*text<='Z'?*text-'A'+11:
                 *text>='0'&&*text<='9'?*text-'0'+1:42;
  unsigned px,py;
  for(py=0;py<8;py++)for(px=0;px<8;px++){
   unsigned addr=(PPU.BG[2].NameBase*2+(0x100+glyph)*16+py*2)&65535;
   unsigned bit=7-px,ink=((Memory.VRAM[addr]>>bit)&1)|
                        (((Memory.VRAM[(addr+1)&65535]>>bit)&1)<<1),i;
   if(!ink)continue;
   for(i=0;i<scale;i++)if((x+px)*scale+i<w)
    br_output[(y+py)*w+(x+px)*scale+i]=IPPU.ScreenColors[28+ink];
  }
 }
}
static void br_appearance_draw(unsigned w,unsigned h){
 unsigned x,y,scale=w/256;
 unsigned short cursor[32*16];
 if(!br_supported || !scale || h<224)return;
 if(br_r16(0x32)==2 && br_r16(0x34)==1 && !BR_MENU){
  /* Native rows start at tile column 13, with a two-tile vertical step.
   * The 32-pixel extra HUD strip is outside the original playfield. */
  br_option_text(w,104,208+32,"COOP OPTIONS");
 }
 if(!br_extra.appearance)return;
 /* Reuse the native Batman cursor from the selected third title row. */
 for(y=0;y<16;y++)for(x=0;x<32;x++)cursor[y*32+x]=br_output[(236+y)*w+(64+x)*scale];
 memset(br_output,0,w*(h+32)*2);
 br_option_text(w,80,56,"COOP OPTIONS");
 br_option_text(w,40,88,"PLAYER 2 COLOR");
 br_option_text(w,176,88,br_color_names[br_extra.color%BR_COLOR_COUNT]);
 for(y=0;y<16;y++)for(x=0;x<16;x++){
  unsigned ink=br_portrait[y*16+x],a,b;
  for(a=0;a<4;a++)for(b=0;b<4;b++)
   br_output[(120+y*4+b)*w+(96+x*4+a)*scale]=br_suit_color(ink,15);
 }
 br_option_text(w,40,216,"EXIT");
 br_option_text(w,40,248,"LEFT RIGHT TO CHANGE");
 for(y=0;y<16;y++)for(x=0;x<32;x++){
  unsigned i,top=br_extra.appearance_row?212:84;
  for(i=0;i<scale;i++)br_output[(top+y)*w+(8+x)*scale+i]=cursor[y*32+x];
 }
}
