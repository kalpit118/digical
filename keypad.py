"""
Keypad Driver for DigiCal — 7×5 Matrix Keypad on Raspberry Pi Zero 2W
Scans a 7-column × 5-row matrix and returns key names like R1C1 … R5C7.

Pin wiring (active-low with internal pull-ups):
  COLUMNS (outputs, directly driven LOW one at a time to scan):
    C1 = GPIO 17   (Physical pin 11)
    C2 = GPIO 27   (Physical pin 13)
    C3 = GPIO 22   (Physical pin 15)
    C4 = GPIO 23   (Physical pin 16)
    C5 = GPIO  5   (Physical pin 29)
    C6 = GPIO  6   (Physical pin 31)
    C7 = GPIO 13   (Physical pin 33)

  ROWS (inputs with internal pull-up resistors):
    R1 = GPIO 16   (Physical pin 36)
    R2 = GPIO 19   (Physical pin 35)
    R3 = GPIO 20   (Physical pin 38)
    R4 = GPIO 21   (Physical pin 40)
    R5 = GPIO 26   (Physical pin 37)

Avoided GPIOs (used by 3.5″ SPI display):
  GPIO 8  — LCD chip select (CE0)
  GPIO 10 — SPI MOSI
  GPIO 11 — SPI clock (SCK)
  GPIO 24 — LCD data/cmd (RS)
  GPIO 25 — LCD reset (RST)

How it works:
  Each column is driven LOW one at a time while all others are HIGH.
  The row pins are read — a LOW on a row means that key is pressed.
  Built-in pull-ups on the row pins keep them HIGH when no key is pressed.
  De-bounce is handled with a short settle delay + confirmation re-read.

Key Mapping (7 columns × 5 rows):
  Row 1: R1C1=Right  R1C2=Down   R1C3=Left  R1C4=M-/TAX-  R1C5=M+/TAX+  R1C6=MR  R1C7=SHIFT
  Row 2: R2C1=Graph  R2C2=%      R2C3=÷     R2C4=9        R2C5=8        R2C6=7   R2C7=MENU
  Row 3: R3C1=QR     R3C2=−      R3C3=×     R3C4=6        R3C5=5        R3C6=4   R3C7=AC
  Row 4: R4C1=F1     R4C2=SALES  R4C3=+     R4C4=3        R4C5=2        R4C6=1   R4C7=C
  Row 5: R5C1=Up     R5C2=DUE    R5C3=EXP   R5C4==        R5C5=.        R5C6=00  R5C7=0

Usage:
  from keypad import Keypad

  kp = Keypad()
  kp.on_key_press(callback)   # callback receives the key name, e.g. "R1C1"
  kp.on_action(callback)      # callback receives action name, e.g. "digit_9"
  kp.start()                  # starts scanning in a daemon thread
  # ...
  kp.stop()                   # stops the scanning thread
"""

import time
import threading

try:
    import RPi.GPIO as GPIO
    _HAS_GPIO = True
except ImportError:
    _HAS_GPIO = False

# ─── Pin Configuration ───────────────────────────────────────────────

# BCM pin numbers for columns (directly driven outputs)
COL_PINS = [17, 27, 22, 23, 5, 6, 13]

# BCM pin numbers for rows (inputs with pull-ups)
ROW_PINS = [16, 19, 20, 21, 26]

# Generated key names: R<row>C<col> (1-indexed)
KEY_NAMES = [
    [f"R{r}C{c}" for c in range(1, len(COL_PINS) + 1)]
    for r in range(1, len(ROW_PINS) + 1)
]

# ─── Key-to-Action Mapping ───────────────────────────────────────────
# Maps physical key name (R{row}C{col}) → logical action name.
# To remap a key, change only the value in this dict.

KEY_MAP = {
    # Row 1: Direction keys, Memory, SHIFT
    "R1C1": "dir_right",
    "R1C2": "dir_down",
    "R1C3": "dir_left",
    "R1C4": "mem_minus",
    "R1C5": "mem_plus",
    "R1C6": "mem_recall",
    "R1C7": "shift",

    # Row 2: Graph, %, ÷, 9, 8, 7, MENU
    "R2C1": "graph",
    "R2C2": "percent",
    "R2C3": "op_div",
    "R2C4": "digit_9",
    "R2C5": "digit_8",
    "R2C6": "digit_7",
    "R2C7": "menu",

    # Row 3: QR (payment cycle), −, ×, 6, 5, 4, AC
    "R3C1": "qr_cycle",
    "R3C2": "op_minus",
    "R3C3": "op_mul",
    "R3C4": "digit_6",
    "R3C5": "digit_5",
    "R3C6": "digit_4",
    "R3C7": "all_clear",

    # Row 4: F1, SALES, +, 3, 2, 1, C (backspace)
    "R4C1": "f1",
    "R4C2": "sales",
    "R4C3": "op_plus",
    "R4C4": "digit_3",
    "R4C5": "digit_2",
    "R4C6": "digit_1",
    "R4C7": "clear_last",

    # Row 5: Up, DUE, EXPENSE, =, ., 00, 0
    "R5C1": "dir_up",
    "R5C2": "due",
    "R5C3": "expense",
    "R5C4": "equals",
    "R5C5": "decimal",
    "R5C6": "digit_00",
    "R5C7": "digit_0",
}

