import re
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

with open("app.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

print(f"Total lines in app.py: {len(lines)}")
print("--- ALL MULTILINE / HTML st.markdown CALLS ---")

i = 0
while i < len(lines):
    line = lines[i]
    if "st.markdown(" in line:
        start_line = i + 1
        block = [line]
        # Check if multiline
        if '"""' in line or "'''" in line or "(" in line and not ")" in line:
            j = i + 1
            while j < len(lines) and not (")" in lines[j] and ("unsafe_allow_html" in lines[j] or lines[j].strip().startswith(")"))):
                block.append(lines[j])
                j += 1
            if j < len(lines):
                block.append(lines[j])
            i = j
        full_text = "".join(block)
        if '"""' in full_text or "'''" in full_text or "<div" in full_text:
            # Check indentation of lines inside
            has_indented_html = False
            for bline in block[1:-1]:
                stripped = bline.strip()
                leading = len(bline) - len(bline.lstrip())
                if stripped.startswith("<") and leading >= 4:
                    has_indented_html = True
                    break
            print(f"\n[Line {start_line}] has_indented_html={has_indented_html}")
            first_few = [b.strip() for b in block if b.strip()][:3]
            print("  Preview:", " | ".join(first_few))
    i += 1
