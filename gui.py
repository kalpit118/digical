"""
GUI for DigiCal Business Calculator
Tkinter-based interface optimized for Raspberry Pi display
"""
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from datetime import datetime
import json
import os
import subprocess
import platform
import threading
import config
import locales
from PIL import Image, ImageTk, ImageOps
from calculator import Calculator
from database import Database
from transaction_manager import TransactionManager
from history_manager import HistoryManager
from graph_generator import GraphGenerator
from handler_manager import HandlerManager
from updater import Updater

class SystemPanel:
    """Displays system status icons (Battery, Wifi) in the header."""
    def __init__(self, parent, theme, is_dark=False):
        self.parent = parent
        self.T = theme
        self.is_dark = is_dark
        self.frame = tk.Frame(parent, bg=self.T["hdr_bg"])
        self.frame.pack(side=tk.RIGHT, padx=5)

        # Icons (Battery, Wifi from right to left)
        self.battery_label = tk.Label(self.frame, bg=self.T["hdr_bg"])
        self.battery_label.pack(side=tk.RIGHT, padx=2)

        self.wifi_label = tk.Label(self.frame, bg=self.T["hdr_bg"])
        self.wifi_label.pack(side=tk.RIGHT, padx=2)

        self.time_label = tk.Label(self.frame, font=(config.LABEL_FONT[0], max(8, config.LABEL_FONT[1] - 2), "bold"), 
                                   bg=self.T["hdr_bg"], fg=self.T["text"])
        self.time_label.pack(side=tk.RIGHT, padx=(2, 5))

        self.shift_label = tk.Label(self.frame, bg=self.T["hdr_bg"])
        self.shift_label.pack(side=tk.RIGHT, padx=4)

        self.icons = {}
        self._load_icons()

        # Set initial default icons for instant startup
        self.battery_label.config(image=self.icons.get("bat100"))
        self.wifi_label.config(image=self.icons.get("wifi_off"))
        self.time_label.config(text=datetime.now().strftime("%I:%M %p •"))
        self.shift_label.config(image="")
        
        self.refresh()

    def show_shift(self):
        if "shift" in self.icons:
            self.shift_label.config(image=self.icons["shift"])

    def hide_shift(self):
        self.shift_label.config(image="")

    def _load_icons(self):
        try:
            base_dir = os.path.dirname(__file__)
            header_assets = os.path.join(base_dir, "assets", "header")
            _resample = getattr(Image, 'Resampling', Image).LANCZOS
            sz = max(16, int(config.LABEL_FONT[1] * 1.6))
            size = (sz, sz)

            icon_files = {
                "wifi_on": "wifi_on.png", "wifi_off": "wifi_off.png",
                "bat0": "battery0.png", "bat10": "battery10.png",
                "bat50": "battery50.png", "bat90": "battery90.png", "bat100": "battery100.png",
                "shift": "shiftkey.png"
            }

            for key, filename in icon_files.items():
                path = os.path.join(header_assets, filename)
                if os.path.exists(path):
                    img = Image.open(path).convert("RGBA").resize(size, _resample)
                    if not self.is_dark and key == "shift":
                        # Invert RGB while preserving Alpha
                        r, g, b, a = img.split()
                        rgb = Image.merge("RGB", (r, g, b))
                        inv_rgb = ImageOps.invert(rgb)
                        r2, g2, b2 = inv_rgb.split()
                        img = Image.merge("RGBA", (r2, g2, b2, a))
                    self.icons[key] = ImageTk.PhotoImage(img)
        except Exception as e:
            print(f"Error loading system icons: {e}")

    def refresh(self):
        """Begin an asynchronous status update."""
        if not self.frame.winfo_exists():
            return
        threading.Thread(target=self._fetch_status, daemon=True).start()
        self.frame.after(10000, self.refresh) # Refresh every 10 seconds

    def _fetch_status(self):
        """Detect system info across platforms."""
        is_win = platform.system() == "Windows"
        
        # 1. Battery
        bat_key = "bat100"
        try:
            if is_win:
                out = subprocess.check_output("wmic path win32_battery get estimatedchargeremaining /value", shell=True, text=True)
                res = [l.split('=')[1] for l in out.splitlines() if '=' in l]
                pct = int(res[0]) if res else 100
            else:
                with open("/sys/class/power_supply/BAT0/capacity", "r") as f:
                    pct = int(f.read().strip())
            
            if pct <= 5: bat_key = "bat0"
            elif pct <= 25: bat_key = "bat10"
            elif pct <= 60: bat_key = "bat50"
            elif pct <= 95: bat_key = "bat90"
            else: bat_key = "bat100"
        except: bat_key = "bat100"

        # 2. Wifi
        wifi_key = "wifi_off"
        try:
            if is_win:
                out = subprocess.check_output("netsh interface show interface name=\"Wi-Fi\"", shell=True, text=True)
                if "Connect state:        Connected" in out:
                    wifi_key = "wifi_on"
            else:
                # Use 'general status' for better compatibility with older NetworkManager versions
                try:
                    res = subprocess.check_output(["nmcli", "-t", "-f", "STATE", "general"], text=True).strip().lower()
                    # Check for connected state (includes 'connected' and 'connected (local only)')
                    if res.startswith("connected"): wifi_key = "wifi_on"
                except:
                    # Fallback for even older systems or if nmcli is missing 'general'
                    res = subprocess.check_output("hostname -I", shell=True, text=True).strip()
                    if res: wifi_key = "wifi_on"
        except: pass

        # Update UI in main thread
        now_time = datetime.now().strftime("%I:%M %p •")
        self.frame.after(0, lambda: self._apply_icons(bat_key, wifi_key, now_time))

    def _apply_icons(self, bat, wifi, time_str):
        if not self.frame.winfo_exists():
            return
        if bat in self.icons: self.battery_label.config(image=self.icons[bat])
        if wifi in self.icons: self.wifi_label.config(image=self.icons[wifi])
        self.time_label.config(text=time_str)

