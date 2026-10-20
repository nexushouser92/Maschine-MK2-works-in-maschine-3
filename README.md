# Maschine MK2 Works in Maschine 3

Makes your **Maschine MK2** work in the **Maschine 3** software again (Windows). Download **MK2 Activator**, click one button, and play.

> [!CAUTION]
> **!!! MASCHINE JAM WILL STOP WORKING IN MASCHINE 3 WHILE THE MK2 IS ENABLED !!!**
>
> The patch reuses the Maschine Jam connection slot for the MK2. Use **Restore original** in the Activator to get the Jam back.

> [!WARNING]
> This is an unofficial project, not affiliated with or endorsed by Native Instruments. It modifies `Maschine 3.exe`, which most likely goes against the Native Instruments license agreement. Use it at your own risk. It does not touch licensing or activation: you need your own licensed copy of Maschine 3.

## Requirements

- Windows 10 or 11 (64-bit)
- Maschine 3 installed and activated with Native Access, in a supported version
- Maschine MK2 driver installed (*Maschine Controller MK2 Driver*)

### Supported versions

| Maschine 3 | `Maschine 3` SHA-256 |
|---|---|
| 3.6.0 | 
| 3.7.1 | 

Any other version is refused and nothing is changed.

## How to use (no programming needed)

1. Download `MK2 Activator.exe` from the [Releases](../../releases) page.
2. Close Maschine 3.
3. Double-click `MK2 Activator.exe` and allow it to make changes (it needs administrator rights to modify Maschine 3 in Program Files).
4. Click **Enable MK2**.
5. Connect the MK2 and open Maschine 3.

To undo it, open the Activator again and click **Restore original**. This restores the exact factory file, without needing a backup. Repairing Maschine 3 in Native Access works too.

**After every Maschine 3 update from Native Access, the patch is gone.** Run the Activator again: if the new version is supported, click **Enable MK2**.

### Windows says the app is dangerous

The Activator is not digitally signed, so Windows SmartScreen shows "Unknown publisher". Click **More info** → **Run anyway**. You can review the source code in this repository or build it yourself (see below).

## How it works

Maschine 3 subscribes to each supported controller through the NI Hardware Agent, one code block per controller. Each block loads a per-device slot and sends `PID_CONNECT` with the controller's USB product ID:

```
ADD RAX, <slot>        48 05 xx xx 00 00
...
MOV EDX, <PID>         BA xx xx 00 00
MOV R9D, 'prmy'        41 B9 79 6D 72 70
MOV R8D, 'NiM3'        41 B8 33 4D 69 4E
```

The patch changes **3 bytes** in the Maschine Jam block:

| Change | Meaning |
|---|---|
| `ADD RAX,0x308` → `ADD RAX,0x368` | Jam slot → MK2 slot (unused by any other controller) |
| `MOV EDX,0x1500` → `MOV EDX,0x1140` | Jam PID → MK2 PID |

| Version | Slot byte | PID bytes |
|---|---|---|
| 3.6.0 | offset `0x5DD32F`: `08` → `68` | offsets `0x5DD37E`–`0x5DD37F`: `00 15` → `40 11` |
| 3.7.1 | offset `0x5C08EF`: `08` → `68` | offsets `0x5C093E`–`0x5C093F`: `00 15` → `40 11` |

Instruction lengths do not change. The `.exe` digital signature becomes invalid (expected for any modified file).

## Command line

```bash
python patch_mk2.py "Maschine 3.exe" "Maschine 3.patched.exe"
python patch_mk2.py "Maschine 3.patched.exe" "Maschine 3.restored.exe" --revert
```

The script checks the SHA-256 and every byte before writing, never modifies the input file, and on revert checks the result matches the original exactly.

## Build the Activator

```bash
python -m pip install pyinstaller
python -m PyInstaller --onefile --windowed --uac-admin --name "MK2 Activator" mk2_patcher.py
```

The result is in `dist\MK2 Activator.exe`. Upload it to a GitHub Release; do not commit it.

## Adding a new Maschine 3 version

1. Find the Jam block in the new `Maschine 3.exe` (search for `BA 00 15 00 00 41 B9 79 6D 72 70 41 B8 33 4D 69 4E`, then the `48 05 08 03 00 00` before it).
2. Check that slot `0x368` is still unused by every other block.
3. Add the original SHA-256 and the two offsets to `VERSIONS` in `patch_mk2.py`.
4. Test with a real MK2, then rebuild the Activator.

## Other unsupported controllers (research)

The controller slots are spaced `0x18` apart. In 3.7.1 four slots are unused: `0x350`, `0x368` (MK2, confirmed), `0x398` and `0x3B0`, which probably belong to the other dropped controllers: Maschine MK1 (`0x0808`), Mikro MK1 (`0x1110`) and Mikro MK2 (`0x1200`). Which slot belongs to which model is **unknown** and needs testing with the real hardware. `slot_tests.py` builds test variants:

```bash
python slot_tests.py "Maschine 3.exe" tests 1200 350 398 3b0
```

## Files

| File | Purpose |
|---|---|
| `patch_mk2.py` | Patch tables (versions, offsets, bytes) and command-line tool |
| `mk2_patcher.py` | MK2 Activator GUI |
| `slot_tests.py` | Test variants for other controllers |

This repository contains no Native Instruments code or binaries. Never upload `Maschine 3.exe`, original or patched.
