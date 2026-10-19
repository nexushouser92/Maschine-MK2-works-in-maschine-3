"""Builds test variants: the Jam block subscribes <PID> using <slot>, to find out which
free slot belongs to each unsupported controller.

Usage:
    python pruebas_slot.py <original.exe> <output_folder> <PID hex> <slot hex> [<slot hex> ...]
    python pruebas_slot.py "Maschine 3.7.1.original.exe" tests 1200 350 398 3b0

Starts from the same blocks as patch_mk2.py (known versions only) and changes the slot and the PID.
"""
import os
import sys

from patch_mk2 import apply, identify, sha256


def variant(patches, slot, pid):
    (off_add, va_add, orig_add, _, _), (off_mov, va_mov, orig_mov, _, _) = patches
    return [
        (off_add, va_add, orig_add, orig_add[:2] + slot.to_bytes(4, "little"), f"ADD RAX,0x308 -> ADD RAX,{slot:#x}"),
        (off_mov, va_mov, orig_mov, b"\xBA" + pid.to_bytes(4, "little"), f"MOV EDX,0x1500 -> MOV EDX,{pid:#x}"),
    ]


def main():
    if len(sys.argv) < 5:
        sys.exit(__doc__)
    src, out_dir, pid, slots = sys.argv[1], sys.argv[2], int(sys.argv[3], 16), [int(s, 16) for s in sys.argv[4:]]
    data = open(src, "rb").read()
    state, version, patches = identify(data)
    if state != "original":
        sys.exit("ABORTED: the input is not an original of a known version")
    os.makedirs(out_dir, exist_ok=True)
    for slot in slots:
        out, log = apply(data, variant(patches, slot, pid), revert=False)
        if out is None:
            sys.exit(f"ABORTED {log}")
        dst = os.path.join(out_dir, f"Maschine 3 {version} PID {pid:04X} slot {slot:X}.exe")
        with open(dst, "wb") as f:
            f.write(out)
        print(f"{dst}\n  " + "\n  ".join(log) + f"\n  SHA-256 {sha256(out)}")


if __name__ == "__main__":
    main()
