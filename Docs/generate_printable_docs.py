#!/usr/bin/env python3
"""Converts every Docs/*.md file into a printable PDF in Docs/PrintableDocs/.

Requires: pip install markdown xhtml2pdf
Run from anywhere: python Docs/generate_printable_docs.py
Re-run any time the .md files change to regenerate the PDFs.
"""
import os

import markdown
from xhtml2pdf import pisa

DOCS_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(DOCS_DIR, "PrintableDocs")

PAGE_CSS = """
@page {
    size: A4;
    margin: 2cm;
}
body {
    font-family: Helvetica, Arial, sans-serif;
    font-size: 10pt;
    line-height: 1.45;
    color: #1a1a1a;
}
h1, h2, h3, h4 {
    font-family: Helvetica, Arial, sans-serif;
    color: #372976;
    -pdf-keep-with-next: true;
}
h1 { font-size: 20pt; margin-top: 0; border-bottom: 2pt solid #372976; padding-bottom: 6pt; }
h2 { font-size: 15pt; margin-top: 18pt; border-bottom: 0.5pt solid #ccc; padding-bottom: 3pt; }
h3 { font-size: 12.5pt; margin-top: 14pt; }
h4 { font-size: 11pt; margin-top: 12pt; }
p, li { font-size: 10pt; }
code {
    font-family: Courier, monospace;
    background-color: #f2f0f7;
    color: #372976;
    padding: 1pt 3pt;
}
pre {
    font-family: Courier, monospace;
    font-size: 8.5pt;
    background-color: #f5f3ee;
    border: 0.5pt solid #ddd;
    padding: 8pt;
    -pdf-keep-with-next: false;
}
pre code {
    background-color: transparent;
    color: #1a1a1a;
    padding: 0;
}
table {
    border-collapse: collapse;
    width: 100%;
    margin: 8pt 0;
    font-size: 9pt;
}
th {
    background-color: #372976;
    color: white;
    padding: 4pt 6pt;
    text-align: left;
    border: 0.5pt solid #372976;
}
td {
    padding: 4pt 6pt;
    border: 0.5pt solid #ccc;
}
a { color: #372976; }
hr { border: none; border-top: 0.5pt solid #ccc; margin: 12pt 0; }
"""

HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>{css}</style>
</head>
<body>
{body}
</body>
</html>"""


def convert_one(md_path: str, out_path: str):
    with open(md_path, "r", encoding="utf-8") as f:
        text = f.read()

    body_html = markdown.markdown(
        text, extensions=["extra", "sane_lists", "toc"]
    )
    full_html = HTML_TEMPLATE.format(css=PAGE_CSS, body=body_html)

    with open(out_path, "wb") as out_file:
        result = pisa.CreatePDF(full_html, dest=out_file)
    if result.err:
        raise RuntimeError(f"Failed to convert {md_path} ({result.err} errors)")


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    md_files = sorted(f for f in os.listdir(DOCS_DIR) if f.endswith(".md"))
    for name in md_files:
        md_path = os.path.join(DOCS_DIR, name)
        out_path = os.path.join(OUTPUT_DIR, name[:-3] + ".pdf")
        convert_one(md_path, out_path)
        print(f"  {name} -> PrintableDocs/{os.path.basename(out_path)}")
    print(f"Done: {len(md_files)} PDF(s) written to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