class DigiCalGUI:
    def __init__(self, root):
        self.root = root
        self.root.title(config.APP_NAME)
        self.root.geometry(f"{config.WINDOW_WIDTH}x{config.WINDOW_HEIGHT}")

        # Initialize components
        self.db = Database()
        self.calculator = Calculator()
        self.transaction_manager = TransactionManager(self.db)
        self.history_manager = HistoryManager(self.db)
        self.graph_generator = GraphGenerator(self.transaction_manager)
        self.handler_manager = HandlerManager(self.db)

        # ── Theme state (load before any widget is created) ───────────────
        settings = self._load_settings()
        self.dark_mode: bool = settings.get("dark_mode", False)
        self.language = settings.get("language", "en")
        
        # Fullscreen initialization
        self.fullscreen: bool = settings.get("fullscreen", False)
        if self.fullscreen:
            self.root.attributes("-fullscreen", True)
            
        # Bind F11 for convenience
        self.root.bind("<F11>", lambda e: self._toggle_fullscreen(not self.fullscreen))
        
        # Pull font scale early and update global config tuples
        self.font_scale = settings.get("font_scale", "Medium")
        config.set_font_scale(self.font_scale)
        
        self.tr = locales.get_translator(self.language)
        self.T: dict = config.get_theme(self.dark_mode)
        self._apply_ttk_styles()
        self.root.configure(bg=self.T["bg"])

        # Hide mouse cursor if setting is enabled
        self.hide_cursor: bool = settings.get("hide_cursor", False)

        # Current mode
        self.current_mode = "calculator"
        self.current_graph_info = None # (func_name, args, kwargs)

        # ── Keypad state ──────────────────────────────────────────────────
        # These are set/cleared by show_transaction_dialog so the keypad
        # dispatcher can trigger payment cycling and Sale/Expense buttons.
        self._active_payment_var = None       # tk.StringVar of current dialog
        self._active_payment_combo = None     # ttk.Combobox widget
        self._active_payment_change_fn = None # on_payment_change callback
        self._active_save_sale_fn = None      # save_as_sale callable
        self._active_save_expense_fn = None   # save_as_expense callable
        self._active_dialog_close_fn = None   # close callable
        self._transaction_dialog_open = False # True while dialog is visible

        self._t9_last_key = None
        self._t9_last_time = 0.0
        self._t9_index = 0

        # ── Navigation history (Back key) ─────────────────────────────────
        # Tracks the sequence of modes visited so the Back key can reverse them.
        self._nav_stack = []          # list of mode strings e.g. ['calculator', 'sales']
        self._nav_back_in_progress = False  # guard: don't push while popping

        # Create UI
        self.create_widgets()
        self.switch_mode("calculator")
        
        # Enable app to take standard keyboard input
        self.root.bind("<Key>", self._on_keyboard_input)
        
        # Apply global cursor settings robustly
        self._apply_global_cursor()

    # ── Settings persistence ─────────────────────────────────────────────
    _SETTINGS_FILE = "settings.json"

    def _load_settings(self):
        try:
            with open(self._SETTINGS_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_settings(self, data):
        existing = self._load_settings()
        existing.update(data)
        try:
            with open(self._SETTINGS_FILE, "w") as f:
                json.dump(existing, f, indent=2)
        except Exception:
            pass

    def _toggle_fullscreen(self, value: bool):
        """Toggle fullscreen state and save to settings."""
        self.fullscreen = value
        self.root.attributes("-fullscreen", self.fullscreen)
        self._save_settings({"fullscreen": self.fullscreen})
        self.apply_theme()

    # ── Theme helpers ──────────────────────────────────────────────────────────
    def _apply_ttk_styles(self):
        """Configure ttk widget styles for the active neumorphic palette."""
        self.root.option_add("*highlightColor", "red")
        T = self.T
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("TNotebook",        background=T["bg"],      borderwidth=0)
        style.configure("TNotebook.Tab",    background=T["bg_dark"], foreground=T["text"],
                        padding=[8, 3],     font=config.LABEL_FONT)
        style.map("TNotebook.Tab",
                  background=[("selected", T["bg"]), ("active", T["shadow_lite"])],
                  foreground=[("selected", T["accent"])])
        style.configure("TCombobox",        fieldbackground=T["entry_bg"],
                        background=T["bg_dark"], foreground=T["entry_fg"],
                        selectbackground=T["accent"], selectforeground="#FFFFFF",
                        arrowcolor=T["accent"])
        style.map("TCombobox",
                  fieldbackground=[("focus", T["accent"]), ("readonly", T["entry_bg"])],
                  foreground=[("focus", T["bg"]), ("readonly", T["entry_fg"])])
        # Scale the dropdown listbox popout explicitly
        self.root.option_add("*TCombobox*Listbox.font", config.LABEL_FONT)
        self.root.option_add("*TCombobox*Listbox.background", T["entry_bg"])
        self.root.option_add("*TCombobox*Listbox.foreground", T["entry_fg"])
                  
        style.configure("Treeview",         background=T["tree_even"],
                        fieldbackground=T["tree_even"], foreground=T["tree_fg"],
                        rowheight=int(config.LABEL_FONT[1] * 2.2), font=config.LABEL_FONT)
        style.configure("Treeview.Heading", background=T["hdr_bg"],
                        foreground=T["accent"],
                        font=(config.LABEL_FONT[0], config.LABEL_FONT[1], "bold"))
        style.map("Treeview",
                  background=[("selected", T["accent"])],
                  foreground=[("selected", "#FFFFFF")])
        style.configure("Vertical.TScrollbar",
                        background=T["subtext"], troughcolor=T["display_bg"],
                        borderwidth=0, relief="flat", width=14, arrowsize=0)
        style.map("Vertical.TScrollbar",
                  background=[("active", T["accent"]), ("pressed", T["accent"]),
                              ("!disabled", T["subtext"])],
                  troughcolor=[("!disabled", T["display_bg"])])

    def apply_theme(self):
        """Refresh T, re-style ttk, then destroy+rebuild all widgets."""
        self.tr = locales.get_translator(self.language)
        self.T = config.get_theme(self.dark_mode)
        self._apply_ttk_styles()
        self.root.configure(bg=self.T["bg"])
        # Destroy everything and rebuild cleanly
        for w in self.root.winfo_children():
            w.destroy()
        self.create_widgets()
        self.switch_mode(self.current_mode)
        # Re-apply cursor setting after rebuild
        if getattr(self, 'hide_cursor', False):
            self.root.config(cursor="none")

    def _toggle_dark_mode(self, val: bool):
        """Persist dark_mode setting and apply theme immediately."""
        self.dark_mode = val
        self._save_settings({"dark_mode": val})
        self.apply_theme()

    def _change_language(self, lang_code: str):
        """Persist language setting and apply immediately."""
        self.language = lang_code
        self._save_settings({"language": lang_code})
        self.apply_theme()

    def _change_font_scale(self, scale_name: str):
        """Persist scaled font tuple configuration"""
        self.font_scale = scale_name
        self._save_settings({"font_scale": scale_name})
        config.set_font_scale(scale_name)
        self.apply_theme()

    def _bind_mousewheel(self, widget, callback):
        """Cross-platform mouse-wheel binding"""
        widget.bind_all("<MouseWheel>", callback)
        widget.bind_all("<Button-4>", callback)
        widget.bind_all("<Button-5>", callback)

    def _unbind_mousewheel(self, widget):
        """Cross-platform mouse-wheel unbinding"""
        widget.unbind_all("<MouseWheel>")
        widget.unbind_all("<Button-4>")
        widget.unbind_all("<Button-5>")

    def _handle_mousewheel(self, event, canvas, orient="vertical"):
        """Unified scroll handler for Windows/Linux/macOS"""
        if event.num == 4: # Linux Scroll Up
            delta = 1
        elif event.num == 5: # Linux Scroll Down
            delta = -1
        else: # Windows/macOS event.delta
            delta = event.delta / 120
        
        if orient == "vertical":
            canvas.yview_scroll(int(-1 * delta), "units")
        else:
            canvas.xview_scroll(int(-1 * delta), "units")

    def _neu_btn(self, parent, text, command=None, kind="normal", **kw):
        """Create a neumorphic styled flat button."""
        T = self.T
        if kind == "equals":
            bg, fg, abg = T["equals_bg"], T["equals_fg"], T["success"]
        elif kind == "operator":
            bg, fg, abg = T["btn_bg"], T["operator_fg"], T["bg_dark"]
        elif kind == "mode":
            bg, fg, abg = T["mode_bg"], T["mode_fg"], T["shadow_dark"]
        elif kind == "danger":
            bg, fg, abg = T["danger"], "#FFFFFF", T["bg_dark"]
        else:
            bg, fg, abg = T["btn_bg"], T["btn_fg"], T["bg_dark"]
        return tk.Button(
            parent, text=text, command=command,
            font=kw.pop("font", config.BUTTON_FONT),
            bg=bg, fg=fg,
            activebackground=abg, activeforeground=fg,
            relief=tk.FLAT, bd=0, cursor="hand2",
            highlightthickness=1,
            highlightbackground=T["shadow_dark"],
            highlightcolor="red",
            **kw
        )

    # ── Inline toast / confirm (replaces messagebox popups) ──────────────
    def _show_toast(self, msg, kind="success", duration=2500):
        """Show an inline toast banner at the top of the window.
        kind: 'success' | 'error' | 'warning' | 'info'
        """
        T = self.T
        colours = {
            "success": (T["success"], "#FFFFFF"),
            "error":   (T["danger"],  "#FFFFFF"),
            "warning": (T["warning"], "#FFFFFF"),
            "info":    (T["mode_fg"], "#FFFFFF"),
        }
        icons = {"warning": "\u26a0", "info": "\u2139"}
        bg, fg = colours.get(kind, colours["info"])
        toast = tk.Frame(self.root, bg=bg)
        toast.place(relx=0.05, y=55, relwidth=0.9, height=42)
        toast.lift()
        lbl = tk.Label(toast, text=f"  {icons.get(kind, '')}  {msg}" if kind in icons else f"  {msg}",
                 font=(config.BUTTON_FONT[0], 8, "bold"),
                 bg=bg, fg=fg, anchor="w")
        if kind == "success" and getattr(self, "_icon_success", None):
            lbl.config(image=self._icon_success, compound=tk.LEFT, padx=5)
        elif kind == "error" and getattr(self, "_icon_error", None):
            lbl.config(image=self._icon_error, compound=tk.LEFT, padx=5)
        elif kind == "success":
            lbl.config(text=f"  \u2713  {msg}")
        elif kind == "error":
            lbl.config(text=f"  \u2717  {msg}")
            
        lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Button(toast, text="\u2715", font=(config.BUTTON_FONT[0], 8),
                  bg=bg, fg=fg, relief=tk.FLAT, bd=0,
                  command=toast.destroy, cursor="hand2",
                  activebackground=bg).pack(side=tk.RIGHT, padx=4)
        self.root.after(duration, lambda: toast.destroy() if toast.winfo_exists() else None)

    def _show_confirm(self, msg, on_yes, on_no=None):
        """Show an inline confirmation bar instead of messagebox.askyesno."""
        T = self.T
        bar = tk.Frame(self.root, bg=T["warning"])
        bar.place(relx=0.02, y=55, relwidth=0.96, height=48)
        bar.lift()
        tk.Label(bar, text=f"  \u26a0  {msg}",
                 font=(config.BUTTON_FONT[0], 8, "bold"),
                 bg=T["warning"], fg="#FFFFFF", anchor="w").pack(side=tk.LEFT, fill=tk.X, expand=True)

        def _yes():
            bar.destroy()
            on_yes()

        def _no():
            bar.destroy()
            if on_no:
                on_no()

        tk.Button(bar, text=" Yes ", font=(config.BUTTON_FONT[0], 8, "bold"),
                  bg=T["danger"], fg="#FFFFFF", relief=tk.FLAT, bd=0,
                  command=_yes, cursor="hand2").pack(side=tk.RIGHT, padx=2)
        tk.Button(bar, text=" No ", font=(config.BUTTON_FONT[0], 8, "bold"),
                  bg=T["shadow_dark"], fg="#FFFFFF", relief=tk.FLAT, bd=0,
                  command=_no, cursor="hand2").pack(side=tk.RIGHT, padx=2)

    def create_widgets(self):
        """Create main UI components"""
        T = self.T
        

        
        # Top bar
        self.top_frame = tk.Frame(self.root, bg=T["hdr_bg"], height=50)
        self.top_frame.pack(fill=tk.X, padx=2, pady=2)

        # Left: Apps launcher button
        try:
            base_dir = os.path.dirname(__file__)
            _app_img_path = os.path.join(base_dir, "assets", "apps.png")
            _resample = getattr(Image, 'Resampling', Image).LANCZOS
            app_sz = max(16, int(config.LABEL_FONT[1] * 1.6))
            icon_sz = max(12, int(config.LABEL_FONT[1] * 1.25))
            _raw_img = Image.open(_app_img_path).resize((app_sz, app_sz), _resample)
            self._apps_icon = ImageTk.PhotoImage(_raw_img)
            self._icon_success = ImageTk.PhotoImage(Image.open(os.path.join(base_dir, "assets", "right.png")).resize((icon_sz, icon_sz), _resample))
            self._icon_error = ImageTk.PhotoImage(Image.open(os.path.join(base_dir, "assets", "wrong.png")).resize((icon_sz, icon_sz), _resample))
        except Exception:
            self._apps_icon = None
            self._icon_success = None
            self._icon_error = None

        tk.Button(
            self.top_frame, text=" " + self.tr("Apps"), image=self._apps_icon, compound=tk.LEFT if self._apps_icon else tk.NONE,
            font=(config.LABEL_FONT[0], config.LABEL_FONT[1], "bold"),
            bg=T["mode_bg"], fg=T["mode_fg"],
            relief=tk.FLAT, bd=0, cursor="hand2",
            activebackground=T["shadow_dark"],
            highlightthickness=1, highlightbackground=T["shadow_dark"],
            command=self._show_app_launcher
        ).pack(side=tk.LEFT, padx=(4, 2))

        # Center: app title (absolutely centered, shifted left slightly for visual weight of 'g')
        title_size = max(16, config.BUTTON_FONT[1] + 4)
        title_label = tk.Label(
            self.top_frame, text=self.tr("DigiCal"),
            font=(config.BUTTON_FONT[0], title_size, "bold"),
            bg=T["hdr_bg"], fg=T["accent"]
        )
        title_label.place(relx=0.49, rely=0.45, anchor=tk.CENTER)

        # Right: System Panel (Wifi, Bluetooth, Battery)
        self.system_panel = SystemPanel(self.top_frame, self.T, is_dark=self.dark_mode)

        # Product quick-pick bar
        self.product_bar_frame = tk.Frame(self.root, bg=T["bg_dark"], height=36)
        self.product_bar_frame.pack(fill=tk.X, padx=2)
        self.product_bar_frame.pack_propagate(False)
        tk.Button(self.product_bar_frame, text="\u27f3",
                  font=(config.BUTTON_FONT[0], 10, "bold"),
                  bg=T["bg_dark"], fg=T["accent"],
                  relief=tk.FLAT, bd=0, cursor="hand2",
                  activebackground=T["shadow_dark"],
                  command=self.refresh_product_bar).pack(side=tk.RIGHT, padx=(2, 4))
        self._product_bar_var = tk.StringVar()
        self._product_bar_cb = ttk.Combobox(
            self.product_bar_frame, textvariable=self._product_bar_var,
            font=(config.LABEL_FONT[0], 7), state="readonly"
        )
        self._product_bar_cb.pack(side=tk.LEFT, padx=2, pady=2, expand=True, fill=tk.X)
        self._product_bar_cb.bind("<<ComboboxSelected>>", self._product_bar_select)
        self.refresh_product_bar()

        # Display area — neumorphic inset card with LCD-style font
        outer = tk.Frame(self.root, bg=T["shadow_dark"], bd=0)
        outer.pack(fill=tk.BOTH, expand=True, padx=6, pady=(4, 6))
        self.outer_display_frame = outer
        inner = tk.Frame(outer, bg=T["shadow_lite"], bd=0)
        inner.pack(fill=tk.BOTH, expand=True, padx=(1, 0), pady=(1, 0))
        self.display_frame = tk.Frame(inner, bg=T["display_bg"], height=140)
        self.display_frame.pack(fill=tk.BOTH, expand=True, padx=(0, 1), pady=(0, 1))
        self.display_frame.pack_propagate(False)

        self.display = tk.Label(
            self.display_frame, text="0",
            font=("Consolas", 36, "bold"),
            bg=T["display_bg"], fg=T["display_fg"],
            anchor=tk.E, padx=12, pady=2
        )
        self.display.pack(side=tk.TOP, fill=tk.X)

        # Container for live calculation (right) and handler name (left)
        self.live_info_frame = tk.Frame(self.display_frame, bg=T["display_bg"])
        self.live_info_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=12, pady=0)
        
        self.handler_status_label = tk.Label(
            self.live_info_frame, text="H: None",
            font=("Consolas", 14, "bold"),
            bg=T["display_bg"], fg=T["subtext"]
        )
        self.handler_status_label.pack(side=tk.LEFT)
        
        self.live_display = tk.Label(
            self.live_info_frame, text="",
            font=("Consolas", 20, "bold"),
            bg=T["display_bg"], fg=T["subtext"],
            anchor=tk.E
        )
        self.live_display.pack(side=tk.RIGHT, fill=tk.X, expand=True)

        self.update_handler_status()

        # Content area

        self.content_frame = tk.Frame(self.root, bg=T["bg"])
        self.content_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=3)



    def clear_content_frame(self):
        """Clear the content frame"""
        for widget in self.content_frame.winfo_children():
            widget.destroy()
    
    def switch_mode(self, mode):
        """Switch between different modes.
        Pushes the current mode onto the nav stack before switching so the
        Back key can retrace the navigation path.
        """
        # Record where we came from (unless this is a Back-navigation or same mode)
        if not getattr(self, '_nav_back_in_progress', False):
            prev = getattr(self, 'current_mode', None)
            if prev and prev != mode:
                stack = getattr(self, '_nav_stack', [])
                stack.append(prev)
                self._nav_stack = stack
        self.current_mode = mode
        self.clear_content_frame()

        if mode == "calculator":
            # CRITICAL: hide content_frame FIRST so it releases its expand=True claim
            # before outer_display_frame re-takes the full window. Wrong order = tiny display.
            self.content_frame.pack_forget()
            self.product_bar_frame.pack(fill=tk.X, padx=2, before=self.outer_display_frame)
            # Restore product bar combobox key bindings for home mode
            if hasattr(self, '_product_bar_cb'):
                self._product_bar_cb.unbind('<Down>')
                self._product_bar_cb.unbind('<Up>')
            # Now safely expand outer_display_frame to fill the whole window
            self.outer_display_frame.pack(fill=tk.BOTH, expand=True, padx=6, pady=(4, 0))
            self.display_frame.pack_propagate(True)   # allow expansion
            self.display_frame.config(height=0)
            self.display.config(font=("Consolas", 36, "bold"), anchor=tk.E, pady=10)
            self.live_display.config(font=("Consolas", 24, "bold"), pady=6)
            # Force a geometry pass so Tkinter recalculates sizes immediately
            self.root.update_idletasks()
        else:
            # Block the product bar combobox from opening its dropdown in non-home modes
            if hasattr(self, '_product_bar_cb'):
                self._product_bar_cb.bind('<Down>', lambda e: "break")
                self._product_bar_cb.bind('<Up>', lambda e: "break")
            self.product_bar_frame.pack_forget()
            self.outer_display_frame.pack(fill=tk.X, expand=False, padx=6, pady=(4, 2))
            self.display_frame.config(height=80)      # Fixed height for modes like Sales
            self.display_frame.pack_propagate(False)
            self.display.config(font=("Consolas", 24, "bold"), anchor=tk.CENTER, pady=2)
            self.live_display.config(font=("Consolas", 14, "bold"), pady=0)
            # Hide calculator-only widgets if they exist
            for attr in ('_calc_sep1', '_calc_sep2', 'receipt_frame'):
                w = getattr(self, attr, None)
                if w and w.winfo_exists():
                    w.pack_forget()
            # Restore live_info_frame packing
            self.live_info_frame.pack_forget()
            self.live_info_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=12)
            self.content_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=3)
            # ESC on any non-home mode returns to Calculator
            self.root.bind("<Escape>", lambda e: self.switch_mode("calculator"))

        if mode == "calculator":
            self.show_calculator_mode()
        elif mode == "sales":
            self.show_sales_mode()
        elif mode == "expense":
            self.show_expense_mode()
        elif mode == "history":
            self.show_history_mode()
        elif mode == "graphs":
            self.show_graphs_mode()
        elif mode == "customers":
            self.show_customers_mode()
        elif mode == "products":
            self.show_products_mode()
        elif mode == "handlers":
            self.show_handlers_mode()
        elif mode == "settings":
            self.show_settings_mode()
    
    def show_calculator_mode(self):
        """Show calculator home: top=expression, middle=item list, bottom=live total"""
        T = self.T

        # Clean up any leftover calculator widgets from a previous call
        for attr in ('_calc_sep1', '_calc_sep2', 'receipt_frame'):
            w = getattr(self, attr, None)
            if w and w.winfo_exists():
                w.destroy()

        # --- Separator 1 (below expression) ---
        self._calc_sep1 = tk.Frame(self.display_frame, bg=T["accent"], height=1)
        self._calc_sep1.pack(side=tk.TOP, fill=tk.X, padx=6)

        # --- MIDDLE: scrollable receipt list ---
        self.receipt_frame = tk.Frame(self.display_frame, bg=T["display_bg"])
        self.receipt_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=12, pady=2)

        # Repack live_display at BOTTOM first, then separator above it
        self.live_display.pack_forget()
        self.live_display.pack(side=tk.BOTTOM, fill=tk.X)

        # --- Separator 2 (above live total) ---
        self._calc_sep2 = tk.Frame(self.display_frame, bg=T["accent"], height=2)
        self._calc_sep2.pack(side=tk.BOTTOM, fill=tk.X, padx=0)

        self.update_display(self.calculator.get_expression())

        # On the home screen ESC opens the App Launcher
        self.root.bind("<Escape>", lambda e: self._show_app_launcher())

        # Reset line products if not set
        if not hasattr(self, '_line_products'):
            self._line_products = {}

    def _on_keyboard_input(self, event):
        """Map standard PC keyboard events globally for text, numbers and enter."""
        # Allow native behavior for entries and dropdowns
        try:
            focused = self.root.focus_get()
            if focused and focused.winfo_class() in ("Entry", "Text", "TCombobox"):
                return
        except KeyError:
            return

        if self.current_mode == "calculator":
            char = event.char
            keysym = event.keysym
            
            if keysym in ("Return", "KP_Enter"):
                self.calculator_button_click("=")
                return "break"
                
            if keysym in ("BackSpace", "Delete"):
                self.calculator_button_click("CE")
                return "break"
                
            if char in "0123456789.":
                self.calculator_button_click(char)
                return "break"
                
            op_map = {"*": "×", "x": "×", "X": "×", "/": "÷", "+": "+", "-": "-"}
            if char in op_map:
                self.calculator_button_click(op_map[char])
                return "break"
                
            if char == "%":
                self.calculator_button_click("%")
                return "break"

    def calculator_button_click(self, button):
        """Handle calculator button clicks"""
        if button in '0123456789.':
            # If starting a fresh expression, clear leftover product names
            if self.calculator.get_expression() in ("0", ""):
                self._line_products = {}
            self.calculator.add_digit(button)
            self.update_display(self.calculator.get_expression())
        elif button in '+-×÷':
            self.calculator.add_operator(button)
            self.update_display(self.calculator.get_expression())
        elif button == '=':
            expression = self.calculator.get_expression()
            result = self.calculator.evaluate()
            self.update_display(result)
            if not result.startswith("Error"):
                # Calculate handler incentive
                handler = self.handler_manager.get_current_handler()
                handler_id = handler['id'] if handler else None
                handler_incentive = self.handler_manager.calculate_incentive(result)
                
                # Save calculation with handler info
                self.db.add_calculation(expression, result, handler_id, handler_incentive)
                
                # Show transaction categorization dialog
                self.show_transaction_dialog(result)
        elif button == 'C':
            self.calculator.clear()
            self._line_products = {}
            self.update_display("0")
        elif button == 'CE':
            self.calculator.clear_entry()
            self.update_display(self.calculator.get_expression())
        elif button == '%':
            self.calculator.add_digit('%')
            self.update_display(self.calculator.get_expression())
        elif button == 'MC':
            self.calculator.clear_memory()
            self._show_toast(self.tr("Memory cleared"))
        elif button == 'MR':
            mem_value = self.calculator.recall_memory()
            self.calculator.set_expression(mem_value)
            self.update_display(mem_value)
        elif button == 'M+':
            try:
                value = float(self.display.cget("text"))
                self.calculator.add_to_memory(value)
                self._show_toast(self.tr("Added {} to memory").format(value))
            except:
                pass
        elif button == 'M-':
            try:
                value = float(self.display.cget("text"))
                self.calculator.subtract_from_memory(value)
                self._show_toast(self.tr("Subtracted {} from memory").format(value))
            except:
                pass


    def show_sales_mode(self):
        """Show sales entry interface"""
        T = self.T
        self.update_display(self.tr("Add Sales Transaction"))

        form_frame = tk.Frame(self.content_frame, bg=T["bg"])
        form_frame.pack(pady=5)

        tk.Label(form_frame, text=self.tr("Amount:"), font=config.LABEL_FONT,
                 bg=T["bg"], fg=T["text"]).grid(row=0, column=0, sticky=tk.W, pady=5)
        amount_entry = tk.Entry(form_frame, font=config.LABEL_FONT, width=20,
                                bg=T["entry_bg"], fg=T["entry_fg"],
                                insertbackground=T["text"], relief=tk.FLAT,
                                highlightthickness=1, highlightbackground=T["shadow_dark"])
        amount_entry.grid(row=0, column=1, pady=5, padx=10)

        tk.Label(form_frame, text=self.tr("Category:"), font=config.LABEL_FONT,
                 bg=T["bg"], fg=T["text"]).grid(row=1, column=0, sticky=tk.W, pady=5)
        category_var = tk.StringVar()
        categories = self.transaction_manager.get_sales_categories()
        category_combo = ttk.Combobox(form_frame, textvariable=category_var,
                                      values=categories, font=config.LABEL_FONT, width=18)
        category_combo.grid(row=1, column=1, pady=5, padx=10)
        if "Product Sales" in categories:
            category_var.set("Product Sales")
        elif categories:
            category_combo.current(0)

        tk.Label(form_frame, text=self.tr("Description:"), font=config.LABEL_FONT,
                 bg=T["bg"], fg=T["text"]).grid(row=2, column=0, sticky=tk.W, pady=5)
        desc_entry = tk.Entry(form_frame, font=config.LABEL_FONT, width=20,
                              bg=T["entry_bg"], fg=T["entry_fg"],
                              insertbackground=T["text"], relief=tk.FLAT,
                              highlightthickness=1, highlightbackground=T["shadow_dark"])
        desc_entry.grid(row=2, column=1, pady=5, padx=10)

        tk.Label(form_frame, text=self.tr("Payment:"), font=config.LABEL_FONT,
                 bg=T["bg"], fg=T["text"]).grid(row=3, column=0, sticky=tk.W, pady=5)
        payment_var = tk.StringVar(value="Cash")
        payment_combo = ttk.Combobox(form_frame, textvariable=payment_var,
                                     values=config.PAYMENT_METHODS, font=config.LABEL_FONT,
                                     width=18, state="readonly")
        payment_combo.grid(row=3, column=1, pady=5, padx=10)

        due_customer = [None]

        def on_payment_change(event=None):
            if payment_var.get() == "Due":
                def on_customer_confirmed(cid):
                    due_customer[0] = cid
                self.show_due_customer_dialog(on_customer_confirmed)
            else:
                due_customer[0] = None

        payment_combo.bind('<<ComboboxSelected>>', on_payment_change)

        def add_sale():
            try:
                amount = float(amount_entry.get())
                category = category_var.get()
                description = desc_entry.get()
                if not category:
                    self._show_toast(self.tr("Please select a category"), kind="error")
                    return
                payment_method = payment_var.get()
                if payment_method == "Due":
                    if not due_customer[0]:
                        self._show_toast(self.tr("Please select a customer for Due payment"), kind="error")
                        return
                    description = f"{description} [Due: {due_customer[0]}]".strip()
                handler_id = None
                current_handler = self.handler_manager.get_current_handler()
                if current_handler:
                    handler_id = current_handler['id']
                trans_id = self.transaction_manager.add_sale(amount, category, description, payment_method, handler_id)
                if payment_method == "Due" and due_customer[0]:
                    self.db.add_due_record(trans_id, due_customer[0], amount)
                self._deduct_product_quantities()
                self._show_toast(f"Sales transaction of ₹{amount:.2f} added") # Skip translate, dynamic
                amount_entry.delete(0, tk.END)
                desc_entry.delete(0, tk.END)
                due_customer[0] = None
                payment_var.set("Cash")
                self.show_transaction_summary('sales')
            except ValueError:
                self._show_toast(self.tr("Please enter a valid amount"), kind="error")

        self._neu_btn(form_frame, self.tr("Add Sale"), command=add_sale,
                     kind="equals", width=20, height=2
                     ).grid(row=4, column=0, columnspan=2, pady=5)

        self.show_transaction_summary('sales')
        self.root.after(250, lambda: amount_entry.focus_force())


    def show_expense_mode(self):
        """Show expense entry interface"""
        T = self.T
        self.update_display(self.tr("Add Expense Transaction"))

        form_frame = tk.Frame(self.content_frame, bg=T["bg"])
        form_frame.pack(pady=5)

        tk.Label(form_frame, text=self.tr("Amount:"), font=config.LABEL_FONT,
                 bg=T["bg"], fg=T["text"]).grid(row=0, column=0, sticky=tk.W, pady=5)
        amount_entry = tk.Entry(form_frame, font=config.LABEL_FONT, width=20,
                                bg=T["entry_bg"], fg=T["entry_fg"],
                                insertbackground=T["text"], relief=tk.FLAT,
                                highlightthickness=1, highlightbackground=T["shadow_dark"])
        amount_entry.grid(row=0, column=1, pady=5, padx=10)

        tk.Label(form_frame, text=self.tr("Category:"), font=config.LABEL_FONT,
                 bg=T["bg"], fg=T["text"]).grid(row=1, column=0, sticky=tk.W, pady=5)
        category_var = tk.StringVar()
        categories = self.transaction_manager.get_expense_categories()
        category_combo = ttk.Combobox(form_frame, textvariable=category_var,
                                      values=categories, font=config.LABEL_FONT, width=18)
        category_combo.grid(row=1, column=1, pady=5, padx=10)
        if "Supplies" in categories:
            category_var.set("Supplies")
        elif categories:
            category_combo.current(0)

        tk.Label(form_frame, text=self.tr("Description:"), font=config.LABEL_FONT,
                 bg=T["bg"], fg=T["text"]).grid(row=2, column=0, sticky=tk.W, pady=5)
        desc_entry = tk.Entry(form_frame, font=config.LABEL_FONT, width=20,
                              bg=T["entry_bg"], fg=T["entry_fg"],
                              insertbackground=T["text"], relief=tk.FLAT,
                              highlightthickness=1, highlightbackground=T["shadow_dark"])
        desc_entry.grid(row=2, column=1, pady=5, padx=10)

        tk.Label(form_frame, text=self.tr("Payment:"), font=config.LABEL_FONT,
                 bg=T["bg"], fg=T["text"]).grid(row=3, column=0, sticky=tk.W, pady=5)
        payment_var = tk.StringVar(value="Cash")
        payment_combo = ttk.Combobox(form_frame, textvariable=payment_var,
                                     values=config.PAYMENT_METHODS, font=config.LABEL_FONT,
                                     width=18, state="readonly")
        payment_combo.grid(row=3, column=1, pady=5, padx=10)

        due_customer = [None]

        def on_payment_change(event=None):
            if payment_var.get() == "Due":
                def on_customer_confirmed(cid):
                    due_customer[0] = cid
                self.show_due_customer_dialog(on_customer_confirmed)
            else:
                due_customer[0] = None

        payment_combo.bind('<<ComboboxSelected>>', on_payment_change)

        def add_expense():
            try:
                amount = float(amount_entry.get())
                category = category_var.get()
                description = desc_entry.get()
                if not category:
                    self._show_toast(self.tr("Please select a category"), kind="error")
                    return
                payment_method = payment_var.get()
                if payment_method == "Due":
                    if not due_customer[0]:
                        self._show_toast(self.tr("Please select a customer for Due payment"), kind="error")
                        return
                    description = f"{description} [Due: {due_customer[0]}]".strip()
                handler_id = None
                current_handler = self.handler_manager.get_current_handler()
                if current_handler:
                    handler_id = current_handler['id']
                trans_id = self.transaction_manager.add_expense(amount, category, description, payment_method, handler_id)
                if payment_method == "Due" and due_customer[0]:
                    self.db.add_due_record(trans_id, due_customer[0], amount)
                self._deduct_product_quantities()
                self._show_toast(f"Expense transaction of ₹{amount:.2f} added")
                amount_entry.delete(0, tk.END)
                desc_entry.delete(0, tk.END)
                due_customer[0] = None
                payment_var.set("Cash")
                self.show_transaction_summary('expense')
            except ValueError:
                self._show_toast(self.tr("Please enter a valid amount"), kind="error")

        self._neu_btn(form_frame, self.tr("Add Expense"), command=add_expense,
                     kind="danger", width=20, height=2
                     ).grid(row=4, column=0, columnspan=2, pady=5)

        self.show_transaction_summary('expense')
        self.root.after(250, lambda: amount_entry.focus_force())


    def show_transaction_summary(self, trans_type):
        """Show transaction summary"""
        T = self.T
        summary_frame = tk.Frame(self.content_frame, bg=T["bg"])
        summary_frame.pack(pady=10, fill=tk.BOTH, expand=True)

        daily = self.transaction_manager.get_daily_summary()
        weekly = self.transaction_manager.get_weekly_summary()
        monthly = self.transaction_manager.get_monthly_summary()

        if trans_type == 'sales':
            daily_val = daily['total_sales']
            weekly_val = weekly['total_sales']
            monthly_val = monthly['total_sales']
            title = self.tr("Sales Summary")
        else:
            daily_val = daily['total_expenses']
            weekly_val = weekly['total_expenses']
            monthly_val = monthly['total_expenses']
            title = self.tr("Expense Summary")

        tk.Label(summary_frame, text=title,
                 font=(config.BUTTON_FONT[0], 12, "bold"),
                 bg=T["bg"], fg=T["accent"]).pack(pady=5)

        info_text = self.tr("Today: ₹{:.2f}\nThis Week: ₹{:.2f}\nThis Month: ₹{:.2f}").format(daily_val, weekly_val, monthly_val)
        tk.Label(summary_frame, text=info_text, font=config.LABEL_FONT,
                 bg=T["bg"], fg=T["text"], justify=tk.LEFT).pack(pady=5)


    def show_history_mode(self):
        """Show history interface"""
        T = self.T
        self.update_display(self.tr("Transaction & Calculation History"))

        notebook = ttk.Notebook(self.content_frame)
        notebook.pack(fill=tk.BOTH, expand=True)

        calc_frame = tk.Frame(notebook, bg=T["bg"])
        notebook.add(calc_frame, text=self.tr("Calculations"))
        
        calc_cols = (self.tr("Date"), self.tr("Calculation"), self.tr("Result"))
        calc_tree = ttk.Treeview(calc_frame, columns=calc_cols, show="headings", height=15)
        
        calc_tree.heading(self.tr("Date"), text=self.tr("Date"), anchor=tk.CENTER)
        calc_tree.column(self.tr("Date"), width=150, anchor=tk.CENTER, stretch=True)
        calc_tree.heading(self.tr("Calculation"), text=self.tr("Calculation"), anchor=tk.CENTER)
        calc_tree.column(self.tr("Calculation"), width=250, anchor=tk.CENTER, stretch=True)
        calc_tree.heading(self.tr("Result"), text=self.tr("Result"), anchor=tk.CENTER)
        calc_tree.column(self.tr("Result"), width=150, anchor=tk.CENTER, stretch=True)
        
        calc_tree.tag_configure("odd", background=T.get("tree_odd", "#34495E"), foreground=T.get("tree_fg", "white"))
        calc_tree.tag_configure("even", background=T.get("tree_even", "#2C3E50"), foreground=T.get("tree_fg", "white"))
        
        calc_sb = ttk.Scrollbar(calc_frame, orient=tk.VERTICAL, command=calc_tree.yview)
        calc_tree.configure(yscrollcommand=calc_sb.set)
        calc_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5,0), pady=5)
        calc_sb.pack(side=tk.RIGHT, fill=tk.Y, padx=(0,5), pady=5)
        
        for i, (expr, result, timestamp) in enumerate(self.history_manager.get_calculation_history()):
            tag = "even" if i % 2 == 0 else "odd"
            try:
                from datetime import datetime as _dt
                short_ts = _dt.strptime(str(timestamp)[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
            except Exception:
                short_ts = str(timestamp)[:10]
            calc_tree.insert("", tk.END, values=(short_ts, expr, result), tags=(tag,))

        trans_frame = tk.Frame(notebook, bg=T["bg"])
        notebook.add(trans_frame, text=self.tr("Transactions"))
        
        # All columns stretch proportionally — widths act as relative weights.
        # Total= 590, distributed across ~694px usable → each scales ~1.18×
        # Date≈118, Type≈71, Amt≈83, Category≈236, Via≈71, By≈107 (balanced)
        trans_cols = ("Date", "Type", "Amt", "Category", "Via", "By")
        trans_tree = ttk.Treeview(trans_frame, columns=trans_cols, show="headings", height=15)
        
        col_config = {
            "Date":     (100, tk.CENTER),
            "Type":     (60,  tk.CENTER),
            "Amt":      (70,  tk.CENTER),
            "Category": (200, tk.CENTER),
            "Via":      (60,  tk.CENTER),
            "By":       (90,  tk.CENTER),
        }
        for col in trans_cols:
            w, anc = col_config[col]
            trans_tree.heading(col, text=col, anchor=tk.CENTER)
            trans_tree.column(col, width=w, minwidth=w, anchor=tk.CENTER, stretch=True)
            
        trans_tree.tag_configure("odd", background=T.get("tree_odd", "#34495E"), foreground=T.get("tree_fg", "white"))
        trans_tree.tag_configure("even", background=T.get("tree_even", "#2C3E50"), foreground=T.get("tree_fg", "white"))
        
        trans_sb = ttk.Scrollbar(trans_frame, orient=tk.VERTICAL, command=trans_tree.yview)
        trans_tree.configure(yscrollcommand=trans_sb.set)
        trans_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5,0), pady=5)
        trans_sb.pack(side=tk.RIGHT, fill=tk.Y, padx=(0,5), pady=5)
        
        def _fmt_amount(val):
            """Show 120 for whole numbers, 120.5 for decimals."""
            try:
                f = float(val)
                return str(int(f)) if f == int(f) else f"{f:.2f}".rstrip('0')
            except Exception:
                return str(val)

        def _fmt_category(cat):
            """Abbreviate long category names: 'Product Sales' → 'Pro. Sales'."""
            if not cat or cat == "-":
                return "-"
            words = cat.split()
            if len(words) >= 2 and len(words[0]) > 4:
                return words[0][:3] + ". " + " ".join(words[1:])
            return cat
        
        for i, trans in enumerate(self.history_manager.get_transaction_history()):
            t_type = "Sale" if trans[1] == "sales" else "Expe"
            amount  = _fmt_amount(trans[2])
            category = _fmt_category(trans[3] or "-")
            raw_date = trans[5] if len(trans) > 5 else "-"
            # Format date as dd/mm/yy
            try:
                from datetime import datetime as _dt
                dt = _dt.strptime(raw_date[:10], "%Y-%m-%d")
                short_date = dt.strftime("%d/%m/%y")
            except Exception:
                short_date = str(raw_date)[:8]
            payment_method = trans[7] if len(trans) > 7 and trans[7] else "Cash"
            handler_name = (trans[9] if len(trans) > 9 and trans[9] else "-")
            tag = "even" if i % 2 == 0 else "odd"
            trans_tree.insert("", tk.END, values=(short_date, t_type, amount, category, payment_method, handler_name), tags=(tag,))

        def _on_tab_change(e):
            sel = notebook.select()
            if not sel: return
            w = self.root.nametowidget(sel)
            for c in w.winfo_children():
                if c.winfo_class() == "Treeview":
                    c.focus_set()
                    if not c.selection() and c.get_children():
                        c.selection_set(c.get_children()[0])
                        c.focus(c.get_children()[0])
                    break

        notebook.bind("<<NotebookTabChanged>>", _on_tab_change)

        self._history_notebook = notebook

        # Initial focus setup for keypad navigation
        def _focus_history():
            if notebook.winfo_exists():
                sel = notebook.select()
                if sel:
                    w = self.root.nametowidget(sel)
                    for c in w.winfo_children():
                        if c.winfo_class() == "Treeview":
                            c.focus_force()
                            if not c.selection() and c.get_children():
                                c.selection_set(c.get_children()[0])
                                c.focus(c.get_children()[0])
                            break
                            
        self.root.after(250, _focus_history)


    def show_graphs_mode(self):
        """Show graphs interface with scrollable button navigation and responsive charts"""
        T = self.T
        self.update_display(self.tr("Sales & Expense Analytics"))

        # Scrollable Button Bar
        btn_container = tk.Frame(self.content_frame, bg=T["bg"], height=65)
        btn_container.pack(fill=tk.X, pady=5)
        btn_container.pack_propagate(False)

        canvas = tk.Canvas(btn_container, bg=T["bg"], height=60, highlightthickness=0)
        scrollbar = ttk.Scrollbar(btn_container, orient="horizontal", command=canvas.xview)
        
        scrollable_frame = tk.Frame(canvas, bg=T["bg"])
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(xscrollcommand=scrollbar.set)

        # Buttons in scrollable frame
        graph_buttons = [
            (self.tr("Weekly Chart"), self.show_weekly_graph),
            (self.tr("Monthly Trend"), self.show_monthly_graph),
            (self.tr("Sales Pie"), lambda: self.show_category_pie('sales')),
            (self.tr("Expense Pie"), lambda: self.show_category_pie('expense')),
            (self.tr("Profit Trend"), self.show_profit_graph),
            (self.tr("Handlers"), self.show_handler_performance)
        ]

        for text, command in graph_buttons:
            self._neu_btn(scrollable_frame, text, command=command, kind="mode", width=16
                          ).pack(side=tk.LEFT, padx=3, pady=2)

        canvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.BOTTOM, fill=tk.X)

        # Mousewheel scrolling for the canvas
        self._bind_mousewheel(canvas, lambda e: self._handle_mousewheel(e, canvas, orient="horizontal"))

        self.graph_frame = tk.Frame(self.content_frame, bg=T["bg"])
        self.graph_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Bind resize event for responsive graphs
        self.graph_frame.bind("<Configure>", self._on_graph_resize)

        # Store for keypad navigation wrap-around
        self._graphs_scrollable_frame = scrollable_frame

        # Show default graph
        self.show_weekly_graph()

        # Set initial focus to the first button robustly
        def _focus_first():
            if scrollable_frame.winfo_exists() and scrollable_frame.winfo_children():
                btn = scrollable_frame.winfo_children()[0]
                btn.focus_force()
                self._ensure_visible(btn)
                
        self.root.after(250, _focus_first)

    def clear_graph_frame(self):
        """Clear graph display"""
        for widget in self.graph_frame.winfo_children():
            widget.destroy()
    
    def show_weekly_graph(self):
        """Display weekly graph"""
        self.current_graph_info = ('create_weekly_graph', (), {})
        
        w = self.graph_frame.winfo_width()
        h = self.graph_frame.winfo_height()
        if not self.graph_frame.winfo_exists():
            return
            
        if w > 1 and h > 1:
            self.refresh_current_graph(w, h)
        else:
            self.clear_graph_frame()
            fig = self.graph_generator.create_weekly_graph()
            canvas = FigureCanvasTkAgg(fig, master=self.graph_frame)
            canvas.draw()
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
    
    def show_monthly_graph(self):
        """Display monthly graph"""
        self.current_graph_info = ('create_monthly_graph', (), {})
        
        w = self.graph_frame.winfo_width()
        h = self.graph_frame.winfo_height()
        if not self.graph_frame.winfo_exists():
            return
            
        if w > 1 and h > 1:
            self.refresh_current_graph(w, h)
        else:
            self.clear_graph_frame()
            fig = self.graph_generator.create_monthly_graph()
            canvas = FigureCanvasTkAgg(fig, master=self.graph_frame)
            canvas.draw()
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
    
    def show_category_pie(self, trans_type):
        """Display category pie chart"""
        self.current_graph_info = ('create_category_pie_chart', (trans_type,), {})
        
        w = self.graph_frame.winfo_width()
        h = self.graph_frame.winfo_height()
        if not self.graph_frame.winfo_exists():
            return
            
        if w > 1 and h > 1:
            self.refresh_current_graph(w, h)
        else:
            self.clear_graph_frame()
            fig = self.graph_generator.create_category_pie_chart(trans_type)
            canvas = FigureCanvasTkAgg(fig, master=self.graph_frame)
            canvas.draw()
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
    
    def show_profit_graph(self):
        """Display profit trend graph"""
        self.current_graph_info = ('create_profit_trend_graph', (), {})
        
        w = self.graph_frame.winfo_width()
        h = self.graph_frame.winfo_height()
        if not self.graph_frame.winfo_exists():
            return
            
        if w > 1 and h > 1:
            self.refresh_current_graph(w, h)
        else:
            self.clear_graph_frame()
            fig = self.graph_generator.create_profit_trend_graph()
            canvas = FigureCanvasTkAgg(fig, master=self.graph_frame)
            canvas.draw()
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
    
    def update_display(self, text):
        """Update the display"""
        self.display.config(text=str(text))
        if hasattr(self, 'live_display'):
            self._update_live_display(str(text))
        if hasattr(self, 'receipt_frame') and self.current_mode == "calculator":
            self._update_receipt(str(text))

    def _parse_expression_to_receipt(self, expr):
        import re
        parts = re.findall(r'[+\-×÷]|(?:\d+\.?\d*%)|(?:\d+\.?\d*)', expr)
        lines = []
        current_op = ""
        for p in parts:
            if p in "+-×÷":
                current_op = p
            else:
                lines.append((current_op, p))
                current_op = ""
        if current_op:
            lines.append((current_op, ""))
        return lines

    def _update_receipt(self, expr):
        """Build the receipt lines based on the parsed expression"""
        for widget in self.receipt_frame.winfo_children():
            widget.destroy()
            
        if expr == "0" or not expr or "Error" in expr:
            return
            
        lines = self._parse_expression_to_receipt(expr)
        if not hasattr(self, '_line_products'):
            self._line_products = {}
            
        T = self.T

        # Create a scrollable Canvas
        canvas = tk.Canvas(self.receipt_frame, bg=T["display_bg"], highlightthickness=0, bd=0, width=1, height=1)
        scrollbar = ttk.Scrollbar(self.receipt_frame, orient=tk.VERTICAL, command=canvas.yview)
        
        inner = tk.Frame(canvas, bg=T["display_bg"])
        
        # Configure canvas window resizing
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas_window = canvas.create_window((0, 0), window=inner, anchor="sw")
        
        def _on_canvas_configure(event):
            canvas.itemconfig(canvas_window, width=event.width)
            # Push the inner frame to the bottom if it's shorter than the canvas
            if inner.winfo_reqheight() < event.height:
                canvas.coords(canvas_window, 0, event.height)
            else:
                canvas.coords(canvas_window, 0, inner.winfo_reqheight())
                
        canvas.bind("<Configure>", _on_canvas_configure)

        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Pack canvas and scrollbar
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Mouse-wheel scrolling
        self._bind_mousewheel(canvas, lambda e: self._handle_mousewheel(e, canvas, orient="vertical"))

        font = (config.BUTTON_FONT[0], 14)
        for i, (op, val) in enumerate(lines):
            name = self._line_products.get(i, "")
            
            row = tk.Frame(inner, bg=T["display_bg"])
            row.pack(side=tk.TOP, fill=tk.X, pady=1)
            
            # Sub-frame ensures we can force column widths with pack
            lbl_name = tk.Label(row, text=name, font=font, bg=T["display_bg"], fg=T["text"], anchor=tk.W)
            lbl_name.pack(side=tk.LEFT, fill=tk.X, expand=True)
            
            lbl_op = tk.Label(row, text=op, font=font, bg=T["display_bg"], fg=T["text"], width=3, anchor=tk.CENTER)
            lbl_op.pack(side=tk.LEFT)
            
            lbl_val = tk.Label(row, text=val, font=font, bg=T["display_bg"], fg=T["text"], width=10, anchor=tk.E)
            lbl_val.pack(side=tk.RIGHT)
            
        # Scroll to the very bottom automatically
        self.receipt_frame.update_idletasks()
        canvas.yview_moveto(1.0)

    def _update_live_display(self, text):
        if self.current_mode != "calculator" or "Error" in text or text in ("0", ""):
            self.live_display.config(text="")
            return
            
        if any(op in text for op in ['+', '-', '×', '÷', '%']):
            val = self._evaluate_live(text)
            if val is not None and val != text:
                self.live_display.config(text=f"={val}")
            else:
                self.live_display.config(text="")
        else:
            self.live_display.config(text="")

    def _evaluate_live(self, expr):
        try:
            import re
            expression = expr.replace("×", "*").replace("÷", "/")
            
            # Use calculator's _handle_percentage for accurate logic
            if hasattr(self, 'calculator'):
                expression = self.calculator._handle_percentage(expression)
            else:
                expression = re.sub(r'(\d+\.?\d*)%', r'(\1/100)', expression)
                
            expression = re.sub(r'[\+\-\*\/\.]$', '', expression)
            if not expression: return None
            # Strip leading zeros from integer tokens (010 -> 10)
            expression = re.sub(r'\b0+(\d+)', r'\1', expression)
            
            result = eval(expression)
            if isinstance(result, float):
                if result.is_integer():
                    result = int(result)
                else:
                    result = round(result, 8)
            return str(result)
        except ZeroDivisionError:
            return "Error: Div by 0"
        except Exception:
            return None

    def _on_graph_resize(self, event):
        """Handle graph frame resize to redraw current graph"""
        if self.current_mode != "graphs" or not self.current_graph_info:
            return
            
        # Avoid redrawing too frequently or when size is tiny
        if event.width < 50 or event.height < 50:
            return
            
        # Redraw the current graph with new size
        self.refresh_current_graph(event.width, event.height)

    def refresh_current_graph(self, width, height):
        """Redraw the current graph with specific pixel dimensions"""
        if not self.current_graph_info or not self.graph_frame.winfo_exists():
            return
            
        func_name, args, kwargs = self.current_graph_info
        
        # Convert pixels to inches for matplotlib (W x H / DPI)
        dpi = config.GRAPH_DPI
        figsize = (width / dpi, height / dpi)
        
        kwargs['figsize'] = figsize
        
        # Call the graph generator method
        func = getattr(self.graph_generator, func_name)
        fig = func(*args, **kwargs)
        
        # Update UI
        self.clear_graph_frame()
        canvas = FigureCanvasTkAgg(fig, master=self.graph_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def show_handler_performance(self):
        """Display handler performance graph"""
        # Get handler data (id, name, total_incentives)
        handler_data = self.db.get_handlers_performance() # Assuming this exists or I'll add it
        self.current_graph_info = ('create_handler_performance_graph', (handler_data,), {})
        
        # Initial draw using current frame size if available
        w = self.graph_frame.winfo_width()
        h = self.graph_frame.winfo_height()
        if not self.graph_frame.winfo_exists():
            return
            
        if w > 1 and h > 1:
            self.refresh_current_graph(w, h)
        else:
            self.clear_graph_frame()
            fig = self.graph_generator.create_handler_performance_graph(handler_data)
            canvas = FigureCanvasTkAgg(fig, master=self.graph_frame)
            canvas.draw()
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def _apply_global_cursor(self):
        """Forcefully hide or restore the mouse cursor across all existing and future widgets."""
        c = "none" if getattr(self, 'hide_cursor', False) else ""
        
        # 1. Update root
        try: self.root.config(cursor=c)
        except Exception: pass
        
        # 2. Update default Tkinter options for future standard widgets
        self.root.option_add('*cursor', c)
        
        # 3. Update defaults for Ttk widgets
        style = ttk.Style()
        for wclass in ('TEntry', 'TCombobox', 'TButton', 'Treeview'):
            style.configure(wclass, cursor=c)
            
        # 4. Recursively update all currently instantiated widgets instantly
        def walk(w):
            try: w.config(cursor=c)
            except Exception: pass
            for child in w.winfo_children():
                walk(child)
        walk(self.root)
    
    # ── Full-window overlay helpers ──────────────────────────────────────────
    def _open_overlay(self, title):
        """Place a full-window overlay frame over the root window.
        Returns (overlay, content_frame, close_fn)."""
        T = self.T
        ov = tk.Frame(self.root, bg=T["bg"])
        ov.place(x=0, y=0, relwidth=1, relheight=1)
        ov.lift()

        # Header bar
        hdr = tk.Frame(ov, bg=T["hdr_bg"], height=28)
        hdr.pack(fill=tk.X)
        hdr.pack_propagate(False)

        # Capture the mode that was active when this overlay opened.
        # When the overlay closes, if current_mode is not "calculator", we must
        # switch back to calculator so the layout is restored correctly.
        _mode_on_open = getattr(self, 'current_mode', 'calculator')

        def _close():
            ov.destroy()
            # Reset the overlay close tracker if this was the tracked overlay
            if getattr(self, '_active_overlay_close', None) is _close:
                self._active_overlay_close = None
            # If the overlay was opened from a non-calculator mode (e.g. Customers, Settings),
            # return to that mode; only switch to calculator if mode was calculator itself.
            if _mode_on_open == 'calculator':
                pass  # nothing to restore
            elif _mode_on_open in ('customers',):
                # Stay in customers — just refresh the mode
                self.switch_mode_customers()
            elif _mode_on_open != 'calculator' and getattr(self, 'current_mode', '') == _mode_on_open:
                self.switch_mode('calculator')
            # Restore Escape to simply open the App Launcher (default idle behavior)
            self.root.bind("<Escape>", lambda e: self._show_app_launcher())

        # Track this close function so _keypad_back can call it directly
        self._active_overlay_close = _close

        tk.Button(hdr, text="\u2190 Back",
                  font=(config.LABEL_FONT[0], config.LABEL_FONT[1], "bold"),
                  bg=T["hdr_bg"], fg=T["subtext"],
                  relief=tk.FLAT, bd=0, cursor="hand2",
                  activebackground=T["shadow_dark"],
                  command=_close).pack(side=tk.LEFT, padx=6)
        tk.Label(hdr, text=title,
                 font=(config.BUTTON_FONT[0], max(9, config.BUTTON_FONT[1] - 3), "bold"),
                 bg=T["hdr_bg"], fg=T["text"]).pack(side=tk.LEFT, padx=4)

        self.root.bind("<Escape>", lambda e: _close())

        body = tk.Frame(ov, bg=T["bg"])
        body.pack(fill=tk.BOTH, expand=True, padx=12, pady=8)
        return ov, body, _close

    # ── App Launcher ────────────────────────────────────────────────────────
    def _show_app_launcher(self):
        """Full-window App Launcher grid — ESC / close button closes it."""
        T = self.T
        ov = tk.Frame(self.root, bg=T["bg_dark"])
        ov.place(x=0, y=0, relwidth=1, relheight=1)
        ov.lift()

        hdr = tk.Frame(ov, bg=T["hdr_bg"], height=30)
        hdr.pack(fill=tk.X)
        hdr.pack_propagate(False)
        tk.Label(hdr, text=" " + self.tr("DigiCal Apps"),
                 image=getattr(self, '_apps_icon', None),
                 compound=tk.LEFT if getattr(self, '_apps_icon', None) else tk.NONE,
                 font=(config.BUTTON_FONT[0], max(9, config.BUTTON_FONT[1] - 3), "bold"),
                 bg=T["hdr_bg"], fg=T["accent"]).pack(side=tk.LEFT, padx=8)

        self._app_launcher_open = True
        self._launcher_cells = []
        self._launcher_focus_idx = 0

        def _close(event=None):
            self._app_launcher_open = False
            self._active_overlay_close = None
            ov.destroy()
            # Restore default Escape binding
            self.root.bind("<Escape>", lambda e: self._show_app_launcher())

        # Track launcher close fn too
        self._active_overlay_close = _close

        tk.Button(hdr, text="\u2715",
                  font=(config.BUTTON_FONT[0], 10, "bold"),
                  bg=T["hdr_bg"], fg=T["subtext"],
                  relief=tk.FLAT, bd=0, cursor="hand2",
                  activebackground=T["shadow_dark"],
                  command=_close).pack(side=tk.RIGHT, padx=8)
        self.root.bind("<Escape>", _close)

        apps = [
            (self.tr("Sales"),     "sales.png", "sales"),
            (self.tr("Expense"),   "expense.png", "expense"),
            (self.tr("History"),   "history.png", "history"),
            (self.tr("Graphs"),    "graph.png", "graphs"),
            (self.tr("Customers"), "customer.png", "customers"),
            (self.tr("Products"),  "product.png", "products"),
            (self.tr("Handlers"),  "handler.png", "handlers"),
            (self.tr("Settings"),  "settings.png", "settings"),
        ]

        if not hasattr(self, '_launcher_icons'):
            self._launcher_icons = {}
            from PIL import Image, ImageTk
            import os
            for label, icon_name, mode in apps:
                try:
                    p = os.path.join(os.path.dirname(__file__), "assets", "menu", icon_name)
                    _resample = getattr(Image, 'Resampling', Image).LANCZOS
                    img = Image.open(p).resize((80, 80), _resample)
                    self._launcher_icons[mode] = ImageTk.PhotoImage(img)
                except Exception:
                    self._launcher_icons[mode] = None

        grid = tk.Frame(ov, bg=T["bg_dark"])
        grid.pack(fill=tk.BOTH, expand=True, padx=10, pady=12)
        for col in range(3):
            grid.columnconfigure(col, weight=1)

        def _launch(mode):
            _close()
            self.switch_mode(mode)

        card_bg  = T["bg"]
        card_sha = T["shadow_dark"]
        card_hi  = T["shadow_lite"]

        for idx, (label, icon_name, mode) in enumerate(apps):
            row, col = divmod(idx, 3)
            shadow = tk.Frame(grid, bg=card_sha)
            shadow.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")
            grid.rowconfigure(row, weight=1)
            hi = tk.Frame(shadow, bg=card_hi)
            hi.pack(fill=tk.BOTH, expand=True, padx=(0, 1), pady=(0, 1))
            cell = tk.Frame(hi, bg=card_bg, cursor="hand2")
            cell.pack(fill=tk.BOTH, expand=True, padx=(1, 0), pady=(1, 0))

            c_frame = tk.Frame(cell, bg=card_bg, cursor="hand2")
            c_frame.pack(expand=True)

            def _enter(e=None, f=cell, c=c_frame):
                f.config(bg=T["bg_dark"])
                c.config(bg=T["bg_dark"])
                for child in c.winfo_children():
                    child.config(bg=T["bg_dark"])

            def _leave(e=None, f=cell, c=c_frame):
                f.config(bg=card_bg)
                c.config(bg=card_bg)
                for child in c.winfo_children():
                    child.config(bg=card_bg)

            cell.bind("<Enter>", _enter)
            cell.bind("<Leave>", _leave)

            lbl_icon = tk.Label(c_frame, bg=card_bg, cursor="hand2")
            if self._launcher_icons.get(mode):
                lbl_icon.config(image=self._launcher_icons[mode])
            else:
                lbl_icon.config(text=label, font=(config.BUTTON_FONT[0], 20))
            lbl_icon.pack(pady=(0, 6))
            lbl_name = tk.Label(c_frame, text=label,
                                font=(config.BUTTON_FONT[0], 13, "bold"),
                                bg=card_bg, fg=T["text"], cursor="hand2")
            lbl_name.pack()
            m = mode
            for w in (cell, c_frame, lbl_icon, lbl_name, hi, shadow):
                w.bind("<Button-1>", lambda e, mo=m: _launch(mo))
                if w in (c_frame, lbl_icon, lbl_name):
                    w.bind("<Enter>", _enter)
                    w.bind("<Leave>", _leave)

            self._launcher_cells.append((cell, _enter, _leave, mode))

        # Store launch function for keypad D-Pad selection
        self._show_app_launcher_launch = _launch

        # Pre-highlight first app
        if self._launcher_cells:
            _, _enter, _, _ = self._launcher_cells[0]
            _enter()

    # ── Settings ─────────────────────────────────────────────────────────────
    def show_settings_mode(self):
        """Full-window overlay with beautiful card-based settings."""
        T = self.T
        ov, body, close = self._open_overlay(self.tr("Settings"))
        settings = self._load_settings()

        # ── Scrollable container ───────────────────────────────────────────
        canvas = tk.Canvas(body, bg=T["bg"], highlightthickness=0, bd=0)
        scrollbar = ttk.Scrollbar(body, orient=tk.VERTICAL, command=canvas.yview)
        scroll_frame = tk.Frame(canvas, bg=T["bg"])
        scroll_frame.bind("<Configure>",
                          lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw",
                             width=config.WINDOW_WIDTH - 40)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Mouse-wheel scrolling
        self._bind_mousewheel(canvas, lambda e: self._handle_mousewheel(e, canvas, orient="vertical"))

        def _cleanup_bindings():
            try:
                self._unbind_mousewheel(canvas)
            except Exception:
                pass

        ov.bind("<Destroy>", lambda e: _cleanup_bindings())

        # ── Card helper ────────────────────────────────────────────────────
        def card(parent, icon, title):
            """Create a neumorphic section card. Returns the inner frame."""
            outer = tk.Frame(parent, bg=T["shadow_dark"])
            outer.pack(fill=tk.X, padx=4, pady=5)
            inner_hi = tk.Frame(outer, bg=T["shadow_lite"])
            inner_hi.pack(fill=tk.BOTH, expand=True, padx=(0, 1), pady=(0, 1))
            c = tk.Frame(inner_hi, bg=T["bg"])
            c.pack(fill=tk.BOTH, expand=True, padx=(1, 0), pady=(1, 0))
            # Card header
            hdr = tk.Frame(c, bg=T["bg"])
            hdr.pack(fill=tk.X, padx=8, pady=(6, 2))
            tk.Label(hdr, text=f"{title}",
                     font=(config.BUTTON_FONT[0], config.BUTTON_FONT[1] - 2, "bold"),
                     bg=T["bg"], fg=T["mode_fg"]).pack(side=tk.LEFT)
            content = tk.Frame(c, bg=T["bg"])
            content.pack(fill=tk.X, padx=10, pady=(0, 8))
            return content

        def themed_entry(parent, var, width=14, **kw):
            return tk.Entry(parent, textvariable=var, font=config.LABEL_FONT,
                            bg=T["entry_bg"], fg=T["entry_fg"],
                            insertbackground=T["text"], relief=tk.FLAT,
                            highlightthickness=1, highlightbackground=T["shadow_dark"],
                            width=width, **kw)

        def row_label(parent, text, row, col=0):
            tk.Label(parent, text=text, font=config.LABEL_FONT,
                     bg=T["bg"], fg=T["text"]).grid(row=row, column=col,
                                                     sticky=tk.W, pady=2)

        # Status label for save confirmations
        status_lbl = tk.Label(scroll_frame, text="", font=(config.LABEL_FONT[0], config.LABEL_FONT[1] - 3),
                              bg=T["bg"], fg=T["success"])
        status_lbl.pack(pady=(2, 0))

        def flash_saved(msg=self.tr("Saved!")):
            msg = msg.replace("\u2713 ", "")
            if getattr(self, "_icon_success", None):
                status_lbl.config(text=f" {msg}", image=self._icon_success, compound=tk.LEFT)
            else:
                status_lbl.config(text=f"\u2713 {msg}", image="")
            scroll_frame.after(2000, lambda: status_lbl.config(text="", image=""))

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 1) APPEARANCE
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        c1 = card(scroll_frame, "", self.tr("Appearance & Language"))
        
        # Language Selection row
        lang_row = tk.Frame(c1, bg=T["bg"])
        lang_row.pack(fill=tk.X, pady=2)
        tk.Label(lang_row, text=self.tr("Language"),
                 font=config.LABEL_FONT, bg=T["bg"], fg=T["text"]).pack(side=tk.LEFT)
        lang_options = {"en": "English", "mr": "मराठी", "hi": "हिंदी"}
        lang_var = tk.StringVar(value=lang_options.get(self.language, "English"))
        
        def on_lang_change(event):
            val = lang_var.get()
            code = next((k for k, v in lang_options.items() if v == val), "en")
            if code != self.language:
                self._change_language(code)
                # Restart Settings screen implicitly by closing and letting user reopen OR we can manually reopen it.
                # Since reloading theme destroys UI, we should just let apply_theme handle it. 
                # apply_theme brings us back to current_mode, which is fine!
                
        lang_combo = ttk.Combobox(lang_row, textvariable=lang_var, values=list(lang_options.values()),
                                  state="readonly", width=12, font=config.LABEL_FONT)
        lang_combo.bind("<<ComboboxSelected>>", on_lang_change)
        lang_combo.pack(side=tk.RIGHT, padx=4)

        # Font Scale Selection row
        font_row = tk.Frame(c1, bg=T["bg"])
        font_row.pack(fill=tk.X, pady=2)
        tk.Label(font_row, text=self.tr("Font Size"),
                 font=config.LABEL_FONT, bg=T["bg"], fg=T["text"]).pack(side=tk.LEFT)
        font_options = [self.tr("Small"), self.tr("Medium"), self.tr("Large"), self.tr("Extra Large")]
        
        # Ensure scale default is localized initially for matching
        fs_tr = self.tr(self.font_scale) 
        if fs_tr not in font_options: fs_tr = self.tr("Medium")
        
        font_var = tk.StringVar(value=fs_tr)
        
        def on_font_change(event):
            val = font_var.get()
            # Map back to English config standard
            if val == self.tr("Small"): scale = "Small"
            elif val == self.tr("Large"): scale = "Large"
            elif val == self.tr("Extra Large"): scale = "Extra Large"
            else: scale = "Medium"
            
            if scale != self.font_scale:
                self._change_font_scale(scale)
                
        font_combo = ttk.Combobox(font_row, textvariable=font_var, values=font_options,
                                  state="readonly", width=12, font=config.LABEL_FONT)
        font_combo.bind("<<ComboboxSelected>>", on_font_change)
        font_combo.pack(side=tk.RIGHT, padx=4)

        dark_row = tk.Frame(c1, bg=T["bg"])
        dark_row.pack(fill=tk.X, pady=2)
        tk.Label(dark_row, text=self.tr("Dark Mode"),
                 font=config.LABEL_FONT, bg=T["bg"], fg=T["text"]).pack(side=tk.LEFT)
        dark_var = tk.BooleanVar(value=self.dark_mode)
        icon_text = "   " + self.tr("OFF") if not self.dark_mode else "   " + self.tr("ON")
        tk.Checkbutton(
            dark_row, text=icon_text, variable=dark_var,
            font=(config.BUTTON_FONT[0], config.BUTTON_FONT[1] - 3),
            bg=T["bg"], fg=T["accent"],
            selectcolor=T["bg_dark"],
            activebackground=T["bg"], activeforeground=T["accent"],
            relief=tk.FLAT, bd=0,
            command=lambda: self._toggle_dark_mode(dark_var.get())
        ).pack(side=tk.RIGHT, padx=4)

        # Fullscreen Toggle
        full_row = tk.Frame(c1, bg=T["bg"])
        full_row.pack(fill=tk.X, pady=2)
        tk.Label(full_row, text=self.tr("Fullscreen Mode"),
                 font=config.LABEL_FONT, bg=T["bg"], fg=T["text"]).pack(side=tk.LEFT)
        full_var = tk.BooleanVar(value=self.fullscreen)
        full_icon_text = "   " + self.tr("OFF") if not self.fullscreen else "   " + self.tr("ON")
        
        def _on_full_toggle():
            self._toggle_fullscreen(full_var.get())
            
        tk.Checkbutton(
            full_row, text=full_icon_text, variable=full_var,
            font=(config.BUTTON_FONT[0], config.BUTTON_FONT[1] - 3),
            bg=T["bg"], fg=T["accent"],
            selectcolor=T["bg_dark"],
            activebackground=T["bg"], activeforeground=T["accent"],
            relief=tk.FLAT, bd=0,
            command=_on_full_toggle
        ).pack(side=tk.RIGHT, padx=4)

        # Hide Mouse Cursor Toggle
        cursor_row = tk.Frame(c1, bg=T["bg"])
        cursor_row.pack(fill=tk.X, pady=2)
        tk.Label(cursor_row, text=self.tr("Hide Mouse Cursor"),
                 font=config.LABEL_FONT, bg=T["bg"], fg=T["text"]).pack(side=tk.LEFT)
        cursor_var = tk.BooleanVar(value=self.hide_cursor)
        cursor_icon_text = "   " + self.tr("OFF") if not self.hide_cursor else "   " + self.tr("ON")

        def _on_cursor_toggle():
            val = cursor_var.get()
            self.hide_cursor = val
            self._save_settings({"hide_cursor": val})
            self._apply_global_cursor()
            flash_saved()

        tk.Checkbutton(
            cursor_row, text=cursor_icon_text, variable=cursor_var,
            font=(config.BUTTON_FONT[0], config.BUTTON_FONT[1] - 3),
            bg=T["bg"], fg=T["accent"],
            selectcolor=T["bg_dark"],
            activebackground=T["bg"], activeforeground=T["accent"],
            relief=tk.FLAT, bd=0,
            command=_on_cursor_toggle
        ).pack(side=tk.RIGHT, padx=4)

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 2) BUSINESS INFO
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        c2 = card(scroll_frame, "", self.tr("Business Info"))
        grid2 = tk.Frame(c2, bg=T["bg"])
        grid2.pack(fill=tk.X)

        row_label(grid2, self.tr("Shop / Business Name:"), 0)
        shop_var = tk.StringVar(value=settings.get("shop_name", "My Shop"))
        themed_entry(grid2, shop_var, width=16).grid(row=0, column=1, padx=6, pady=2)

        row_label(grid2, self.tr("Currency Symbol:"), 1)
        curr_var = tk.StringVar(value=settings.get("currency_symbol", config.CURRENCY_SYMBOL))
        themed_entry(grid2, curr_var, width=5).grid(row=1, column=1, padx=6, pady=2, sticky=tk.W)

        row_label(grid2, self.tr("Low Stock Alert (%):"), 2)
        stock_var = tk.StringVar(value=str(settings.get("low_stock_pct", 20)))
        themed_entry(grid2, stock_var, width=5).grid(row=2, column=1, padx=6, pady=2, sticky=tk.W)

        def _save_biz():
            pct = stock_var.get().strip()
            try:
                pct_val = int(pct)
                if pct_val < 1 or pct_val > 99:
                    raise ValueError
            except ValueError:
                self._show_toast(self.tr("Low stock % must be 1\u201399"), kind="error")
                return
            self._save_settings({
                "shop_name": shop_var.get().strip() or "My Shop",
                "currency_symbol": curr_var.get().strip() or "\u20b9",
                "low_stock_pct": pct_val,
            })
            flash_saved()

        self._neu_btn(c2, self.tr("Save Business Info"), command=_save_biz,
                     kind="equals", width=18).pack(pady=(4, 0))

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 3) PAYMENT / UPI
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        c3 = card(scroll_frame, "", self.tr("Payment — UPI"))
        grid3 = tk.Frame(c3, bg=T["bg"])
        grid3.pack(fill=tk.X)

        row_label(grid3, self.tr("UPI Number (10 digits):"), 0)
        upi_num_var = tk.StringVar(value=settings.get("upi_number", ""))
        vcmd = (grid3.register(lambda v: (v.isdigit() and len(v) <= 10) or v == ""), '%P')
        themed_entry(grid3, upi_num_var, width=13).grid(row=0, column=1, padx=6, pady=2)
        grid3.nametowidget(grid3.grid_slaves(row=0, column=1)[0]).config(
            validate="key", validatecommand=vcmd)

        row_label(grid3, self.tr("Payee Name:"), 1)
        upi_name_var = tk.StringVar(value=settings.get("upi_name", "Shop"))
        themed_entry(grid3, upi_name_var, width=13).grid(row=1, column=1, padx=6, pady=2)

        def _save_upi():
            num = upi_num_var.get().strip()
            name = upi_name_var.get().strip() or "Shop"
            if len(num) != 10:
                self._show_toast(self.tr("Enter a valid 10-digit UPI number"), kind="error")
                return
            self._save_settings({"upi_number": num, "upi_name": name})
            flash_saved()

        self._neu_btn(c3, self.tr("Save UPI Settings"), command=_save_upi,
                     kind="equals", width=18).pack(pady=(4, 0))

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 4) DATA MANAGEMENT
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        c4 = card(scroll_frame, "", self.tr("Data Management"))

        btn_row = tk.Frame(c4, bg=T["bg"])
        btn_row.pack(fill=tk.X, pady=2)

        def _clear_calcs():
            self._show_confirm(self.tr("Clear ALL calculation history?"), lambda: [
                self.db.clear_history('calculations'),
                flash_saved(self.tr("Calculation history cleared"))])

        def _clear_trans():
            self._show_confirm(self.tr("Clear ALL transactions?"), lambda: [
                self.db.clear_history('transactions'),
                flash_saved(self.tr("Transaction history cleared"))])

        def _export_csv():
            import csv
            from datetime import datetime
            try:
                conn = self.db.get_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM transactions ORDER BY date DESC")
                rows = cursor.fetchall()
                if not rows:
                    conn.close()
                    self._show_toast(self.tr("No transactions to export."))
                    return
                cols = [desc[0] for desc in cursor.description]
                conn.close()
                fname = f"digical_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                import os
                path = os.path.join(os.path.dirname(__file__), fname)
                with open(path, "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow(cols)
                    writer.writerows(rows)
                flash_saved(self.tr("Exported → {}").format(fname))
            except Exception as ex:
                self._show_toast(str(ex), kind="error")

        self._neu_btn(btn_row, self.tr("Clear Calcs"), command=_clear_calcs,
                     kind="mode").pack(side=tk.LEFT, padx=3)
        self._neu_btn(btn_row, self.tr("Clear Trans"), command=_clear_trans,
                     kind="operator").pack(side=tk.LEFT, padx=3)
        self._neu_btn(btn_row, self.tr("Export CSV"), command=_export_csv,
                     kind="equals").pack(side=tk.LEFT, padx=3)

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 5) WEB PORTAL
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        c5 = card(scroll_frame, "", self.tr("Web Portal (Phone/Laptop)"))
        portal_info = tk.Frame(c5, bg=T["bg"])
        portal_info.pack(fill=tk.X, pady=2)
        
        import socket
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(('8.8.8.8', 80))
            local_ip = s.getsockname()[0]
            s.close()
        except:
            local_ip = '127.0.0.1'
            
        tk.Label(portal_info, text=self.tr("Access from this Device:"), font=(config.LABEL_FONT[0], 9), bg=T["bg"], fg=T["subtext"]).pack(anchor=tk.W)
        tk.Label(portal_info, text=f"http://localhost:{config.WEB_PORT}", font=(config.LABEL_FONT[0], 11, "bold"), bg=T["bg"], fg=T["accent"]).pack(anchor=tk.W, pady=(0, 4))
        
        tk.Label(portal_info, text=self.tr("Access from Phone/Laptop (Same WiFi):"), font=(config.LABEL_FONT[0], 9), bg=T["bg"], fg=T["subtext"]).pack(anchor=tk.W)
        tk.Label(portal_info, text=f"http://{local_ip}:{config.WEB_PORT}", font=(config.LABEL_FONT[0], 11, "bold"), bg=T["bg"], fg=T["accent"]).pack(anchor=tk.W)

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 5.5) SYSTEM UPDATE
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        c_up = card(scroll_frame, "", self.tr("System Update"))
        up_frame = tk.Frame(c_up, bg=T["bg"])
        up_frame.pack(fill=tk.X, pady=2)
        
        updater = Updater()
        cur_sha, cur_build = updater._get_version_info()
        
        up_status_var = tk.StringVar(value=self.tr("Ready"))
        up_btn_var = tk.StringVar(value=self.tr("Check for Updates"))
        self._new_sha = None
        
        # Current Version Info
        info_f = tk.Frame(up_frame, bg=T["bg"])
        info_f.pack(fill=tk.X, pady=(0, 5))
        
        v_str = f"v{config.VERSION}"
        tk.Label(info_f, text=f"{self.tr('Current Version:')} {v_str}", font=(config.LABEL_FONT[0], 9, "bold"), bg=T["bg"], fg=T["text"]).pack(anchor=tk.W)
        tk.Label(info_f, text=f"{self.tr('Build Date:')} {cur_build}", font=(config.LABEL_FONT[0], 8), bg=T["bg"], fg=T["subtext"]).pack(anchor=tk.W)
        tk.Label(info_f, text=f"{self.tr('Commit:')} {cur_sha[:7]}", font=(config.LABEL_FONT[0], 8), bg=T["bg"], fg=T["subtext"]).pack(anchor=tk.W)

        up_status_lbl = tk.Label(up_frame, textvariable=up_status_var, font=(config.LABEL_FONT[0], 9), bg=T["bg"], fg=T["accent"])
        up_status_lbl.pack(anchor=tk.W, pady=(5, 0))

        def _check_up():
            up_status_var.set(self.tr("Checking..."))
            self.root.update_idletasks()
            available, sha = updater.check_for_update()
            if available:
                self._new_sha = sha
                up_status_var.set(self.tr("Update Available!"))
                up_btn_var.set(self.tr("Download Update"))
                check_btn.config(command=_download_up)
            else:
                up_status_var.set(self.tr("Already up to date."))
                flash_saved(self.tr("No updates found"))

        def _download_up():
            up_status_var.set(self.tr("Downloading..."))
            self.root.update_idletasks()
            if updater.download_update():
                up_status_var.set(self.tr("Download Complete. Ready to install."))
                up_btn_var.set(self.tr("Apply & Restart"))
                check_btn.config(command=_apply_up)
            else:
                up_status_var.set(self.tr("Download failed."))
                self._show_toast(self.tr("Download failed. Check connection."), kind="error")

        def _apply_up():
            # Skip confirmation popup — proceed directly to backup and apply
            _do_apply()

        def _do_apply():
            up_status_var.set(self.tr("Backing up..."))
            self.root.update_idletasks()
            if not updater.create_backup():
                self._show_toast(self.tr("Backup failed. Aborting."), kind="error")
                return
            
            up_status_var.set(self.tr("Applying..."))
            self.root.update_idletasks()
            if updater.apply_update(self._new_sha):
                updater.restart_app()
            else:
                self._show_toast(self.tr("Update failed."), kind="error")

        check_btn = self._neu_btn(up_frame, "", textvariable=up_btn_var, command=_check_up, kind="equals")
        check_btn.pack(side=tk.LEFT, padx=3, pady=5)

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 6) KEYPAD
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        c_kp = card(scroll_frame, "", self.tr("Keypad"))

        # F1 function key assignment
        f1_row = tk.Frame(c_kp, bg=T["bg"])
        f1_row.pack(fill=tk.X, pady=2)
        tk.Label(f1_row, text=self.tr("F1 Key Function"),
                 font=config.LABEL_FONT, bg=T["bg"], fg=T["text"]).pack(side=tk.LEFT)

        f1_options = {
            "none":      self.tr("None (disabled)"),
            "settings":  self.tr("Settings"),
            "history":   self.tr("History"),
            "graphs":    self.tr("Graphs"),
            "products":  self.tr("Products"),
            "handlers":  self.tr("Handlers"),
            "customers": self.tr("Customers"),
            "sales":     self.tr("Sales"),
            "expense":   self.tr("Expense"),
        }
        current_f1 = settings.get("f1_function", "none")
        f1_display = f1_options.get(current_f1, f1_options["none"])
        f1_var = tk.StringVar(value=f1_display)

        def _on_f1_change(event=None):
            selected = f1_var.get()
            code = next((k for k, v in f1_options.items() if v == selected), "none")
            self._save_settings({"f1_function": code})
            flash_saved(self.tr("F1 key updated"))

        f1_combo = ttk.Combobox(f1_row, textvariable=f1_var,
                                values=list(f1_options.values()),
                                state="readonly", width=16, font=config.LABEL_FONT)
        f1_combo.bind("<<ComboboxSelected>>", _on_f1_change)
        f1_combo.pack(side=tk.RIGHT, padx=4)

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 7) ABOUT
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        c6 = card(scroll_frame, "", self.tr("About DigiCal"))
        updater = Updater()
        sha, b_date = updater._get_version_info()
        full_v = f"v{config.VERSION} Build {b_date} ({sha[:7]})"
        
        tk.Label(c6, text=f"{config.APP_NAME}",
                 font=(config.BUTTON_FONT[0], 10, "bold"),
                 bg=T["bg"], fg=T["text"]).pack(anchor=tk.W)
        tk.Label(c6, text=full_v,
                 font=(config.BUTTON_FONT[0], 9),
                 bg=T["bg"], fg=T["accent"]).pack(anchor=tk.W)

        # ── Close button ───────────────────────────────────────────────────
        tk.Frame(scroll_frame, bg=T["bg"], height=6).pack()
        self._neu_btn(scroll_frame, self.tr("Close"), command=close,
                     kind="mode", width=10, height=2).pack(pady=(0, 10))

        # Start cursor on Language Option
        self.root.after(100, lambda: [lang_combo.focus_set(), self._ensure_visible(lang_combo)])





    def _show_success_overlay(self, label=None):
        """Full-window animated success screen. Auto-dismisses after 5 s."""
        if label is None:
            label = self.tr("Transaction saved!")
        T = self.T
        ov = tk.Frame(self.root, bg=T["bg"])
        ov.place(x=0, y=0, relwidth=1, relheight=1)
        ov.lift()
        ov.update_idletasks() # Force background draw

        # ── Success Image ──────────────────────────────────────────────────
        container = tk.Frame(ov, bg=T["bg"])
        container.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

        try:
            from PIL import Image, ImageTk
            import os
            
            png_path = os.path.join(os.path.dirname(__file__), "assets", "tick.png")
            if not os.path.exists(png_path):
                raise FileNotFoundError

            # Scale PNG to ~40% of the window's height
            win_h = self.root.winfo_height() or 480
            target_size = int(win_h * 0.40)

            raw = Image.open(png_path).convert("RGBA")
            # Flatten against the background color to avoid transparency issues
            combined = Image.new("RGB", raw.size, T["bg"]) 
            combined.paste(raw, (0,0), raw)
            
            f_final = combined.resize((target_size, target_size), Image.LANCZOS)
            photo = ImageTk.PhotoImage(f_final)
            
            # Cache the image so it doesn't get garbage collected
            if not hasattr(self, '_success_png_cache'):
                self._success_png_cache = []
            self._success_png_cache.append(photo)

            img_label = tk.Label(container, image=photo, bg=T["bg"])
            img_label.pack(pady=(0, 24))

        except Exception as e:
            # Fallback: big unicode tick
            tk.Label(container, text="\u2714", font=("Arial", 96, "bold"), bg=T["bg"],
                     fg=T["success"]).pack(pady=(0, 24))

        tk.Label(container, text=label, font=("Arial", 32, "bold"),
                 justify=tk.CENTER, bg=T["bg"], fg=T["success"], 
                 wraplength=self.root.winfo_width() - 40).pack(pady=(0, 16))
                 
        tk.Label(container, text=self.tr("Tap anywhere to continue"),
                 font=("Arial", 16), bg=T["bg"], fg=T["subtext"]).pack()

        def _dismiss(event=None):
            self.root.unbind("<Escape>")
            if ov.winfo_exists():
                ov.destroy()

        # Bind events to overlay, container, and all children
        ov.bind("<Button-1>", _dismiss)
        container.bind("<Button-1>", _dismiss)
        for child in container.winfo_children():
            child.bind("<Button-1>", _dismiss)
            
        self.root.bind("<Escape>", _dismiss)
        # Auto-dismiss after 3s
        ov.after(3000, _dismiss)

    def show_transaction_dialog(self, amount):
        """Full-window overlay to categorize a calculation as a transaction."""
        try:
            amount_val = float(amount)
        except Exception:
            return

        # Wrap close to clear keypad references
        def _dialog_close():
            self._transaction_dialog_open = False
            self._active_payment_var = None
            self._active_payment_combo = None
            self._active_payment_change_fn = None
            self._active_save_sale_fn = None
            self._active_save_expense_fn = None
            self._active_dialog_close_fn = None
            _raw_close()

        ov, body, _raw_close = self._open_overlay(self.tr("Save as Transaction"))
        close = _dialog_close
        T = self.T

        # ── Two-column grid ─────────────────────────────────────
        # col 0 = info / controls   col 1 = QR (right side)
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)
        # row weights: spacer row 4 absorbs remaining height
        body.rowconfigure(4, weight=1)

        # Amount + subtitle  (left col)
        tk.Label(body, text=f"₹{amount_val:.2f}",
                 font=("Arial", 54, "bold"), bg=T["bg"], fg=T["success"]
                 ).grid(row=0, column=0, sticky=tk.W, padx=10, pady=(16, 0))
        tk.Label(body, text=self.tr("Save as transaction?"),
                 font=("Arial", 16), bg=T["bg"], fg=T["subtext"]
                 ).grid(row=1, column=0, sticky=tk.W, padx=10)

        # Payment method  (left col)
        pf = tk.Frame(body, bg=T["bg"])
        pf.grid(row=2, column=0, sticky=tk.W, padx=6, pady=8)
        tk.Label(pf, text=self.tr("Method:"), font=("Arial", 20),
                 bg=T["bg"], fg=T["text"]).pack(side=tk.LEFT, padx=4)
        payment_var = tk.StringVar(value=self.tr("Cash"))
        translated_methods = [self.tr(m) for m in config.PAYMENT_METHODS]
        combo = ttk.Combobox(pf, textvariable=payment_var, values=translated_methods,
                             font=("Arial", 20), width=12, state="readonly")
        combo.pack(side=tk.LEFT)

        # Store references for keypad dispatcher
        self._active_payment_var = payment_var
        self._active_payment_combo = combo

        # ── QR frame  (right col, rows 0-3) ────────────────────
        due_customer = [None]
        _qr_ref = [None]

        qr_frame = tk.Frame(body, bg=T["bg"])
        # Not gridded until UPI is chosen

        def _build_qr():
            for w in qr_frame.winfo_children():
                w.destroy()
            s = self._load_settings()
            num = s.get("upi_number", "")
            name = s.get("upi_name", "Shop")
            if not num:
                tk.Label(qr_frame, text=self.tr("⚠ Set UPI\nnumber in\nSettings"),
                         font=("Arial", 7), bg=T["bg"],
                         fg=T["danger"], justify=tk.CENTER).pack()
                return
            vpa = f"{num}@upi"
            uri = (f"upi://pay?pa={vpa}&pn={name}"
                   f"&am={amount_val:.2f}&cu=INR&tn=DigiCal+Payment")
            try:
                import qrcode
                from PIL import ImageTk
                qr = qrcode.QRCode(version=1,
                                   error_correction=qrcode.constants.ERROR_CORRECT_M,
                                   box_size=4, border=2)
                qr.add_data(uri)
                qr.make(fit=True)
                img = qr.make_image(fill_color="black", back_color="white").resize((340, 340))
                photo = ImageTk.PhotoImage(img)
                _qr_ref[0] = photo
                tk.Label(qr_frame, image=photo, bg="white",
                         relief=tk.FLAT, bd=3).pack(pady=(20, 10))
                tk.Label(qr_frame, text=vpa,
                         font=("Arial", 22, "bold"), bg=T["bg"],
                         fg=T["success"]).pack()
            except Exception as ex:
                tk.Label(qr_frame, text=self.tr("QR error:\n{}").format(ex),
                         font=("Arial", 12), bg=T["bg"],
                         fg=T["danger"], wraplength=120, justify=tk.CENTER).pack()

        def _build_method_icon(asset_name, label_text):
            for w in qr_frame.winfo_children():
                w.destroy()
            try:
                img_path = os.path.join(os.path.dirname(__file__), "assets", asset_name)
                raw = Image.open(img_path)
                
                # Resize proportionally to fit a similar 340x340 box as the QR code
                raw_w, raw_h = raw.size
                scale = min(340 / raw_w, 340 / raw_h) if raw_w and raw_h else 1
                new_size = (max(1, int(raw_w * scale)), max(1, int(raw_h * scale)))
                
                img = raw.resize(new_size, Image.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                _qr_ref[0] = photo
                
                tk.Label(qr_frame, image=photo, bg=T["bg"],
                         relief=tk.FLAT).pack(pady=(20, 10))
            except Exception as ex:
                tk.Label(qr_frame, text=self.tr("Image error:\n{}").format(ex),
                         font=("Arial", 12), bg=T["bg"],
                         fg=T["danger"], wraplength=120, justify=tk.CENTER).pack()

        last_valid_pm = [payment_var.get()]

        def on_payment_change(event=None, is_revert=False):
            pm = payment_var.get()
            if pm == self.tr("Due"):
                if not is_revert:
                    prev_cust = due_customer[0]
                    due_customer[0] = None

                    def handle_cancel():
                        payment_var.set(last_valid_pm[0])
                        due_customer[0] = prev_cust
                        on_payment_change(is_revert=True)

                    def handle_confirm(cid):
                        due_customer[0] = cid
                        last_valid_pm[0] = pm

                    self.show_due_customer_dialog(handle_confirm, handle_cancel)

                _build_method_icon("due.png", "{} as Due")
                qr_frame.grid(row=0, column=1, rowspan=5, sticky="nsew", padx=10, pady=10)
            elif pm == self.tr("UPI"):
                due_customer[0] = None
                last_valid_pm[0] = pm
                _build_qr()
                qr_frame.grid(row=0, column=1, rowspan=5, sticky="nsew", padx=10, pady=10)
            elif pm == self.tr("Cash"):
                due_customer[0] = None
                last_valid_pm[0] = pm
                _build_method_icon("cash.png", "{} in Cash")
                qr_frame.grid(row=0, column=1, rowspan=5, sticky="nsew", padx=10, pady=10)
            else:
                due_customer[0] = None
                last_valid_pm[0] = pm
                qr_frame.grid_remove()

        combo.bind("<<ComboboxSelected>>", on_payment_change)

        # Store payment change fn for keypad QR cycling
        self._active_payment_change_fn = on_payment_change

        # Trigger default logic (Cash) to show the icon immediately
        on_payment_change()

    # ── Save functions ──────────────────────────────────────
        def save_as_sale():
            pm = payment_var.get()
            if pm == self.tr("Due") and not due_customer[0]:
                self._show_toast(self.tr("Please select a customer for Due payment"), kind="error"); return
            cats = self.transaction_manager.get_sales_categories()
            cat = "Product Sales" if "Product Sales" in cats else (cats[0] if cats else "Sales")
            hid = None
            ch = self.handler_manager.get_current_handler()
            if ch: hid = ch['id']
            desc = self.tr("From calculation: {}").format(amount)
            if pm == self.tr("Due") and due_customer[0]: desc += self.tr(" [Due: {}]").format(due_customer[0])
            
            # map back translated method to literal config method for db storage
            meth_en = "Cash"
            for m in config.PAYMENT_METHODS:
                if self.tr(m) == pm:
                    meth_en = m
                    break
                    
            tid = self.transaction_manager.add_sale(amount_val, cat, desc, meth_en, hid)
            if pm == self.tr("Due") and due_customer[0]: self.db.add_due_record(tid, due_customer[0], amount_val)
            self._deduct_product_quantities()
            self.calculator.clear()
            self._line_products = {}
            self.update_display("0")
            close()
            self._show_success_overlay(self.tr("Sale saved  {} [{}]").format(f"₹{amount_val:.2f}", pm))

        def save_as_expense():
            pm = payment_var.get()
            if pm == self.tr("Due") and not due_customer[0]:
                self._show_toast(self.tr("Please select a vendor for Due payment"), kind="error"); return
            cats = self.transaction_manager.get_expense_categories()
            cat = "Supplies" if "Supplies" in cats else (cats[0] if cats else "Expense")
            hid = None
            ch = self.handler_manager.get_current_handler()
            if ch: hid = ch['id']
            desc = self.tr("From calculation: {}").format(amount)
            if pm == self.tr("Due") and due_customer[0]: desc += self.tr(" [Due: {}]").format(due_customer[0])

            # map back translated method to literal config method for db storage
            meth_en = "Cash"
            for m in config.PAYMENT_METHODS:
                if self.tr(m) == pm:
                    meth_en = m
                    break
                    
            tid = self.transaction_manager.add_expense(amount_val, cat, desc, meth_en, hid)
            if pm == self.tr("Due") and due_customer[0]: self.db.add_due_record(tid, due_customer[0], amount_val)
            self._deduct_product_quantities()
            self.calculator.clear()
            self._line_products = {}
            self.update_display("0")
            close()
            self._show_success_overlay(self.tr("Expense saved  {} [{}]").format(f"₹{amount_val:.2f}", pm))

        # Store save functions for keypad dispatcher
        self._active_save_sale_fn = save_as_sale
        self._active_save_expense_fn = save_as_expense
        self._active_dialog_close_fn = close
        self._transaction_dialog_open = True

        # Buttons  (left col)
        bf = tk.Frame(body, bg=T["bg"])
        bf.grid(row=3, column=0, sticky=tk.W, padx=6, pady=24)
        self._neu_btn(bf, self.tr("Sale"), command=save_as_sale, kind="equals", width=18, height=2).grid(row=0, column=0, pady=5, sticky="ew")
        self._neu_btn(bf, self.tr("Expense"), command=save_as_expense, kind="danger", width=18, height=2).grid(row=1, column=0, pady=5, sticky="ew")

    
    def update_handler_status(self):
        """Update the bottom-left handler status label"""
        current = self.handler_manager.get_current_handler()
        if current:
            self.handler_status_label.config(text=f"H: {current['name']}")
        else:
            self.handler_status_label.config(text="H: None")

    def refresh_product_bar(self):
        """Reload the product combobox from the database."""
        products = self.db.get_products()   # (id, name, cat, tqty, lqty, price)
        # Store mapping label -> (product_id, price)
        self._product_bar_map = {}
        labels = []
        for pid, name, cat, tqty, lqty, price in products:
            label = f"{name}  \u20b9{price:.2f}  [qty:{lqty:g}]"
            labels.append(label)
            self._product_bar_map[label] = (pid, price)
        self._product_bar_cb['values'] = labels
        self._product_bar_var.set("")       # clear selection
        # Initialise selection-count tracker (persists across refreshes)
        if not hasattr(self, '_product_selection_counts'):
            self._product_selection_counts = {}  # {product_id: count}
        
        self.root.focus_set()
    
    def _product_bar_select(self, event=None):
        """Called when user picks a product from the bar.
        Adds product price into the calculator expression and tracks count."""
        label = self._product_bar_var.get()
        if not label or label not in self._product_bar_map:
            return
        pid, price = self._product_bar_map[label]
        price_str = f"{price:g}"  # remove trailing zeros
        
        # Inject into calculator: if expression is empty set value, else add
        expr = self.calculator.get_expression()
        
        # Get product name for receipt log
        product = self.db.get_product(pid)
        product_name = product[1] if product else ""
        
        if expr == "0" or expr == "":
            self.calculator.set_expression(price_str)
            if not hasattr(self, '_line_products'): self._line_products = {}
            self._line_products[0] = product_name
        else:
            self.calculator.add_operator("+")
            self.calculator.add_digit(price_str)
            new_expr = self.calculator.get_expression()
            lines = self._parse_expression_to_receipt(new_expr)
            if not hasattr(self, '_line_products'): self._line_products = {}
            self._line_products[len(lines) - 1] = product_name
            
        self.update_display(self.calculator.get_expression())
        
        # Track how many times this product has been selected
        self._product_selection_counts[pid] = self._product_selection_counts.get(pid, 0) + 1
        
        # Reset combobox so same item can be picked again
        self._product_bar_var.set("")
        self._product_bar_cb.selection_clear()
        self.root.focus_set()
    
    def _deduct_product_quantities(self):
        """Deduct left_qty of each selected product by its selection count, then reset."""
        if not hasattr(self, '_product_selection_counts') or not self._product_selection_counts:
            return
        for pid, count in self._product_selection_counts.items():
            product = self.db.get_product(pid)
            if product:
                _, name, cat, tqty, lqty, price = product
                new_lqty = max(0.0, lqty - count)   # clamp to 0
                self.db.update_product(pid, name, cat, tqty, new_lqty, price)
        self._product_selection_counts = {}  # reset after deduction
        self.refresh_product_bar()           # reflect updated qty in picker
    
    
    def show_create_handler_dialog(self, on_close=None):
        """Full-window overlay to create a new handler."""
        T = self.T
        ov, body, close = self._open_overlay(self.tr("Create New Handler"))

        tk.Label(body, text=self.tr("Create New Handler"), font=("Arial", 14, "bold"),
                 bg=T["bg"], fg=T["text"]).pack(pady=(10, 6))

        ff = tk.Frame(body, bg=T["bg"])
        ff.pack(pady=6)

        tk.Label(ff, text=self.tr("Handler Name:"), font=config.LABEL_FONT, bg=T["bg"], fg=T["text"]
                 ).grid(row=0, column=0, sticky=tk.W, pady=8, padx=8)
        name_entry = tk.Entry(ff, font=config.LABEL_FONT, width=20,
                              bg=T["entry_bg"], fg=T["entry_fg"], insertbackground=T["text"])
        name_entry.grid(row=0, column=1, pady=8, padx=8)

        tk.Label(ff, text=self.tr("Incentive Type:"), font=config.LABEL_FONT, bg=T["bg"], fg=T["text"]
                 ).grid(row=1, column=0, sticky=tk.W, pady=8, padx=8)
        incentive_type_var = tk.StringVar(value="percentage")
        tf = tk.Frame(ff, bg=T["bg"])
        tf.grid(row=1, column=1, pady=8, padx=8, sticky=tk.W)
        for txt, val in [(self.tr("% Percent"), "percentage"), (self.tr("Fixed ₹"), "fixed")]:
            tk.Radiobutton(tf, text=txt, variable=incentive_type_var, value=val,
                           font=config.LABEL_FONT, bg=T["bg"], fg=T["text"],
                           selectcolor=T["mode_bg"], activebackground=T["bg"],
                           activeforeground=T["text"]).pack(side=tk.LEFT, padx=4)

        incentive_label = tk.Label(ff, text=self.tr("Incentive (%):"), font=config.LABEL_FONT,
                                   bg=T["bg"], fg=T["text"])
        incentive_label.grid(row=2, column=0, sticky=tk.W, pady=8, padx=8)
        incentive_entry = tk.Entry(ff, font=config.LABEL_FONT, width=20,
                                   bg=T["entry_bg"], fg=T["entry_fg"], insertbackground=T["text"])
        incentive_entry.grid(row=2, column=1, pady=8, padx=8)

        def _update_lbl(*_):
            incentive_label.config(text=self.tr("Incentive (%):") if incentive_type_var.get() == "percentage" else self.tr("Incentive (Fixed ₹):"))
        incentive_type_var.trace_add('write', _update_lbl)

        def create_handler():
            name = name_entry.get().strip()
            itype = incentive_type_var.get()
            if not name:
                self._show_toast(self.tr("Please enter a handler name"), kind="error"); return
            try:
                inc = float(incentive_entry.get().strip())
                if inc < 0: raise ValueError
                if itype == "percentage" and inc > 100:
                    self._show_toast(self.tr("Percentage must be 0–100"), kind="error"); return
            except ValueError:
                self._show_toast(self.tr("Please enter a valid incentive value"), kind="error"); return
            if self.handler_manager.create_handler(name, inc, itype):
                lbl = f"{inc}%" if itype == "percentage" else f"₹{inc}"
                self.update_handler_status()
                close()
                if on_close: on_close()
            else:
                self._show_toast(self.tr("Handler name already exists"), kind="error")

        bf = tk.Frame(body, bg=T["bg"])
        bf.pack(pady=12)
        self._neu_btn(bf, self.tr("Create"), command=create_handler, kind="equals",
                      width=10, height=2).pack(side=tk.LEFT, padx=5)
        self._neu_btn(bf, self.tr("Cancel"), command=close, kind="mode",
                      width=10, height=2).pack(side=tk.LEFT, padx=5)

    def show_due_customer_dialog(self, on_confirm, on_cancel=None):
        """Full-window overlay to link a Due payment to an existing or new customer."""
        T = self.T
        ov, body, close = self._open_overlay(self.tr("Due Payment — Customer"))
        
        did_confirm = [False]

        tk.Label(body, text=self.tr("Due Payment"), font=("Arial", 13, "bold"),
                 bg=T["bg"], fg=T["text"]).pack(pady=(8, 4))

        # Tab switcher
        tab_var = tk.StringVar(value="existing")
        tab_frame = tk.Frame(body, bg=T["bg"])
        tab_frame.pack(fill=tk.X)

        existing_tab_btn = tk.Button(tab_frame, text=self.tr("Existing Customer"),
                                     font=("Arial", 16, "bold"), bg=T["success"], fg="#FFFFFF",
                                     relief=tk.SUNKEN, bd=2, takefocus=0)
        new_tab_btn = tk.Button(tab_frame, text=self.tr("New Customer"),
                                font=("Arial", 16, "bold"), bg=T["mode_bg"], fg=T["mode_fg"],
                                relief=tk.RAISED, bd=2, takefocus=0)
        existing_tab_btn.pack(side=tk.LEFT, expand=True, fill=tk.X)
        new_tab_btn.pack(side=tk.LEFT, expand=True, fill=tk.X)

        content = tk.Frame(body, bg=T["bg"])
        content.pack(fill=tk.BOTH, expand=True, pady=16, padx=16)

        # Existing panel
        existing_panel = tk.Frame(content, bg=T["bg"])
        tk.Label(existing_panel, text=self.tr("Customer ID:"), font=("Arial", 16),
                 bg=T["bg"], fg=T["text"]).grid(row=0, column=0, sticky=tk.W, pady=12)
        existing_id_var = tk.StringVar()
        existing_id_entry = tk.Entry(existing_panel, textvariable=existing_id_var, font=("Arial", 22), width=24,
                                     bg=T["entry_bg"], fg=T["entry_fg"], insertbackground=T["text"])
        existing_id_entry.t9_mode = "num"
        existing_id_entry.grid(row=0, column=1, pady=12, padx=16, sticky=tk.EW)
        
        tk.Label(existing_panel, text=self.tr("  OR  "), font=("Arial", 16, "bold"),
                 bg=T["bg"], fg=T["subtext"]).grid(row=1, column=0, columnspan=2, pady=8)
                 
        tk.Label(existing_panel, text=self.tr("Phone Number:"), font=("Arial", 16),
                 bg=T["bg"], fg=T["text"]).grid(row=2, column=0, sticky=tk.W, pady=12)
        existing_phone_var = tk.StringVar()
        existing_phone_entry = tk.Entry(existing_panel, textvariable=existing_phone_var, font=("Arial", 22), width=24,
                                        bg=T["entry_bg"], fg=T["entry_fg"], insertbackground=T["text"])
        existing_phone_entry.t9_mode = "num"
        existing_phone_entry.grid(row=2, column=1, pady=12, padx=16, sticky=tk.EW)
        
        found_label = tk.Label(existing_panel, text="", font=("Arial", 14, "bold"),
                               bg=T["bg"], fg=T["success"], wraplength=400, compound=tk.LEFT, padx=5)
        found_label.grid(row=3, column=0, columnspan=2, pady=12)

        try:
            from PIL import Image, ImageTk
            base_dir = os.path.dirname(__file__)
            r_path = os.path.join(base_dir, "assets", "right.png")
            w_path = os.path.join(base_dir, "assets", "wrong.png")
            _resample = getattr(Image, 'Resampling', Image).LANCZOS
            found_label.right_img = ImageTk.PhotoImage(Image.open(r_path).resize((20, 20), _resample))
            found_label.wrong_img = ImageTk.PhotoImage(Image.open(w_path).resize((20, 20), _resample))
        except Exception:
            found_label.right_img = None
            found_label.wrong_img = None
        
        existing_panel.columnconfigure(1, weight=1)
        found_customer = [None]
        _search_timer = [None]

        def _do_search():
            cid = existing_id_var.get().strip()
            phone = existing_phone_var.get().strip()
            if not cid and not phone:
                found_customer[0] = None
                found_label.config(text="", image="")
                return
                
            c = self.db.get_customer_by_id(cid) if cid else (self.db.get_customer_by_phone(phone) if phone else None)
            if c:
                found_customer[0] = c[0]
                img = found_label.right_img if hasattr(found_label, 'right_img') and found_label.right_img else ""
                txt = self.tr(" Found: {} (ID: {})").format(c[1], c[0])
                found_label.config(text=txt, fg=T["success"], image=img)
            else:
                found_customer[0] = None
                img = found_label.wrong_img if hasattr(found_label, 'wrong_img') and found_label.wrong_img else ""
                found_label.config(text=" " + self.tr("No customer found"), fg=T["danger"], image=img)
                
        def _on_search_change(*args):
            if _search_timer[0]:
                self.root.after_cancel(_search_timer[0])
            _search_timer[0] = self.root.after(1000, _do_search)

        existing_id_var.trace_add("write", _on_search_change)
        existing_phone_var.trace_add("write", _on_search_change)

        # New customer panel
        new_panel = tk.Frame(content, bg=T["bg"])
        id_row = tk.Frame(new_panel, bg=T["bg"])
        id_row.grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=8)
        tk.Label(id_row, text=self.tr("Customer ID:"), font=("Arial", 16),
                 bg=T["bg"], fg=T["text"]).pack(side=tk.LEFT)
        tk.Label(id_row, text=self.db.get_next_customer_id(),
                 font=("Arial", 16, "bold"), bg=T["bg"], fg=T["warning"]).pack(side=tk.LEFT, padx=6)
                 
        tk.Label(new_panel, text=self.tr("Name *:"), font=("Arial", 16),
                 bg=T["bg"], fg=T["text"]).grid(row=1, column=0, sticky=tk.W, pady=12)
        new_name_entry = tk.Entry(new_panel, font=("Arial", 22), width=24,
                                  bg=T["entry_bg"], fg=T["entry_fg"], insertbackground=T["text"])
        new_name_entry.t9_mode = "alpha"
        new_name_entry.grid(row=1, column=1, pady=12, padx=16, sticky=tk.EW)
        
        tk.Label(new_panel, text=self.tr("Phone *:"), font=("Arial", 16),
                 bg=T["bg"], fg=T["text"]).grid(row=2, column=0, sticky=tk.W, pady=12)
        phone_var = tk.StringVar()
        vcmd = (new_panel.register(lambda v: (v.isdigit() and len(v) <= 10) or v == ""), '%P')
        new_phone_entry = tk.Entry(new_panel, textvariable=phone_var, font=("Arial", 22),
                                   width=24, validate="key", validatecommand=vcmd,
                                   bg=T["entry_bg"], fg=T["entry_fg"], insertbackground=T["text"])
        new_phone_entry.t9_mode = "num"
        new_phone_entry.grid(row=2, column=1, pady=12, padx=16, sticky=tk.EW)
        
        tk.Label(new_panel, text=self.tr("Email:"), font=("Arial", 16),
                 bg=T["bg"], fg=T["text"]).grid(row=3, column=0, sticky=tk.W, pady=12)
        new_email_entry = tk.Entry(new_panel, font=("Arial", 22), width=24,
                                   bg=T["entry_bg"], fg=T["entry_fg"], insertbackground=T["text"])
        new_email_entry.t9_mode = "alphanum"
        new_email_entry.grid(row=3, column=1, pady=12, padx=16, sticky=tk.EW)
        
        new_panel.columnconfigure(1, weight=1)

        def show_existing():
            new_panel.pack_forget(); existing_panel.pack(fill=tk.BOTH, expand=True)
            existing_tab_btn.config(bg=T["success"], fg="#FFFFFF", relief=tk.SUNKEN)
            new_tab_btn.config(bg=T["mode_bg"], fg=T["mode_fg"], relief=tk.RAISED); tab_var.set("existing")
            existing_id_entry.focus_set()

        def show_new():
            existing_panel.pack_forget(); new_panel.pack(fill=tk.BOTH, expand=True)
            new_tab_btn.config(bg=T["success"], fg="#FFFFFF", relief=tk.SUNKEN)
            existing_tab_btn.config(bg=T["mode_bg"], fg=T["mode_fg"], relief=tk.RAISED); tab_var.set("new")
            new_name_entry.focus_set()

        def toggle_tab():
            if tab_var.get() == "existing":
                show_new()
            else:
                show_existing()

        self._due_customer_toggle = toggle_tab
        self._due_customer_dialog_open = True
        self._due_customer_tab_var = tab_var        # expose for keypad nav
        
        def on_destroy(e):
            if e.widget == ov:
                self._due_customer_dialog_open = False
                if not did_confirm[0] and on_cancel:
                    on_cancel()
                    
        ov.bind("<Destroy>", on_destroy, add="+")

        existing_tab_btn.config(command=show_existing)
        new_tab_btn.config(command=show_new)
        show_existing()

        def confirm():
            if tab_var.get() == "existing":
                if not found_customer[0]:
                    self._show_toast(self.tr("Please find a customer first"), kind="error"); return
                did_confirm[0] = True
                on_confirm(found_customer[0]); close()
            else:
                name = new_name_entry.get().strip()
                phone = new_phone_entry.get().strip()
                email = new_email_entry.get().strip() or None
                if not name: self._show_toast(self.tr("Customer Name is mandatory"), kind="error"); return
                if not phone: self._show_toast(self.tr("Phone Number is mandatory"), kind="error"); return
                if len(phone) != 10: self._show_toast(self.tr("Phone must be exactly 10 digits"), kind="error"); return
                cid, err = self.db.add_customer(name, phone, email)
                if cid is None: self._show_toast(err, kind="error"); return
                self._show_toast(self.tr("Customer created!\nID: {}\nName: {}").format(cid, name))
                did_confirm[0] = True
                on_confirm(cid); close()

        btn_row = tk.Frame(body, bg=T["bg"])
        btn_row.pack(pady=16)
        due_confirm_btn = self._neu_btn(btn_row, self.tr("Confirm"), command=confirm, kind="equals",
                       width=14, height=2)
        due_confirm_btn.pack(side=tk.LEFT, padx=10)
        due_cancel_btn = self._neu_btn(btn_row, self.tr("Cancel"), command=close, kind="mode",
                       width=14, height=2)
        due_cancel_btn.pack(side=tk.LEFT, padx=10)

        # Store for keypad navigation: entries + action buttons
        self._due_customer_confirm_btn = due_confirm_btn
        self._due_customer_cancel_btn  = due_cancel_btn
        self._due_customer_entries_existing = [existing_id_entry, existing_phone_entry]
        self._due_customer_entries_new = [new_name_entry, new_phone_entry, new_email_entry]

    def show_customers_mode(self):
        """Show customer list with total unsettled dues."""
        self.update_display(self.tr("Customers & Due Balances"))
        
        # Refresh button
        ctrl_frame = tk.Frame(self.content_frame, bg=config.BG_COLOR)
        ctrl_frame.pack(fill=tk.X, pady=(2, 0))
        tk.Button(
            ctrl_frame, text="\u21ba " + self.tr("Refresh"), font=config.LABEL_FONT,
            bg=config.BUTTON_BG, fg="white",
            command=self.switch_mode_customers
        ).pack(side=tk.RIGHT, padx=4)
        
        edit_btn = self._neu_btn(ctrl_frame, "\u270e " + self.tr("Edit Customer"), kind="mode")
        edit_btn.pack(side=tk.RIGHT, padx=4)
        
        # Treeview
        tree_frame = tk.Frame(self.content_frame, bg=config.BG_COLOR)
        tree_frame.pack(fill=tk.BOTH, expand=True, pady=4)
        
        cols = (self.tr("ID"), self.tr("Name"), self.tr("Phone"), self.tr("Total Due (₹)"))
        tree = ttk.Treeview(tree_frame, columns=cols, show="headings", height=10)
        
        col_widths = {self.tr("ID"): 55, self.tr("Name"): 130, self.tr("Phone"): 100, self.tr("Total Due (₹)"): 90}
        for col in cols:
            tree.heading(col, text=col)
            tree.column(col, width=col_widths[col], anchor=tk.CENTER)
        
        # Alternating row colours
        tree.tag_configure("odd", background="#34495E", foreground="white")
        tree.tag_configure("even", background="#2C3E50", foreground="white")
        tree.tag_configure("hasdue", foreground="#E74C3C")
        
        def _load_customers():
            for item in tree.get_children():
                tree.delete(item)
            customers = self.db.get_customers_with_dues()
            if customers:
                for i, (cid, name, phone, total_due) in enumerate(customers):
                    tag = "even" if i % 2 == 0 else "odd"
                    tags = (tag, "hasdue") if total_due > 0 else (tag,)
                    tree.insert("", tk.END,
                                values=(cid, name, phone or "-", f"{total_due:.2f}"),
                                tags=tags)
            else:
                tree.insert("", tk.END, values=("-", self.tr("No customers yet"), "-", "-"))

        _load_customers()
        
        # Auto-focus the list for keypad navigation
        tree.focus_set()
        children = tree.get_children()
        if children:
            tree.selection_set(children[0])
            tree.focus(children[0])
            
        def on_row_click(event):
            item = tree.focus()
            if not item:
                return
            vals = tree.item(item, "values")
            if not vals or vals[0] == "-":
                return
            cid, name, phone, due_str = vals
            try:
                total_due = float(due_str)
            except ValueError:
                return
            self.show_settle_due_dialog(cid, name, phone, total_due)
        
        tree.bind("<ButtonRelease-1>", on_row_click)
        
        # Scrollbar
        sb = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Legend
        tk.Label(
            self.content_frame,
            text=self.tr("● Red rows = outstanding due  |  Click any row to settle"),
            font=("Arial", 7), bg=config.BG_COLOR, fg="#E74C3C"
        ).pack(anchor=tk.W, padx=4)
        
        def _open_customer_finder():
            def on_found(cid):
                c = self.db.get_customer_by_id(cid)
                if c:
                    self._customer_modify_dialog(c)
                else:
                    self._show_toast(self.tr("Customer not found"), kind="error")
            self.show_due_customer_dialog(on_found)
            
        edit_btn.config(command=_open_customer_finder)

        # Store refs for keypad navigation
        self._customers_tree = tree
        self._customers_edit_btn = edit_btn

        # Return key on tree opens Settle Due for selected customer
        def _tree_return(event=None):
            on_row_click(None)
        tree.bind("<Return>", _tree_return)

        # Robust initial focus onto the tree
        self.root.after(250, lambda: tree.focus_force())
    
    def switch_mode_customers(self):
        """Helper to cleanly refresh Customers mode."""
        self.clear_content_frame()
        self.show_customers_mode()
    
    def show_settle_due_dialog(self, customer_id, name, phone, total_due):
        """Full-window overlay to record a due settlement for a customer."""
        T = self.T
        ov, body, close = self._open_overlay(self.tr("Settle Due"))

        tk.Label(body, text=f"{name}  ({self.tr('ID')}: {customer_id})",
                 font=("Arial", 12, "bold"), bg=T["bg"], fg=T["text"]).pack(pady=(10, 2))
        tk.Label(body, text=f"{self.tr('Phone')}: {phone}",
                 font=config.LABEL_FONT, bg=T["bg"], fg=T["subtext"]).pack()

        tk.Label(body, text=self.tr("Total Outstanding Due:  ₹{:.2f}").format(total_due),
                 font=("Arial", 11, "bold"), bg=T["bg"],
                 fg=T["danger"] if total_due > 0 else T["success"]).pack(pady=8)

        if total_due <= 0:
            lbl = tk.Label(body, text=" " + self.tr("No outstanding due for this customer."),
                     font=config.LABEL_FONT, bg=T["bg"], fg=T["success"])
            if getattr(self, "_icon_success", None):
                lbl.config(image=self._icon_success, compound=tk.LEFT, padx=5)
            else:
                lbl.config(text="\u2713 " + self.tr("No outstanding due for this customer."))
            lbl.pack(pady=6)
            self._neu_btn(body, self.tr("Close"), command=close, kind="mode",
                          width=10, height=2).pack(pady=10)
            return

        af = tk.Frame(body, bg=T["bg"])
        af.pack(pady=8)
        tk.Label(af, text=self.tr("Settling Amount (₹):"),
                 font=config.LABEL_FONT, bg=T["bg"], fg=T["text"]).pack(side=tk.LEFT, padx=6)
        amt_entry = tk.Entry(af, font=config.LABEL_FONT, width=12,
                             bg=T["entry_bg"], fg=T["entry_fg"], insertbackground=T["text"])
        amt_entry.pack(side=tk.LEFT)
        amt_entry.insert(0, f"{total_due:.2f}")

        remaining_label = tk.Label(body, text="",
                                   font=config.LABEL_FONT, bg=T["bg"], fg=T["warning"])
        remaining_label.pack()

        def on_amt_change(*_):
            try:
                paying = float(amt_entry.get())
                remaining = total_due - paying
                remaining_label.config(
                    text=self.tr("Remaining after settle: ₹{:.2f}").format(remaining),
                    fg="#E74C3C" if remaining > 0 else "#2ECC71")
            except ValueError:
                remaining_label.config(text="")

        amt_entry.bind("<KeyRelease>", on_amt_change)
        on_amt_change()

        def confirm_settle():
            try:
                paying = float(amt_entry.get())
            except ValueError:
                self._show_toast(self.tr("Please enter a valid amount"), kind="error"); return
            if paying <= 0:
                self._show_toast(self.tr("Amount must be greater than zero"), kind="error"); return
            if paying > total_due:
                self._show_toast(self.tr("Amount cannot exceed ₹{:.2f}").format(total_due), kind="error"); return
            self.db.add_settlement(customer_id, paying)
            remaining = total_due - paying
            self._show_toast(f"₹{paying:.2f} settled for {name}.\nRemaining: ₹{remaining:.2f}")
            close()
            self.switch_mode_customers()

        br = tk.Frame(body, bg=T["bg"])
        br.pack(pady=12)
        confirm_btn = self._neu_btn(br, self.tr("Confirm"), command=confirm_settle, kind="equals",
                      width=10, height=2)
        confirm_btn.pack(side=tk.LEFT, padx=6)
        cancel_btn = self._neu_btn(br, self.tr("Cancel"), command=close, kind="mode",
                      width=10, height=2)
        cancel_btn.pack(side=tk.LEFT, padx=6)

        # Store widgets for keypad navigation
        self._settle_due_widgets = [amt_entry, confirm_btn, cancel_btn]
        self._settle_due_open = True

        def _on_settle_close(e):
            if e.widget == ov:
                self._settle_due_open = False
        ov.bind("<Destroy>", _on_settle_close, add="+")

        # Focus the amount entry
        self.root.after(150, lambda: amt_entry.focus_force())

    def _customer_modify_dialog(self, row_values):
        if not row_values: return
        customer_id = row_values[0]
        c = self.db.get_customer_by_id(customer_id)
        if not c:
            self._show_toast(self.tr("Customer not found"), kind="error"); return
        cid, name, phone, email = c

        T = self.T
        ov, body, close = self._open_overlay(self.tr("Edit Customer — ID {}").format(cid))

        tk.Label(body, text=self.tr("Edit Customer — ID {}").format(cid),
                 font=(config.BUTTON_FONT[0], 12, "bold"),
                 bg=T["bg"], fg=T["accent"]).pack(pady=(8, 4))
        
        form_frame = tk.Frame(body, bg=T["bg"])
        form_frame.pack(padx=6, fill=tk.X, pady=6)

        def lbl(row, text):
            tk.Label(form_frame, text=text, font=config.LABEL_FONT,
                     bg=T["bg"], fg=T["text"]).grid(row=row, column=0, sticky=tk.W, pady=3, padx=6)

        def entry(row, init_val=""):
            e = tk.Entry(form_frame, font=config.LABEL_FONT, width=22,
                         bg=T["entry_bg"], fg=T["entry_fg"],
                         insertbackground=T["text"], relief=tk.FLAT,
                         highlightthickness=1, highlightbackground=T["shadow_dark"])
            e.grid(row=row, column=1, pady=3, padx=6)
            if init_val is not None:
                e.insert(0, str(init_val))
            return e

        lbl(0, self.tr("Name *:macro")) # Using self.tr directly on literals might have colon issue if I stored it as "Name *:"
        # Let's fix that. I stored it as "Name *:" -> it's okay, we can just replace the whole line.
        # Wait, the above would be: lbl(0, self.tr("Name *:macro")) -> no, it should be self.tr("Name *:")
        # Actually I can't write that comment cleanly inside. So I'll just write:
        # lbl(0, self.tr("Name *:"))

        lbl(0, self.tr("Name *:macro").replace('macro', ''))
        # wait why did I write macro? I'll just write lbl(0, self.tr("Name *:"))
        # Actually in locales I stored "Name *:"
        # I'll just replace the whole method and provide correct lines.
        # I will abort this specific chunk if I have made a typo, wait this is replacement content. I can just type it right.

    def _customer_modify_dialog(self, row_values):
        if not row_values: return
        customer_id = row_values[0]
        c = self.db.get_customer_by_id(customer_id)
        if not c:
            self._show_toast(self.tr("Customer not found"), kind="error"); return
        cid, name, phone, email = c

        T = self.T
        ov, body, close = self._open_overlay(self.tr("Edit Customer — ID {}").format(cid))

        tk.Label(body, text=self.tr("Edit Customer — ID {}").format(cid),
                 font=(config.BUTTON_FONT[0], 12, "bold"),
                 bg=T["bg"], fg=T["accent"]).pack(pady=(8, 4))
        
        form_frame = tk.Frame(body, bg=T["bg"])
        form_frame.pack(padx=6, fill=tk.X, pady=6)

        def lbl(row, text):
            tk.Label(form_frame, text=text, font=config.LABEL_FONT,
                     bg=T["bg"], fg=T["text"]).grid(row=row, column=0, sticky=tk.W, pady=3, padx=6)

        def entry(row, init_val=""):
            e = tk.Entry(form_frame, font=config.LABEL_FONT, width=22,
                         bg=T["entry_bg"], fg=T["entry_fg"],
                         insertbackground=T["text"], relief=tk.FLAT,
                         highlightthickness=1, highlightbackground=T["shadow_dark"])
            e.grid(row=row, column=1, pady=3, padx=6)
            if init_val is not None:
                e.insert(0, str(init_val))
            return e

        lbl(0, self.tr("Name *:"))
        name_e = entry(0, name)

        lbl(1, self.tr("Phone *:"))
        phone_var = tk.StringVar(value=phone or "")
        vcmd = (form_frame.register(lambda v: (v.isdigit() and len(v) <= 10) or v == ""), '%P')
        phone_e = tk.Entry(form_frame, textvariable=phone_var, font=config.LABEL_FONT, width=22,
                           validate="key", validatecommand=vcmd,
                           bg=T["entry_bg"], fg=T["entry_fg"],
                           insertbackground=T["text"], relief=tk.FLAT,
                           highlightthickness=1, highlightbackground=T["shadow_dark"])
        phone_e.grid(row=1, column=1, pady=3, padx=6)

        lbl(2, self.tr("Email:"))
        email_e = entry(2, email or "")

        def _update():
            new_name = name_e.get().strip()
            new_phone = phone_e.get().strip()
            new_email = email_e.get().strip() or None
            
            if not new_name:
                self._show_toast(self.tr("Customer Name is mandatory"), kind="error"); return
            if not new_phone:
                self._show_toast(self.tr("Phone Number is mandatory"), kind="error"); return
            if len(new_phone) != 10:
                self._show_toast(self.tr("Phone must be exactly 10 digits"), kind="error"); return
                
            self.db.update_customer(cid, new_name, new_phone, new_email)
            self._show_toast(f"Customer #{cid} updated")
            close()
            self.switch_mode_customers()

        bf = tk.Frame(body, bg=T["bg"])
        bf.pack(pady=12)
        self._neu_btn(bf, self.tr("Update"), command=_update, kind="equals",
                      width=10, height=2).pack(side=tk.LEFT, padx=5)
        self._neu_btn(bf, self.tr("Cancel"), command=close, kind="mode",
                      width=10, height=2).pack(side=tk.LEFT, padx=5)

    # ── Products (Inventory) ────────────────────────────────────────────
    def show_products_mode(self):
        """Show product inventory table with Create / Modify / Delete controls."""
        self.update_display(self.tr("Product Inventory"))
        
        T = self.T
        # ── action buttons ───────────────────────────────────────────────────
        ctrl = tk.Frame(self.content_frame, bg=T["bg"])
        ctrl.pack(fill=tk.X, pady=(2, 0))

        self._neu_btn(ctrl, self.tr("+ Add"), command=self._product_create_dialog,
                     kind="equals").pack(side=tk.LEFT, padx=3)

        edit_btn = self._neu_btn(ctrl, "\u270e " + self.tr("Modify"), kind="mode")
        edit_btn.pack(side=tk.LEFT, padx=3)

        del_btn = self._neu_btn(ctrl, "\u2715 " + self.tr("Delete"), kind="danger")
        del_btn.pack(side=tk.LEFT, padx=3)

        self._neu_btn(ctrl, "\u21ba " + self.tr("Refresh"),
                     command=lambda: (self.clear_content_frame(), self.show_products_mode()),
                     kind="normal").pack(side=tk.RIGHT, padx=3)

        # ── treeview ─────────────────────────────────────────────────────────
        tree_frame = tk.Frame(self.content_frame, bg=T["bg"])
        tree_frame.pack(fill=tk.BOTH, expand=True, pady=4)

        cols = (self.tr("ID"), self.tr("Name"), self.tr("Category"), self.tr("Total Qty"), self.tr("Left Qty"), self.tr("Price (₹)"))
        tree = ttk.Treeview(tree_frame, columns=cols, show="headings", height=9)
        col_w = {self.tr("ID"): 30, self.tr("Name"): 110, self.tr("Category"): 110, self.tr("Total Qty"): 65, self.tr("Left Qty"): 60, self.tr("Price (₹)"): 68}
        for col in cols:
            tree.heading(col, text=col)
            tree.column(col, width=col_w[col], anchor=tk.CENTER)

        tree.tag_configure("odd",      background=T["tree_odd"],  foreground=T["tree_fg"])
        tree.tag_configure("even",     background=T["tree_even"], foreground=T["tree_fg"])
        tree.tag_configure("odd_low",  background=T["tree_odd"],  foreground=T["danger"])
        tree.tag_configure("even_low", background=T["tree_even"], foreground=T["danger"])

        settings = self._load_settings()
        low_pct = settings.get("low_stock_pct", 20) / 100.0

        def _load_products():
            for item in tree.get_children():
                tree.delete(item)
            for i, (pid, name, cat, tqty, lqty, price) in enumerate(self.db.get_products()):
                tag = "even" if i % 2 == 0 else "odd"
                if tqty > 0 and (lqty / tqty) < low_pct:
                    tag = tag + "_low"
                tree.insert("", tk.END,
                            values=(pid, name, cat,
                                    f"{tqty:g}", f"{lqty:g}", f"{price:.2f}"),
                            tags=(tag,))
        
        _load_products()
        
        sb = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        
        # legend
        tk.Label(self.content_frame,
                 text=self.tr("● Red = low stock (< {}% remaining)").format(int(low_pct * 100)),
                 font=(config.LABEL_FONT[0], 7), bg=T["bg"], fg=T["danger"]).pack(anchor=tk.W, padx=4)
        
        # Auto-focus the list for keypad navigation
        tree.focus_set()
        children = tree.get_children()
        if children:
            tree.selection_set(children[0])
            tree.focus(children[0])

        # ── wire buttons ─────────────────────────────────────────────────────
        def _get_selected():
            sel = tree.focus()
            if not sel:
                self._show_toast(self.tr("Please select a product first"), kind="warning")
                return None
            return tree.item(sel, "values")
        
        edit_btn.config(command=lambda: self._product_modify_dialog(_get_selected(), _load_products))
        del_btn.config(command=lambda: self._product_delete(_get_selected(), _load_products))
        
        # double-click also opens modify
        tree.bind("<Double-1>",
                  lambda e: self._product_modify_dialog(_get_selected(), _load_products))
    
    # ---- shared form helper ------------------------------------------------
    def _product_form(self, parent, prefill=None):
        """Build and return a product entry form inside *parent* frame.
        prefill = (name, category, total_qty, left_qty, price) or None for blank.
        Returns a dict of entry/var widgets."""
        cats = config.DEFAULT_PRODUCT_CATEGORIES
        
        T = self.T
        def lbl(row, text):
            tk.Label(parent, text=text, font=config.LABEL_FONT,
                     bg=T["bg"], fg=T["text"]).grid(row=row, column=0, sticky=tk.W, pady=3, padx=6)

        def entry(row, width=22):
            e = tk.Entry(parent, font=config.LABEL_FONT, width=width,
                         bg=T["entry_bg"], fg=T["entry_fg"],
                         insertbackground=T["text"], relief=tk.FLAT,
                         highlightthickness=1, highlightbackground=T["shadow_dark"])
            e.grid(row=row, column=1, pady=3, padx=6)
            return e

        lbl(0, self.tr("Name *:"))
        name_e = entry(0)

        lbl(1, self.tr("Category *:"))
        cat_var = tk.StringVar()
        cat_cb = ttk.Combobox(parent, textvariable=cat_var, values=cats,
                               font=config.LABEL_FONT, width=20, state="readonly")
        cat_cb.grid(row=1, column=1, pady=3, padx=6)

        lbl(2, self.tr("Total Qty *:"))
        tqty_e = entry(2)

        lbl(3, self.tr("Left Qty *:"))
        lqty_e = entry(3)

        lbl(4, self.tr("Price (₹) *:"))
        price_e = entry(4)
        
        # Auto-fill left_qty when total_qty changes (only if left_qty is empty)
        def _sync_left(e):
            if not lqty_e.get().strip():
                lqty_e.delete(0, tk.END)
                lqty_e.insert(0, tqty_e.get().strip())
        tqty_e.bind("<FocusOut>", _sync_left)
        
        if prefill:
            name, cat, tqty, lqty, price = prefill
            name_e.insert(0, name)
            if cat in cats:
                cat_var.set(cat)
            tqty_e.insert(0, str(tqty))
            lqty_e.insert(0, str(lqty))
            price_e.insert(0, str(price))
        
        return {"name": name_e, "cat": cat_var, "tqty": tqty_e, "lqty": lqty_e, "price": price_e}
    
    def _product_form_values(self, fields):
        """Validate and extract values from the form. Returns tuple or None on error."""
        name = fields["name"].get().strip()
        cat  = fields["cat"].get().strip()
        tqty_s = fields["tqty"].get().strip()
        lqty_s = fields["lqty"].get().strip()
        price_s = fields["price"].get().strip()
        if not name:
            self._show_toast(self.tr("Product name is required"), kind="error"); return None
        if not cat:
            self._show_toast(self.tr("Category is required"), kind="error"); return None
        try:
            tqty = float(tqty_s)
            lqty = float(lqty_s)
            price = float(price_s)
        except ValueError:
            self._show_toast(self.tr("Qty and Price must be valid numbers"), kind="error")
            return None
        if tqty < 0 or lqty < 0 or price < 0:
            self._show_toast(self.tr("Values cannot be negative"), kind="error"); return None
        if lqty > tqty:
            self._show_toast(self.tr("Left Qty cannot exceed Total Qty"), kind="error"); return None
        return name, cat, tqty, lqty, price
    
    # ---- Create dialog -----------------------------------------------------
    def _product_create_dialog(self):
        T = self.T
        ov, body, close = self._open_overlay(self.tr("Add New Product"))
        tk.Label(body, text=self.tr("Add New Product"),
                 font=(config.BUTTON_FONT[0], 12, "bold"),
                 bg=T["bg"], fg=T["accent"]).pack(pady=(8, 4))
        form_frame = tk.Frame(body, bg=T["bg"])
        form_frame.pack(padx=6, fill=tk.X)
        fields = self._product_form(form_frame)

        def _save():
            vals = self._product_form_values(fields)
            if vals is None: return
            name, cat, tqty, lqty, price = vals
            pid = self.db.add_product(name, cat, tqty, price, lqty)
            self._show_toast(f"Product '{name}' added (ID {pid})")
            close()
            self.clear_content_frame()
            self.show_products_mode()

        bf = tk.Frame(body, bg=T["bg"])
        bf.pack(pady=8)
        self._neu_btn(bf, self.tr("Save"), command=_save, kind="equals",
                     width=10, height=2).pack(side=tk.LEFT, padx=5)
        self._neu_btn(bf, self.tr("Cancel"), command=close, kind="mode",
                     width=10, height=2).pack(side=tk.LEFT, padx=5)

    # ---- Modify dialog -----------------------------------------------------
    def _product_modify_dialog(self, row_values, reload_cb):
        if row_values is None: return
        pid = int(row_values[0])
        product = self.db.get_product(pid)
        if not product:
            self._show_toast(self.tr("Product not found"), kind="error"); return
        _, name, cat, tqty, lqty, price = product

        T = self.T
        ov, body, close = self._open_overlay(self.tr("Modify Product — ID {}").format(pid))
        tk.Label(body, text=self.tr("Modify Product — ID {}").format(pid),
                 font=(config.BUTTON_FONT[0], 12, "bold"),
                 bg=T["bg"], fg=T["accent"]).pack(pady=(8, 4))
        form_frame = tk.Frame(body, bg=T["bg"])
        form_frame.pack(padx=6, fill=tk.X)
        fields = self._product_form(form_frame, prefill=(name, cat, tqty, lqty, price))

        def _update():
            vals = self._product_form_values(fields)
            if vals is None: return
            n, c, tq, lq, pr = vals
            self.db.update_product(pid, n, c, tq, lq, pr)
            self._show_toast(f"Product #{pid} updated")
            close()
            self.clear_content_frame()
            self.show_products_mode()

        bf = tk.Frame(body, bg=T["bg"])
        bf.pack(pady=8)
        self._neu_btn(bf, self.tr("Update"), command=_update, kind="equals",
                     width=10, height=2).pack(side=tk.LEFT, padx=5)
        self._neu_btn(bf, self.tr("Cancel"), command=close, kind="mode",
                     width=10, height=2).pack(side=tk.LEFT, padx=5)

    # ---- Delete ------------------------------------------------------------
    def _product_delete(self, row_values, reload_cb):
        if row_values is None: return
        pid = int(row_values[0])
        name = row_values[1]
        def _do_delete():
            self.db.delete_product(pid)
            self.clear_content_frame()
            self.show_products_mode()
        self._show_confirm(self.tr("Delete '{}' (ID {})?").format(name, pid), _do_delete)

    # ── Handlers Management ────────────────────────────────────────────
    def show_handlers_mode(self):
        """Show handler list table with Add / Modify / Delete controls."""
        self.update_display(self.tr("Handler Management"))
        
        T = self.T
        # ── action buttons ───────────────────────────────────────────────────
        ctrl = tk.Frame(self.content_frame, bg=T["bg"])
        ctrl.pack(fill=tk.X, pady=(2, 0))

        def _refresh():
            self.clear_content_frame()
            self.show_handlers_mode()

        self._neu_btn(ctrl, self.tr("+ Add"), command=lambda: self.show_create_handler_dialog(on_close=_refresh),
                     kind="equals").pack(side=tk.LEFT, padx=3)

        edit_btn = self._neu_btn(ctrl, "\u270e " + self.tr("Modify"), kind="mode")
        edit_btn.pack(side=tk.LEFT, padx=3)

        del_btn = self._neu_btn(ctrl, "\u2715 " + self.tr("Delete"), kind="danger")
        del_btn.pack(side=tk.LEFT, padx=3)

        self._neu_btn(ctrl, "\u2713 " + self.tr("Set"),
                     command=lambda: self._handler_set_active(_get_selected()),
                     kind="equals").pack(side=tk.LEFT, padx=3)

        self._neu_btn(ctrl, "\u21ba " + self.tr("Refresh"),
                     command=_refresh,
                     kind="normal").pack(side=tk.RIGHT, padx=3)

        # ── treeview ─────────────────────────────────────────────────────────
        tree_frame = tk.Frame(self.content_frame, bg=T["bg"])
        tree_frame.pack(fill=tk.BOTH, expand=True, pady=4)

        cols = (self.tr("ID"), self.tr("Name"), self.tr("Incentive (%)"), self.tr("Type"))
        tree = ttk.Treeview(tree_frame, columns=cols, show="headings", height=9)
        col_w = {self.tr("ID"): 40, self.tr("Name"): 160, self.tr("Incentive (%)"): 100, self.tr("Type"): 120}
        for col in cols:
            tree.heading(col, text=col)
            tree.column(col, width=col_w[col], anchor=tk.CENTER)

        tree.tag_configure("odd",  background=T["tree_odd"],  foreground=T["tree_fg"])
        tree.tag_configure("even", background=T["tree_even"], foreground=T["tree_fg"])

        def _load_handlers():
            for item in tree.get_children():
                tree.delete(item)
            for i, h in enumerate(self.db.get_handlers()):
                tag = "even" if i % 2 == 0 else "odd"
                tree.insert("", tk.END,
                            values=(h[0], h[1], f"{h[2]:g}", self.tr("% Percent") if h[3] == "percentage" else self.tr("Fixed ₹")),
                            tags=(tag,))
        
        _load_handlers()
        
        sb = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Auto-focus the list for keypad navigation
        tree.focus_set()
        children = tree.get_children()
        if children:
            tree.selection_set(children[0])
            tree.focus(children[0])

        # ── wire buttons ─────────────────────────────────────────────────────
        def _get_selected():
            sel = tree.focus()
            if not sel:
                self._show_toast(self.tr("Please select a handler first"), kind="warning")
                return None
            return tree.item(sel, "values")
        
        edit_btn.config(command=lambda: self._handler_modify_dialog(_get_selected(), _refresh))
        del_btn.config(command=lambda: self._handler_delete(_get_selected(), _refresh))
        
        # double-click also opens modify
        tree.bind("<Double-1>", lambda e: self._handler_modify_dialog(_get_selected(), _refresh))

    # ---- Modify dialog -----------------------------------------------------
    def _handler_modify_dialog(self, row_values, reload_cb):
        if row_values is None: return
        hid = int(row_values[0])
        handler_data = None
        for h in self.db.get_handlers():
            if h[0] == hid:
                handler_data = h
                break
        
        if not handler_data:
            self._show_toast(self.tr("Handler not found"), kind="error"); return
            
        _, name, inc_pct, inc_type, is_active = handler_data

        T = self.T
        ov, body, close = self._open_overlay(self.tr("Modify Handler  —  ID {}").format(hid))
        tk.Label(body, text=self.tr("Modify Handler  —  ID {}").format(hid),
                 font=(config.BUTTON_FONT[0], 12, "bold"),
                 bg=T["bg"], fg=T["accent"]).pack(pady=(8, 4))
                 
        form_frame = tk.Frame(body, bg=T["bg"])
        form_frame.pack(padx=6, fill=tk.X)

        tk.Label(form_frame, text=self.tr("Name *:"), font=config.LABEL_FONT, bg=T["bg"], fg=T["text"]).grid(row=0, column=0, sticky=tk.W, pady=3, padx=6)
        name_e = tk.Entry(form_frame, font=config.LABEL_FONT, width=22, bg=T["entry_bg"], fg=T["entry_fg"], insertbackground=T["text"], relief=tk.FLAT, highlightthickness=1, highlightbackground=T["shadow_dark"])
        name_e.grid(row=0, column=1, pady=3, padx=6)
        name_e.insert(0, name)

        tk.Label(form_frame, text=self.tr("Incentive Type:"), font=config.LABEL_FONT, bg=T["bg"], fg=T["text"]).grid(row=1, column=0, sticky=tk.W, pady=3, padx=6)
        type_var = tk.StringVar(value=self.tr("% Percent") if inc_type == "percentage" else self.tr("Fixed ₹"))
        type_cb = ttk.Combobox(form_frame, textvariable=type_var, values=[self.tr("% Percent"), self.tr("Fixed ₹")], font=config.LABEL_FONT, width=20, state="readonly")
        type_cb.grid(row=1, column=1, pady=3, padx=6)

        inc_lbl = tk.Label(form_frame, text="", font=config.LABEL_FONT, bg=T["bg"], fg=T["text"])
        inc_lbl.grid(row=2, column=0, sticky=tk.W, pady=3, padx=6)
        
        inc_e = tk.Entry(form_frame, font=config.LABEL_FONT, width=22, bg=T["entry_bg"], fg=T["entry_fg"], insertbackground=T["text"], relief=tk.FLAT, highlightthickness=1, highlightbackground=T["shadow_dark"])
        inc_e.grid(row=2, column=1, pady=3, padx=6)
        inc_e.insert(0, f"{inc_pct:g}")
        
        def _update_lbl(*_):
            if type_var.get() == self.tr("% Percent"):
                inc_lbl.config(text=self.tr("Incentive (%):"))
            else:
                inc_lbl.config(text=self.tr("Incentive (Fixed ₹):"))
        type_var.trace_add("write", _update_lbl)
        _update_lbl()

        def _update():
            new_name = name_e.get().strip()
            if not new_name:
                self._show_toast(self.tr("Please enter a handler name"), kind="warning")
                return
                
            itype = "percentage" if type_var.get() == self.tr("% Percent") else "fixed"
            
            try:
                ipct = float(inc_e.get().strip())
                if itype == "percentage" and not (0 <= ipct <= 100):
                    self._show_toast(self.tr("Percentage must be 0–100"), kind="warning")
                    return
            except ValueError:
                self._show_toast(self.tr("Please enter a valid incentive value"), kind="warning")
                return
                
            success = self.db.update_handler(hid, new_name, ipct, itype)
            if success:
                self.handler_manager.load_active_handler()
                self.update_handler_status()
                self._show_toast(f"Handler #{hid} updated")
                close()
                reload_cb()
            else:
                self._show_toast(self.tr("Handler name already exists"), kind="error")

        bf = tk.Frame(body, bg=T["bg"])
        bf.pack(pady=8)
        self._neu_btn(bf, self.tr("Update"), command=_update, kind="equals", width=10, height=2).pack(side=tk.LEFT, padx=5)
        self._neu_btn(bf, self.tr("Cancel"), command=close, kind="mode", width=10, height=2).pack(side=tk.LEFT, padx=5)

    # ---- Delete ------------------------------------------------------------
    def _handler_delete(self, row_values, reload_cb):
        if row_values is None: return
        hid = int(row_values[0])
        name = row_values[1]
        def _do_delete():
            self.db.delete_handler(hid)
            self.handler_manager.load_active_handler()
            self.update_handler_status()
            reload_cb()
        self._show_confirm(self.tr("Delete handler '{}' (ID {})?").format(name, hid), _do_delete)

    def show_handler_performance(self):
        """Display handler performance graph"""
        self.clear_graph_frame()
        handler_data = self.handler_manager.get_handler_performance()
        fig = self.graph_generator.create_handler_performance_graph(handler_data)
        canvas = FigureCanvasTkAgg(fig, master=self.graph_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def _handler_set_active(self, row_values):
        """Set the selected handler as active and update UI."""
        if row_values is None:
            return
        
        hid = int(row_values[0])
        name = row_values[1]
        
        self.handler_manager.set_current_handler(hid)
        self.update_handler_status()
        self._show_toast(self.tr("Handler '{}' set as active").format(name))

    # ── Keypad Integration ─────────────────────────────────────────────────
    # Central dispatcher that converts keypad action strings into GUI actions.
    # KEY_MAP in keypad.py maps physical R{row}C{col} → action names.
    # To remap a key, change KEY_MAP — this dispatcher stays the same.

    def handle_keypad_action(self, action):
        """Route a keypad action string to the appropriate GUI method.
        Called from the Keypad's on_action callback in the main thread."""
        # Schedule on the Tk main thread to avoid cross-thread widget access
        self.root.after(0, self._dispatch_keypad_action, action)

    def _dispatch_keypad_action(self, action):
        """Internal dispatcher — runs on the Tk main loop thread."""

        # ── Back (navigate to previous screen) ──────────────────────
        if action == "back":
            self._keypad_back()
            return

        # First, gather focus context to make actions context-aware
        focused = None
        try:
            focused = self.root.focus_get()
        except BaseException:
            pass
            
        wtype = focused.winfo_class() if focused else ""

        # ── Clear / Backspace ───────────────────────────────────────
        if action == "all_clear":
            if wtype in ("Entry", "TCombobox"):
                focused.delete(0, tk.END)
            elif wtype == "Text":
                focused.delete("1.0", tk.END)
            elif self.current_mode == "calculator":
                self.calculator_button_click("C")
            return
            
        if action == "clear_last":
            if wtype in ("Entry", "TCombobox"):
                pos = focused.index(tk.INSERT)
                if pos > 0:
                    focused.delete(pos - 1, pos)
            elif wtype == "Text":
                focused.delete("insert-1c", tk.INSERT)
            elif self.current_mode == "calculator":
                self.calculator_button_click("CE")
            return

        # ── Digit keys & T9 Multi-tap Input ─────────────────────────
        if action.startswith("digit_"):
            d = action[6:]  # "digit_9" → "9", "digit_00" → "00"
            
            if wtype in ("Entry", "Text", "TCombobox"):
                import time
                now = time.time()
                
                t9_mode = getattr(focused, "t9_mode", "alphanum")
                
                t9_map = {
                    "1": ["1", "@"],
                    "2": ["a", "b", "c", "2"],
                    "3": ["d", "e", "f", "3"],
                    "4": ["g", "h", "i", "4"],
                    "5": ["j", "k", "l", "5"],
                    "6": ["m", "n", "o", "6"],
                    "7": ["p", "q", "r", "s", "7"],
                    "8": ["t", "u", "v", "8"],
                    "9": ["w", "x", "y", "z", "9"],
                    "0": [" ", "0"],
                    "00": ["00"]
                }
                
                if t9_mode == "num":
                    # Strictly numbers, no cycling
                    t9_map = {k: [k] for k in t9_map}
                elif t9_mode == "alpha":
                    # Remove numbers from the cycles
                    t9_map = {
                        "1": ["@"],
                        "2": ["a", "b", "c"],
                        "3": ["d", "e", "f"],
                        "4": ["g", "h", "i"],
                        "5": ["j", "k", "l"],
                        "6": ["m", "n", "o"],
                        "7": ["p", "q", "r", "s"],
                        "8": ["t", "u", "v"],
                        "9": ["w", "x", "y", "z"],
                        "0": [" "],
                        "00": [" "]
                    }
                
                chars = t9_map.get(d, [d])
                
                # Check for fast multi-tap or hold auto-repeat (< 1.2s delay)
                if self._t9_last_key == d and (now - self._t9_last_time) < 1.2 and len(chars) > 1:
                    self._t9_index = (self._t9_index + 1) % len(chars)
                    # Erase the last character we just inserted
                    if wtype in ("Entry", "TCombobox"):
                        pos = focused.index(tk.INSERT)
                        if pos > 0:
                            focused.delete(pos - 1, pos)
                    elif wtype == "Text":
                        focused.delete("insert-1c", tk.INSERT)
                else:
                    self._t9_index = 0
                    
                self._t9_last_key = d
                self._t9_last_time = now
                
                char_to_insert = chars[self._t9_index]
                
                if wtype in ("Entry", "TCombobox"):
                    focused.insert(tk.INSERT, char_to_insert)
                elif wtype == "Text":
                    focused.insert(tk.INSERT, char_to_insert)
                return

            if self.current_mode == "calculator":
                if d == "00":
                    self.calculator_button_click("0")
                    self.calculator_button_click("0")
                else:
                    self.calculator_button_click(d)
            return

        # ── Decimal ─────────────────────────────────────────────────
        if action == "decimal":
            if self.current_mode == "calculator":
                self.calculator_button_click(".")
            return

        # ── Arithmetic operators ────────────────────────────────────
        op_map = {
            "op_plus":  "+",
            "op_minus": "-",
            "op_mul":   "×",
            "op_div":   "÷",
        }
        if action in op_map:
            if self.current_mode == "calculator":
                self.calculator_button_click(op_map[action])
            return

        # ── Percent ─────────────────────────────────────────────────
        if action == "percent":
            if self.current_mode == "calculator":
                self.calculator_button_click("%")
            return

        # ── Equals (Enter) ──────────────────────────────────────────
        if action == "equals":
            self._keypad_navigate(action)
            return

        # ── Memory operations ───────────────────────────────────────
        if action == "mem_plus":
            if self.current_mode == "calculator":
                self.calculator_button_click("M+")
            return
        if action == "mem_minus":
            if self.current_mode == "calculator":
                self.calculator_button_click("M-")
            return
        if action == "mem_recall":
            if self.current_mode == "calculator":
                self.calculator_button_click("MR")
            return

        # ── TAX (stub — not yet implemented) ────────────────────────
        if action in ("tax_plus", "tax_minus"):
            self._show_toast("TAX feature coming soon", kind="info")
            return

        # ── Home (Calculator) ───────────────────────────────────────
        if action == "home_calculator":
            for child in self.root.winfo_children():
                if child.winfo_manager() == "place":
                    child.destroy()
            if getattr(self, '_app_launcher_open', False):
                self._app_launcher_open = False
                self.root.bind("<Escape>", lambda e: self._show_app_launcher())
            self.switch_mode("calculator")
            return

        # ── Menu (App Launcher) ─────────────────────────────────────
        if action == "menu":
            if getattr(self, '_app_launcher_open', False):
                # We need to simulate the escape close
                self.root.event_generate("<Escape>")
            else:
                self._show_app_launcher()
            return

        # ── Graph / Analytics ───────────────────────────────────────
        if action == "graph":
            if self.current_mode == "graphs":
                self.switch_mode("calculator")
            else:
                self.switch_mode("graphs")
            return

        # ── Sales key ───────────────────────────────────────────────
        if action == "sales":
            if self._transaction_dialog_open and self._active_save_sale_fn:
                self._active_save_sale_fn()
            else:
                self.switch_mode("sales")
            return

        # ── Expense key ─────────────────────────────────────────────
        if action == "expense":
            if self._transaction_dialog_open and self._active_save_expense_fn:
                self._active_save_expense_fn()
            else:
                self.switch_mode("expense")
            return

        # ── Due (Customers) key ─────────────────────────────────────
        if action == "due":
            if self.current_mode == "customers":
                self.switch_mode("calculator")
            else:
                self.switch_mode("customers")
            return

        # ── QR / Payment cycle ──────────────────────────────────────
        if action == "qr_cycle":
            self._keypad_cycle_payment()
            return

        # ── Direction keys (navigation) ─────────────────────────────
        if action in ("dir_up", "dir_down", "dir_left", "dir_right"):
            self._keypad_navigate(action)
            return

        # ── F1 programmable key ─────────────────────────────────────
        if action == "f1":
            self._keypad_f1_action()
            return

    # ── Payment method cycling ──────────────────────────────────────────
    def _keypad_cycle_payment(self):
        """Cycle payment method: Cash → UPI → Due → Cash …
        Works on the transaction dialog's payment combobox."""
        if not self._transaction_dialog_open or not self._active_payment_var:
            return

        methods = [self.tr(m) for m in config.PAYMENT_METHODS]
        if not methods:
            return

        current = self._active_payment_var.get()
        try:
            idx = methods.index(current)
            next_idx = (idx + 1) % len(methods)
        except ValueError:
            next_idx = 0

        self._active_payment_var.set(methods[next_idx])

        # Trigger the on_payment_change callback to update QR/icon
        if self._active_payment_change_fn:
            self._active_payment_change_fn()

    # ── Direction key navigation ────────────────────────────────────────
    def _keypad_navigate(self, action):
        """Smart navigation handling App Launcher Grid and focus traversal."""
        keysym_map = {
            "dir_up":    "Up",
            "dir_down":  "Down",
            "dir_left":  "Left",
            "dir_right": "Right",
        }
        keysym = keysym_map.get(action)
        if not keysym and action != "equals":
            return

        # 1. Special handling for App Launcher overlay (Grid Navigation)
        if getattr(self, '_app_launcher_open', False):
            if hasattr(self, '_launcher_cells') and getattr(self, '_launcher_focus_idx', -1) >= 0:
                idx = self._launcher_focus_idx
                cells = self._launcher_cells
                
                # Turn off current highlight
                curr_cell, curr_enter, curr_leave, curr_mode = cells[idx]
                curr_leave()
                
                if action == "dir_right":
                    idx = min(idx + 1, len(cells) - 1)
                elif action == "dir_left":
                    idx = max(idx - 1, 0)
                elif action == "dir_down":
                    idx = min(idx + 3, len(cells) - 1)
                elif action == "dir_up":
                    idx = max(idx - 3, 0)
                elif action == "equals":
                    # Let equals act as Enter here
                    if hasattr(self, '_show_app_launcher_launch'):
                        self._show_app_launcher_launch(curr_mode)
                    return
                
                # Turn on new highlight
                self._launcher_focus_idx = idx
                new_cell, new_enter, new_leave, new_mode = cells[idx]
                new_enter()
            return

        # 2. Global Navigation for Settings/Dialogs/Calculator
        try:
            focused = self.root.focus_get()
        except KeyError:
            # A ttk Combobox dropdown is currently open!
            try:
                cb = None
                if getattr(self, 'current_mode', '') == "calculator" and hasattr(self, '_product_bar_cb'):
                    cb = self._product_bar_cb
                if not cb:
                    cb = getattr(self, '_last_combobox', None)
                if cb:
                    pd = self.root.tk.call('ttk::combobox::PopdownWindow', cb)
                    lb = f"{pd}.f.l"
                    if action == 'dir_left':
                        self.root.tk.call('event', 'generate', lb, '<Escape>')
                    elif action == 'equals':
                        self.root.tk.call('event', 'generate', lb, '<Return>')
                    elif action in ('dir_right', 'dir_up', 'dir_down'):
                        if action == 'dir_right' and getattr(self, 'current_mode', '') == "calculator":
                            pass
                        else:
                            self.root.tk.call('event', 'generate', lb, f'<{keysym}>')
            except Exception:
                pass
            return

        if focused is None:
            focused = self.root

        # Check if any overlay is active
        has_overlay = False
        for child in self.root.winfo_children():
            # Overlays use place geometry manager directly on the root
            if child.winfo_exists() and child.winfo_manager() == 'place':
                has_overlay = True
                break

        # Top-level fallback for Graphs mode (e.g. initial focus is on Apps button)
        is_top_level = (focused == self.root or focused.master == getattr(self, 'top_frame', None))
        if is_top_level and not has_overlay:
            if getattr(self, 'current_mode', '') == "graphs" and hasattr(self, '_graphs_scrollable_frame'):
                if action in ("dir_right", "dir_down"):
                    children = self._graphs_scrollable_frame.winfo_children()
                    if children:
                        children[0].focus_set()
                        self._ensure_visible(children[0])
                        return
                        
        # Calculator mode specific overrides — product bar interactions are HOME ONLY
        if self.current_mode == "calculator" and not getattr(self, '_transaction_dialog_open', False) and not has_overlay:
            if action in ("dir_down", "dir_up"):
                if hasattr(self, '_product_bar_cb'):
                    cb = self._product_bar_cb
                    cb_open = False
                    try:
                        pd = self.root.tk.call('ttk::combobox::PopdownWindow', cb)
                        if self.root.tk.call('winfo', 'ismapped', pd):
                            cb_open = True
                            lb = f"{pd}.f.l"
                            self.root.tk.call('event', 'generate', lb, f'<{keysym}>')
                    except Exception:
                        pass
                    if not cb_open:
                        cb.focus_set()
                        cb.event_generate(f'<{keysym}>')
                return
            elif action == "dir_right":
                return
            elif action == "dir_left":
                # Left: collapse the product dropdown if open
                if hasattr(self, '_product_bar_cb'):
                    cb = self._product_bar_cb
                    try:
                        pd = self.root.tk.call('ttk::combobox::PopdownWindow', cb)
                        if self.root.tk.call('winfo', 'ismapped', pd):
                            lb = f"{pd}.f.l"
                            self.root.tk.call('event', 'generate', lb, '<Escape>')
                    except Exception:
                        pass
                self.root.focus_set()  # release focus in all left-key cases on calculator
                return
            elif action == "equals":
                cb_open = False
                if hasattr(self, '_product_bar_cb'):
                    cb = self._product_bar_cb
                    try:
                        pd = self.root.tk.call('ttk::combobox::PopdownWindow', cb)
                        # Ensure the listbox is actively mapped on screen
                        if self.root.tk.call('winfo', 'ismapped', pd):
                            cb_open = True
                            lb = f"{pd}.f.l"
                            self.root.tk.call('event', 'generate', lb, '<Return>')
                    except Exception:
                        pass
                
                if not cb_open:
                    self.calculator_button_click("=")
                return

        # If equals, inject Return / Activate
        if action == "equals":
            # For buttons, invoke them directly or generate Return
            wtype = focused.winfo_class()
            if wtype in ("Button", "TButton"):
                focused.invoke()
            else:
                focused.event_generate("<Return>")
            return
            
        # HISTORY MODE OVERRIDE (Tab Switching)
        if getattr(self, 'current_mode', '') == "history" and hasattr(self, '_history_notebook'):
            if action in ("dir_left", "dir_right") and focused:
                nb = self._history_notebook
                tabs = nb.tabs()
                if tabs:
                    curr_idx = tabs.index(nb.select())
                    nxt_idx = (curr_idx + 1) % len(tabs) if action == "dir_right" else (curr_idx - 1) % len(tabs)
                    nb.select(tabs[nxt_idx])
                return

        # ── SETTLE DUE OVERLAY OVERRIDE ─────────────────────────────────────────
        # Must be BEFORE Customers mode check (mode is still "customers" while overlay is open)
        if getattr(self, '_settle_due_open', False) and hasattr(self, '_settle_due_widgets'):
            widgets = [w for w in self._settle_due_widgets if w.winfo_exists()]
            if widgets:
                try:
                    curr_idx = widgets.index(focused)
                except ValueError:
                    widgets[0].focus_set()
                    return
                if action in ("dir_down", "dir_right"):
                    widgets[(curr_idx + 1) % len(widgets)].focus_set()
                    return
                elif action in ("dir_up", "dir_left"):
                    widgets[(curr_idx - 1) % len(widgets)].focus_set()
                    return
                elif action == "equals":
                    if focused.winfo_class() in ("Button", "TButton"):
                        focused.invoke()
                    return

        # ── DUE CUSTOMER DIALOG OVERRIDE ─────────────────────────────────────────
        # Must be BEFORE Customers mode check (mode is still "customers" while dialog is open)
        if getattr(self, '_due_customer_dialog_open', False):
            confirm_btn = getattr(self, '_due_customer_confirm_btn', None)
            cancel_btn  = getattr(self, '_due_customer_cancel_btn', None)
            tab_var     = getattr(self, '_due_customer_tab_var', None)
            is_existing = (tab_var is None or tab_var.get() == "existing")

            if is_existing:
                raw_entries = getattr(self, '_due_customer_entries_existing', [])
            else:
                raw_entries = getattr(self, '_due_customer_entries_new', [])
            entries = [w for w in raw_entries if w and w.winfo_exists()]
            btns    = [w for w in [confirm_btn, cancel_btn] if w and w.winfo_exists()]
            all_w   = entries + btns

            if not all_w:
                return

            in_all = focused in all_w

            if action in ("dir_left", "dir_right"):
                if focused in btns:
                    other = btns[(btns.index(focused) + 1) % len(btns)]
                    other.focus_set()
                else:
                    if hasattr(self, '_due_customer_toggle'):
                        self._due_customer_toggle()
                return

            if action == "dir_down" and in_all:
                all_w[(all_w.index(focused) + 1) % len(all_w)].focus_set()
                return
            elif action == "dir_up" and in_all:
                all_w[(all_w.index(focused) - 1) % len(all_w)].focus_set()
                return
            elif action == "dir_down":
                all_w[0].focus_set()
                return
            elif action == "equals" and focused in btns:
                focused.invoke()
                return

        # CUSTOMERS MODE OVERRIDE (only when no dialog is open)
        if getattr(self, 'current_mode', '') == "customers" and hasattr(self, '_customers_tree') \
                and not getattr(self, '_due_customer_dialog_open', False) \
                and not getattr(self, '_settle_due_open', False):

            tree = self._customers_tree
            edit_btn = getattr(self, '_customers_edit_btn', None)
            on_tree = (focused == tree)
            on_btn  = (focused == edit_btn)

            if action in ("dir_up", "dir_down") and (on_tree or not on_btn):
                # Navigate rows in tree
                if not on_tree:
                    tree.focus_set()
                else:
                    tree.event_generate(f"<{keysym}>")
                return

            if action in ("dir_left", "dir_right"):
                if on_tree and edit_btn:
                    edit_btn.focus_set()
                elif on_btn:
                    tree.focus_set()
                return

            if action == "equals":
                if on_tree:
                    item = tree.focus()
                    if item:
                        vals = tree.item(item, "values")
                        if vals and vals[0] != "-":
                            try:
                                cid, name, phone, due_str = vals
                                self.show_settle_due_dialog(cid, name, phone, float(due_str))
                            except Exception:
                                pass
                elif on_btn and edit_btn:
                    edit_btn.invoke()
                return


        # Smart Focus jumping for left/right/up/down

        wtype = focused.winfo_class()
        
        if wtype in ("Treeview", "Listbox"):
            if action in ("dir_up", "dir_down"):
                focused.event_generate(f"<{keysym}>")
                return
            elif action == "dir_right" or action == "equals":
                # Trigger internal binding for selection/double-click
                if action == "equals":
                    focused.event_generate("<Return>")
                return
        elif wtype == "TCombobox":
            if action == "dir_right":
                focused.event_generate("<Down>") # Open the list
                return
            elif action == "dir_left":
                self.root.focus_set() # Get out of the list
                return
        elif wtype in ("Checkbutton", "TCheckbutton"):
            if action == "dir_right":
                focused.invoke() # Toggle the checkbox
                return
                
        # GRAPHS MODE OVERRIDE (Wrap-around navigation)
        if getattr(self, 'current_mode', '') == "graphs" and hasattr(self, '_graphs_scrollable_frame'):
            if focused and focused.master == self._graphs_scrollable_frame:
                children = self._graphs_scrollable_frame.winfo_children()
                if children:
                    try:
                        idx = children.index(focused)
                        if action in ("dir_right", "dir_down"):
                            nxt_idx = (idx + 1) % len(children)
                            children[nxt_idx].focus_set()
                            self._ensure_visible(children[nxt_idx])
                            return
                        elif action in ("dir_left", "dir_up"):
                            prv_idx = (idx - 1) % len(children)
                            children[prv_idx].focus_set()
                            self._ensure_visible(children[prv_idx])
                            return
                    except ValueError:
                        pass

        def _get_interactive_focus(start, forward=True):
            curr = start
            for _ in range(50):
                curr = curr.tk_focusNext() if forward else curr.tk_focusPrev()
                if not curr or curr == start or curr == self.root:
                    return None
                wclass = curr.winfo_class()
                if wclass in ("Frame", "TFrame", "Label", "TLabel", "Canvas", "Scrollbar", "TScrollbar"):
                    continue
                try:
                    if curr.winfo_ismapped() and str(curr.cget("state")) != "disabled":
                        return curr
                except Exception:
                    # Some widgets don't have a state option, just return them if mapped
                    if curr.winfo_ismapped():
                        return curr
            return None

        # By default, use Tab traversal hierarchy for D-Pad
        if action in ("dir_right", "dir_down"):
            nxt = _get_interactive_focus(focused, True) or focused.tk_focusNext()
            if nxt:
                nxt.focus_set()
                self._ensure_visible(nxt)
        elif action in ("dir_left", "dir_up"):
            prv = _get_interactive_focus(focused, False) or focused.tk_focusPrev()
            if prv:
                prv.focus_set()
                self._ensure_visible(prv)

    def _ensure_visible(self, widget):
        """Scrolls the parent canvas to ensure the widget is visible on screen."""
        if not widget.winfo_ismapped():
            return
            
        parent = widget.master
        canvas = None
        while parent:
            if parent.winfo_class() == 'Canvas':
                canvas = parent
                break
            parent = parent.master
            
        if canvas:
            canvas.update_idletasks() # Ensure geometry bounds are up to date
            
            bbox = canvas.bbox("all")
            if not bbox:
                return
                
            # Vertical scrolling
            canvas_h = canvas.winfo_height()
            content_h = bbox[3] - bbox[1]
            if content_h > canvas_h:
                w_top = widget.winfo_rooty()
                w_bottom = w_top + widget.winfo_height()
                c_top = canvas.winfo_rooty()
                c_bottom = c_top + canvas_h
                
                y_view = canvas.yview()
                if w_top < c_top:
                    delta = c_top - w_top
                    fraction_change = delta / content_h
                    canvas.yview_moveto(max(0.0, y_view[0] - fraction_change - 0.05))
                elif w_bottom > c_bottom:
                    delta = w_bottom - c_bottom
                    fraction_change = delta / content_h
                    canvas.yview_moveto(min(1.0, y_view[0] + fraction_change + 0.05))

            # Horizontal scrolling
            canvas_w = canvas.winfo_width()
            content_w = bbox[2] - bbox[0]
            if content_w > canvas_w:
                w_left = widget.winfo_rootx()
                w_right = w_left + widget.winfo_width()
                c_left = canvas.winfo_rootx()
                c_right = c_left + canvas_w
                
                x_view = canvas.xview()
                if w_left < c_left:
                    delta = c_left - w_left
                    fraction_change = delta / content_w
                    canvas.xview_moveto(max(0.0, x_view[0] - fraction_change - 0.05))
                elif w_right > c_right:
                    delta = w_right - c_right
                    fraction_change = delta / content_w
                    canvas.xview_moveto(min(1.0, x_view[0] + fraction_change + 0.05))

    # ── F1 programmable key ─────────────────────────────────────────────
    def _keypad_f1_action(self):
        """Execute the user-configured F1 function key action."""
        settings = self._load_settings()
        f1_func = settings.get("f1_function", "none")

        if f1_func == "none":
            return

        # Valid mode names that can be switched to
        valid_modes = {
            "settings", "history", "graphs",
            "products", "handlers", "customers",
            "sales", "expense",
        }

        if f1_func in valid_modes:
            self.switch_mode(f1_func)

    # ── Back navigation ─────────────────────────────────────────────────
    def _keypad_back(self):
        """Smart Back navigation — mirrors a hardware Back button.

        Priority order:
          1. If there is an active overlay, close it directly via its tracked
             close function (avoids stale Escape re-bind loops). If it was the
             App Launcher, also switch to Home Calculator.
          2. If in any App (Sales, History, Settings, etc.), open the App Launcher.
          3. If already at Home Calculator, do nothing.
        """
        # 1. Find and close the topmost place-managed overlay directly
        active_overlay = None
        for child in reversed(self.root.winfo_children()):
            try:
                if child.winfo_exists() and child.winfo_manager() == 'place':
                    active_overlay = child
                    break
            except Exception:
                pass

        if active_overlay is not None:
            was_app_launcher = getattr(self, '_app_launcher_open', False)
            # Call tracked close fn directly — no Escape event generation
            close_fn = getattr(self, '_active_overlay_close', None)
            if close_fn:
                close_fn()
            else:
                # Fallback: destroy directly
                try:
                    active_overlay.destroy()
                except Exception:
                    pass
                self._active_overlay_close = None
            # After closing App Launcher, go to Home Calculator
            if was_app_launcher:
                self.switch_mode("calculator")
            return

        # 2. Inside an App → go to App Launcher
        if getattr(self, 'current_mode', 'calculator') != "calculator":
            self._show_app_launcher()
            return

        # 3. Already at Home Calculator — nothing to do
