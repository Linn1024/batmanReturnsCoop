// Windows Libretro host. Architecture follows the adjacent co-op projects.
#define _WIN32_WINNT 0x0A00
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <mmsystem.h>
#include <xinput.h>
#include <bcrypt.h>
#include <cstdio>
#include <cstdint>
#include <cstring>
#include <vector>
#include <string>
#include <map>
#include <algorithm>
#include "coop_desktop.h"
#include "engine/libretro-common/include/libretro.h"
struct Core {
 HMODULE dll;
 void (*init)(),(*deinit)(),(*run)(),(*reset)(),(*unload_game)();
 void (*set_environment)(retro_environment_t);
 void (*set_video_refresh)(retro_video_refresh_t);
 void (*set_audio_sample)(retro_audio_sample_t);
 void (*set_audio_sample_batch)(retro_audio_sample_batch_t);
 void (*set_input_poll)(retro_input_poll_t);
 void (*set_input_state)(retro_input_state_t);
 void (*set_controller_port_device)(unsigned,unsigned);
 bool (*load_game)(const retro_game_info*);
 void (*get_system_av_info)(retro_system_av_info*);
 size_t (*serialize_size)();bool (*serialize)(void*,size_t),(*unserialize)(const void*,size_t);
 void (*status)(unsigned*);
} core;
static HWND windowHandle,controlsWindow;
static std::map<std::string,std::string> options;
static std::vector<uint32_t> pixels;
static std::vector<int16_t> sound;
static unsigned width=256,height=224,format,pads[2],details[10];
static bool running=true,paused,fullscreen;
static int testFrames,frameNumber,slot=1,captureBinding=-1;
static RECT savedWindow;
static int keys[2][12]={{VK_SPACE,'F', 'Q',VK_RETURN,'W','S','A','D','G','H','R','T'},
 { 'L','J','O',VK_NUMPAD0,VK_UP,VK_DOWN,VK_LEFT,VK_RIGHT,'K','I','U','P'}};
