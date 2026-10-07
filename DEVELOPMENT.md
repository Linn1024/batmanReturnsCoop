# Development notes

The architectural references were the adjacent `aladdinGameCoop`, `splatterhouse` and `indianaJonesCoop` projects: retain original ROM behavior, isolate player state inside a modified core, run the world once, and preserve extra state in saves. No ROM instructions or executable WRAM trampolines are injected.

The SNES core is vendored from `https://github.com/libretro/snes9x2005`, revision `a79dfe9047e7fec58808aefe48ad2bf499c7af11`. This build uses its native audio implementation, Windows x64 and RGB565. The game adapter recognizes only the 1 MiB ROM with CRC32 `E87DFDF6`; the launcher additionally checks SHA-256. Existing emulator notices remain in `engine/copyright`.

## ROM map discovered in this project

Addresses below are SNES CPU addresses for this ROM only. WRAM addresses omit bank `7E`.

| Address | Observed role |
| --- | --- |
| `80:AF04` | Belt-scrolling player update call |
| `80:C8CC` | Player lifecycle dispatcher |
| `80:C9AC` | Normal player simulation, contacts and animation |
| `80:AF08` | End of the player pass, before shared camera/world work |
| `80:B42E` | Shared camera/map update |
| `80:D55D` | Player screen Y and shadow update |
| `80:BE2E` | Apply shared scroll displacement to player |
| `80:D9C3` | Batarang update |
| `84:828B`, `84:82D1`, `84:8317` | Native per-object AI dispatch boundaries |
| `83:8C9A`, `83:8CBA`, `83:8CDF` | Side-view AI dispatch boundaries |
| `87:F638` | Enemy attack contact against Batman |
| `87:F53C` | Batman attack contact against enemy |
| `80:C97E` | Native life charge after completed death animation |
| `80:944E` | Sorted sprite list ready |
| `80:9474`, `80:947E` | One sorted object's native sprite build |
| `80:8FDD` | Native Batman graphics uploads |
| `0320..04FF` | Player, attack, projectile and shadow context |
| `0328`, `0338`, `0334` | Screen X, ground-depth coordinate, jump height |
| `035C` | Lifecycle: entrance / respawn / normal / death |
| `0380` | Active native player attack |
| `008A`, `008C` | Health, shared lives |
| `008E`, `0090` | Selected item, shared test-tube stock |
| `00D8..00DB` | Mapped held and edge-triggered player inputs |
| `17A0`, `188C` | Camera X, frame scroll displacement |
| `15B0..160F` | Native list of objects sorted by ground depth |

`source/batman_coop.h` is included once by `cpuexec.c`. Native replay runs a bounded sequence of real opcodes, preserving CPU state and the actual `$1F00..1FFF` stack page. It does not advance CPU/APU/PPU time. Do not back up `$1E00`: it contains real game state, including the Game Over fade.

P2 replays the normal player update and screen-coordinate/projectile passes. Enemies still advance once, with the nearer player's context temporarily installed. This is not a full audit of every attack/grapple ownership path; ownership needs further work for simultaneous grabs and special scenes.

Side-view dispatches now also select the nearer Batman, using rendered Y
instead of belt-mode ground depth. Extra slots are filtered to living enemy
types so lift/platform controllers retain their native context. The third
projectile slot follows the selected player at AI entry and return.
`verify_enemy_aggro_save.py` checks the reported QS0 with either owner in
the nearer position: robots face, chase and damage that player, with
deterministic state/video/audio replay.

Belt-mode attack contact is independent of the nearer-player AI choice.
On a miss at 87:F636, check the other player's existing melee/projectile
context once, using the native collision routine. Restore the selected
context at either hit return or the final miss. Reserved owner[9] records
the swap for serialized states; native reactions and world updates run
once. `verify_melee_target_save.py` reproduces the reported QS0 using real
Down/Y input, tests reversed player ownership, and checks deterministic
state/video/audio replay. Native ground-depth range checks remain intact.

Side-view contact at 80:EF94 likewise tests P2's full attack context after
P1 misses. The earlier retry swapped only projectile slots and entered at
80:EFE2, skipping P2's melee check. The retry now enters at 80:EF94 and
restores at the melee hit, projectile hit or final miss return. owner[9]=2
marks a P1-to-P2 swap, and value 3 checks P1 when AI already selected P2;
value 1 still restores legacy projectile-only
saves correctly. The third projectile slot is swapped independently of the
player prefix. `verify_side_melee_save.py` checks the latest reported QS0
with real Y input and reversed player ownership, plus idle and replay checks.

The shared camera uses the players' midpoint, native map boundaries, and screen-edge separation constraints. Death consumes one shared life and restores a normal player context at the partner; the final life follows native Game Over. Both Batmans now share the native arrival pose and gain independent controls after landing.

