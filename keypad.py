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

Usage:
  from keypad import Keypad

  kp = Keypad()
  kp.on_key_press(callback)   # callback receives the key name, e.g. "R1C1"
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

# Timing
DEBOUNCE_MS = 20        # milliseconds to wait after detecting a press
SCAN_INTERVAL_S = 0.01  # 10 ms between full scans (~100 Hz)


class Keypad:
    """Matrix keypad scanner for a 7-column × 5-row keypad."""

    def __init__(self, col_pins=None, row_pins=None):
        self.col_pins = col_pins or COL_PINS
        self.row_pins = row_pins or ROW_PINS
        self._callbacks = []
        self._running = False
        self._thread = None
        self._prev_keys = set()

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
        """Register a callback: callback(key_name: str) → None.
        Multiple callbacks can be registered."""
        self._callbacks.append(callback)

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
                for cb in self._callbacks:
                    try:
                        cb(key_name)
                    except Exception as e:
                        print(f"[Keypad] Callback error for {key_name}: {e}")

            time.sleep(SCAN_INTERVAL_S)

    def __del__(self):
        self.stop()


# ─── Standalone test ──────────────────────────────────────────────────
if __name__ == "__main__":
    print("=== DigiCal 7×5 Matrix Keypad Test ===")
    print("Press keys on the keypad. Ctrl+C to exit.\n")

    kp = Keypad()

    def on_press(key):
        print(f"  Key pressed: {key}")

    kp.on_key_press(on_press)
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