static const char* actions[] = {"Jump (B)","Attack (Y)","Switch item","Start / pause","Up","Down","Left","Right","Use item (A)","X","Block (L)","Block (R)"};
static WORD padButtons[12]={XINPUT_GAMEPAD_A,XINPUT_GAMEPAD_X,XINPUT_GAMEPAD_BACK,XINPUT_GAMEPAD_START,XINPUT_GAMEPAD_DPAD_UP,XINPUT_GAMEPAD_DPAD_DOWN,XINPUT_GAMEPAD_DPAD_LEFT,XINPUT_GAMEPAD_DPAD_RIGHT,XINPUT_GAMEPAD_B,XINPUT_GAMEPAD_Y,XINPUT_GAMEPAD_LEFT_SHOULDER,XINPUT_GAMEPAD_RIGHT_SHOULDER};
typedef DWORD (WINAPI *GetPad)(DWORD,XINPUT_STATE*);
static GetPad getPad;
static HWAVEOUT audioDevice;
static WAVEHDR headers[12]={};static std::vector<int16_t> audioBuffers[12];static int audioSlot;
static std::string configPath;
struct Action {int first,last,player,button;};static std::vector<Action> testActions;
static std::vector<unsigned char> readFile(const char*path){FILE*f=fopen(path,"rb");if(!f)return {};fseek(f,0,SEEK_END);long n=ftell(f);rewind(f);std::vector<unsigned char>b(n>0?n:0);if(!b.empty()&&fread(b.data(),1,b.size(),f)!=b.size())b.clear();fclose(f);return b;}
static bool environment(unsigned cmd,void* data){
 switch(cmd){
 case RETRO_ENVIRONMENT_GET_SYSTEM_DIRECTORY:case RETRO_ENVIRONMENT_GET_SAVE_DIRECTORY:*(const char**)data=".";return true;
 case RETRO_ENVIRONMENT_SET_PIXEL_FORMAT:format=*(int*)data;return format<=2;
 case RETRO_ENVIRONMENT_GET_VARIABLE:{auto*v=(retro_variable*)data;auto it=options.find(v->key);v->value=it==options.end()?nullptr:it->second.c_str();return v->value;}
 case RETRO_ENVIRONMENT_SET_VARIABLES:for(auto*v=(retro_variable*)data;v->key;v++){std::string s=v->value;auto p=s.find(';');if(p==s.npos)continue;s=s.substr(p+1);while(!s.empty()&&s[0]==' ')s.erase(0,1);options.emplace(v->key,s.substr(0,s.find('|')));}return true;
 case RETRO_ENVIRONMENT_GET_VARIABLE_UPDATE:*(bool*)data=false;return true;
 case RETRO_ENVIRONMENT_GET_CAN_DUPE:*(bool*)data=true;return true;
 case RETRO_ENVIRONMENT_GET_INPUT_BITMASKS:return true;
 case RETRO_ENVIRONMENT_GET_CORE_OPTIONS_VERSION:*(unsigned*)data=0;return true;
 case RETRO_ENVIRONMENT_SET_INPUT_DESCRIPTORS:case RETRO_ENVIRONMENT_SET_CONTROLLER_INFO:case RETRO_ENVIRONMENT_SET_GEOMETRY:case RETRO_ENVIRONMENT_SET_SYSTEM_AV_INFO:return true;
 default:return false;
 }
}
static void video(const void*data,unsigned w,unsigned h,size_t pitch){
 if(!data)return;width=w;height=h;coopdesktop::geometry(w,h);pixels.resize(w*h);
 for(unsigned y=0;y<h;y++)for(unsigned x=0;x<w;x++){
  unsigned rgb;
  if(format==1)rgb=((const uint32_t*)((const char*)data+y*pitch))[x];
  else{unsigned v=((const uint16_t*)((const char*)data+y*pitch))[x],r,g,b=v&31;
   if(format==2){r=v>>11;g=((v>>5)&63)*255/63;}else{r=(v>>10)&31;g=((v>>5)&31)*255/31;}
   rgb=(r*255/31<<16)|(g<<8)|(b*255/31);
  }pixels[y*w+x]=rgb;
 }
}
static size_t audioBatch(const int16_t*p,size_t n){sound.insert(sound.end(),p,p+n*2);return n;}
static void audioSample(int16_t l,int16_t r){int16_t p[]={l,r};audioBatch(p,1);}
static void poll(){}
static int16_t input(unsigned p,unsigned d,unsigned,unsigned id){if(p>1||d!=RETRO_DEVICE_JOYPAD)return 0;return id==RETRO_DEVICE_ID_JOYPAD_MASK?pads[p]:(pads[p]>>id)&1;}
static void readInputs(){
 pads[0]=pads[1]=0;
 if(testFrames){for(const auto&a:testActions)if(frameNumber>=a.first&&frameNumber<a.last&&a.player<2)pads[a.player]|=1u<<a.button;return;}
 if(GetForegroundWindow()!=windowHandle || controlsWindow)return;
 for(unsigned p=0;p<2;p++)pads[p]=coopdesktop::buttons(p);
}
static void outputAudio(){
 if(!audioDevice||sound.empty())return;
 WAVEHDR&h=headers[audioSlot];if((h.dwFlags&WHDR_PREPARED)&&!(h.dwFlags&WHDR_DONE))return;
 if(h.dwFlags&WHDR_PREPARED)waveOutUnprepareHeader(audioDevice,&h,sizeof(h));
 audioBuffers[audioSlot]=sound;h={};h.lpData=(LPSTR)audioBuffers[audioSlot].data();h.dwBufferLength=sound.size()*2;
 waveOutPrepareHeader(audioDevice,&h,sizeof(h));waveOutWrite(audioDevice,&h,sizeof(h));audioSlot=(audioSlot+1)%12;
}
static void title(const char*message=nullptr){char t[240];if(message)snprintf(t,sizeof(t),"Batman Returns Co-op — %s",message);else snprintf(t,sizeof(t),"Batman Returns Co-op — slot %d%s",slot,paused?" — paused":"");SetWindowTextA(windowHandle,t);}
static bool saveState(){
 CreateDirectoryA("saves",nullptr);char path[128],temp[128];snprintf(path,sizeof(path),"saves/slot-%d.brstate",slot);snprintf(temp,sizeof(temp),"saves/slot-%d.tmp",slot);
 std::vector<unsigned char>b(core.serialize_size());if(!core.serialize(b.data(),b.size()))return false;
 FILE*f=fopen(temp,"wb");if(!f)return false;bool ok=fwrite("BRCOOP01",1,8,f)==8&&fwrite(b.data(),1,b.size(),f)==b.size();if(fclose(f))ok=false;
 return ok&&MoveFileExA(temp,path,MOVEFILE_REPLACE_EXISTING|MOVEFILE_WRITE_THROUGH);
}
static bool loadState(){char path[128];snprintf(path,sizeof(path),"saves/slot-%d.brstate",slot);auto b=readFile(path);bool ok=b.size()>8&&!memcmp(b.data(),"BRCOOP01",8)&&core.unserialize(b.data()+8,b.size()-8);if(ok&&audioDevice)waveOutReset(audioDevice);return ok;}
static void controls(){coopdesktop::openControls();}
static void toggleFullscreen(){fullscreen=!fullscreen;if(fullscreen){GetWindowRect(windowHandle,&savedWindow);SetWindowLongPtr(windowHandle,GWL_STYLE,WS_POPUP|WS_VISIBLE);MONITORINFO mi={sizeof(mi)};GetMonitorInfo(MonitorFromWindow(windowHandle,MONITOR_DEFAULTTONEAREST),&mi);SetWindowPos(windowHandle,HWND_TOP,mi.rcMonitor.left,mi.rcMonitor.top,mi.rcMonitor.right-mi.rcMonitor.left,mi.rcMonitor.bottom-mi.rcMonitor.top,SWP_FRAMECHANGED);}else{SetWindowLongPtr(windowHandle,GWL_STYLE,WS_OVERLAPPEDWINDOW|WS_VISIBLE);SetWindowPos(windowHandle,nullptr,savedWindow.left,savedWindow.top,savedWindow.right-savedWindow.left,savedWindow.bottom-savedWindow.top,SWP_FRAMECHANGED|SWP_NOZORDER);}}
static LRESULT CALLBACK windowProc(HWND h,UINT m,WPARAM w,LPARAM l){
 if(coopdesktop::handle(h,m,w,l))return 0;
 if(m==WM_CLOSE){running=false;DestroyWindow(h);return 0;}
 if(m==WM_ERASEBKGND)return 1;
 if(m==WM_SYSKEYDOWN&&w==VK_RETURN){toggleFullscreen();return 0;}
 if(m==WM_KEYDOWN && !(l&(1L<<30))){
  if(w==VK_F2){controls();return 0;}if(w==VK_F5){title(saveState()?"Saved":"Save failed");return 0;}if(w==VK_F8){title(loadState()?"Loaded":"Load failed or empty slot");return 0;}
  if(w==VK_F9){paused=!paused;if(audioDevice)waveOutReset(audioDevice);title();return 0;}if(w==VK_F1){MessageBoxA(h,"P1: WASD, Space jump, F attack, G use item, Q switch item, R block.\nP2: arrows, L jump, J attack, K use item, O switch item, U block.\nEnter / controller Start: in-game pause.\nF2: controls. F5: save. F8: load. F9: emulator pause.\nAlt+Enter: fullscreen. Save menu: choose slot.","Batman Returns Co-op",MB_OK);return 0;}
 }
 if(m==WM_COMMAND){int id=LOWORD(w);if(id==1)controls();if(id==2)title(saveState()?"Saved":"Save failed");if(id==3)title(loadState()?"Loaded":"Load failed or empty slot");if(id>=101&&id<=109){slot=id-100;title();}return 0;}
 if(m==WM_PAINT){PAINTSTRUCT ps;HDC dc=BeginPaint(h,&ps);RECT r;GetClientRect(h,&r);HDC mem=CreateCompatibleDC(dc);HBITMAP bitmap=CreateCompatibleBitmap(dc,std::max(1L,r.right),std::max(1L,r.bottom));auto old=SelectObject(mem,bitmap);FillRect(mem,&r,(HBRUSH)GetStockObject(BLACK_BRUSH));
  if(!pixels.empty()){double scale=std::min(double(r.right)/width,double(r.bottom)/height);int w1=int(width*scale),h1=int(height*scale);BITMAPINFO bi={};bi.bmiHeader.biSize=sizeof(BITMAPINFOHEADER);bi.bmiHeader.biWidth=width;bi.bmiHeader.biHeight=-(int)height;bi.bmiHeader.biPlanes=1;bi.bmiHeader.biBitCount=32;SetStretchBltMode(mem,COLORONCOLOR);StretchDIBits(mem,(r.right-w1)/2,(r.bottom-h1)/2,w1,h1,0,0,width,height,pixels.data(),&bi,DIB_RGB_COLORS,SRCCOPY);}
  BitBlt(dc,0,0,r.right,r.bottom,mem,0,0,SRCCOPY);SelectObject(mem,old);DeleteObject(bitmap);DeleteDC(mem);EndPaint(h,&ps);return 0;}
 return DefWindowProcA(h,m,w,l);
}
static bool correctRom(const std::vector<unsigned char>&b){if(b.size()!=1048576)return false;BCRYPT_ALG_HANDLE a;unsigned char digest[32];if(BCryptOpenAlgorithmProvider(&a,BCRYPT_SHA256_ALGORITHM,nullptr,0)<0)return false;NTSTATUS r=BCryptHash(a,nullptr,0,(PUCHAR)b.data(),b.size(),digest,32);BCryptCloseAlgorithmProvider(a,0);if(r<0)return false;char hex[65];for(int i=0;i<32;i++)sprintf(hex+i*2,"%02x",digest[i]);return !strcmp(hex,"f8d5c51f74df33edc827fbf8df7aab70160770ab0a896db6e59438ad9208cc6e");}
static int fail(const char*s){if(testFrames){CreateDirectoryA("diagnostics",nullptr);FILE*f=fopen("diagnostics/launcher-error.txt","w");if(f){fputs(s,f);fclose(f);}}else MessageBoxA(nullptr,s,"Batman Returns Co-op",MB_ICONERROR);return 1;}
int main(int argc,char**argv){
 char root[MAX_PATH];GetModuleFileNameA(nullptr,root,sizeof(root));if(char*s=strrchr(root,'\\'))*s=0;SetCurrentDirectoryA(root);configPath=std::string(root)+"\\controls.ini";
 const char*script=nullptr;for(int i=1;i<argc;i++){if(!strcmp(argv[i],"--test")&&i+1<argc)testFrames=atoi(argv[++i]);else if(!strcmp(argv[i],"--script")&&i+1<argc)script=argv[++i];}
 if(script){FILE*f=fopen(script,"r");Action a;if(!f)return fail("Input script missing");while(fscanf(f,"%d %d %d %d",&a.first,&a.last,&a.player,&a.button)==4)testActions.push_back(a);fclose(f);}
 coopdesktop::init(L"BatmanReturnsCoop",L"Batman Returns Co-op",testFrames!=0);
 std::vector<unsigned char> rom;if(!coopdesktop::loadRom(rom,L"Batman Returns (U) [!].smc",correctRom))return coopdesktop::cancelled?0:fail("The selected ROM is missing or is not the supported original USA version.");
 core.dll=coopdesktop::loadCore(L"engine\\snes9x2005_libretro.dll");if(!core.dll)return fail("Cannot load engine/snes9x2005_libretro.dll.");
#define LOAD(n) core.n=(decltype(core.n))GetProcAddress(core.dll,"retro_" #n);if(!core.n)return fail("Missing core export: " #n);
 LOAD(init);LOAD(deinit);LOAD(run);LOAD(reset);LOAD(unload_game);LOAD(set_environment);LOAD(set_video_refresh);LOAD(set_audio_sample);LOAD(set_audio_sample_batch);LOAD(set_input_poll);LOAD(set_input_state);LOAD(set_controller_port_device);LOAD(load_game);LOAD(get_system_av_info);LOAD(serialize_size);LOAD(serialize);LOAD(unserialize);
#undef LOAD
 core.status=(decltype(core.status))GetProcAddress(core.dll,"br_status");if(!core.status)return fail("Co-op core export missing.");
 core.set_environment(environment);core.set_video_refresh(video);core.set_audio_sample(audioSample);core.set_audio_sample_batch(audioBatch);core.set_input_poll(poll);core.set_input_state(input);core.init();
 retro_game_info game={coopdesktop::romUtf8.c_str(),rom.data(),rom.size(),nullptr};if(!core.load_game(&game))return fail("ROM failed to load.");for(unsigned p=0;p<2;p++)core.set_controller_port_device(p,RETRO_DEVICE_JOYPAD);
 retro_system_av_info av={};core.get_system_av_info(&av);
 for(int p=0;p<2;p++)for(int b=0;b<12;b++){char section[8],key[12];snprintf(section,sizeof(section),"P%d",p+1);snprintf(key,sizeof(key),"Button%d",b);keys[p][b]=GetPrivateProfileIntA(section,key,keys[p][b],configPath.c_str());}
 int desktopKeys[2][16]{};for(int p=0;p<2;p++)for(int b=0;b<12;b++)desktopKeys[p][b]=keys[p][b];
 unsigned desktopPads[16]{};for(int b=0;b<12;b++)desktopPads[b]=padButtons[b];
 coopdesktop::configure(desktopKeys,desktopPads,{{4,L"Up"},{5,L"Down"},{6,L"Left"},{7,L"Right"},{0,L"Jump"},{1,L"Attack"},{8,L"Use item"},{2,L"Switch item"},{10,L"Block L"},{11,L"Block R"},{3,L"Pause"}});
 if(!testFrames){
  SetProcessDPIAware();WNDCLASSA wc={};wc.lpfnWndProc=windowProc;wc.hInstance=GetModuleHandle(nullptr);wc.lpszClassName="BatmanReturnsCoop";wc.hCursor=LoadCursor(nullptr,IDC_ARROW);RegisterClassA(&wc);

  HMENU menu=CreateMenu(),gameMenu=CreatePopupMenu(),slotMenu=CreatePopupMenu();AppendMenuA(gameMenu,MF_STRING,1,"Controls\tF2");AppendMenuA(gameMenu,MF_STRING,2,"Save\tF5");AppendMenuA(gameMenu,MF_STRING,3,"Load\tF8");AppendMenuA(menu,MF_POPUP,(UINT_PTR)gameMenu,"Game");for(int i=1;i<=9;i++){char n[16];snprintf(n,sizeof(n),"Slot %d",i);AppendMenuA(slotMenu,MF_STRING,100+i,n);}AppendMenuA(menu,MF_POPUP,(UINT_PTR)slotMenu,"Save slot");
  windowHandle=CreateWindowA("BatmanReturnsCoop","Batman Returns Co-op",WS_OVERLAPPEDWINDOW|WS_VISIBLE,CW_USEDEFAULT,CW_USEDEFAULT,800,800,nullptr,menu,GetModuleHandle(nullptr),nullptr);title();coopdesktop::attach(windowHandle,256,256);
  HMODULE xi=LoadLibraryA("xinput1_4.dll");if(!xi)xi=LoadLibraryA("xinput9_1_0.dll");if(xi)getPad=(GetPad)GetProcAddress(xi,"XInputGetState");
  WAVEFORMATEX wf={};wf.wFormatTag=WAVE_FORMAT_PCM;wf.nChannels=2;wf.nSamplesPerSec=(DWORD)av.timing.sample_rate;wf.wBitsPerSample=16;wf.nBlockAlign=4;wf.nAvgBytesPerSec=wf.nSamplesPerSec*4;waveOutOpen(&audioDevice,WAVE_MAPPER,&wf,0,0,CALLBACK_NULL);timeBeginPeriod(1);
 }
 LARGE_INTEGER freq,now;QueryPerformanceFrequency(&freq);QueryPerformanceCounter(&now);double deadline=double(now.QuadPart)/freq.QuadPart;
 while(running&&(!testFrames||frameNumber<testFrames)){
  MSG msg;while(PeekMessage(&msg,nullptr,0,0,PM_REMOVE)){TranslateMessage(&msg);DispatchMessage(&msg);}if(!running)break;
  if((paused||controlsWindow||coopdesktop::busy())&&!testFrames){Sleep(15);QueryPerformanceCounter(&now);deadline=double(now.QuadPart)/freq.QuadPart;continue;}
  readInputs();sound.clear();core.run();core.status(details);
  if(!testFrames){outputAudio();InvalidateRect(windowHandle,nullptr,FALSE);UpdateWindow(windowHandle);deadline+=1.0/av.timing.fps;QueryPerformanceCounter(&now);double wait=deadline-double(now.QuadPart)/freq.QuadPart;if(wait>0)Sleep((DWORD)(wait*1000));else if(wait<-.2)deadline=double(now.QuadPart)/freq.QuadPart;}
  frameNumber++;
 }
 if(testFrames){CreateDirectoryA("diagnostics",nullptr);FILE*f=fopen("diagnostics/launcher-status.txt","w");if(f){for(auto v:details)fprintf(f,"%u ",v);fclose(f);}BITMAPFILEHEADER bf={};BITMAPINFOHEADER bi={};bi.biSize=sizeof(bi);bi.biWidth=width;bi.biHeight=-(int)height;bi.biPlanes=1;bi.biBitCount=32;bi.biSizeImage=pixels.size()*4;bf.bfType=0x4d42;bf.bfOffBits=sizeof(bf)+sizeof(bi);bf.bfSize=bf.bfOffBits+bi.biSizeImage;f=fopen("diagnostics/launcher.bmp","wb");if(f){fwrite(&bf,sizeof(bf),1,f);fwrite(&bi,sizeof(bi),1,f);fwrite(pixels.data(),4,pixels.size(),f);fclose(f);}}
 if(audioDevice){waveOutReset(audioDevice);for(auto&h:headers)if(h.dwFlags&WHDR_PREPARED)waveOutUnprepareHeader(audioDevice,&h,sizeof(h));waveOutClose(audioDevice);}if(!testFrames)timeEndPeriod(1);core.unload_game();core.deinit();FreeLibrary(core.dll);return 0;
}
