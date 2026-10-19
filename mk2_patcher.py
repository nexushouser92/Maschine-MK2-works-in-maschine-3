"""MK2 Activator for Maschine 3: a GUI over patch_mk2.py for non-technical users.

Finds Maschine 3.exe (NI registry key or default path), tells whether it is original or patched,
and enables the MK2 or restores the original. Only touches known versions (see VERSIONS in patch_mk2.py).
"""
import ctypes
import os
import subprocess
import sys
import tkinter as tk
import winreg
from tkinter import filedialog, messagebox

from patch_mk2 import VERSIONS, apply, identify

EXE_NAME = "Maschine 3.exe"
DEFAULT_PATH = r"C:\Program Files\Native Instruments\Maschine 3\Maschine 3.exe"
JAM_WARNING = "!!! WARNING: MASCHINE JAM WILL STOP WORKING IN MASCHINE 3 WHILE THE MK2 IS ENABLED !!!"


def find_maschine():
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Native Instruments\Maschine 3") as key:
            path = os.path.join(winreg.QueryValueEx(key, "InstallDir")[0], EXE_NAME)
            if os.path.isfile(path):
                return path
    except OSError:
        pass
    return DEFAULT_PATH if os.path.isfile(DEFAULT_PATH) else None


def maschine_running():
    out = subprocess.run(["tasklist", "/FI", f"IMAGENAME eq {EXE_NAME}", "/NH"],
                         capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW).stdout
    # Compared as bytes: the output uses the console code page (accents on non-English Windows).
    return EXE_NAME.lower().encode("ascii") in out.lower()


def write_atomic(path, data):
    """Writes to a temp file next to the target and swaps it in one step: never leaves a half-written .exe."""
    tmp = path + ".mk2tmp"
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, path)


class App:
    def __init__(self, root):
        self.root = root
        self.path = find_maschine()
        root.title("MK2 Activator for Maschine 3")
        root.resizable(False, False)
        frame = tk.Frame(root, padx=20, pady=16)
        frame.pack()
        tk.Label(frame, text="MK2 Activator for Maschine 3", font=("Segoe UI", 14, "bold")).pack(anchor="w")
        tk.Label(frame, text="Close Maschine 3 before continuing.",
                 font=("Segoe UI", 9), fg="#555").pack(anchor="w", pady=(2, 8))
        tk.Label(frame, text=JAM_WARNING, font=("Segoe UI", 10, "bold"), fg="#d00000",
                 wraplength=440, justify="left").pack(anchor="w")
        self.status = tk.Label(frame, font=("Segoe UI", 11), wraplength=440, justify="left")
        self.status.pack(anchor="w", pady=(12, 14))
        buttons = tk.Frame(frame)
        buttons.pack(fill="x")
        self.action = tk.Button(buttons, font=("Segoe UI", 10, "bold"), width=22, command=self.run)
        self.action.pack(side="left")
        tk.Button(buttons, text="Choose another file…", font=("Segoe UI", 10), command=self.choose).pack(side="right")
        self.refresh()

    def refresh(self):
        self.state = self.version = self.patches = self.data = None
        if not self.path:
            self.show("Maschine 3 was not found. Use “Choose another file…” to locate Maschine 3.exe.", "#b00", None)
            return
        self.show("Checking…", "#555", None)
        self.root.update()
        try:
            with open(self.path, "rb") as f:
                self.data = f.read()
        except OSError as e:
            self.show(f"Could not read Maschine 3: {e.strerror}", "#b00", None)
            return
        self.state, self.version, self.patches = identify(self.data)
        if self.state == "original":
            self.show(f"Maschine {self.version} original. The MK2 is not enabled yet.", "#000", "Enable MK2")
        elif self.state == "patched":
            self.show(f"Maschine {self.version} with the MK2 enabled.", "#070", "Restore original")
        else:
            known = ", ".join(v for v, _ in VERSIONS.values())
            self.show(f"This Maschine 3 version is not supported (supported: {known}). "
                      "Nothing was changed.", "#b00", None)

    def show(self, text, color, action):
        self.status.config(text=text, fg=color)
        self.action.config(text=action or "—", state="normal" if action else "disabled")

    def choose(self):
        path = filedialog.askopenfilename(title="Locate Maschine 3.exe", filetypes=[("Maschine 3", EXE_NAME)])
        if path:
            self.path = os.path.normpath(path)
            self.refresh()

    def run(self):
        if maschine_running():
            messagebox.showwarning("Maschine 3 is open", "Close Maschine 3 and press the button again.")
            return
        revert = self.state == "patched"
        if not revert and not messagebox.askyesno(
                "Enable MK2", f"{JAM_WARNING}\n\nDo you want to enable the MK2?", icon="warning"):
            return
        out, _ = apply(self.data, self.patches, revert)
        if out is None:
            messagebox.showerror("Error", "The file does not contain the expected bytes. Nothing was changed.")
            return
        try:
            write_atomic(self.path, out)
        except OSError as e:
            messagebox.showerror("Error", f"Could not write Maschine 3. Nothing was changed.\n\n{e.strerror}")
            return
        self.refresh()
        if revert:
            messagebox.showinfo("Done", "Maschine 3 is back to its factory state. The Maschine Jam works again.")
        else:
            messagebox.showinfo("Done", "MK2 enabled. Connect the MK2 and open Maschine 3.\n\n"
                                "If Native Access updates Maschine 3, you will need to enable it again.")


def main():
    if not ctypes.windll.shell32.IsUserAnAdmin():
        # Needed to write to Program Files; the compiled .exe already asks for it on launch.
        script = "" if getattr(sys, "frozen", False) else f'"{os.path.abspath(__file__)}"'
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, script, None, 1)
        return
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
