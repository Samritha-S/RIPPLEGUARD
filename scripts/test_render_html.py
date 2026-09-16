import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

def clean_html(html_str: str) -> str:
    return "\n".join(line.strip() for line in html_str.strip().splitlines() if line.strip())

fix_card = """
                    <div style="background:rgba(0,0,0,0.25); border:1px solid #1a3c42; border-radius:6px; padding:10px 14px; margin-bottom:8px;">
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px; flex-wrap:wrap;">
                            <div>
                                <b style="color:#c8b6ff; font-size:0.95rem;">#2 Priority Fix: <code>mime-types</code></b>
                                <span style="color:#f4a261; font-weight:700; font-size:0.8rem; margin-left:8px;">[HIGH • 58.6/100]</span>
                            </div>
                            <div style="display:flex; align-items:center; gap:8px;">
                                <span style='background:rgba(233, 196, 106, 0.2); color:#e9c46a;'>🟡 Low-Medium Effort</span>
                                <span style='background:rgba(179, 136, 235, 0.15); color:#c8b6ff;'>⚡ ROI: 22.2</span>
                                <span style="color:#0a9396; font-weight:700; font-size:0.85rem; margin-left:4px;">
                                    83.3% Cumulative Risk (+4)
                                </span>
                            </div>
                        </div>
                        <div style="font-size:0.78rem; color:#9bb3b8; margin-top:2px; margin-bottom:4px;">
                            Action: <span style="color:#e0e7e9; font-weight:600;">Pin/upgrade version</span>
                        </div>
                        <div style="font-size:0.84rem; color:#e0e7e9; line-height:1.45;">
                            Fixing this package eliminates 4 downstream risk paths.
                        </div>
                    </div>
"""

cleaned = clean_html(fix_card)
lines = cleaned.splitlines()
print(f"Total lines: {len(lines)}")
for i, l in enumerate(lines):
    leading_spaces = len(l) - len(l.lstrip())
    print(f"Line {i} leading={leading_spaces}: {l[:40]}")
    assert leading_spaces == 0, f"Line {i} has leading spaces!"

print("All lines start with 0 leading spaces - zero chance of CommonMark code block!")
