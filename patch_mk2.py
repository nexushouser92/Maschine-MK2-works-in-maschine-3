"""MK2 patch for Maschine 3: reuses the Maschine Jam subscription block (PID 0x1500)
so it sends PID_CONNECT for the Maschine MK2 (PID 0x1140), using the free slot +0x368.

Usage:
    python patch_mk2.py <input.exe> <output.exe>            apply the patch
    python patch_mk2.py <input.exe> <output.exe> --revert   undo it

Only works on the exact binaries analyzed (SHA-256 in VERSIONS); anything else aborts.
Never modifies the input file.
"""
import hashlib
import os
import sys

# SHA-256 of the original .exe -> (version, [(file offset, VA, original bytes, patched bytes, description)])
VERSIONS = {
    "968c0d3fc5e8e1f145b5ad95ab9862ac8cec508ccfea4768f09a85e5c9b2393a": ("3.6.0", [
        (0x5DD32D, 0x1405DDF2D, bytes.fromhex("480508030000"), bytes.fromhex("480568030000"),
         "ADD RAX,0x308 (Jam subscription) -> ADD RAX,0x368 (MK2 subscription)"),
        (0x5DD37D, 0x1405DDF7D, bytes.fromhex("BA00150000"), bytes.fromhex("BA40110000"),
         "MOV EDX,0x1500 (Jam PID) -> MOV EDX,0x1140 (MK2 PID)"),
    ]),
    "432948f7da644f092312c1c35dbc93c74185b4a7cd1fc869e444bcc6f8b7f20b": ("3.7.1", [
        (0x5C08ED, 0x1405C14ED, bytes.fromhex("480508030000"), bytes.fromhex("480568030000"),
         "ADD RAX,0x308 (Jam subscription) -> ADD RAX,0x368 (MK2 subscription)"),
        (0x5C093D, 0x1405C153D, bytes.fromhex("BA00150000"), bytes.fromhex("BA40110000"),
         "MOV EDX,0x1500 (Jam PID) -> MOV EDX,0x1140 (MK2 PID)"),
    ]),
}


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def apply(data, patches, revert):
    """Applies (or reverts) the patches on a copy; returns None if any byte does not match."""
    out = bytearray(data)
    log = []
    for off, va, orig, new, desc in patches:
        expect, write = (new, orig) if revert else (orig, new)
        found = bytes(out[off:off + len(expect)])
        if found != expect:
            return None, f"at {va:#x} (offset {off:#x}): expected {expect.hex(' ')}, found {found.hex(' ')}"
        out[off:off + len(write)] = write
        log.append(f"{'reverted' if revert else 'patched'} {va:#x} @ {off:#x}: {found.hex(' ')} -> {write.hex(' ')}  ({desc})")
    return out, log


def identify(data):
    """Returns ("original" | "patched", version, patches), or (None, None, None) for an unknown version."""
    h = sha256(data)
    if h in VERSIONS:
        return ("original",) + VERSIONS[h]
    # The patched file has no known hash up front: accept the version whose revert gives back the exact original.
    for orig_hash, (version, patches) in VERSIONS.items():
        out, _ = apply(data, patches, revert=True)
        if out is not None and sha256(out) == orig_hash:
            return "patched", version, patches
    return None, None, None


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    src, dst = sys.argv[1], sys.argv[2]
    revert = "--revert" in sys.argv[3:]
    if os.path.exists(dst) and os.path.samefile(src, dst):
        sys.exit("ABORTED: the output cannot be the same file as the input")
    data = open(src, "rb").read()

    state, version, patches = identify(data)
    if revert and state != "patched":
        sys.exit("ABORTED: the input is not a patched file of any known version")
    if not revert and state != "original":
        sys.exit(f"ABORTED: the input SHA-256 does not match any analyzed version\n  {sha256(data)}\n"
                 f"  known: {', '.join(v for v, _ in VERSIONS.values())}")
    out, log = apply(data, patches, revert)
    if out is None:
        sys.exit(f"ABORTED {log}")

    print(f"Maschine {version}")
    print("\n".join(log))
    with open(dst, "wb") as f:
        f.write(out)
    print(f"written {dst}\nSHA-256 {sha256(out)}")


if __name__ == "__main__":
    main()