## Graphics

Scripted belt poses copy P1's committed VRAM into P2's tile cache before
applying any pending native DMA descriptors. Descriptor lengths can be
zero after NMI has consumed an upload; copying the actor pose alone then
leaves blue Batman's older combat tiles under a different sprite layout.
`verify_script_tiles_save.py` checks the reported scene-clear QS0 against
native body tiles for more than 200 frames, preserves private inventory
and health, and verifies deterministic state/video/audio replay.

Native player DMA descriptors reconstruct P2's private tile buffer from ROM. Pending tiles are committed alongside the next OAM upload, so new animation tiles do not appear under an older sprite list. Private tile caches never replace P1 or enemy VRAM.

Virtual renderer entries in the sorted list place P2, their batarang and their shadow at their own ground depth. These markers are intercepted before any native object-memory read. Native sprite construction retains original flipping, clipping and background priority. Both player bodies are built into private OAM and merged at its native depth without consuming the original game's OAM slots.

P2's palette keeps the native black shadow/outline ink and uses blue for the six body shading inks, preserving the original face and yellow belt. The previous pose-relative gray suit mask produced rectangular patches in some animations and has been removed. The existing saved pixel-mask arrays now select only ink-2 pixels at the ground line in grounded belt and side-view poses; these embedded oval-shadow pixels use black instead of the body blue. This does not restore the old rectangular suit mask. Airborne shadows retain native rendering. Native sprite geometry, transparency and animation frames remain unchanged. The same palette gives the blue Batmobile brighter blue highlights while preserving its red lights.

`br_video` places a 32-line P2 HUD above the full native frame, producing
256x256 during normal gameplay. Both frontends receive this output. The
original frame is shifted down 32 pixels without cropping, and no bottom
HUD remains. br_top_hud decodes the native BG3 2bpp HUD tiles and palette
onto black, retaining the original font, borders, health colors and layout.
The portrait/name are tinted blue. The name keeps ink 1 black for its
lettering shadow, with separate blue/cyan foreground tones. The native
blank 16-row gray separator is black in the combined HUD. Health tiles use
the native depletion table with P2 HP. P2's complete 26x26 item frame at
x=115..140, y=11..36 matches P1's native border, five-pixel inset and
vertical position relative to the HUD text. Its bottom extends into the
black separator; all four native item tiles fit at x=120..135, y=16..31.
The item descriptors use character
page 1 (2Dxx), which the removed middle display accidentally omitted.
The native P1 item display remains untouched. Both players retain
independent weapon selection; stock, lives and score remain shared.
The shared score and native enemy/boss portrait, name and health gauge
appear only in the added top strip, with the enemy gauge below the score.
The BG3 renderer temporarily substitutes the native blank glyph for the
right HUD cells (columns 18..31, rows 2..4), then restores the tilemap
immediately after drawing. This removes duplicate overlays while revealing
the scenery underneath, without persistent RAM/VRAM or palette changes.
The original player HUD and item frame remain in the main screen.
verify_top_hud.py checks the native full-health pixels/border, portrait tint,
score font, private health and all three item icons, readable name/shadow,
black separator, all four native item tiles against P1 rendering, complete
frame and unclipped margins for every item, real P2 selection without
changing P1, and exact save/video/audio
replay, as well as an ordinary enemy HUD with no duplicate in the game
frame. Pixel-based game regressions account for the 32-pixel display offset.

## Saves and audio

The Libretro save suffix includes player context, AI context if mid-pass, input edges, pending/live sprite ownership, both tile buffers and both material masks. Derived tile caches are invalidated on load.

The upstream save omitted DSP echo/filter/noise history and the fractional audio frame accumulator. A separate native-audio suffix preserves these plus exact channel decoding state. Its load runs after the upstream repair function and relocates channel buffer pointers. Full state, video and audio now match replay; a separate process test covers reloading after ASLR relocates the DLL.

Standalone saves add `BRCOOP01` and use a temporary file followed by replacement. This prototype targets this x64 core build. Original single-player core snapshots remain accepted as research input and initialize fresh co-op context. Earlier intermediate prototype save sizes are not supported.

## Build and checks

```powershell
.\build.ps1
python tools/verify_coop.py
python tools/verify_saved_process.py
python tools/verify_cheats.py
```

Python checks require Pillow and NumPy. They cold boot the ROM; no local save fixture is required. Reports and screenshots go to `diagnostics/`. The combat test positions a naturally spawned clown and attacks through controller input; the damage test injects a native attack box; death tests enter the native completed-death state. These checks do not prove campaign completion.

