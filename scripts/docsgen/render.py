"""The chrome every page shares, and the two text tricks they all need.

A page is written here as one string: the head, the rail, whatever the page has
to say, the foot. Keeping the chrome in one place is what makes the nav, the
favicon and the licence identical on every page; the glaze itself is a
stylesheet both the hand-written and the generated pages link.
"""

from __future__ import annotations

import html
import re

NAV = [
    ("home", "index.html"),
    ("guide", "guide.html"),
    ("api", "api.html"),
    ("demo", "sampling.html"),
    ("github", "https://github.com/moonbitstack/moonseed"),
]

# A tile with a crack in it: the same figure the home page draws at full size,
# small enough to read at sixteen pixels. Single quotes inside, and xmlns, so it
# works both as a link icon and as an image.
FAVICON = (
    "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E"
    "%3Crect width='32' height='32' fill='%23A9C9BB'/%3E"
    "%3Cpath d='M3 11.5 L12.5 15 L10.5 27' fill='none' stroke='%2323477F' stroke-width='1.3'/%3E"
    "%3Cpath d='M12.5 15 L28 9.5' fill='none' stroke='%2323477F' stroke-width='1.3'/%3E"
    "%3Cpath d='M12.5 15 L21.5 22.5' fill='none' stroke='%2323477F' stroke-width='1.3'/%3E"
    "%3Crect x='24' y='23' width='6' height='6' fill='%23AC382A'/%3E"
    "%3C/svg%3E"
)

KEYWORDS = {
    "as", "async", "break", "catch", "continue", "else", "enum", "extern",
    "false", "fn", "for", "guard", "if", "impl", "in", "is", "let", "match",
    "mut", "noraise", "open", "priv", "pub", "raise", "return", "self", "struct",
    "suberror", "test", "trait", "true", "try", "type", "typealias", "while",
    "with",
}
TOKEN = re.compile(
    r'(?P<comment>//[^\n]*)'
    r'|(?P<string>b"(?:[^"\\]|\\.)*"|"(?:[^"\\]|\\.)*")'
    r'|(?P<word>[A-Za-z_][A-Za-z0-9_]*)'
    r'|(?P<other>.)',
    re.S,
)


def esc(text: str) -> str:
    return html.escape(text, quote=False)


def attr(text: str) -> str:
    return html.escape(text, quote=True)


def inline(text: str) -> str:
    """`code`, **bold** and [text](url) in the prose of a doc comment."""
    out: list[str] = []
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "`":
            end = text.find("`", i + 1)
            if end > i:
                out.append(f"<code>{esc(text[i + 1 : end])}</code>")
                i = end + 1
                continue
        if text.startswith("**", i):
            end = text.find("**", i + 2)
            if end > i:
                out.append(f"<b>{esc(text[i + 2 : end])}</b>")
                i = end + 2
                continue
        m = re.match(r"\[([^\]]+)\]\(([^)]+)\)", text[i:])
        if m:
            out.append(
                f'<a href="{attr(m.group(2))}">{esc(m.group(1))}</a>'
            )
            i += m.end()
            continue
        out.append(esc(ch))
        i += 1
    return "".join(out)


def highlight(code: str) -> str:
    """MoonBit, coloured with the three inks the page already uses."""
    out: list[str] = []
    for m in TOKEN.finditer(code):
        kind = m.lastgroup
        text = m.group(0)
        if kind == "comment":
            out.append(f'<span class="c">{esc(text)}</span>')
        elif kind == "string":
            out.append(f'<span class="s">{esc(text)}</span>')
        elif kind == "word" and text in KEYWORDS:
            out.append(f'<span class="k">{esc(text)}</span>')
        else:
            out.append(esc(text))
    return "".join(out)


def code_block(code: str, extra: str = "") -> str:
    return f'<pre class="code{(" " + extra) if extra else ""}">{highlight(code)}</pre>'


def page(*, title: str, description: str, body: str, current: str, version: str) -> str:
    nav = []
    for name, href in NAV:
        here = ' aria-current="page"' if name == current else ""
        if href.startswith("http"):
            nav.append(
                f'<a href="{href}"{here} rel="noopener">{name}'
                f'<span class="rail__out" aria-hidden="true">↗</span></a>'
            )
        else:
            nav.append(f'<a href="{href}"{here}>{name}</a>')
    rail = "\n".join(f"      {a}" for a in nav)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="description" content="{attr(description)}">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="icon" href="{FAVICON}">
<link rel="stylesheet" href="assets/glaze.css">
<link rel="stylesheet" href="assets/docs.css">
<title>{esc(title)}</title>
</head>
<body data-page="{current}">

<div class="rail">
  <div class="rail__in">
    <div class="rail__brand">
      <b>moonseed</b><span class="mono"><span id="rev-head">{version}</span> &nbsp;·&nbsp; Apache-2.0</span>
    </div>
    <nav class="rail__nav">
{rail}
    </nav>
  </div>
</div>

{body}

<footer class="foot">
  <div class="sheet foot__in">
    <div><span class="mono">rev</span><b id="rev-value">{version}</b></div>
    <div><span class="mono">licence</span><b>Apache-2.0</b></div>
    <div><span class="mono">pages</span><b><a href="index.html">home</a> · <a href="guide.html">guide</a> · <a href="api.html">api</a> · <a href="sampling.html">demo</a></b></div>
    <div class="foot__next"><span>the other layer · a seedable stream</span><span><a href="https://moonbitstack.github.io/moonrand/">moonrand · ChaCha12</a></span></div>
  </div>
</footer>

</body>
</html>
"""
