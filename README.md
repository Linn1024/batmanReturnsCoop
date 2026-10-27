# Batman Returns Co-op

## Portable EXE: choose a ROM and play

[Download the portable Windows x64 ZIP](https://github.com/Linn1024/coop-releases/releases/download/windows-2026-10-27/BatmanReturns-Coop-Portable-Windows-x64.zip).

1. Extract the entire ZIP and open **BatmanReturns-Coop.exe**. Keep its `engine` folder beside it.
2. On first run, choose your own original USA ROM. Its filename and folder can
   be anything; the launcher verifies the contents and remembers the location.
3. Next time, open the same EXE to play. The ROM is read from its original
   location and is not copied into the download.

Use **Settings > Choose ROM** to select a different location, **Settings >
Screen size** for 1x/2x/3x/4x windows or fullscreen, and **Settings > Controls**
(or **F2**) to rebind either player's keyboard and Xbox-compatible gamepad.
**F11** or **Alt+Enter** toggles fullscreen. Resizing the window and changing
controls are remembered for the next launch.

Settings and standalone saves live in `%LOCALAPPDATA%\Linn1024Coop\BatmanReturnsCoop`.
**Settings > Open saves and settings folder** opens that folder. Existing local
standalone saves/controls are copied there once when upgrading without replacing
newer user files. If the selected ROM is moved or deleted, choose it again.
These settings apply to the standalone EXE; BizHawk retains its own settings.


An **opening-stage prototype** for the SNES USA version, using a modified emulator core. The original ROM is unchanged.

Double-click **Play Batman Returns Co-op.cmd** or **BatmanReturns-Coop.exe**. Start the original game normally. A second Batman joins after the entrance animation lands.

- Independent movement, jumping, attacks, blocking and batarangs.
- P2 has a blue cowl, cape, gloves and boots with a gray suit, adapted from the supplied reference. This recolors the original sprite art; it does not add the reference's armor geometry.
- Separate health, shared lives, shared camera and world. Enemies choose the nearer player.
- A death consumes one shared life and respawns the fallen player beside the partner. Losing the final life reaches the original Game Over screen.
- P2 has a native-style HUD above the full playfield: blue portrait/name, original health bar, own complete item frame, and shared stock/lives/score. Each player selects their own item.
- Shared score and enemy/boss portrait, name and health appear in the top HUD only. The main screen keeps Black Batman's HUD.

## Controls

| Action | P1 keyboard | P2 keyboard | Xbox-style controller |
| --- | --- | --- | --- |
| Move | WASD | Arrow keys | D-pad / left stick |
| Jump | Space | L | A |
| Attack | F | J | X |
| Use selected item | G | K | B |
| Switch item | Q | O | Back |
| Block | R or T | U or P | Shoulder buttons |
| Start / pause | Enter | Numpad 0 | Start |

Both controller Start buttons can pause. Keyboard/controller mapping follows the game's default control type.

## Co-op options

On the title screen, select **COOP OPTIONS**, directly below **OPTIONS**, and
press **Start**. Either controller can choose Player 2's color: blue, red,
purple, green, gray or gold. Left/Right changes the color with a portrait
preview; A cycles it, and B returns to the title screen. Select BACK and
press Start or A to return as well.

The color applies to Player 2's sprites, Batmobile and top HUD. Ground shadows
stay black. Blue remains the default, and the choice is included in save states;
loading an older save uses blue.

## Cheat menu

Press **SNES Start + A + B** together on either controller. With the default
keyboard bindings, use **Enter + G + Space** for P1 or **Numpad 0 + K + L** for P2.
On an Xbox-style controller, use **Start + A + B**.

The menu pauses gameplay. Up/Down selects a row; Left/Right changes a setting;
SNES A applies an action; SNES B closes the menu. On the P1 keyboard, these are
W/S, A/D, G, and Space respectively. The opening chord also closes the menu.

- Invulnerability and one-hit kills for both players.
- Infinite shared lives and test tubes.
- Heal both players, add five lives, refill test tubes, and bring P2 beside P1.
- Select any of the seven levels and their sublevels, or restart the current level. Use Left/Right on LEVEL and SUBLEVEL, then A on LOAD SELECTED LEVEL.

Cheat settings are included in saves. Loading an older save restores cheats to
off. Level selection uses the original game's loader; it does **not** complete
complete co-op support for later stages or driving.

Both SNES **scanline** restrictions (32 sprites and 34 eight-pixel sprite
segments per row) are removed in this core, in both standalone and BizHawk.
Both players use a separate sprite buffer, so adding the second player no longer consumes
the original game's 128 OAM slots or cuts off enemies in crowded scenes. The
renderer supports 256 combined sprites; the game's native object limits remain.

**F2** opens keyboard rebinding, **F5** saves, **F8** loads, **F9** pauses emulation, **F1** shows controls, and **Alt+Enter** toggles fullscreen. Choose one of nine save slots in the window menu. Standalone settings and `saves/slot-N.brstate` are in the per-user folder described above.

## BizHawk

The local **Play Batman Returns in BizHawk.lnk** uses the installed `C:\TEMP2\Bizhawk\EmuHawk.exe` and this project's separate `bizhawk/batman.ini` profile.

On another machine, use **File > Open Advanced > Libretro**, select `engine/snes9x2005_libretro.dll`, then select your USA ROM. Configure both RetroPads under **Config > Controllers**. Opening the ROM through an ordinary SNES core runs the original single-player game. BizHawk manages its own saves.

## Current limits

Verified: cold boot, opening-stage movement/jumping, native attacks by either player, independent damage, batarangs, shared-life respawns, Game Over, P2 pause, deterministic state/video/audio replay and save reload after closing the process. Combat and death regressions include controlled fixtures. Both standalone and local BizHawk boot/input paths were exercised.

**This is not a completed campaign conversion.** Basic side-view movement, jumping and attacks now work for both players. Later stages, bosses, side-view projectiles and special interactions, driving sections, stage transitions, simultaneous grapples and all sprite poses still need implementation or testing. Full two-person playthroughs and physical controllers have not been tested. Save compatibility across prototype revisions is not guaranteed.

## Build

Place the original headerless 1,048,576-byte USA ROM beside the executable as `Batman Returns (U) [!].smc`. Supported SHA-256:

```text
f8d5c51f74df33edc827fbf8df7aab70160770ab0a896db6e59438ad9208cc6e
```

Build with a Windows x64 MinGW-w64 toolchain:

```powershell
.\build.ps1 -ToolchainBin C:\path\to\mingw64\bin
```

This workstation's existing toolchain is detected by default. See [development notes](DEVELOPMENT.md) and [third-party notices](THIRD_PARTY_NOTICES.md).
