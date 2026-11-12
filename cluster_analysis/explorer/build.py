"""Builds the Gene Cluster Explorer from its parts.

page.html is the page's shell: header, tab sections and the shared helpers, with an include marker where each part goes
(`/* @include th.css */`, `<!-- @include th.html -->`, `// @include th.js`). Edit the parts and page.html; never
index.html, which this script writes.

    python cluster_analysis/explorer/build.py
        index.html            the assembled page, readable (committed)

    python cluster_analysis/explorer/build.py --standalone DATASET_DIR OUT_DIR
        OUT_DIR/index.html, runtime.js, tokens.css, d3.min.js, data/*.json: the page as a static site with its own
        runtime (runtime/dash.js) and a local copy of d3, so it works without internet; what
        `python -m cluster_analysis.explorer serve` serves on localhost. Readable with any web server:
            python -m http.server -d OUT_DIR 8000
        DATASET_DIR is an export folder (python -m cluster_analysis.explorer export). Personal datasets hold genotypes: keep OUT_DIR outside the
        repo (data/output is ignored by git) and don't serve it beyond your own machine.

    python cluster_analysis/explorer/build.py --publish
        build/publish.json    the minified copy for the old claude.ai artifact's files/index.html document
                              ({"text": ...}), checked against its 262,144-byte document limit. Optional: the localhost
                              site has no size limit.
"""
import argparse
import json
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LIMIT = 262144  # bytes, JSON-encoded: the artifact's per-document limit
INCLUDE = re.compile(r"[ \t]*(?:/\*|<!--|//)[ \t]*@include[ \t]+([\w.\-/]+)[ \t]*(?:\*/|-->)?[ \t]*")


def read(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as f:
        return f.read().replace("\r\n", "\n").rstrip("\n")


def assemble():
    """page.html with each include marker replaced by its part (parts keep their own indentation)."""
    shell = read("page.html")
    seen = []

    def part(m):
        seen.append(m.group(1))
        return read(m.group(1))

    page = INCLUDE.sub(part, shell)
    if len(seen) != len(set(seen)):
        raise SystemExit(f"a part is included twice: {seen}")
    return page + "\n"


def minify_js(code):
    """Conservative: whole-line // comments, indentation and blank lines go; every line break stays, so automatic
    semicolon insertion and template strings behave as before (the Swedish layer collapses whitespace in texts before
    matching, so indentation inside template strings doesn't matter)."""
    return "\n".join(t for t in (l.strip() for l in code.split("\n")) if t and not t.startswith("//"))


def minify_css(code):
    code = re.sub(r"/\*.*?\*/", "", code, flags=re.S)
    code = re.sub(r"\s+", " ", code)
    # Not around ":" — in a selector ".a :hover" the space is a descendant combinator
    return re.sub(r"\s*([{};,>])\s*", r"\1", code).replace(";}", "}").strip()


def minify(page):
    page = re.sub(r"(<script>)(.*?)(</script>)", lambda m: m.group(1) + minify_js(m.group(2)) + m.group(3), page, flags=re.S)
    return re.sub(r"(<style>)(.*?)(</style>)", lambda m: m.group(1) + minify_css(m.group(2)) + m.group(3), page, flags=re.S)


def standalone(page, data_dir, out):
    """The page with the standalone runtime and design tokens loaded before its own styles and scripts."""
    os.makedirs(os.path.join(out, "data"), exist_ok=True)
    for f in ("dash.js", "tokens.css", "d3.min.js"):
        shutil.copyfile(os.path.join(HERE, "runtime", f), os.path.join(out, "runtime.js" if f == "dash.js" else f))
    names = []
    for f in sorted(os.listdir(data_dir)):
        if f.endswith(".json") and f != "bundle.json":
            shutil.copyfile(os.path.join(data_dir, f), os.path.join(out, "data", f))
            names.append(f[:-5])
    # The page's own wording in Swedish: the dataset is [{en, sv}] rows, as published to the artifact
    for name, src in (("i18n_sv", "i18n_sv.json"), ("i18n_sv_terms", "i18n_sv_terms.json")):
        d = json.loads(read(src))
        with open(os.path.join(out, "data", name + ".json"), "w", encoding="utf-8") as f:
            json.dump([{"en": k, "sv": v} for k, v in d.items() if v], f, ensure_ascii=False)
        names.append(name)
    head = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1">\n<title>Gene Cluster Explorer</title>\n'
            '<link rel="stylesheet" href="tokens.css">\n'
            '<script src="d3.min.js"></script>\n'
            '<script src="runtime.js"></script>\n</head>\n<body>\n')
    # The Dashboard runtime runs each <script> in its own scope (what scripts share goes on window): the same here, so a
    # name two parts both declare behaves the same on both runtimes
    page = re.sub(r"<script>(.*?)</script>", lambda m: "<script>(() => {" + m.group(1) + "})();</script>", page, flags=re.S)
    with open(os.path.join(out, "index.html"), "w", encoding="utf-8", newline="\n") as f:
        f.write(head + page + "<script>dash.start();</script>\n</body>\n</html>\n")
    print(f"standalone site in {out}: {len(names)} datasets. Serve it with: python -m http.server -d \"{out}\" 8000")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--standalone", nargs=2, metavar=("DATASET_DIR", "OUT_DIR"))
    ap.add_argument("--publish", action="store_true", help="also the minified copy for the claude.ai artifact, checked "
                                                           "against its 262,144-byte document limit")
    a = ap.parse_args()
    page = assemble()
    with open(os.path.join(HERE, "index.html"), "w", encoding="utf-8", newline="\n") as f:
        f.write(page)
    print(f"index.html {len(page.encode()):,} bytes")
    if a.publish:
        publish_copy(page)
    if a.standalone:
        standalone(page, *a.standalone)


def publish_copy(page):
    pub = minify(page)
    os.makedirs(os.path.join(HERE, "build"), exist_ok=True)
    with open(os.path.join(HERE, "build", "publish.json"), "w", encoding="utf-8") as f:
        json.dump({"text": pub}, f, ensure_ascii=False)
    enc = len(json.dumps({"text": pub}, ensure_ascii=False).encode())
    print(f"build/publish.json {enc:,} of {LIMIT:,} bytes")
    if enc > LIMIT:
        print("  over the artifact's document limit: it can't be published as is", file=sys.stderr)


if __name__ == "__main__":
    main()