# SHIFT + key overrides (only keys that have a secondary function)
SHIFT_MAP = {
    "R1C4": "tax_minus",   # SHIFT + M- = TAX-
    "R1C5": "tax_plus",    # SHIFT + M+ = TAX+
}

# Timing
DEBOUNCE_MS = 20        # milliseconds to wait after detecting a press
SCAN_INTERVAL_S = 0.01  # 10 ms between full scans (~100 Hz)


class Keypad:
    """Matrix keypad scanner for a 7-column × 5-row keypad."""

    def __init__(self, col_pins=None, row_pins=None):
        self.col_pins = col_pins or COL_PINS
        self.row_pins = row_pins or ROW_PINS
        self._callbacks = []
        self._action_callbacks = []
        self._running = False
        self._thread = None
        self._prev_keys = set()
        self._shift_active = False

        if not _HAS_GPIO:
            print("[Keypad] RPi.GPIO not available — running in stub mode.")
            return

        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)

        # Set up column pins as outputs, initially HIGH
        for pin in self.col_pins:
            GPIO.setup(pin, GPIO.OUT, initial=GPIO.HIGH)

        # Set up row pins as inputs with internal pull-ups
        for pin in self.row_pins:
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

    # ── Public API ────────────────────────────────────────────────────

    def on_key_press(self, callback):
        """Register a raw key callback: callback(key_name: str) → None.
        key_name is the physical name like "R1C1", "R3C7", etc.
        Multiple callbacks can be registered."""
        self._callbacks.append(callback)

    def on_action(self, callback):
        """Register an action callback: callback(action: str) → None.
        action is the logical name like "digit_9", "op_plus", "menu", etc.
        SHIFT state is automatically handled — shifted keys fire their
        SHIFT_MAP action instead of their normal action.
        Multiple callbacks can be registered."""
        self._action_callbacks.append(callback)

    def start(self):
        """Start the scanning loop in a background daemon thread."""
        if not _HAS_GPIO:
            print("[Keypad] Cannot start — no GPIO available.")
            return
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._scan_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop the scanning loop and clean up GPIO."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None
        if _HAS_GPIO:
            # Reset column pins to inputs to avoid driving anything
            for pin in self.col_pins:
                GPIO.setup(pin, GPIO.IN)

    def scan_once(self):
        """Perform a single scan and return a set of pressed key names."""
        if not _HAS_GPIO:
            return set()

        pressed = set()
        for ci, col_pin in enumerate(self.col_pins):
            # Drive this column LOW
            GPIO.output(col_pin, GPIO.LOW)
            # Brief settle time for signal propagation
            time.sleep(0.0005)

            for ri, row_pin in enumerate(self.row_pins):
                if GPIO.input(row_pin) == GPIO.LOW:
                    pressed.add(KEY_NAMES[ri][ci])

            # Release column back to HIGH
            GPIO.output(col_pin, GPIO.HIGH)

        return pressed

    # ── Internal ──────────────────────────────────────────────────────

    def _resolve_action(self, key_name):
        """Resolve a physical key name to its logical action,
        taking SHIFT state into account."""
        if key_name == "R1C7":
            # SHIFT key itself — toggle shift and don't fire an action
            self._shift_active = True
            return None

        if self._shift_active:
            self._shift_active = False
            # Check shifted mapping first, fall back to normal
            action = SHIFT_MAP.get(key_name, KEY_MAP.get(key_name))
        else:
            action = KEY_MAP.get(key_name)

        return action

    def _scan_loop(self):
        """Continuous scanning loop with debounce."""
        while self._running:
            current_keys = self.scan_once()

            # Debounce: if we detected something, wait and confirm
            if current_keys:
                time.sleep(DEBOUNCE_MS / 1000.0)
                confirmed = self.scan_once()
                current_keys = current_keys & confirmed  # only keep stable presses

            # Detect newly pressed keys (not held from last scan)
            new_presses = current_keys - self._prev_keys
            self._prev_keys = current_keys

            # Fire callbacks for each new press
            for key_name in sorted(new_presses):
                # Raw key name callbacks
                for cb in self._callbacks:
                    try:
                        cb(key_name)
                    except Exception as e:
                        print(f"[Keypad] Raw callback error for {key_name}: {e}")

                # Action callbacks (with SHIFT resolution)
                action = self._resolve_action(key_name)
                if action:
                    for cb in self._action_callbacks:
                        try:
                            cb(action)
                        except Exception as e:
                            print(f"[Keypad] Action callback error for {key_name}→{action}: {e}")

            time.sleep(SCAN_INTERVAL_S)

    def __del__(self):
        self.stop()


# ─── Standalone test ──────────────────────────────────────────────────
if __name__ == "__main__":
    print("=== DigiCal 7×5 Matrix Keypad Test ===")
    print("Press keys on the keypad. Ctrl+C to exit.\n")

    print("Key Map:")
    for key, action in sorted(KEY_MAP.items()):
        shift_action = SHIFT_MAP.get(key, "")
        shift_str = f"  (SHIFT → {shift_action})" if shift_action else ""
        print(f"  {key} → {action}{shift_str}")
    print()

    kp = Keypad()

    def on_press(key):
        print(f"  [RAW]    Key pressed: {key}")

    def on_action(action):
        print(f"  [ACTION] → {action}")

    kp.on_key_press(on_press)
    kp.on_action(on_action)
    kp.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping keypad scanner...")
        kp.stop()
        if _HAS_GPIO:
            GPIO.cleanup()
        print("Done.")