`tools/native_probe.py` is the headless Libretro driver. `tools/disasm.py` produces a linear 65816 listing; supply the correct entry M/X flags and interpret control-flow joins manually. Trace exports are explicitly enabled by research tools and normally do nothing.

`launcher.cpp` provides Win32 video, queued stereo audio, two XInput controllers, keyboard rebinding, save slots and fullscreen. For unattended boot/input tests, use `--test N --script path`; each script line is `firstFrame exclusiveLastFrame playerIndex libretroButtonID`.

## Remaining conversion work

The cheat UI lives in `source/batman_cheats.h`, included by the co-op adapter.
It uses the previously unused `br.owner` words, keeping the serialized size
compatible with existing saves. The menu is sampled from raw input before native
Start merging. While open, CPU/game time stops, the overlay renders, and the host
receives silence. Consumed buttons remain blocked until release. Level changes
enter the ROM's original level-select dispatcher at `80:8613` / `80:85ED`, so
VRAM reset and asset loading run with normal emulated timing. LEVEL and
SUBLEVEL expose all 18 native sections. Sublevel counts come from the ROM's
81:80A7 bounds table (2/3/3/4/1/2/3). Opening the menu selects the current
sublevel; changing levels resets it to the first valid section. Sublevel
loads initialize the level's first section, then take the ROM's actual
159A=11 transition through each preceding section until the selected one.
BR_LOAD=3 persists through these timed loaders; the 80:8492 hook advances
only after the previous load finishes. This preserves inherited tiles and
special transitions (notably sections 9 and 11) which bypass the ordinary
background loader. A loading screen hides the initialization sections.
Simply loading the destination's assets, or replaying full level initialization
for every section, leaves missing tiles or font tiles in the background.
Serialized owner words and save size remain
unchanged. verify_sublevels.py checks every destination through both
controllers, valid bounds and wrapping, selection save/restore, entrances,
and independent movement. Existing cheat, arrival, racing, scripted walk
and health-bar checks also pass.

verify_sublevel_graphics_save.py reloads the reported section-11 QS0 through
the real menu, checks all prerequisite sections were initialized and the
previously corrupted rooftop background matches a fresh load, and verifies
the native boss HUD and exact mid-load save/video/audio replay. Existing
bad saves retain their saved VRAM; use LOAD SELECTED LEVEL to rebuild assets.

The renderer stores up to 256 objects per scanline with a safe extra sentinel
entry. Both normal and rotated OAM evaluation use a 2048-segment budget (256 times
the maximum eight segments per object), and drawing visits all 256 entries.
`verify_cheats.py` injects 128 sprites through the original OAM DMA and observes
128 sprites / 256 segments on the same row. It also tests real menu input from
both ports, pause/input isolation, invulnerability/contact fixtures, one-hit
melee kills, refill actions, save restoration, all seven level starts, and level
restart. Menu rendering was additionally checked in BizHawk and standalone.

Encounter-camera regression: the midpoint camera must preserve the native
displacement while `$A0` holds an encounter/cutscene lock. Earlier builds ignored
this lock, scrolling beyond the first encounter and eventually exhausting the
three event slots with waiting scripts. New cold boots use co-op version 2 (same
serialized layout). For version-1 saves already past the first stage's lock,
allocation may use free `$1090..1180` slots, which the original event-update loop
already visits, so pending events can finish without deleting them or changing
health/lives. `tools/verify_encounter_save.py` tests the supplied QS0 with controlled
combat: pending allocation advances, the encounter finishes, and camera scrolling
resumes. `verify_coop.py` also checks that an encounter lock stops midpoint scroll
from a fresh boot. Internal frame counts alone do not detect a stalled encounter.

Sprite-capacity regression: P2's native sprite-builder replay must return its
carry flag to the caller. Carry means all 128 OAM entries are occupied; discarding
it allowed drawing to continue with an exhausted high-OAM sentinel and trapped
the game in `80:94AE`. Both player bodies now build into private OAM; carry determines its length before the native
OAM and scratch state are restored. The main builder resumes with free capacity.
A narrowly scoped recovery still takes the native full-OAM exit when an older
save is already stuck in that loop.
`python tools/verify_freeze_save.py "path/to/QuickSave0.State"` checks recovery,
600 further gameplay frames, and preservation of the original save. The reported
QS0 and QS5 both passed; QS0 was also loaded and advanced in BizHawk.

- Extend side-view support to projectiles, full combat/death coverage and all special/vehicle stages.
- Preserve independent context deliberately across every stage loader and scripted scene.
- Test/fix both players' simultaneous grapples, throws, pickups, special weapons and boss collisions.
- Audit P2's materials across the full animation set and sprite capacity in crowded scenes.
- Complete two-person campaign, physical gamepad and sustained audio playtests.
# BizHawk display regression

