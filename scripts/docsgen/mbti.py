"""Read the compiler's interfaces and the doc comments beside them.

The compiler prints one ``pkg.generated.mbti`` per package: that file is the
list of public items and the authority for what the library exposes. The prose
for each item lives in a ``///`` comment above its declaration, and only there.
This module joins the two, so the reference page and the summary table are
written from one source and neither can drift from the code.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

# Members the compiler writes for a type: derived equality, and the Show impl.
# They are named in the type's own entry rather than getting one of their own.
DERIVED = ("::equal", "::not_equal", "::to_repr", "::to_string", "::output")


@dataclass
class Doc:
    """What a ``///`` comment says: paragraphs of prose, and the code in it."""

    prose: list[str] = field(default_factory=list)
    examples: list[str] = field(default_factory=list)

    def first_sentence(self) -> str:
        if not self.prose:
            return ""
        text = self.prose[0].strip()
        depth = False
        for i, ch in enumerate(text):
            if ch == "`":
                depth = not depth
            elif ch == "." and not depth and (i + 1 == len(text) or text[i + 1] == " "):
                return text[: i + 1]
        return text


@dataclass
class Item:
    pkg: str
    kind: str  # fn, method, type, error, trait, value
    key: str  # `bytes`, `Replay::new`, `Unavailable`
    lines: list[str]  # the signature as the page prints it
    doc: Doc
    target: str = ""  # for a method, the type it belongs to
    variants: list[tuple[str, str]] = field(default_factory=list)


def _doc_of(lines: list[str]) -> Doc:
    body: list[str] = []
    for line in lines:
        text = line.lstrip()[3:]
        if text.startswith("|"):
            continue
        if text.startswith(" "):
            text = text[1:]
        body.append(text.rstrip())
    doc = Doc()
    para: list[str] = []

    def flush() -> None:
        if para:
            doc.prose.append(" ".join(x.strip() for x in para if x.strip()))
            para.clear()

    rows = body
    i = 0
    while i < len(rows):
        row = rows[i]
        if row.startswith("```"):
            flush()
            i += 1
            code: list[str] = []
            while i < len(rows) and not rows[i].startswith("```"):
                code.append(rows[i])
                i += 1
            doc.examples.append("\n".join(code).rstrip())
        elif not row.strip():
            flush()
        else:
            para.append(row)
        i += 1
    flush()
    return doc


def _join_decl(lines: list[str], i: int) -> tuple[str, int]:
    """The declaration at ``i``, joined over the lines its signature spans.

    A brace at the end opens the body, not the signature, so it is left out of
    the balance; parentheses and brackets that are still open pull the next
    line in.
    """
    text = lines[i].strip()

    def open_parens(t: str) -> int:
        return t.count("(") + t.count("[") - t.count(")") - t.count("]")

    j = i + 1
    while j < len(lines) and (open_parens(text) > 0 or text.endswith((",", "("))):
        text += " " + lines[j].strip()
        j += 1
    return re.sub(r"\s+", " ", text).strip(), j


def _param_items(text: str) -> list[str]:
    out, depth, cur = [], 0, ""
    for ch in text:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        if ch == "," and depth == 0:
            out.append(cur.strip())
            cur = ""
        else:
            cur += ch
    if cur.strip():
        out.append(cur.strip())
    return out


def _split_sig(sig: str) -> tuple[str, list[str], str]:
    paren = sig.find("(")
    if paren < 0:
        return sig, [], ""
    depth, close = 0, -1
    for k in range(paren, len(sig)):
        if sig[k] == "(":
            depth += 1
        elif sig[k] == ")":
            depth -= 1
            if depth == 0:
                close = k
                break
    if close < 0:
        return sig, [], ""
    return sig[:paren], _param_items(sig[paren + 1 : close]), sig[close + 1 :]


