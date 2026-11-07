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
        "zh": "n 个均匀字节，不多不少。n 为负是调用方的错，直接中止，不会假装给了空串。",
        "en": "N uniform bytes, no more and no fewer. A negative n is a caller's mistake, so it aborts rather than pretend to hand back nothing.",
    },
    {
        "pkg": "moonbitstack/moonseed",
        "kind": "fn",
        "key": "below",
        "sig": ["pub fn[S : Source] below(bound : BytesView, source : S) -> Bytes raise Unavailable"],
        "zh": "[0, bound) 之内，宽度同 bound。多余的高位清掉，越界就重抽；bound 为 1 时不读字节，为 0 则中止。",
        "en": "[0, bound), as wide as the bound. Mask the unused high bits, redraw while at or above bound. A bound of 1 reads nothing; zero aborts.",
    },
    {
        "pkg": "moonbitstack/moonseed",
        "kind": "fn",
        "key": "scalar",
        "sig": ["pub fn[S : Source] scalar(order : BytesView, source : S) -> Bytes raise Unavailable"],
        "zh": "[1, order)，宽度同 order。留最左边的位，遇到零或越界就重抽，即 FIPS 186-5 A.2.2 的取法。",
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
        "zh": "全库只有这一处要你自己实现。把缓冲填满，做不到就 raise；任何东西实现了它就能接进来，本库一行都不用改。",
        "en": "The one thing you implement. Fill the buffer or raise; anything that keeps this contract plugs in without a line changed here.",
    },
    {
        "pkg": "moonbitstack/moonseed",
        "kind": "type",
        "key": "Replay",
        "sig": ["pub struct Replay", "Replay::new(data : Bytes) -> Self"],
        "zh": "按顺序把给定的字节发完就停的来源。只由字节构造，不碰平台，所以可以把一次抽取钉在固定的字节序列上。",
        "en": "A source that hands out what it was given, in order, then stops. Built from bytes alone, so a draw can be pinned to a fixed sequence.",
    },
    {
        "pkg": "moonbitstack/moonseed",
        "kind": "fn",
        "key": "Replay::fill",
        "sig": ["Replay::fill(self, buf : FixedArray[Byte]) -> Unit raise Unavailable"],
        "zh": "要的比剩下的多时，直接 raise Exhausted，缓冲里一个字节也不留下；它不会凭空造字节。",
        "en": "When fewer bytes remain than the buffer wants, it copies nothing, leaves the buffer as it was, and raises Exhausted. Not one byte is invented.",
    },
    {
        "pkg": "moonbitstack/moonseed",
        "kind": "fn",
        "key": "Replay::remaining",
        "sig": ["Replay::remaining(self) -> Int32"],
        "zh": "还剩几个字节可发。序列对不上时，先看这个数。",
        "en": "How many bytes are still to give. Ask this first when a sequence does not line up.",
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
        "zh": "Platform：平台没有来源；Exhausted：回放用完了；Failed：你自己的来源失败了，原因原样交给调用方。带 Eq、Show、Debug，可以比较、打印、记录。",
        "en": "Platform: no source; Exhausted: the replay is spent; Failed: your source failed, and its reason reaches the caller unchanged. Eq, Show and Debug come with it.",
    },
    {
        "pkg": "moonbitstack/moonseed/system",
        "kind": "value",
        "key": "source",
        "sig": ["pub let source : System"],
        "zh": "平台的熵，全库唯一碰平台的地方。JS 用 crypto，wasm 用 WASI random_get，native 交给运行时。",
        "en": "The platform's entropy — the one place this library touches the platform. crypto on JS, WASI random_get on wasm, the runtime on native.",
    },
    {
        "pkg": "moonbitstack/moonseed/system",
        "kind": "type",
        "key": "System",
        "sig": ["pub struct System {}"],
        "zh": "空记录，什么都不存：每次 fill 都重新问平台，中间不缓存。",
        "en": "An empty record that holds nothing: every fill asks the platform again, and nothing is cached between them.",
    },
    {
        "pkg": "moonbitstack/moonseed/system",
        "kind": "fn",
        "key": "System::fill",
        "sig": ["System::fill(self, buf : FixedArray[Byte]) -> Unit raise Unavailable"],
        "zh": "一次调用，一次回答。给少了或给不出来就 raise Platform，不问别处。",
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

CN_DIGIT = "零一二三四五六七八九十"


def cn_count(n: int) -> str:
    """Chinese numerals for counts, up to ninety-nine. Arabic digits would
    break the line of a Chinese page: 函数十四, not 函数14."""
    if n < 0:
        return str(n)
    if n <= 10:
        return CN_DIGIT[n]
    if n < 20:
        return "十" + CN_DIGIT[n - 10]
    if n < 100:
        tens, units = divmod(n, 10)
        return CN_DIGIT[tens] + "十" + (CN_DIGIT[units] if units else "")
    return str(n)


CN_WORD = {
    "fn": "函数",
    "type": "类型",
    "error": "错误",
    "value": "值",
    "trait": "契约",
    "alias": "别名",
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
            cn_summary = " · ".join(f"{CN_WORD[k]}{cn_count(n)}" for k, n in counts.items())
            out.append(
                f'        <div class="api__grp"><span>{html.escape(group)}</span>'
                f'<i data-zh="{cn_summary}">{summary}</i></div>'
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
    page = re.sub(r'(<span id="rev-head">)[^<]*(</span>)', rf"\g<1>{version.group(1)}\g<2>", page)
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

    # Not Path.write_text: on Windows it truncates before it validates newline,
    # and a ValueError there leaves the page at zero bytes.
    with open(PAGE, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(fresh)
    print(f"wrote docs/index.html: {len(ROWS)} rows for {len(declared)} public items")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
