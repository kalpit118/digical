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
import config
import locales
from calculator import Calculator
from database import Database
from transaction_manager import TransactionManager
from history_manager import HistoryManager
from graph_generator import GraphGenerator
from handler_manager import HandlerManager

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
        self.tr = locales.get_translator(self.language)
        self.T: dict = config.get_theme(self.dark_mode)
        self._apply_ttk_styles()
        self.root.configure(bg=self.T["bg"])

        # Current mode
        self.current_mode = "calculator"
        self.current_graph_info = None # (func_name, args, kwargs)

        # Create UI
        self.create_widgets()
        self.switch_mode("calculator")

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
        with open(self._SETTINGS_FILE, "w") as f:
            json.dump(existing, f, indent=2)

    # ── Theme helpers ──────────────────────────────────────────────────────────
    def _apply_ttk_styles(self):
        """Configure ttk widget styles for the active neumorphic palette."""
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
                  fieldbackground=[("readonly", T["entry_bg"])],
                  foreground=[("readonly", T["entry_fg"])])
        style.configure("Treeview",         background=T["tree_even"],
                        fieldbackground=T["tree_even"], foreground=T["tree_fg"],
                        rowheight=20, font=config.LABEL_FONT)
        style.configure("Treeview.Heading", background=T["hdr_bg"],
                        foreground=T["accent"],
                        font=(config.LABEL_FONT[0], config.LABEL_FONT[1], "bold"))
        style.map("Treeview",
                  background=[("selected", T["accent"])],
                  foreground=[("selected", "#FFFFFF")])
        style.configure("Vertical.TScrollbar",
                        background=T["shadow_dark"], troughcolor=T["display_bg"],
                        borderwidth=0, relief="flat", width=10, arrowsize=0)
        style.map("Vertical.TScrollbar",
                  background=[("active", T["accent"]), ("pressed", T["accent"]),
                              ("!disabled", T["shadow_dark"])],
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
            highlightcolor=T["shadow_lite"],
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
            from PIL import Image, ImageTk
            import os
            base_dir = os.path.dirname(__file__)
            _app_img_path = os.path.join(base_dir, "assets", "apps.png")
            _raw_img = Image.open(_app_img_path).resize((18, 18), Image.Resampling.LANCZOS)
            self._apps_icon = ImageTk.PhotoImage(_raw_img)
            self._icon_success = ImageTk.PhotoImage(Image.open(os.path.join(base_dir, "assets", "right.png")).resize((14, 14), Image.Resampling.LANCZOS))
            self._icon_error = ImageTk.PhotoImage(Image.open(os.path.join(base_dir, "assets", "wrong.png")).resize((14, 14), Image.Resampling.LANCZOS))
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
        title_label = tk.Label(
            self.top_frame, text=self.tr("DigiCal"),
            font=(config.BUTTON_FONT[0], 16, "bold"),
            bg=T["hdr_bg"], fg=T["accent"]
        )
        title_label.place(relx=0.49, rely=0.45, anchor=tk.CENTER)

        # Right: handler dropdown
        handler_frame = tk.Frame(self.top_frame, bg=T["hdr_bg"])
        handler_frame.pack(side=tk.RIGHT, padx=2)
        tk.Label(handler_frame, text="H:",
                 font=(config.LABEL_FONT[0], 10, "bold"), bg=T["hdr_bg"], fg=T["subtext"]).pack(side=tk.LEFT, padx=2)
        self.handler_var = tk.StringVar()
        self.handler_dropdown = ttk.Combobox(handler_frame, textvariable=self.handler_var, 
                                            state="readonly", width=12, font=config.LABEL_FONT)
        self.handler_dropdown.pack(side=tk.RIGHT)
        
        self.update_handler_dropdown()
        self.handler_dropdown.bind('<<ComboboxSelected>>', self.on_handler_selected)
        self.update_handler_dropdown()

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

        self.live_display = tk.Label(
            self.display_frame, text="",
            font=("Consolas", 20, "bold"),
            bg=T["display_bg"], fg=T["subtext"],
            anchor=tk.E, padx=12, pady=0
        )
        self.live_display.pack(side=tk.BOTTOM, fill=tk.X)

        # Content area

        self.content_frame = tk.Frame(self.root, bg=T["bg"])
        self.content_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=3)

    def clear_content_frame(self):
        """Clear the content frame"""
        for widget in self.content_frame.winfo_children():
            widget.destroy()
    
    def switch_mode(self, mode):
        """Switch between different modes"""
        self.current_mode = mode
        self.clear_content_frame()

        if mode == "calculator":
            self.product_bar_frame.pack(fill=tk.X, padx=2, before=self.outer_display_frame)
            # Make the display box fill the whole remaining window
            self.outer_display_frame.pack(fill=tk.BOTH, expand=True, padx=6, pady=(4, 0))
            self.display_frame.pack_propagate(True)   # allow expansion
            self.display_frame.config(height=0)
            self.display.config(font=("Consolas", 36, "bold"), anchor=tk.E, pady=10)
            self.live_display.config(font=("Consolas", 24, "bold"), pady=6)
            self.content_frame.pack_forget()          # hide; receipt is inside display_frame
        else:
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
            # Restore live_display packing
            self.live_display.pack_forget()
            self.live_display.pack(side=tk.BOTTOM, fill=tk.X)
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

        # Bind keyboard
        self.root.bind('<Key>', self.on_key_press)

        # Reset line products if not set
        if not hasattr(self, '_line_products'):
            self._line_products = {}


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
    
    def on_key_press(self, event):
        """Handle keyboard input"""
        if self.current_mode != "calculator":
            return
        
        key = event.char
        if key in '0123456789.%':
            self.calculator_button_click(key)
        elif key in '+-':
            self.calculator_button_click(key)
        elif key == '*':
            self.calculator_button_click('×')
        elif key == '/':
            self.calculator_button_click('÷')
        elif key in ['\r', '\n', '=']:
            self.calculator_button_click('=')
        elif event.keysym == 'BackSpace':
            self.calculator_button_click('CE')
        # ESC on calculator mode is handled by the root binding (opens app launcher)
        # so we intentionally do NOT handle Escape here
    
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
        
        calc_tree.heading(self.tr("Date"), text=self.tr("Date"))
        calc_tree.column(self.tr("Date"), width=150, anchor=tk.W)
        calc_tree.heading(self.tr("Calculation"), text=self.tr("Calculation"))
        calc_tree.column(self.tr("Calculation"), width=250, anchor=tk.W)
        calc_tree.heading(self.tr("Result"), text=self.tr("Result"))
        calc_tree.column(self.tr("Result"), width=150, anchor=tk.W)
        
        calc_tree.tag_configure("odd", background=T.get("tree_odd", "#34495E"), foreground=T.get("tree_fg", "white"))
        calc_tree.tag_configure("even", background=T.get("tree_even", "#2C3E50"), foreground=T.get("tree_fg", "white"))
        
        calc_sb = ttk.Scrollbar(calc_frame, orient=tk.VERTICAL, command=calc_tree.yview)
        calc_tree.configure(yscrollcommand=calc_sb.set)
        calc_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5,0), pady=5)
        calc_sb.pack(side=tk.RIGHT, fill=tk.Y, padx=(0,5), pady=5)
        
        for i, (expr, result, timestamp) in enumerate(self.history_manager.get_calculation_history()):
            tag = "even" if i % 2 == 0 else "odd"
            calc_tree.insert("", tk.END, values=(timestamp, expr, result), tags=(tag,))

        trans_frame = tk.Frame(notebook, bg=T["bg"])
        notebook.add(trans_frame, text=self.tr("Transactions"))
        
        trans_cols = (self.tr("Date"), self.tr("Type"), self.tr("Amount (₹)"), self.tr("Category"), self.tr("Method"), self.tr("Handler"))
        trans_tree = ttk.Treeview(trans_frame, columns=trans_cols, show="headings", height=15)
        
        col_widths = {self.tr("Date"): 150, self.tr("Type"): 70, self.tr("Amount (₹)"): 100, self.tr("Category"): 180, self.tr("Method"): 90, self.tr("Handler"): 120}
        for col in trans_cols:
            trans_tree.heading(col, text=col)
            trans_tree.column(col, width=col_widths[col], anchor=tk.W)
            
        trans_tree.tag_configure("odd", background=T.get("tree_odd", "#34495E"), foreground=T.get("tree_fg", "white"))
        trans_tree.tag_configure("even", background=T.get("tree_even", "#2C3E50"), foreground=T.get("tree_fg", "white"))
        trans_tree.tag_configure("sales", foreground="#2ECC71") # override colors with tags? No, let's keep it simple.
        
        trans_sb = ttk.Scrollbar(trans_frame, orient=tk.VERTICAL, command=trans_tree.yview)
        trans_tree.configure(yscrollcommand=trans_sb.set)
        trans_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5,0), pady=5)
        trans_sb.pack(side=tk.RIGHT, fill=tk.Y, padx=(0,5), pady=5)
        
        for i, trans in enumerate(self.history_manager.get_transaction_history()):
            t_type = self.tr("Sales") if trans[1] == "sales" else self.tr("Expense")
            amount = f"{trans[2]:.2f}"
            category = trans[3]
            date = trans[5] if len(trans) > 5 else "-"
            payment_method = trans[7] if len(trans) > 7 and trans[7] else "Cash"
            handler_name = trans[9] if len(trans) > 9 and trans[9] else "-"
            tag = "even" if i % 2 == 0 else "odd"
            trans_tree.insert("", tk.END, values=(date, t_type, amount, category, payment_method, handler_name), tags=(tag,))


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
        def _on_mousewheel(event):
            canvas.xview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        self.graph_frame = tk.Frame(self.content_frame, bg=T["bg"])
        self.graph_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Bind resize event for responsive graphs
        self.graph_frame.bind("<Configure>", self._on_graph_resize)

        # Show default graph
        self.show_weekly_graph()


    def clear_graph_frame(self):
        """Clear graph display"""
        for widget in self.graph_frame.winfo_children():
            widget.destroy()
    
    def show_weekly_graph(self):
        """Display weekly graph"""
        self.current_graph_info = ('create_weekly_graph', (), {})
        
        w = self.graph_frame.winfo_width()
        h = self.graph_frame.winfo_height()
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
        def _on_mousewheel(e):
            canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

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
        if not self.current_graph_info:
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
        if w > 1 and h > 1:
            self.refresh_current_graph(w, h)
        else:
            self.clear_graph_frame()
            fig = self.graph_generator.create_handler_performance_graph(handler_data)
            canvas = FigureCanvasTkAgg(fig, master=self.graph_frame)
            canvas.draw()
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
    
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

        def _close():
            ov.destroy()
            if self.current_mode == "settings":
                self.switch_mode("calculator")
            elif self.current_mode == "calculator":
                self.root.bind("<Escape>", lambda e: self._show_app_launcher())
            else:
                self.root.bind("<Escape>", lambda e: self.switch_mode("calculator"))

        tk.Button(hdr, text="\u2190 Back",
                  font=(config.LABEL_FONT[0], config.LABEL_FONT[1], "bold"),
                  bg=T["hdr_bg"], fg=T["subtext"],
                  relief=tk.FLAT, bd=0, cursor="hand2",
                  activebackground=T["shadow_dark"],
                  command=_close).pack(side=tk.LEFT, padx=6)
        tk.Label(hdr, text=title,
                 font=(config.BUTTON_FONT[0], 9, "bold"),
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
                 font=(config.BUTTON_FONT[0], 9, "bold"),
                 bg=T["hdr_bg"], fg=T["accent"]).pack(side=tk.LEFT, padx=8)

        def _close(event=None):
            ov.destroy()
            self.root.bind("<Escape>", lambda e: self._show_app_launcher())

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
                    img = Image.open(p).resize((80, 80), Image.Resampling.LANCZOS)
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

            def _enter(e, f=cell, c=c_frame):
                f.config(bg=T["bg_dark"])
                c.config(bg=T["bg_dark"])
                for child in c.winfo_children():
                    child.config(bg=T["bg_dark"])

            def _leave(e, f=cell, c=c_frame):
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
        def _on_mousewheel(e):
            canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        def _cleanup_bindings():
            try:
                canvas.unbind_all("<MouseWheel>")
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
                     font=(config.BUTTON_FONT[0], 10, "bold"),
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
        status_lbl = tk.Label(scroll_frame, text="", font=(config.LABEL_FONT[0], 8),
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

        dark_row = tk.Frame(c1, bg=T["bg"])
        dark_row.pack(fill=tk.X, pady=2)
        tk.Label(dark_row, text=self.tr("Dark Mode"),
                 font=config.LABEL_FONT, bg=T["bg"], fg=T["text"]).pack(side=tk.LEFT)
        dark_var = tk.BooleanVar(value=self.dark_mode)
        icon_text = "   " + self.tr("OFF") if not self.dark_mode else "   " + self.tr("ON")
        tk.Checkbutton(
            dark_row, text=icon_text, variable=dark_var,
            font=(config.BUTTON_FONT[0], 9),
            bg=T["bg"], fg=T["accent"],
            selectcolor=T["bg_dark"],
            activebackground=T["bg"], activeforeground=T["accent"],
            relief=tk.FLAT, bd=0,
            command=lambda: self._toggle_dark_mode(dark_var.get())
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
            s.connect(('10.255.255.255', 1))
            local_ip = s.getsockname()[0]
            s.close()
        except:
            local_ip = '127.0.0.1'
            
        tk.Label(portal_info, text=self.tr("Access from this Device:"), font=(config.LABEL_FONT[0], 9), bg=T["bg"], fg=T["subtext"]).pack(anchor=tk.W)
        tk.Label(portal_info, text=f"http://localhost:{config.WEB_PORT}", font=(config.LABEL_FONT[0], 11, "bold"), bg=T["bg"], fg=T["accent"]).pack(anchor=tk.W, pady=(0, 4))
        
        tk.Label(portal_info, text=self.tr("Access from Phone/Laptop (Same WiFi):"), font=(config.LABEL_FONT[0], 9), bg=T["bg"], fg=T["subtext"]).pack(anchor=tk.W)
        tk.Label(portal_info, text=f"http://{local_ip}:{config.WEB_PORT}", font=(config.LABEL_FONT[0], 11, "bold"), bg=T["bg"], fg=T["accent"]).pack(anchor=tk.W)

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 6) ABOUT
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        c6 = card(scroll_frame, "", self.tr("About DigiCal"))
        tk.Label(c6, text=f"{config.APP_NAME}  v{config.VERSION}",
                 font=(config.BUTTON_FONT[0], 9, "bold"),
                 bg=T["bg"], fg=T["accent"]).pack(anchor=tk.W)

        # ── Close button ───────────────────────────────────────────────────
        tk.Frame(scroll_frame, bg=T["bg"], height=6).pack()
        self._neu_btn(scroll_frame, self.tr("Close"), command=close,
                     kind="mode", width=10, height=2).pack(pady=(0, 10))





    def _show_success_overlay(self, label=None):
        """Full-window animated success screen. Auto-dismisses after 5 s."""
        if label is None:
            label = self.tr("Transaction saved!")
        T = self.T
        ov = tk.Frame(self.root, bg=T["bg"])
        ov.place(x=0, y=0, relwidth=1, relheight=1)
        ov.lift()

        # ── animated GIF ───────────────────────────────────────────────────
        try:
            from PIL import Image, ImageTk
            import os
            
            gif_path = os.path.join(os.path.dirname(__file__), "assets", "checkmark.gif")
            if not os.path.exists(gif_path):
                raise FileNotFoundError

            # Scale GIF to ~50% of the window's current height, preserve ratio
            win_h = self.root.winfo_height() or 480
            target = int(win_h * 0.50)

            # Cache the frames to prevent 1-2s UI freeze
            if not hasattr(self, '_success_gif_cache'):
                self._success_gif_cache = {}

            if target in self._success_gif_cache:
                frames = self._success_gif_cache[target]
            else:
                raw = Image.open(gif_path)
                raw_w, raw_h = raw.size
                scale = target / raw_h if raw_h else 1
                new_w, new_h = max(1, int(raw_w * scale)), max(1, target)
                
                # Check for an existing cache and clear it to save memory if size changed
                self._success_gif_cache.clear()
                
                frames = []
                try:
                    while True:
                        f = raw.copy().convert("RGBA").resize((new_w, new_h), Image.LANCZOS)
                        frames.append(ImageTk.PhotoImage(f))
                        raw.seek(raw.tell() + 1)
                except EOFError:
                    pass
                self._success_gif_cache[target] = frames

            gif_label = tk.Label(ov, bg=T["bg"])
            gif_label.pack(pady=(20, 8))

            def _animate(idx=0):
                if not ov.winfo_exists():
                    return
                gif_label.config(image=frames[idx % len(frames)])
                ov.after(50, _animate, idx + 1)

            _animate()
        except Exception:
            # Fallback: big unicode tick
            tk.Label(ov, text="\u2714", font=("Arial", 72), bg=T["bg"],
                     fg=T["success"]).pack(pady=(60, 8))

        tk.Label(ov, text=label, font=("Arial", 18, "bold"),
                 bg=T["bg"], fg=T["success"], wraplength=self.root.winfo_width() - 40).pack(pady=8)
        tk.Label(ov, text=self.tr("Tap anywhere to continue"),
                 font=("Arial", 12), bg=T["bg"], fg=T["subtext"]).pack(pady=4)

        def _dismiss(event=None):
            self.root.unbind("<Escape>")
            ov.destroy()

        ov.bind("<Button-1>", _dismiss)
        self.root.bind("<Escape>", _dismiss)
        # Auto-dismiss after 5s
        ov.after(5000, _dismiss)

    def show_transaction_dialog(self, amount):
        """Full-window overlay to categorize a calculation as a transaction."""
        try:
            amount_val = float(amount)
        except Exception:
            return

        ov, body, close = self._open_overlay(self.tr("Save as Transaction"))
        T = self.T

        # ── Two-column grid ─────────────────────────────────────
        # col 0 = info / controls   col 1 = QR (right side)
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=0)
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
                img = qr.make_image(fill_color="black", back_color="white").resize((320, 320))
                photo = ImageTk.PhotoImage(img)
                _qr_ref[0] = photo
                tk.Label(qr_frame, image=photo, bg="white",
                         relief=tk.FLAT, bd=3).pack(pady=(8, 4))
                tk.Label(qr_frame, text=self.tr("{} via UPI").format(f"₹{amount_val:.2f}"),
                         font=("Arial", 18, "bold"), bg=T["bg"],
                         fg=T["success"]).pack()
                tk.Label(qr_frame, text=vpa,
                         font=("Arial", 16), bg=T["bg"],
                         fg=T["subtext"]).pack()
            except Exception as ex:
                tk.Label(qr_frame, text=self.tr("QR error:\n{}").format(ex),
                         font=("Arial", 12), bg=T["bg"],
                         fg=T["danger"], wraplength=120, justify=tk.CENTER).pack()

        def _build_cash_icon():
            for w in qr_frame.winfo_children():
                w.destroy()
            try:
                from PIL import Image, ImageTk
                import os
                cash_path = os.path.join(os.path.dirname(__file__), "assets", "cash.png")
                raw = Image.open(cash_path)
                
                # Resize proportionally to fit a similar 320x320 box as the QR code
                raw_w, raw_h = raw.size
                scale = min(320 / raw_w, 320 / raw_h) if raw_w and raw_h else 1
                new_size = (max(1, int(raw_w * scale)), max(1, int(raw_h * scale)))
                
                img = raw.resize(new_size, Image.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                _qr_ref[0] = photo
                
                tk.Label(qr_frame, image=photo, bg=T["bg"],
                         relief=tk.FLAT).pack(pady=(8, 4))
                tk.Label(qr_frame, text=self.tr("{} in Cash").format(f"₹{amount_val:.2f}"),
                         font=("Arial", 18, "bold"), bg=T["bg"],
                         fg=T["success"]).pack()
            except Exception as ex:
                tk.Label(qr_frame, text=self.tr("Cash icon error:\n{}").format(ex),
                         font=("Arial", 12), bg=T["bg"],
                         fg=T["danger"], wraplength=120, justify=tk.CENTER).pack()

        def on_payment_change(event=None):
            pm = payment_var.get()
            if pm == self.tr("Due"):
                qr_frame.grid_remove()
                self.show_due_customer_dialog(lambda cid: due_customer.__setitem__(0, cid))
            elif pm == self.tr("UPI"):
                due_customer[0] = None
                _build_qr()
                qr_frame.grid(row=0, column=1, rowspan=5, sticky=tk.NE, padx=(4, 10), pady=6)
            elif pm == self.tr("Cash"):
                due_customer[0] = None
                _build_cash_icon()
                qr_frame.grid(row=0, column=1, rowspan=5, sticky=tk.NE, padx=(4, 10), pady=6)
            else:
                due_customer[0] = None
                qr_frame.grid_remove()

        combo.bind("<<ComboboxSelected>>", on_payment_change)
        
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

        # Buttons  (left col)
        bf = tk.Frame(body, bg=T["bg"])
        bf.grid(row=3, column=0, sticky=tk.W, padx=6, pady=24)
        self._neu_btn(bf, self.tr("Sale"), command=save_as_sale, kind="equals", width=14, height=3).pack(side=tk.LEFT, padx=5)
        self._neu_btn(bf, self.tr("Expense"), command=save_as_expense, kind="danger", width=14, height=3).pack(side=tk.LEFT, padx=5)
        self._neu_btn(bf, "✕", command=close, kind="mode", width=6, height=3).pack(side=tk.LEFT, padx=5)


    def update_handler_dropdown(self):
        """Update handler dropdown with current handlers"""
        handlers = self.handler_manager.get_handler_list()
        handler_names = [h[1] for h in handlers]
        self.handler_dropdown['values'] = handler_names
        
        # Set current handler
        current_handler = self.handler_manager.get_current_handler()
        if current_handler:
            self.handler_var.set(current_handler['name'])
        elif handler_names:
            self.handler_var.set(handler_names[0])
    
    # ── Product quick-pick bar helpers ────────────────────────────────────
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
    
    def on_handler_selected(self, event=None):
        """Handle handler selection from dropdown"""
        selected_name = self.handler_var.get()
        
        handlers = self.handler_manager.get_handler_list()
        for h in handlers:
            if h[1] == selected_name:
                self.handler_manager.set_current_handler(h[0])
                break
        self.root.focus_set()
    
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
                self._show_toast(self.tr("Handler '{}' created  ({} incentive)").format(name, lbl))
                self.update_handler_dropdown()
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

    def show_due_customer_dialog(self, on_confirm):
        """Full-window overlay to link a Due payment to an existing or new customer."""
        T = self.T
        ov, body, close = self._open_overlay(self.tr("Due Payment — Customer"))

        tk.Label(body, text=self.tr("Due Payment"), font=("Arial", 13, "bold"),
                 bg=T["bg"], fg=T["text"]).pack(pady=(8, 4))

        # Tab switcher
        tab_var = tk.StringVar(value="existing")
        tab_frame = tk.Frame(body, bg=T["bg"])
        tab_frame.pack(fill=tk.X)

        existing_tab_btn = tk.Button(tab_frame, text=self.tr("Existing Customer"),
                                     font=("Arial", 16, "bold"), bg=T["success"], fg="#FFFFFF",
                                     relief=tk.SUNKEN, bd=2)
        new_tab_btn = tk.Button(tab_frame, text=self.tr("New Customer"),
                                font=("Arial", 16, "bold"), bg=T["mode_bg"], fg=T["mode_fg"],
                                relief=tk.RAISED, bd=2)
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
        existing_id_entry.grid(row=0, column=1, pady=12, padx=16, sticky=tk.EW)
        
        tk.Label(existing_panel, text=self.tr("  OR  "), font=("Arial", 16, "bold"),
                 bg=T["bg"], fg=T["subtext"]).grid(row=1, column=0, columnspan=2, pady=8)
                 
        tk.Label(existing_panel, text=self.tr("Phone Number:"), font=("Arial", 16),
                 bg=T["bg"], fg=T["text"]).grid(row=2, column=0, sticky=tk.W, pady=12)
        existing_phone_var = tk.StringVar()
        existing_phone_entry = tk.Entry(existing_panel, textvariable=existing_phone_var, font=("Arial", 22), width=24,
                                        bg=T["entry_bg"], fg=T["entry_fg"], insertbackground=T["text"])
        existing_phone_entry.grid(row=2, column=1, pady=12, padx=16, sticky=tk.EW)
        
        found_label = tk.Label(existing_panel, text="", font=("Arial", 14, "bold"),
                               bg=T["bg"], fg=T["success"], wraplength=400, compound=tk.LEFT, padx=5)
        found_label.grid(row=3, column=0, columnspan=2, pady=12)

        try:
            from PIL import Image, ImageTk
            base_dir = os.path.dirname(__file__)
            r_path = os.path.join(base_dir, "assets", "right.png")
            w_path = os.path.join(base_dir, "assets", "wrong.png")
            found_label.right_img = ImageTk.PhotoImage(Image.open(r_path).resize((20, 20), Image.Resampling.LANCZOS))
            found_label.wrong_img = ImageTk.PhotoImage(Image.open(w_path).resize((20, 20), Image.Resampling.LANCZOS))
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
        new_name_entry.grid(row=1, column=1, pady=12, padx=16, sticky=tk.EW)
        
        tk.Label(new_panel, text=self.tr("Phone *:"), font=("Arial", 16),
                 bg=T["bg"], fg=T["text"]).grid(row=2, column=0, sticky=tk.W, pady=12)
        phone_var = tk.StringVar()
        vcmd = (new_panel.register(lambda v: (v.isdigit() and len(v) <= 10) or v == ""), '%P')
        new_phone_entry = tk.Entry(new_panel, textvariable=phone_var, font=("Arial", 22),
                                   width=24, validate="key", validatecommand=vcmd,
                                   bg=T["entry_bg"], fg=T["entry_fg"], insertbackground=T["text"])
        new_phone_entry.grid(row=2, column=1, pady=12, padx=16, sticky=tk.EW)
        
        tk.Label(new_panel, text=self.tr("Email:"), font=("Arial", 16),
                 bg=T["bg"], fg=T["text"]).grid(row=3, column=0, sticky=tk.W, pady=12)
        new_email_entry = tk.Entry(new_panel, font=("Arial", 22), width=24,
                                   bg=T["entry_bg"], fg=T["entry_fg"], insertbackground=T["text"])
        new_email_entry.grid(row=3, column=1, pady=12, padx=16, sticky=tk.EW)
        
        new_panel.columnconfigure(1, weight=1)

        def show_existing():
            new_panel.pack_forget(); existing_panel.pack(fill=tk.BOTH, expand=True)
            existing_tab_btn.config(bg=T["success"], fg="#FFFFFF", relief=tk.SUNKEN)
            new_tab_btn.config(bg=T["mode_bg"], fg=T["mode_fg"], relief=tk.RAISED); tab_var.set("existing")

        def show_new():
            existing_panel.pack_forget(); new_panel.pack(fill=tk.BOTH, expand=True)
            new_tab_btn.config(bg=T["success"], fg="#FFFFFF", relief=tk.SUNKEN)
            existing_tab_btn.config(bg=T["mode_bg"], fg=T["mode_fg"], relief=tk.RAISED); tab_var.set("new")

        existing_tab_btn.config(command=show_existing)
        new_tab_btn.config(command=show_new)
        show_existing()

        def confirm():
            if tab_var.get() == "existing":
                if not found_customer[0]:
                    self._show_toast(self.tr("Please find a customer first"), kind="error"); return
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
                on_confirm(cid); close()

        btn_row = tk.Frame(body, bg=T["bg"])
        btn_row.pack(pady=16)
        self._neu_btn(btn_row, self.tr("Confirm"), command=confirm, kind="equals",
                      width=14, height=2).pack(side=tk.LEFT, padx=10)
        self._neu_btn(btn_row, self.tr("Cancel"), command=close, kind="mode",
                      width=14, height=2).pack(side=tk.LEFT, padx=10)

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
        self._neu_btn(br, self.tr("Confirm"), command=confirm_settle, kind="equals",
                      width=10, height=2).pack(side=tk.LEFT, padx=6)
        self._neu_btn(br, self.tr("Cancel"), command=close, kind="mode",
                      width=10, height=2).pack(side=tk.LEFT, padx=6)

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

        self._neu_btn(ctrl, self.tr("+ Add Handler"), command=lambda: self.show_create_handler_dialog(on_close=_refresh),
                     kind="equals").pack(side=tk.LEFT, padx=3)

        edit_btn = self._neu_btn(ctrl, "\u270e " + self.tr("Modify Handler"), kind="mode")
        edit_btn.pack(side=tk.LEFT, padx=3)

        del_btn = self._neu_btn(ctrl, "\u2715 " + self.tr("Delete Handler"), kind="danger")
        del_btn.pack(side=tk.LEFT, padx=3)

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
                self.update_handler_dropdown()
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
            self.update_handler_dropdown()
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
