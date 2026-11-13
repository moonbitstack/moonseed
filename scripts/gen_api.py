#!/usr/bin/env python3
"""Write docs/api.html, and the API table on the home page, from the interfaces.

Every public item in ``src/**/pkg.generated.mbti`` appears on the reference
page: the item list is the compiler's own output, the signature is the one the
source declares, and the prose is the ``///`` comment above it. The script
refuses to write when an item has no comment, and refuses to leave a row behind
for an item the library no longer has.

    python scripts/gen_api.py            rewrite docs/api.html and docs/index.html
    python scripts/gen_api.py --check    exit 1 when either page is stale
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from docsgen import mbti, render  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
API_PAGE = ROOT / "docs" / "api.html"
INDEX = ROOT / "docs" / "index.html"
BEGIN = "<!-- api:begin -->"
END = "<!-- api:end -->"

# The order the home page shows its rows in: what a reader reaches for first,
# then the sources, then the platform. Anything new falls in alphabetically at
# the end of its group.
ORDER = [
    "bytes",
    "below",
    "scalar",
    "Source",
    "Replay",
    "Replay::fill",
    "Replay::remaining",
    "Unavailable",
    "source",
    "System",
    "System::fill",
]

# The one-line Chinese beside each row, for the home page's other setting. The
# reference page is English; this is a translation of the same sentence.
ZH = {
    "bytes": "n 个均匀字节，不多不少。n 为负是调用方的错，直接中止。",
    "below": "[0, bound) 之内，宽度同 bound。多余的高位清掉，越界就重抽。",
    "scalar": "[1, order)，宽度同 order。留最左边的位，遇到零或越界就重抽，即 FIPS 186-5 A.2.2 的取法。",
    "Source": "全库只有这一处要你自己实现。把缓冲填满，做不到就 raise。",
    "Replay": "按顺序把给定的字节发完就停的来源。只由字节构造，不碰平台。",
    "Replay::fill": "要的比剩下的多时，直接 raise Exhausted，缓冲里一个字节也不留下。",
    "Replay::remaining": "还剩几个字节可发。序列对不上时，先看这个数。",
    "Unavailable": "平台没有来源、回放用完了、自己的来源失败了，三种情况分开报。",
    "source": "平台的熵，全库唯一碰平台的地方。",
    "System": "空记录，什么都不存：每次 fill 都重新问平台。",
    "System::fill": "一次调用，一次回答。给不出来就 raise Platform，不问别处。",
}

CN_DIGIT = "零一二三四五六七八九十"
CN_WORD = {
    "fn": "函数",
    "type": "类型",
    "error": "错误",
    "value": "值",
    "trait": "契约",
}
COUNT_WORD = {
    "fn": ("function", "functions"),
    "type": ("type", "types"),
    "error": ("error", "errors"),
    "value": ("value", "values"),
    "trait": ("trait", "traits"),
}
GROUP_TITLE = {
    "fn": "Functions",
    "type": "Types",
    "error": "Errors",
    "trait": "Traits",
    "value": "Values",
}
KIND_LABEL = {
    "fn": "function",
    "method": "method",
    "type": "type",
    "error": "error",
    "trait": "trait",
    "value": "value",
}

def cn_count(n: int) -> str:
    """Chinese numerals for counts, up to ninety-nine: 函数十四, not 函数14."""
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


def version() -> str:
    text = (ROOT / "moon.mod").read_text(encoding="utf-8")
    return re.search(r'^version = "(.*)"', text, re.M).group(1)


def collect() -> tuple[list[mbti.Item], list[str], list[str]]:
    """Items of every package, plus whatever the parser could not place."""
    items: list[mbti.Item] = []
    unplaced: list[str] = []
    packages = []
    for mbti_file in sorted((ROOT / "src").rglob("pkg.generated.mbti")):
        if "examples" in mbti_file.parts:
            continue
        pkg = re.search(
            r'^package "([^"]+)"', mbti_file.read_text(encoding="utf-8"), re.M
        ).group(1)
        packages.append(pkg)
        found, lost = mbti.parse_package(mbti_file.parent, pkg, mbti_file)
        items.extend(found)
        unplaced.extend(lost)
    return items, unplaced, packages


def by_package(items: list[mbti.Item], packages: list[str]) -> dict[str, list[mbti.Item]]:
    out = {pkg: [] for pkg in packages}
    for item in items:
        out[item.pkg].append(item)
    return out


def groups(items: list[mbti.Item]) -> list[tuple[str, list[mbti.Item]]]:
    """The reference page's own order: functions, types, errors, traits, values."""
    order = ["fn", "type", "error", "trait", "value"]
    out = []
    for kind in order:
        member = sorted(
            (i for i in items if i.kind == kind and "::" not in i.key),
            key=lambda i: i.key.lower(),
        )
        if member:
            out.append((kind, member))
    return out