Keep `DispSpeedupFeatures` set to `2` in the BizHawk profile. Setting it to `0` disables the actual window's Render method, producing a black window while emulation continues. Lua `client.screenshot` still captures the internal framebuffer, so it cannot verify that the window displays video. After changing the profile, also launch the regular shortcut without Lua and inspect the visible game window. This check reproduced the black screen and verified the corrected setting.

### QS0 motorcycle sprite overflow

The motorcycle QS0 exhausted native OAM after drawing P2: the upper bike received
only nine entries instead of its full 41-entry composite sprite. Both player
bodies now run the original
sprite builder against an isolated 544-byte OAM buffer. The final packed high-OAM
byte is completed before decoding. P1 also needs private slots: without P2, this
scene still needs 129 native entries. Pending/live private entries retain the native
insertion position and tile ownership. `br_build_objs` merges them with PPU OAM
for normal depth, clipping, palette and background-priority rendering.

Native PPU and legacy BR save layouts remain intact. Pending/live extra OAM is
appended after the audio suffix; the loader accepts both old and extended states.
The standalone loader delegates size validation to the core. BizHawk loaded the
original QS0, rendered both bikes, advanced 182 frames and saved/reloaded the new
format. `tools/verify_motorcycle_save.py` checks full upper-bike allocation,
save replay, and continued gameplay using the preserved QS0 fixture.

### Side-view QS0 with both heroes absent

The first side-view subsection dispatches the player through `80:AEBE` / `80:BF27`,
not the belt-scrolling call. The adapter now detects section changes there,
clones the new native context for P2, replays the player pass through `80:AEC2`,
and applies the shared horizontal/vertical camera displacement through
`80:AEC6..AECA`. The positive display-list path at `80:94D8` renders both player
bodies in private OAM at the original P1 list position without extending the
already full native list. Private P2 animation tiles still use the native DMA
descriptors.

The invulnerability cheat had pinned the side-view blink timer to 120, which
became an odd invisible frame on every update and also suppressed attacks.
Side-view invulnerability now clears that timer and rejects native player damage
contacts at `80:C06F` / `80:C0A9`. Belt-scrolling invulnerability is unchanged.

`tools/verify_sideview_save.py` restores the preserved reported QS0 and checks
both sprite pointers, independent movement/jump/attack with cheats enabled,
shared camera scrolling, and deterministic full state/video/audio replay.
BizHawk was also checked with the original save and a newly saved/reloaded state.
This is basic side-view support; P2 projectiles, special interactions and complete
side-view combat/death behavior remain unaudited.

Side-view camera follow-up: A0=2 is the normal side-view mode, not a camera lock.
The belt-scrolling nonzero-A0 override now applies only to mode 1; side-view
horizontal scripted control uses bits 0x30. Normal side-view play uses midpoint
scrolling and the existing trailing-player edge guard. Previously, P1's scroll
request bypassed that guard and the native 8-bit screen-X subtraction wrapped P2
from the left edge to the right. The side-view regression now holds either player
right then left for 300 frames each, checking both remain visible, the idle
partner keeps the same world X, and no discontinuous screen-X jump occurs.
Movement assertions account for camera displacement. BizHawk also ran the
reported P1-only right input for 300 frames from the preserved QS0.

The native directional follow limits also apply: A0 bit 0 blocks forward
follow and bit 1 blocks backward follow (80:BD2F / 80:BD58). Normal A0=2
is forward-only, and the elevator's A0=CF locks both directions while its
vertical script continues. Midpoint follow rejects a blocked direction;
when both directions lock, it preserves the native scripted request. The deliberately
free upper fire-corridor camera remains exempt. `verify_elevator_camera_save.py`
checks the reported elevator QS0 with either/both players walking left/right,
native ascent, falls/respawns without horizontal drift and full replay.

### Side-view batarang ownership

P2 now replays the native projectile pass `80:AECA..AECE` with their own player
context, and the side-view private OAM pass includes their projectile sprites.
The native allocator has three slots (0460, 04B0, 0500); the legacy player context
only covered the first two. Previously those two stayed uninitialized, and a
later throw leaked into shared slot 0500 and initialized using P1's position.
An 80-byte third-slot context is appended to the existing extra-OAM save suffix.
Both P2 simulation and projectile updates swap all three slots, preserving P1.
Rendering the third slot also restores the native slot afterward. Section joins
clear P2's third slot. The loader accepts both prior save sizes and the new suffix.

`verify_sideview_batarangs.py` uses native throw inputs with controlled occupied
slots and cleared enemies to check all three allocation paths for both players,
both facings, owner-relative spawn coordinates, motion and save replay. It also
runs repeated simultaneous throws. Enemy-hit ownership remains a separate audit;
these checks verify spawning, movement and drawing. BizHawk rendered P2's throw
and saved/reloaded the extended state. Side-view camera, opening co-op, motorcycle,
cheat-menu and cross-process save tests still pass.

