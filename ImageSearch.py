import os
import threading
import time
from pathlib import Path

import pyperclip
from PIL import Image
import imagehash
from rembg import remove
import mss
import tkinter as tk
from tkinter import ttk, messagebox

# --------------------------- Configuration -----------------------------------
WINDOW_SIZE = (300, 150)
IMAGES_DIR = Path("Images")
DEBUG_DIR = Path("Debug")
HASH_SIZE = 16  # pHash size ⇒ 64-bit hash

DEBUG_DIR.mkdir(exist_ok=True)

# ---------------------- Helper: perceptual hashing ---------------------------

def compute_phash(pil_img: Image.Image, hash_size: int = HASH_SIZE):
    return imagehash.phash(pil_img, hash_size=hash_size)

def best_match(target_hash, library_hashes):
    best_name, best_dist = None, float('inf')
    for name, h in library_hashes.items():
        d = target_hash - h
        if d < best_dist:
            best_name, best_dist = name, d
    return best_name, best_dist

# --------------------- Pre-compute library hashes ----------------------------

def load_library_hashes():
    hashes = {}
    for path in IMAGES_DIR.iterdir():
        if path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".bmp", ".gif"}:
            continue
        try:
            img = Image.open(path)
            if img.format == "GIF":
                img = img.convert("RGBA")
            hashes[path.name] = compute_phash(img)
        except Exception as e:
            print(f"[WARN] Hashing failed for {path.name}: {e}")
    if not hashes:
        raise RuntimeError("No supported images in Images/ directory.")
    return hashes

LIB_HASHES = load_library_hashes()
print(f"[INFO] Loaded {len(LIB_HASHES)} hashes.")

# --------------------------- GUI Components ----------------------------------

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Image Matcher")
        self.geometry(f"{WINDOW_SIZE[0]}x{WINDOW_SIZE[1]}")
        self.resizable(False, False)

        self.region = None
        self.auto_resize = tk.BooleanVar(value=True)
        self.result_var = tk.StringVar()

        self._build_ui()
        self._bind_keys()

    def _build_ui(self):
        bar = ttk.Frame(self)
        bar.pack(pady=10)
        ttk.Button(bar, text="Select Area", command=self.select_region).pack(side="left", padx=4)
        ttk.Button(bar, text="Check", command=self.check_match).pack(side="left", padx=4)
        ttk.Button(bar, text="Exit", command=self.destroy).pack(side="left", padx=4)

        #ttk.Checkbutton(self, text="Auto-resize after BG removal", variable=self.auto_resize).pack()
        ttk.Separator(self, orient="horizontal").pack(fill="x", pady=6)
        ttk.Label(self, text="Best match filename").pack()
        ttk.Label(self, textvariable=self.result_var,
                  font=("Consolas", 12, "bold"),
                  foreground="#006400").pack()

    def _bind_keys(self):
        def on_key_a(event):
            self.check_match()
            return "break"

        self.bind_all("<a>", on_key_a)
        self.bind_all("<Escape>", lambda e: self.destroy())


    def select_region(self):
        overlay = tk.Toplevel(self)
        overlay.attributes('-fullscreen', True)
        overlay.attributes('-alpha', 0.3)
        overlay.attributes('-topmost', True)
        overlay.config(bg='black')

        canvas = tk.Canvas(overlay, cursor="cross")
        canvas.pack(fill="both", expand=True)

        start_x = start_y = None
        rect = None

        def on_button_press(event):
            nonlocal start_x, start_y, rect
            start_x, start_y = event.x, event.y
            rect = canvas.create_rectangle(start_x, start_y,
                                           start_x, start_y,
                                           outline='red', width=2)

        def on_move(event):
            if rect:
                canvas.coords(rect, start_x, start_y, event.x, event.y)

        def on_button_release(event):
            end_x, end_y = event.x, event.y
            x1, y1 = min(start_x, end_x), min(start_y, end_y)
            x2, y2 = max(start_x, end_x), max(start_y, end_y)
            self.region = (x1, y1, x2, y2)
            overlay.destroy()
            messagebox.showinfo("Region chosen", str(self.region))

        canvas.bind("<ButtonPress-1>", on_button_press)
        canvas.bind("<B1-Motion>", on_move)
        canvas.bind("<ButtonRelease-1>", on_button_release)

    def check_match(self):
        if not self.region:
            self.region = (880, 512, 1081, 655)
        threading.Thread(target=self._pipeline, daemon=True).start()

    def _pipeline(self):
        t0 = time.time()
        try:
            with mss.mss() as sct:
                mon = {
                    'left': self.region[0],
                    'top': self.region[1],
                    'width': self.region[2] - self.region[0],
                    'height': self.region[3] - self.region[1]
                }
                img_rgb = sct.grab(mon)
                pil = Image.frombytes('RGB', img_rgb.size, img_rgb.rgb)

            pil_no_bg = remove(pil).convert('RGBA')
            if self.auto_resize.get():
                alpha = pil_no_bg.split()[-1]
                bbox = alpha.getbbox()
                if bbox:
                    pil_no_bg = pil_no_bg.crop(bbox).resize(pil.size, Image.LANCZOS)

            debug_path = DEBUG_DIR / f"capture_{int(time.time())}.png"
            #pil_no_bg.save(debug_path)

            target_hash = compute_phash(pil_no_bg)
            best_name, dist = best_match(target_hash, LIB_HASHES)
            if best_name:
                name_no_ext = os.path.splitext(best_name)[0]
                pyperclip.copy(name_no_ext)
                self.result_var.set(name_no_ext)
            else:
                self.result_var.set("(no match)")

            print(f"[INFO] done in {time.time() - t0:.2f}s ; dist={dist}")
        except Exception as err:
            messagebox.showerror("Error", str(err))

def main():
    App().mainloop()

if __name__ == "__main__":
    main()
