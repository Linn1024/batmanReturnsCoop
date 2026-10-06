"""Small 65816 ROM listing helper; specify M/X widths at entry."""
from pathlib import Path
import sys
ROM=next(Path(__file__).resolve().parents[1].glob('*.smc')).read_bytes()
ROWS='''BRK ORA COP ORA TSB ORA ASL ORA PHP ORA ASL PHD TSB ORA ASL ORA
BPL ORA ORA ORA TRB ORA ASL ORA CLC ORA INC TCS TRB ORA ASL ORA
JSR AND JSL AND BIT AND ROL AND PLP AND ROL PLD BIT AND ROL AND
BMI AND AND AND BIT AND ROL AND SEC AND DEC TSC BIT AND ROL AND
RTI EOR WDM EOR MVP EOR LSR EOR PHA EOR LSR PHK JMP EOR LSR EOR
BVC EOR EOR EOR MVN EOR LSR EOR CLI EOR PHY TCD JML EOR LSR EOR
RTS ADC PER ADC STZ ADC ROR ADC PLA ADC ROR RTL JMP ADC ROR ADC
BVS ADC ADC ADC STZ ADC ROR ADC SEI ADC PLY TDC JMP ADC ROR ADC
BRA STA BRL STA STY STA STX STA DEY BIT TXA PHB STY STA STX STA
BCC STA STA STA STY STA STX STA TYA STA TXS TXY STZ STA STZ STA
LDY LDA LDX LDA LDY LDA LDX LDA TAY LDA TAX PLB LDY LDA LDX LDA
BCS LDA LDA LDA LDY LDA LDX LDA CLV LDA TSX TYX LDY LDA LDX LDA
CPY CMP REP CMP CPY CMP DEC CMP INY CMP DEX WAI CPY CMP DEC CMP
BNE CMP CMP CMP PEI CMP DEC CMP CLD CMP PHX STP JML CMP DEC CMP
CPX SBC SEP SBC CPX SBC INC SBC INX SBC NOP XBA CPX SBC INC SBC
BEQ SBC SBC SBC PEA SBC INC SBC SED SBC PLX XCE JSR SBC INC SBC'''.split()
MODES='''b ix b sr d d d il z m a z w w w l
r iy di sy d dx dx ly z wy a z w wx wx lx
w ix l sr d d d il z m a z w w w l
r iy di sy dx dx dx ly z wy a z wx wx wx lx
z ix b sr w d d il z m a z w w w l
r iy di sy w dx dx ly z wy z z l wx wx lx
z ix R sr d d d il z m a z wi w w l
r iy di sy dx dx dx ly z wy z z wxi wx wx lx
r ix R sr d d d il z m z z w w w l
r iy di sy dx dx dy ly z wy z z w wx wx lx
x ix x sr d d d il z m z z w w w l
r iy di sy dx dx dy ly z wy z z wx wx wy lx
x ix b sr d d d il z m z z w w w l
r iy di sy di dx dx ly z wy z z wli wx wx lx
x ix b sr d d d il z m z z w w w l
r iy di sy w dx dx ly z wy z z wxi wx wx lx'''.split()
def byte(a):return ROM[((a>>16)&0x7f)*0x8000+(a&0x7fff)]
def listing(start,end,m=0,x=0):
 a=start
 while a<end:
  op=byte(a); mode=MODES[op];n=1 if mode in ('z','a') else (2 if mode in ('b','d','dx','dy','ix','iy','di','il','ly','sr','sy','r') else (4 if mode in ('l','lx') else 3))
  if mode=='m':n=2 if m else 3
  if mode=='x':n=2 if x else 3
  bs=bytes(byte(a+i) for i in range(n));v=int.from_bytes(bs[1:],'little');operand=f'${v:0{(n-1)*2}X}' if n>1 else ''
  if mode in ('m','x','b'):operand='#'+operand
  if mode in ('r','R'):operand=f'${(a+n+int.from_bytes(bs[1:],"little",signed=True))&0xffffff:06X}'
  if mode in ('dx','wx','lx'):operand+=',X'
  if mode in ('dy','wy'):operand+=',Y'
  if mode in ('di','wi','wxi','wli','ix','iy','il','ly','sr','sy'):operand+=' ['+mode+']'
  print(f'{a:06X} {bs.hex(" "):11s} {ROWS[op]} {operand}')
  if op==0xc2:
   if v&32:m=0
   if v&16:x=0
  if op==0xe2:
   if v&32:m=1
   if v&16:x=1
  a+=n
if __name__=='__main__':listing(*(int(a,16) for a in sys.argv[1:]))
