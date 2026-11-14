#!/usr/bin/env python3
"""Write docs/guide.html from scripts/guide.md.

The guide's text and its code live in one markdown file so that the code can be
compiled by ``scripts/check_snippets.py`` — a page whose examples do not compile
is a page that lies. This script only dresses them: the porcelain plates, the
two columns, the panels for code and for what it prints.

    python scripts/gen_guide.py            rewrite docs/guide.html
    python scripts/gen_guide.py --check    exit 1 when the page is stale
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from docsgen import render  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "scripts" / "guide.md"
PAGE = ROOT / "docs" / "guide.html"


def version() -> str:
    text = (ROOT / "moon.mod").read_text(encoding="utf-8")
    return re.search(r'^version = "(.*)"', text, re.M).group(1)


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def inline(text: str) -> str:
    return render.inline(text)


def blocks(text: str) -> list[dict]:
    """Parse the little markdown the guide is written in."""
    lines = text.splitlines()
    out: list[dict] = []
    i = 0
    while i < len(lines):
        raw = lines[i]
        line = raw.rstrip()
        if not line.strip():
            i += 1
            continue
        if line.startswith("# "):
            out.append({"t": "title", "text": line[2:].strip()})
        elif line.startswith("> "):
            # A lede may run over several lines; they are one paragraph.
            lede = [line[2:].strip()]
            i += 1
            while i < len(lines) and lines[i].startswith("> "):
                lede.append(lines[i][2:].strip())
                i += 1
            out.append({"t": "lede", "text": " ".join(lede)})
            continue
        elif line.startswith("## "):
            head = line[3:].strip()
            note = ""
            if "|" in head:
                head, note = (x.strip() for x in head.split("|", 1))
            number, title = head.split(" ", 1) if head[:2].isdigit() else ("", head)
            out.append({"t": "sec", "no": number, "title": title, "note": note})
        elif line.startswith("### "):
            out.append({"t": "h3", "text": line[4:].strip()})
        elif line.startswith("!! "):
            out.append({"t": "pin", "text": line[3:].strip()})
        elif line.startswith("- "):
            items = []
            while i < len(lines) and lines[i].startswith("- "):
                items.append(lines[i][2:].strip())
                i += 1
            out.append({"t": "ul", "items": items})
            continue
        elif line.startswith("```"):
            kind = line[3:].strip() or "mbt"
            i += 1
            code: list[str] = []
            while i < len(lines) and not lines[i].startswith("```"):
                code.append(lines[i])
                i += 1
            out.append({"t": "code" if kind in ("mbt", "moonbit") else "out", "code": "\n".join(code)})
        else:
            para = [line.strip()]
            i += 1
            while i < len(lines) and lines[i].strip() and not re.match(r"^(#|##|###|!!|- |```)", lines[i]):
                para.append(lines[i].strip())
                i += 1
            out.append({"t": "p", "text": " ".join(para)})
            continue
        i += 1
    return out


def render_guide(parsed: list[dict]) -> str:
    title = next((b["text"] for b in parsed if b["t"] == "title"), "Guide")
    lede = next((b["text"] for b in parsed if b["t"] == "lede"), "")
    sections: list[tuple[dict, list[dict]]] = []
    for block in parsed:
        if block["t"] == "sec":
            sections.append((block, []))
        elif sections:
            sections[-1][1].append(block)

    def left(items: list[dict]) -> str:
        out: list[str] = []
        for item in items:
            if item["t"] == "h3":
                out.append(f'        <div class="step"><h3>{inline(item["text"])}</h3></div>')
            elif item["t"] == "ul":
                rows = "\n".join(f"          <li>{inline(x)}</li>" for x in item["items"])
                out.append(f'        <ul class="step">\n{rows}\n        </ul>')
            elif item["t"] == "pin":
                out.append(f'        <p class="pin">{inline(item["text"])}</p>')
            elif item["t"] == "p":
                out.append(f'        <p class="prose">{inline(item["text"])}</p>')
        return "\n".join(out)

    def right(items: list[dict]) -> str:
        out: list[str] = []
        after_code = False
        for item in items:
            if item["t"] == "code":
                out.append(render.code_block(item["code"], "guide__code"))
                after_code = True
            elif item["t"] == "out":
                tag = '<span class="out__tag">what it prints</span>' if after_code else ""
                out.append(f'        <div class="out">{tag}{render.esc(item["code"])}</div>')
                after_code = False
        return "\n".join(out)

    parts = []
    for head, items in sections:
        anchor = slug(head["title"])
        lcol, rcol = left(items), right(items)
        note = f'<p class="sec__note">{inline(head["note"])}</p>' if head["note"] else ""
        if rcol.strip():
            body = f"""<div class="two">
      <div class="guide__col">
{lcol}
      </div>
      <div class="guide__col">
{rcol}
      </div>
    </div>"""
        else:
            body = f"""<div class="guide__single">
{lcol}
    </div>"""
        parts.append(
            f"""<section class="sec" id="{anchor}">
  <div class="sheet">
    <div class="sec__head">
      <div class="sec__plate">
        <span class="sec__no">{head["no"]}</span>
        <h2 class="sec__title">{inline(head["title"])}</h2>
      </div>
      {note}
    </div>
    {body}
  </div>
</section>"""
        )

    jumps = " · ".join(
        f'<a href="#{slug(head["title"])}">{head["no"]} {head["title"]}</a>'
        for head, _ in sections
    )
    body = f"""<header class="dochead">
  <div class="sheet">
    <p class="dochead__eyebrow mono">moonbitstack / moonseed · guide</p>
    <h1 class="dochead__title">{render.esc(title)}</h1>
    <p class="dochead__lede">{inline(lede)}</p>
    <p class="dochead__jump">{jumps} · <a href="api.html">the reference</a></p>
  </div>
</header>

{chr(10).join(parts)}"""
    return render.page(
        title="moonseed — the guide",
        description="From an empty package to a key, a range and a scalar: the whole library, "
        "step by step.",
        body=body,
        current="guide",
        version=version(),
    )


def main() -> int:
    fresh = render_guide(blocks(SOURCE.read_text(encoding="utf-8")))
    if "--check" in sys.argv:
        if not PAGE.exists() or PAGE.read_text(encoding="utf-8") != fresh:
            print("docs/guide.html is stale: run python scripts/gen_guide.py", file=sys.stderr)
            return 1
        print("docs/guide.html is current")
        return 0
    with open(PAGE, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(fresh)
    print("wrote docs/guide.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