def sig_lines(item: mbti.Item) -> list[str]:
    """The signature as the reference prints it: a struct's fields stay private."""
    if item.kind == "error" and item.variants:
        lines = [item.lines[0] + " {"]
        lines += [f"  {name}" for name, _ in item.variants]
        lines.append("}")
        return lines
    return item.lines


def index_sig(item: mbti.Item, children: list[mbti.Item]) -> list[str]:
    """The summary's one row: a trait keeps its method in the braces, a struct
    names its constructor, and a method that has a row of its own keeps it."""
    if item.kind == "trait":
        lines = [item.lines[0] + " {"]
        lines += [f"  {child.lines[0]}" for child in children]
        lines.append("}")
        return lines
    lines = sig_lines(item)
    if item.kind == "method":
        # A row for a method does not repeat the keyword: the name already says
        # which type it hangs from, and the column stays one line wide.
        lines = [line.replace("pub fn ", "", 1) for line in lines]
    if item.kind == "error":
        lines[-1] = "} derive(Eq, Debug) · impl Show"
    if item.kind == "type":
        lines = lines + [
            child.lines[0].replace("pub fn ", "") for child in children if child.key.endswith("::new")
        ]
    return lines


def doc_html(item: mbti.Item) -> str:
    """Prose, the variant notes, and the examples the compiler runs."""
    out: list[str] = []
    for para in item.doc.prose:
        out.append(f"        <p>{render.inline(para)}</p>")
    if item.variants and any(note for _, note in item.variants):
        rows = "\n".join(
            f'          <dt><code>{render.esc(name)}</code></dt><dd>{render.inline(note)}</dd>'
            for name, note in item.variants
            if note
        )
        out.append(f'        <dl class="vars">\n{rows}\n        </dl>')
    for code in item.doc.examples:
        out.append(
            f'        <div class="eg"><span class="eg__tag">runs in the tests</span>'
            f"{render.code_block(code, 'eg__code')}</div>"
        )
    return "\n".join(out)


def item_html(item: mbti.Item, nested: bool = False) -> str:
    anchor = item.key.replace("::", ".")
    sig = "\n".join(render.esc(line) for line in sig_lines(item))
    head = (
        f'          <span class="item__kind">{KIND_LABEL[item.kind]}</span>'
        f'<h4 class="item__name">{render.esc(item.key)}</h4>'
        f'<a class="item__anchor" href="#{anchor}" aria-label="link to this item">#</a>'
    )
    return f"""      <article class="item{' item--nested' if nested else ''}" id="{anchor}">
        <header class="item__head">
{head}
        </header>
        <pre class="code item__sig">{sig}</pre>
        <div class="item__doc">
{doc_html(item)}
        </div>
      </article>"""


def package_html(pkg: str, items: list[mbti.Item], number: str) -> str:
    top = [i for i in items if "::" not in i.key]
    counts: dict[str, int] = {}
    for item in top:
        counts[item.kind] = counts.get(item.kind, 0) + 1
    note = " · ".join(
        f"{n} {COUNT_WORD[k][1] if n > 1 else COUNT_WORD[k][0]}" for k, n in counts.items()
    )
    blocks = []
    for kind, member in groups(items):
        rows = []
        for item in member:
            rows.append(item_html(item))
            if item.kind in ("type", "trait"):
                for child in sorted(
                    (i for i in items if i.target == item.key and i.key != item.key),
                    key=lambda i: i.key,
                ):
                    rows.append(item_html(child, nested=True))
        blocks.append(
            f'      <h3 class="ref__grp">{GROUP_TITLE[kind]}'
            f'<i>{len(member)}</i></h3>\n' + "\n".join(rows)
        )
    return f"""<section class="sec" id="{pkg.split('/')[-1]}">
  <div class="sheet">
    <div class="sec__head">
      <div class="sec__plate">
        <span class="sec__no">{number}</span>
        <h2 class="sec__title sec__title--pkg">{render.esc(pkg)}</h2>
      </div>
      <p class="sec__note">{note}</p>
    </div>
{chr(10).join(blocks)}
  </div>
</section>"""


def api_page(items: list[mbti.Item], packages: list[str]) -> str:
    grouped = by_package(items, packages)
    total = len(items)
    jumps = " · ".join(
        f'<a href="#{p.split("/")[-1]}">{render.esc(p)}</a>' for p in packages
    )
    sections = "\n\n".join(
        package_html(pkg, grouped[pkg], f"{n + 1:02d}") for n, pkg in enumerate(packages)
    )
    body = f"""<header class="dochead">
  <div class="sheet">
    <p class="dochead__eyebrow mono">moonbitstack / moonseed · reference</p>
    <h1 class="dochead__title">API</h1>
    <p class="dochead__lede">
      Every public item of both packages: the signature the source declares, and the note
      beside it. The list of items is the compiler's interfaces; the prose is the source's
      own comments, so this page cannot describe an API the library does not have.
    </p>
    <div class="dochead__meta">
      <span><b>{total}</b> public items</span>
      <span><b>{len(packages)}</b> packages</span>
      <span><b>{version()}</b> rev</span>
    </div>
    <p class="dochead__jump">{jumps} · <a href="guide.html">the guide</a></p>
  </div>
</header>

{sections}"""
    return render.page(
        title="moonseed — the API, item by item",
        description="Every public item of moonseed: secure bytes, unbiased sampling, and the "
        "sources they draw from.",
        body=body,
        current="api",
        version=version(),
    )


