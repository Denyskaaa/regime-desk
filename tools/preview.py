"""Inline docs/ (HTML, CSS, JS, data) into one self-contained preview file."""
import json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, "docs")
out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "preview.html")
html = open(os.path.join(D, "index.html")).read()
css = open(os.path.join(D, "style.css")).read()
js = open(os.path.join(D, "app.js")).read()
data = {n: json.load(open(os.path.join(D, "data", f"{n}.json"))) for n in ["meta", "market", "macro", "regime"]}
html = html.replace('<link rel="stylesheet" href="style.css">', f"<style>{css}</style>")
html = html.replace('<script src="app.js"></script>',
                    f"<script>window.__RD_DATA__={json.dumps(data, separators=(',', ':'))};</script><script>{js}</script>")
open(out, "w").write(html)
print(out, len(html) // 1024, "KB")