def _impl_signature(mbti_line: str, names: list[str], target: str) -> str:
    """A method's signature: the .mbti types with the names the source gives."""
    head, params, tail = _split_sig(mbti_line)
    if not params or len(params) != len(names):
        return mbti_line
    named = []
    for name, kind in zip(names, params):
        name = name.lstrip("_")
        if kind == "Self":
            kind = target
        named.append(f"{name} : {kind}" if name and name != kind else kind)
    return f"{head}({', '.join(named)}){tail}"


def _scan(
    src: Path,
    docs: dict[str, Doc],
    sigs: dict[str, list[str]],
    impl_names: dict[str, tuple[str, list[str]]],
    variants: dict[str, list[tuple[str, str]]],
) -> None:
    """Read one source file into the maps keyed by item."""
    lines = src.read_text(encoding="utf-8").splitlines()
    pending: list[str] = []
    i = 0
    while i < len(lines):
        raw = lines[i]
        stripped = raw.strip()
        if stripped.startswith("///"):
            pending.append(stripped)
            i += 1
            continue
        if not stripped or stripped.startswith("//"):
            i += 1
            continue
        if stripped.startswith("#"):
            # `#derive` and friends sit between a doc comment and its declaration.
            i += 1
            continue

        decl, j = _join_decl(lines, i)
        doc = _doc_of(pending) if pending else Doc()
        pending = []
        i = j

        m = re.match(r"^pub(?:\([a-z]+\))?\s+fn(?:\[[^\]]*\])?\s+([\w:]+)\s*\(", decl)
        if m:
            key = m.group(1)
            sigs[key] = [decl.split("{")[0].strip()]
            docs[key] = doc
            continue
        m = re.match(r"^pub(?:\([a-z]+\))?\s+struct\s+(\w+)", decl)
        if m:
            key = m.group(1)
            sigs[key] = [re.sub(r"\s*\{.*$", "", decl)]
            docs[key] = doc
            continue
        m = re.match(r"^pub(?:\(all\))?\s+suberror\s+(\w+)\s*\{", decl)
        if m:
            key = m.group(1)
            sigs[key] = [re.sub(r"\s*\{.*$", "", decl)]
            docs[key] = doc
            variants[key] = []
            k = i
            while k < len(lines) and not lines[k].startswith("}"):
                row = lines[k].strip()
                vdoc = ""
                if row.startswith("///"):
                    vdoc = row[3:].lstrip("| ")
                    k += 1
                    row = lines[k].strip() if k < len(lines) else ""
                vm = re.match(r"^(\w+(?:\(.*\))?),?$", row)
                if vm:
                    variants[key].append((vm.group(1), vdoc))
                k += 1
            i = k + 1
            continue
        m = re.match(r"^pub(?:\(open\))?\s+trait\s+(\w+)\s*\{", decl)
        if m:
            key = m.group(1)
            sigs[key] = [re.sub(r"\s*\{.*$", "", decl)]
            docs[key] = doc
            k = i
            while k < len(lines) and not lines[k].startswith("}"):
                if lines[k].strip().startswith("///"):
                    tdoc = []
                    while k < len(lines) and lines[k].strip().startswith("///"):
                        tdoc.append(lines[k].strip())
                        k += 1
                    trow = lines[k].strip() if k < len(lines) else ""
                    tm = re.match(r"^fn\s+(\w+)\s*\(", trow)
                    if tm:
                        tkey = f"{key}::{tm.group(1)}"
                        docs[tkey] = _doc_of(tdoc)
                k += 1
            i = k + 1
            continue
        m = re.match(r"^pub\s+let\s+(\w+)\s*:", decl)
        if m:
            key = m.group(1)
            sigs[key] = [re.sub(r"\s*=.*$", "", decl)]
            docs[key] = doc
            continue
        m = re.match(
            r"^pub\s+impl\s+(?:@[\w.]+\.)?\w+(?:\[[^\]]*\])?\s+for\s+(\w+)\s+with\s+fn\s+(\w+)\s*\(",
            decl,
        )
        if m:
            key = f"{m.group(1)}::{m.group(2)}"
            _, params, _ = _split_sig(decl)
            impl_names[key] = (m.group(1), [p.split(":")[0].strip() for p in params])
            docs[key] = doc
            continue
        m = re.match(r"^pub\s+extend\s+(\w+)\s+with\s+(\w+)::\{([^}]*)\}", decl)
        if m:
            # A promoted method has no body of its own: the impl beside it is
            # what a reader should be shown, so the doc lands on that key.
            for method in (x.strip() for x in m.group(3).split(",")):
                docs.setdefault(f"{m.group(1)}::{method}", doc)
            continue