### Side-view P2 batarang enemy contacts

At native enemy-scan miss `80:F01E`, swap in all three P2 projectile slots and
retry the original scan `80:EFE2`. At hit return `80:F012` or miss return
`80:F020`, swap them back while preserving CPU outputs and native hit side
effects. This leaves enemy updates single-pass, preserves P1-first collision
priority, and consumes the correct owner's batarang. The in-progress swap flag
uses reserved serialized owner word 9, so no transient backup is lost in a save.
P2 projectile scroll adjustment also replays the native projectile-only loop
before `83:8C86`; world/enemy simulation is not replayed.

The batarang regression now throws at the same real enemy from the same position
for each player and all three allocation slots. It checks equal native damage,
hit-state transition and projectile consumption without changing the other
owner's slots. Side-view camera/control/save and original belt-scrolling co-op
checks still pass, as does cross-process save replay. BizHawk also ran P2's
approach/throw sequence and saved/reloaded the result.

### Stuck side-view boss introduction (latest QS0)

The reported state has D6=1, 6A=1, A0=3, camera 07A0 and display mode 58=FFFF.
The native script at 83:BE61 waits for camera 0800 before releasing controls.
Midpoint scrolling prevented that threshold, and a P1 already near the left
edge could also stop the original pan at 07F0. During scripted side-view input
(D6), both players now use the native forced controls. The requested 19C0 pan
is preserved; edge players are carried just enough to stay within 16..240,
including their native movement anchor. Normal shared camera guards remain.

This boss introduction changes to the negative/sorted display-list path.
That path now draws P2 and their three projectiles at P1's native list position
in side-view mode, matching the existing positive-list adapter.

verify_scripted_pan_save.py restores the untouched user fixture, verifies the
native script releases control after 228 frames without player input, checks
both players can then move, and checks save replay. BizHawk also completed the
scene and saved/reloaded the recovered state. Side-view camera, batarang hit
and opening-stage co-op regressions pass.

### Boss-defeat exit QS0 freeze

The subsequent save is in 9E:F979 with forced right input and camera 0740;
the exit waits for camera 0800. Unlike the boss introduction, 19C0 is zero:
this is a forced walk, not an automatic pan. The prior override discarded
its scroll request. Scripted side-view handling now uses nonzero 19C0 only
for automatic pans, and follows forced horizontal walking when necessary,
including old states already at the screen edge. It remains active while
D6 owns input even if A0 clears during the walk.

verify_boss_exit_save.py confirms the original save advances to stage 2 in
573 frames without input, then skips the intermission with Start and verifies
independent movement for both players in the next stage. The previous scripted
pan, normal shared camera and all side-view batarang regressions still pass.

### Elevator QS0: player left below the shared view

The elevator save (section 3) has P1 in fall state 18 at screen Y=2856 while P2
is grounded at Y=208. The side-view invulnerability cheat had also zeroed the
fall countdown, permanently preventing the native lifecycle transition.
Invulnerability now clears the attack-blocking timer only for normal combat
states below 14. Old terminal-fall saves with a zero countdown receive 2 ticks,
allowing the native decrement-to-1 transition rather than looping forever.

In the elevator section, a fallen player below the view rejoins a visible,
grounded idle/walking partner using that partner's native body/platform context,
with a 24-pixel horizontal separation and matching movement anchor. Health,
inventory and all projectile slots remain owned by their original players.
The recovery is symmetric and does not charge a life for shared-view separation.
Without a suitable partner, the native fall/respawn lifecycle continues.

verify_elevator_save.py checks the reported save and mirrored player ownership,
independent movement afterward, save replay and the fall countdown without a
safe partner. BizHawk restored both visible players and saved/reloaded recovery.
Camera, boss introduction/exit, batarang contacts and cheat regressions pass.

### Escalator vertical camera oscillation

The shaking QS0 alternated native vertical scroll requests +5/-5 between the
two player passes. P2 had inherited P1's pending vertical displacement, and
then replaced it while centering at a different height. The side-view adapter
now saves P1's vertical request, clears it before P2 simulation, and resolves
both requests against a shared midpoint (172..180 dead band, at most two pixels
per frame). Native requests still gate allowed directions. Scripted input and
vertical camera locks retain native P1 control.

verify_vertical_camera_save.py follows the escalator for 180 idle frames and
asserts continuous upward progress, no direction reversals, bounded steps,
both players visible and deterministic save replay. The reproduced +5/-5
oscillation becomes steps of -1 or 0. Elevator rescue, side-view controls,
batarang damage, both boss scripts and opening co-op tests pass. BizHawk also
loaded the saved escalator scene and advanced 180 frames with the updated core.