def index_rows(items: list[mbti.Item]) -> str:
    """The home page's table: one row per item, the signature and one sentence."""
    rank = {key: n for n, key in enumerate(ORDER)}
    flat = [item for item in items if item.key in ORDER]
    flat.sort(key=lambda i: (rank.get(i.key, len(ORDER)), i.key))
    methods = {}
    for item in items:
        if item.kind == "method" and item.target:
            methods.setdefault(item.target, []).append(item)

    out: list[str] = []
    pkg = None
    for item in flat:
        if item.pkg != pkg:
            if pkg is not None:
                out.append("        </div>")
            pkg = item.pkg
            counts: dict[str, int] = {}
            for other in flat:
                if other.pkg != pkg or "::" in other.key:
                    continue
                kind = "fn" if other.kind in ("fn", "method") else other.kind
                counts[kind] = counts.get(kind, 0) + 1
            summary = " · ".join(
                f"{n} {COUNT_WORD[k][1] if n > 1 else COUNT_WORD[k][0]}"
                for k, n in counts.items()
            )
            cn_summary = " · ".join(f"{CN_WORD[k]}{cn_count(n)}" for k, n in counts.items())
            out.append(
                f'        <div class="api__grp"><span>{render.esc(pkg)}</span>'
                f'<i data-zh="{render.attr(cn_summary)}">{summary}</i></div>'
            )
            out.append('        <div class="api__rows">')
        children = sorted(methods.get(item.key, []), key=lambda i: i.key)
        lines = index_sig(item, children)
        sig = "<br>".join(render.esc(line) for line in lines)
        note = item.doc.first_sentence()
        zh = ZH.get(item.key, "")
        out.append(f'        <div class="api__row" data-item="{render.attr(item.key)}">')
        out.append(f'          <div class="api__sig">{sig}</div>')
        out.append(
            f'          <div class="api__g" data-zh="{render.attr(zh)}">{render.inline(note)}</div>'
        )
        out.append("        </div>")
    out.append("        </div>")
    return "\n".join(out)


def main() -> int:
    items, unplaced, packages = collect()
    silent = [i for i in items if not i.doc.prose]
    if unplaced:
        print("interfaces this script cannot place:", file=sys.stderr)
        for key in sorted(set(unplaced)):
            print(f"  {key}", file=sys.stderr)
    if silent:
        print("public items with no doc comment:", file=sys.stderr)
        for item in silent:
            print(f"  {item.key}", file=sys.stderr)
    missing_zh = [i.key for i in items if i.key in ORDER and i.key not in ZH]
    if missing_zh:
        print("rows with no Chinese: " + ", ".join(missing_zh), file=sys.stderr)
    if unplaced or silent or missing_zh:
        return 1

    fresh_api = api_page(items, packages)

    page = INDEX.read_text(encoding="utf-8")
    if BEGIN not in page or END not in page:
        print(f"docs/index.html has no {BEGIN} / {END} markers", file=sys.stderr)
        return 1
    head, rest = page.split(BEGIN, 1)
    _, tail = rest.split(END, 1)
    fresh_index = f"{head}{BEGIN}\n{index_rows(items)}\n        {END}{tail}"
    fresh_index = re.sub(
        r'(<span id="rev-head">)[^<]*(</span>)', rf"\g<1>{version()}\g<2>", fresh_index
    )
    fresh_index = re.sub(
        r'(<b id="rev-value">)[^<]*(</b>)', rf"\g<1>{version()}\g<2>", fresh_index
    )

    if "--check" in sys.argv:
        stale = []
        if not API_PAGE.exists() or API_PAGE.read_text(encoding="utf-8") != fresh_api:
            stale.append(API_PAGE.name)
        if fresh_index != page:
            stale.append(INDEX.name)
        if stale:
            print(f"stale: {', '.join(stale)} — run python scripts/gen_api.py", file=sys.stderr)
            return 1
        print(f"api.html covers all {len(items)} public items; index.html is current")
        return 0

    with open(API_PAGE, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(fresh_api)
    with open(INDEX, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(fresh_index)
    print(f"wrote docs/api.html and docs/index.html: {len(items)} items")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
