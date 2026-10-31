#!/usr/bin/env python3
"""Render the API table in docs/index.html from the generated interfaces.

Every public item in ``src/**/pkg.generated.mbti`` must appear on the page: the
script refuses to write when an item has no row, and refuses to leave a row
behind for an item the library no longer has. Signature text and prose live
below; the item list comes from the compiler's own output.

    python scripts/gen_api.py            rewrite docs/index.html
    python scripts/gen_api.py --check    exit 1 when the page is stale
"""

from __future__ import annotations

import html
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "docs" / "index.html"
BEGIN = "<!-- api:begin -->"
END = "<!-- api:end -->"

# --------------------------------------------------------------------------
# The rows, in the order the page shows them. `key` names the interface item
# the row documents, spelled as the .mbti file spells it.
# --------------------------------------------------------------------------
ROWS = [
    {
        "pkg": "moonbitstack/moonseed",
        "kind": "fn",
        "key": "bytes",
        "sig": ["pub fn[S : Source] bytes(n : Int32, source : S) -> Bytes raise Unavailable"],
        "zh": "均匀字节 n 枚，不多不少。n 为负乃调用之误，故直接 abort，不假装给了空串。",
        "en": "N uniform bytes, no more and no fewer. A negative n is a caller's mistake, so it aborts rather than pretend to hand back nothing.",
    },
    {
        "pkg": "moonbitstack/moonseed",
        "kind": "fn",
        "key": "below",
        "sig": ["pub fn[S : Source] below(bound : BytesView, source : S) -> Bytes raise Unavailable"],
        "zh": "[0, bound) 之内，宽同 bound。掩码舍去高位，越界即重抽；bound 为 1 不取字节，为 0 则 abort。",
        "en": "[0, bound), as wide as the bound. Mask the unused high bits, redraw while at or above bound. A bound of 1 reads nothing; zero aborts.",
    },
    {
        "pkg": "moonbitstack/moonseed",
        "kind": "fn",
        "key": "scalar",
        "sig": ["pub fn[S : Source] scalar(order : BytesView, source : S) -> Bytes raise Unavailable"],
        "zh": "[1, order)，宽同 order。取左起之位，遇零或越界则重抽，即 FIPS 186-5 A.2.2 之法。",
        "en": "[1, order), as wide as the order. Keep the leftmost bits, redraw on zero or overflow: the FIPS 186-5 A.2.2 draw.",
    },
    {
        "pkg": "moonbitstack/moonseed",
        "kind": "trait",
        "key": "Source",
        "sig": [
            "pub(open) trait Source {",
            "  fn fill(self, buf : FixedArray[Byte]) -> Unit raise Unavailable",
            "}",
        ],
        "zh": "全库唯一须自具者。填满缓冲，不成则 raise；他物实现此约，即可接入，不必改本库一行。",
        "en": "The one thing you implement. Fill the buffer or raise; anything that keeps this contract plugs in without a line changed here.",
    },
    {
        "pkg": "moonbitstack/moonseed",
        "kind": "type",
        "key": "Replay",
        "sig": ["pub struct Replay", "Replay::new(data : Bytes) -> Self"],
        "zh": "依次发尽而止之源。由字节构造，不碰平台，故测试向量得以此回放。",
        "en": "A source that hands out what it was given, in order, then stops. Built from bytes alone, so test vectors replay through it.",
    },
    {
        "pkg": "moonbitstack/moonseed",
        "kind": "fn",
        "key": "Replay::fill",
        "sig": ["Replay::fill(self, buf : FixedArray[Byte]) -> Unit raise Unavailable"],
        "zh": "余量不足一填，则尽发所余而 raise Exhausted；一字节也不凭空生出。",
        "en": "When fewer bytes remain than the buffer wants, it gives every byte left and raises Exhausted. Not one byte is invented.",
    },
    {
        "pkg": "moonbitstack/moonseed",
        "kind": "fn",
        "key": "Replay::remaining",
        "sig": ["Replay::remaining(self) -> Int32"],
        "zh": "尚余几字节可发。向量对不上时，先问此数。",
        "en": "How many bytes are still to give. Ask this first when a vector does not match.",
    },
    {
        "pkg": "moonbitstack/moonseed",
        "kind": "error",
        "key": "Unavailable",
        "sig": [
            "pub(all) suberror Unavailable {",
            "  Platform",
            "  Exhausted",
            "  Failed(String)",
            "} derive(Eq, Debug) · impl Show",
        ],
        "zh": "Platform 平台无源；Exhausted 回放已尽；Failed 自定来源之败，缘由原样陈于调用方。具 Eq、Show、Debug，故可比、可印、可记。",
        "en": "Platform: no source; Exhausted: the replay is spent; Failed: your source failed, and its reason reaches the caller unchanged. Eq, Show and Debug come with it.",
    },
    {
        "pkg": "moonbitstack/moonseed/system",
        "kind": "value",
        "key": "source",
        "sig": ["pub let source : System"],
        "zh": "平台之熵，全库唯一一处碰平台者。JS 取 crypto，wasm 取 WASI random_get，native 委诸运行时。",
        "en": "The platform's entropy — the one place this library touches the platform. crypto on JS, WASI random_get on wasm, the runtime on native.",
    },
    {
        "pkg": "moonbitstack/moonseed/system",
        "kind": "type",
        "key": "System",
        "sig": ["pub struct System {}"],
        "zh": "空记录，无一物可存：每次 fill 都重新问平台，不留缓存。",
        "en": "An empty record that holds nothing: every fill asks the platform again, and nothing is cached between them.",
    },
    {
        "pkg": "moonbitstack/moonseed/system",
        "kind": "type",
        "key": "System::fill",
        "sig": ["System::fill(self, buf : FixedArray[Byte]) -> Unit raise Unavailable"],
        "zh": "一呼一应。取不足数或取之不得，则 raise Platform，不转向他处。",
        "en": "One call, one answer. Short or refused, it raises Platform and turns nowhere else.",
    },
]