### P2 grappling hook graphics

Side-view private rendering now includes hook tip slot 0410. The rope is generated
by the native 80:ECE4 routine into effect slots 0EB0..14EF, which previously only
ran for P1. br_draw_side_hook temporarily installs P2, uses ROM data bank 81,
builds the native rope and draws its segments into private OAM, then restores
P1's effect slots. Both positive and negative display-list paths include it.
P2 hook slot 0410 now also receives the native per-frame camera displacement.

verify_hook_save.py loads the reported live P2 grapple, tests simultaneous-hook
effect isolation, save replay and zero replay errors. Screenshots in the native
harness and BizHawk confirm the previously missing tip and rope. Side-view
camera, batarang ownership/hits and movement regressions pass.

Hook sprite correction: the rope geometry was present but selected P1's current
VRAM tiles. Rope segments use tiles uploaded as part of the throwing player's
animation, so an idle P1 made P2's rope look like repeated Batman limbs. Private
OAM ownership now distinguishes recolored P2 body (1) from P2 animation effects
with native palette (2). Hook tip/rope use P2 tile memory, a separate decoded
cache, and no body material recolor. Both caches are invalidated on tile/state
changes. The serialized ownership byte retains its existing layout.

verify_hook_save.py now compares the isolated P2 rope pixels against a native
P1 hook rendering from the same pose/save, in addition to effect isolation and
save replay. This catches the previously missed wrong-tile regression. The
corrected thin rope was also captured in BizHawk; batarang, opening co-op and
cross-process save checks pass.

### Shared camera during repeated grapples

The private hook/projectile camera pass at 83:8C86 must run only with
X=0550. This address is also the loop header for enemy slots 0640/0730;
running the private pass on every visit subtracted the camera movement
three times from P2's hook and batarangs. On the section-six rooftop this
pulled P2's attached anchor backward, reversed the swing and left P2
offscreen. The X guard restores one scroll subtraction for each player.
`verify_rooftop_hooks_save.py` checks stationary world-space anchors during
a camera pan, then real QS0 traversal with matching/staggered inputs,
a delayed second player, reversed ownership and deterministic replay.
This correction does not copy either player's swing state or inputs.

Grappling temporarily permits horizontal offscreen movement. The camera fits
both players when possible and follows the advancing player when their separation
exceeds the viewport. There is no catch-up teleport. Normal walking retains the shared-screen camera behavior;
native scripted pans and genuine fall recovery retain their existing behavior.

Player movement and camera subtraction now extend the original eight-bit screen
X into a signed 16-bit coordinate. Viewport movement stops and hook range checks
are bypassed during grappling, while true level boundaries and terrain still
apply. Offscreen terrain queries use remembered world collision cells because
the native query rejects positions outside the viewport and its collision ring
is overwritten as the camera advances. The cache is serialized with compatibility
for earlier co-op saves. Private objects far outside the viewport are clipped
before OAM conversion so they cannot wrap back onto the screen. P1/P2 LEFT/RIGHT
indicators identify offscreen partners.

The upper fire corridor now also assists the trailing player during rightward
camera movement. The scope is section 3, camera Y 240..288, camera X 2304..3584,
excluding scripted controller scenes. Once separation exceeds 96 pixels and
the trailing player is left of screen X 72, the body and movement anchor shift
right by at most the actual camera displacement plus eight pixels per frame.
This counters backward swing movement rather than only compensating for the pan.
When the camera reaches the end, the trailing player still receives correction
below screen X 48; this prevents the final swing from drifting out of view.
An active hook tip receives exactly the same shift, preserving its geometry;
pose, momentum, height, weapons and existing projectiles remain independent.
The assist works for either trailing player, including airborne players, and
is disabled outside this corridor. Visibility is a firm invariant inside it:
before player updates, after camera subtraction, and before drawing, each body is kept within
screen X 48..240 by translating its position, movement anchor and active hook
together. This correction also applies during backward pans, small player gaps
and loading already offscreen saves; it does not set a terrain collision flag
or cancel the hook. Forward assistance remains gradual; recovery of an already
offscreen save restores the body into view immediately.

verify_grapple_camera_save.py runs matching and staggered repeated hooks from the
reported QS0 for 420 frames, including swapped player bodies. Both remain above the fire, the camera reaches the
end of this section, both bodies stay within screen X 48..240, attached hook
geometry stays aligned, and world displacement
never exceeds 16 pixels per frame (no catch-up jumps). Save replay is deterministic.
This verifies the reported segment; the rest of the campaign still needs playtesting.