def _clean(line: str) -> str:
    """One signature line: no space inside the parentheses, no package prefix."""
    line = line.replace("@moonseed.", "")
    line = re.sub(r"\(\s+", "(", line)
    line = re.sub(r"\s+\)", ")", line)
    line = re.sub(r",\)", ")", line)
    return re.sub(r"\s+,", ",", line)


def parse_package(src: Path, pkg: str, mbti_path: Path) -> tuple[list[Item], list[str]]:
    """Every public item of one package, and any .mbti entry left unexplained."""
    docs: dict[str, Doc] = {}
    sigs: dict[str, list[str]] = {}
    impl_names: dict[str, tuple[str, list[str]]] = {}
    variants: dict[str, list[tuple[str, str]]] = {}
    for source in sorted(src.glob("*.mbt")):
        _scan(source, docs, sigs, impl_names, variants)

    items: list[Item] = []
    unplaced: list[str] = []
    text = mbti_path.read_text(encoding="utf-8")
    block: str | None = None
    current: Item | None = None
    for raw in text.splitlines():
        s = raw.strip()
        if block is None:
            m = re.match(r"^pub fn(?:\[[^\]]*\])?\s+([\w:]+)\(", s)
            if m:
                key = m.group(1)
                if key in sigs:
                    kind = "method" if "::" in key else "fn"
                    target = key.split("::")[0] if kind == "method" else ""
                    items.append(
                        Item(pkg, kind, key, sigs[key], docs.get(key, Doc()), target)
                    )
                elif key in impl_names:
                    target, names = impl_names[key]
                    sig = _impl_signature(s, names, target)
                    items.append(
                        Item(pkg, "method", key, [sig], docs.get(key, Doc()), target)
                    )
                else:
                    unplaced.append(key)
                continue
            m = re.match(r"^pub (?:struct|enum) (\w+)", s)
            if m:
                key = m.group(1)
                items.append(
                    Item(pkg, "type", key, sigs.get(key, [s]), docs.get(key, Doc()))
                )
                continue
            m = re.match(r"^pub(?:\(all\))? suberror (\w+)", s)
            if m:
                key = m.group(1)
                item = Item(
                    pkg,
                    "error",
                    key,
                    sigs.get(key, [s]),
                    docs.get(key, Doc()),
                    variants=variants.get(key, []),
                )
                items.append(item)
                current, block = item, "error"
                continue
            m = re.match(r"^pub(?:\(open\))? trait (\w+)", s)
            if m:
                key = m.group(1)
                item = Item(
                    pkg,
                    "trait",
                    key,
                    sigs.get(key, [s]),
                    docs.get(key, Doc()),
                )
                items.append(item)
                current, block = item, "trait"
                continue
            m = re.match(r"^pub let (\w+)", s)
            if m:
                key = m.group(1)
                items.append(
                    Item(pkg, "value", key, sigs.get(key, [s]), docs.get(key, Doc()))
                )
                continue
            continue
        if s.startswith("}"):
            block, current = None, None
            continue
        if block == "trait" and current is not None:
            m = re.match(r"^fn (\w+)\(", s)
            if m:
                key = f"{current.key}::{m.group(1)}"
                items.append(
                    Item(pkg, "method", key, [s], docs.get(key, Doc()), current.key)
                )
    for item in items:
        item.lines = [_clean(line) for line in item.lines]
    kept = [i for i in items if not i.key.endswith(DERIVED)]
    return kept, [x for x in unplaced if not x.endswith(DERIVED)]