# Items the compiler derives for a type rather than declaring on its own: they
# are named in the type's row instead of getting a row of their own.
ABSORB = {
    "Replay::new": "Replay",
    "Unavailable::equal": "Unavailable",
    "Unavailable::not_equal": "Unavailable",
    "Unavailable::to_repr": "Unavailable",
    "Unavailable::to_string": "Unavailable",
    "Unavailable::output": "Unavailable",
}

COUNT_WORD = {
    "fn": ("function", "functions"),
    "type": ("type", "types"),
    "error": ("error", "errors"),
    "value": ("value", "values"),
    "trait": ("trait", "traits"),
}


def parse_mbti(path: Path) -> list[tuple[str, str, str]]:
    """Return (package, kind, name) for every public item the file declares."""
    text = path.read_text(encoding="utf-8")
    pkg = re.search(r'^package "([^"]+)"', text, re.M).group(1)
    items: list[tuple[str, str, str]] = []
    block = None
    for line in text.splitlines():
        s = line.strip()
        if block is None:
            patterns = [
                (r"pub fn(?:\[[^\]]*\])?\s+([\w:]+)", "fn"),
                (r"pub struct (\w+)", "type"),
                (r"pub(?:\(all\))? suberror (\w+)", "error"),
                (r"pub let (\w+)", "value"),
                (r"pub(?:\(open\))? trait (\w+)", "trait"),
            ]
            for pattern, kind in patterns:
                m = re.match(pattern, s)
                if m:
                    items.append((pkg, kind, m.group(1)))
                    break
            else:
                m = re.search(r"type \w+ as (\w+)", s) if s.startswith("pub using") else None
                if m:
                    items.append((pkg, "alias", m.group(1)))
            if s.endswith("{"):
                block = s
                continue
        else:
            if s.startswith("}"):
                block = None
            elif block.startswith(("pub(open) trait", "pub trait")) and s.startswith("fn "):
                items.append((pkg, "trait_method", re.match(r"fn (\w+)", s).group(1)))
            elif "suberror" in block and re.fullmatch(r"\w+(\(.*\))?", s):
                items.append((pkg, "variant", s.split("(")[0]))
    return items


def rows_html() -> str:
    out: list[str] = []
    group = None
    for row in ROWS:
        if row["pkg"] != group:
            if group is not None:
                out.append("        </div>")
            group = row["pkg"]
            counts: dict[str, int] = {}
            for other in ROWS:
                if other["pkg"] == group:
                    counts[other["kind"]] = counts.get(other["kind"], 0) + 1
            summary = " · ".join(
                f"{n} {COUNT_WORD[k][1] if n > 1 else COUNT_WORD[k][0]}" for k, n in counts.items()
            )
            out.append(
                f'        <div class="api__grp"><span>{html.escape(group)}</span><i>{summary}</i></div>'
            )
            out.append('        <div class="api__rows">')
        sig = "<br>".join(html.escape(line) for line in row["sig"])
        out.append(f'        <div class="api__row" data-item="{row["key"]}">')
        out.append(f'          <div class="api__sig">{sig}</div>')
        out.append(f'          <div class="api__g" data-zh="{html.escape(row["zh"], quote=True)}">'
                   f'{html.escape(row["en"], quote=False)}</div>')
        out.append("        </div>")
    if group is not None:
        out.append("        </div>")
    return "\n".join(out)


def version_patch(page: str) -> str:
    version = re.search(r'^version = "(.*)"', (ROOT / "moon.mod").read_text(encoding="utf-8"), re.M)
    return re.sub(r'(<b id="rev-value">)[^<]*(</b>)', rf"\g<1>{version.group(1)}\g<2>", page)


def main() -> int:
    items: list[tuple[str, str, str]] = []
    for path in sorted((ROOT / "src").rglob("pkg.generated.mbti")):
        if "examples" in path.parts:
            continue
        items.extend(parse_mbti(path))

    declared = {(pkg, name) for pkg, kind, name in items if kind in ("fn", "type", "error", "value", "trait", "alias")}
    by_name = {name for _, name in declared}
    covered = {row["key"] for row in ROWS}

    missing = sorted(name for _, name in declared if name not in covered and name not in ABSORB)
    stale = sorted(key for key in covered if key not in by_name)
    if missing:
        print("public items with no row:", file=sys.stderr)
        for name in missing:
            print("  " + name, file=sys.stderr)
    if stale:
        print("rows for items the library no longer has:", file=sys.stderr)
        for name in stale:
            print("  " + name, file=sys.stderr)
    if missing or stale:
        return 1

    page = PAGE.read_text(encoding="utf-8")
    if BEGIN not in page or END not in page:
        print(f"{PAGE} has no {BEGIN} / {END} markers", file=sys.stderr)
        return 1
    head, rest = page.split(BEGIN, 1)
    _, tail = rest.split(END, 1)
    fresh = version_patch(f"{head}{BEGIN}\n{rows_html()}\n        {END}{tail}")

    if "--check" in sys.argv:
        if fresh != page:
            print(f"{PAGE.name} is stale: run python scripts/gen_api.py", file=sys.stderr)
            return 1
        print(f"docs API table covers all {len(declared)} public items in {len(ROWS)} rows")
        return 0

    PAGE.write_text(fresh, encoding="utf-8", newline="\n")
    print(f"wrote docs/index.html: {len(ROWS)} rows for {len(declared)} public items")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