The corridor check allows native vertical camera adjustments during swings;
requiring camera Y to equal 256 disabled the assist for several frames. Tests
also cover already offscreen saves, both bodies outside with a small gap, and
backward pans.

### Section-three floor-collapse transition

After the descent reaches camera Y=0200, midpoint scrolling cannot go back
past X=0E00, where the native script installed the lower room. Earlier
columns still contain upper-corridor fire collision despite showing ordinary
street scenery; native forward-only scrolling prevents visiting them.
`verify_lower_room_boundary_save.py` tests the reported QS0 with
invulnerability disabled, either/both players walking fully left, continued
forward progress, next-section entry and deterministic state/video/audio.

The native controller at 83:A3DE tracks the fire corridor's floor collapse.
Its phase 2 at camera X 0E00 waits for vertical camera 0200 before installing
the lower room. The two-pixel midpoint vertical follow let both players fall
past the death threshold before reaching that trigger, causing a respawn loop.
During this specific phase, preserve the native player's vertical camera
request. Track the controller's allocated slot in owner[11], clear it on other
phases and player initialization, and leave ordinary co-op vertical follow intact.

verify_floor_collapse_save.py uses the reported QS0. The camera reaches 0200 in
159 frames, both players land and move independently, mid-descent save replay is
deterministic, and walking right exits to section 4. The saved fixture and the
user's original QS0 are preserved.

### Synchronized character arrivals

Private sprite uploads preserve CPU state around their ROM reads, just as
private native routine execution does. These reads must not charge extra
emulated cycles: otherwise section 1's special window entrance pauses and
jumps more slowly than the original. `verify_window_arrival.py` checks its
native flags, exact 144-frame pause and 52-frame jump, synchronized partner
poses, independent controls after landing, and state/video/audio replay.

Section 1's window entrance gradually reduces P2's trailing distance from
40 to 0 pixels across the native jump. He follows P1 through the same
opening and lands at x=144 without repositioning at the end. The usual
40-pixel offset would put him at x=104, inside the wall. Existing
saves at the trapped landing recover on the next player update, preserving
inventory and P1's world position. `verify_window_controls_save.py` checks
the reported QS0, both walking directions, jumping and deterministic replay.

owner[12] marks the entrance phase. Native player initialization at 80:BF33
(side view) or 80:C8D8 (belt) clears prior private OAM and arms the phase.
Per-frame preparation also detects old QS saves in the scripted state-19
entrance; these can wait several frames without executing player/draw loops,
so the stale P2 must be hidden before native CPU work resumes.

During arrival, P2 mirrors P1's complete native pose at a 40-pixel horizontal
offset. Native arrival/world/script routines execute once. P1 retains timed
native drawing; P2 uses private OAM without consuming native sprite slots.
The side-view movement anchor follows the offset; belt fields have their own
layout. After normal lifecycle, ground contact, the end of the scene wait,
and landing state, P2 switches to independent updates and the respawn template
is refreshed. Active rendering during arrival no longer means controls are
ready; diagnostic waits for gameplay must also check ground and scene state.

verify_arrivals.py checks the reported section-six entrance, removal of stale
P2, matching poses, independent controls after landing, save replay, and all
seven level starts. Six character entrances are mirrored; the vehicle level
is a separate native mode and has no Batman character arrival.

Arrival drawing preserves the caller CPU registers before returning to P1's
native builder. Combat fixtures normalize prior encounter reactions so their
controlled attack edges are not consumed by a reaction from the changed intro
timing; they still use the native combat/damage routines.

### Two Batmobiles (vehicle QS0)

Vehicle mode 9A=0, section 12 now has a private blue P2 Batmobile. The
native car is at 0460, its steering lane at 0328, and its two missile slots
at 04B0/0500. These fit the existing saved player context and third-slot
suffix. owner[13] selects vehicle mode, owner[14] records temporary missile
ownership during native enemy hit scans, and owner[15] selects car contact
ownership. The save layout is unchanged.

The timed road, speed, enemy and race scripts execute once. After the native
84:DD89 update returns at 80:AE91, P2 runs only 84:FCB0 missiles and
84:E554 car movement through a backed-up RAM JSL thunk. Road cursors and
globals are restored, and only P1 owns engine audio. P2 steers with Left/Right
and fires with the native fire button. Both cars share road speed and lives.
P2's lane projects relative to P1's view and stays within 80 pixels of it.
Fresh native vehicle entrance states mirror the timed car script before
independent driving begins. A destroyed P2 respawns using a shared life.

Native missile spawning uses each car's lane. P2 projection uses the shared
view and resets the projection sign scratch before calculating geometry.
Native enemy missile misses scan P2's two slots with the same hit response
and consume the correct owner's missile. Traffic contact checks also select
the correct car. The existing one-hit cheat applies to vehicle enemy hits.
The regroup cheat keeps the 16-bit vehicle lane instead of truncating it.

