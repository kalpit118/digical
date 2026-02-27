"""Replace all messagebox calls with _show_toast / _show_confirm in gui.py"""
import re

with open("gui.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

code = "".join(lines)

# Simple 1-for-1 replacements of messagebox.showinfo → self._show_toast
# messagebox.showerror → self._show_toast(..., kind="error")
# messagebox.showwarning → self._show_toast(..., kind="warning")

# Pattern: messagebox.showinfo("Title", "message") → self._show_toast("message")
# Handle multiline and f-strings

replacements = [
    # showinfo with f-string
    (r'messagebox\.showinfo\(\s*"[^"]*"\s*,\s*(f"[^"]*")\s*\)', r'self._show_toast(\1)'),
    (r"messagebox\.showinfo\(\s*'[^']*'\s*,\s*(f'[^']*')\s*\)", r'self._show_toast(\1)'),
    # showinfo with plain string
    (r'messagebox\.showinfo\(\s*"[^"]*"\s*,\s*("(?:[^"\\]|\\.)*")\s*\)', r'self._show_toast(\1)'),
    # showerror with f-string
    (r'messagebox\.showerror\(\s*"[^"]*"\s*,\s*(f"[^"]*")\s*\)', r'self._show_toast(\1, kind="error")'),
    # showerror with plain string
    (r'messagebox\.showerror\(\s*"[^"]*"\s*,\s*("(?:[^"\\]|\\.)*")\s*\)', r'self._show_toast(\1, kind="error")'),
    # showerror with str(ex)
    (r'messagebox\.showerror\(\s*"[^"]*"\s*,\s*str\((\w+)\)\s*\)', r'self._show_toast(str(\1), kind="error")'),
    # showwarning
    (r'messagebox\.showwarning\(\s*"[^"]*"\s*,\s*("(?:[^"\\]|\\.)*")\s*\)', r'self._show_toast(\1, kind="warning")'),
]

for pattern, repl in replacements:
    code = re.sub(pattern, repl, code)

with open("gui.py", "w", encoding="utf-8") as f:
    f.write(code)

# Count remaining
remaining = len(re.findall(r'messagebox\.', code))
print(f"Done. Remaining messagebox references: {remaining}")
# Show remaining lines
for i, line in enumerate(code.split('\n'), 1):
    if 'messagebox.' in line:
        print(f"  L{i}: {line.strip()[:80]}")