Private OAM marker FF05 draws the second car with blue body colours and the
native red lights, using shared vehicle VRAM. P1's sprite builder stays timed.
verify_batmobile_save.py checks QS0, independent steering, unchanged shared
road generation, both owners and missile slots, native enemy/contact damage,
1800 race frames, exact save/video/audio replay, and a fresh level-five
entrance. BizHawk screenshots in diagnostics/bizhawk-batmobile-*.png confirm
both cars are visible. This is not a complete racing-stage playthrough.

The racing boss uses its own perspective hitbox and cooldown at 84:FA25,
separate from traffic at 84:EE75. After its P1 missile scan misses at
84:FADC, owner[14]=2 temporarily selects P2's pair and repeats only the
native missile check at 84:FA35. Ownership restores at either return,
84:FA88 or 84:FADC. Native boss movement, cooldown and scripts remain timed
once. One-hit damage also applies to the two boss missile hit branches.
verify_batmobile_boss_save.py checks the reported boss QS0: equal damage from
either car and slot, correct consumption, cooldown rejection, native defeat,
save/video/audio replay, and actual controller-2 firing without injected shots.

verify_ground_shadow_save.py checks the reported section-13 QS0 against the pre-fix screenshot: all 61 changed pixels lie on the four-row ground line and become black, with the blue body unchanged. Movement/jump and exact save/video/audio replay also pass.

### Test-tube blasts and enemy targeting

The native tube phase at 0402 belongs to each player's saved context. Enemy
AI temporarily installs the nearer player, so reading only that context hid
the other player's blast. br_tube_enemy_read intercepts the completed native
LDA at the mapped enemy/script read sites in banks 80/82/83/84/87. It supplies
the active phase from either player, prioritizing the initial phase-1 blast
and then retaining the earlier active phase until both explosions finish.
The original read still executes with native timing. No player tube state is
copied or advanced by these checks; ordinary targeting and attacks retain
their selected player context. The native hit, reaction, defeat and cooldown
paths remain in the ROM.

verify_test_tube_save.py uses the reported section-15 QS0 and checks either
player's real block-then-X tube input, both clown enemies' native reactions
and defeat, changed and split nearer-player choices, simultaneous blasts,
separate animation phases, finite shared stock, and exact save/video/audio
replay. The original QS0 is preserved.

### Side-view shadow and layered boss health

Ground-shadow pixel selection now runs in both belt-scrolling mode 1 and
side-view mode 2. The latest QS0 changes exactly 61 embedded shadow pixels
to black while keeping the blue body unchanged.

br_boss_bar reads the native boss HUD health at 19AE and draws inside its
existing border in the top strip (interior y=25..30). Above 80 HP, each 80 HP adds a color layer: yellow, green,
blue, then purple. Each added layer has a lighter upper half and a darker
lower half. The top layer shrinks to reveal the next layer underneath;
the layer beneath yellow uses the original orange tones. Below 80 HP,
the overlay leaves the native bar entirely untouched, including its two
tones and transparent empty area. Exactly 80 HP is drawn as a full orange
two-tone final layer: the ROM switches to solid green at that boundary,
which previously leaked through when the overlay stopped at 80 HP.
Native health, boss scripts, HUD name
and portrait remain unchanged.

verify_side_shadow_boss_bar.py checks the QS0 shadow, all five color layers,
their two-tone boundaries and shrinking widths, exact native final-bar
pixels at 0/1/40/79 HP against captures with the overlay disabled, full
orange at exactly 80 HP (including the reported boss-green QS0), the native border,
and exact save/video/audio replay. Belt-shadow, co-op, Batmobile boss and
boss-exit regressions also pass.

### Scripted belt-scrolling walks

The section-17 introduction uses scene 80 and D6 to drive the native actor.
The previous per-frame scene >= 8 deactivation respawned P2 repeatedly;
the low-X spawn rule briefly put P2 ahead. Ordinary P2 controller updates
also reset the script's walking animation to idle.

br_scripted_walk keeps co-op active during native belt-scrolling actor
scripts. Before sprite construction, br_scripted_pose mirrors the updated
native body pose and animation with a constant 40-pixel trailing offset.
P2 health, inventory and projectile slots remain private. The native script
and world effects execute once; P2 resumes independent controls afterward.
Any in-progress enemy context swap still completes its normal restoration.

verify_script_walk_save.py checks the reported QS0 with opposing P2 input,
multiple native walk poses, constant separation, continuous visibility,
scene completion, independent controls and exact save/video/audio replay.
Arrival, co-op, boss-exit, tube and shadow/health-bar regressions pass.
