"""Builds the desktop app for Windows: a folder that runs on a machine with nothing installed.

    python scripts/build_desktop.py [--out D:/DNA-Analyzer-build] [--references copy|none]

What goes in (docs/architecture/production.md):
  python/      the embeddable Python 3.10 from python.org, with the pinned packages (requirements.txt) in Lib/site-packages
  jre/         a trimmed Java runtime for Beagle, made with jlink from the JDK on this machine (the modules beagle.jar
               needs, from jdeps)
  app code     cluster_analysis/ and genome/ as they are: nothing is frozen, so the pipeline's own `python -m` steps
               run unchanged with the bundled python.exe
  data/        empty input and output folders; with --references copy, the analysis references from this machine
               (GRCh37 extras and the old panel left out). The imputation panel (~14 GB) is not copied: settings.json
               points at it, until the app downloads its own
  launch.py    starts the explorer on a free port, waits until it answers and opens the browser; closing the window
               stops it. "Start.cmd" runs it with the bundled Python.

Never copied: anyone's DNA files, results, profiles or the lookup cache. The app starts with no people.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import urllib.request
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_NAME = "DNA-Analyzer"  # until the product name is chosen
PY_VERSION = "3.10.11"     # the last 3.10 release with a Windows embeddable build; matches the 3.10 the code runs on
PY_URL = f"https://www.python.org/ftp/python/{PY_VERSION}/python-{PY_VERSION}-embed-amd64.zip"
CODE = ("cluster_analysis", "genome")
SKIP_DIRS = {"__pycache__", "cache", "outreach"}
REF_SKIP = ("grch37", "GRCh37", os.path.join("imputation", "panel"), os.path.join("imputation", "sites.vcf.gz"),
            os.path.join("imputation", "sites_"))


def step(msg):
    print(f"== {msg}", flush=True)


def python_embed(app, cache):
    """The embeddable Python, with its path file opened up: the app root and site-packages on sys.path."""
    z = os.path.join(cache, os.path.basename(PY_URL))
    if not os.path.exists(z):
        step(f"downloading {PY_URL}")
        urllib.request.urlretrieve(PY_URL, z + ".part")
        os.replace(z + ".part", z)
    py = os.path.join(app, "python")
    with zipfile.ZipFile(z) as f:
        f.extractall(py)
    pth = next(n for n in os.listdir(py) if n.endswith("._pth"))
    with open(os.path.join(py, pth), "w", encoding="utf-8", newline="\n") as f:
        # The zip of the standard library, the folder, the packages, the app's code (its parent), and site
        f.write(f"{pth.replace('._pth', '.zip')}\n.\nLib\\site-packages\n..\nimport site\n")
    return py


def packages(py):
    """The pinned packages, installed with this machine's pip for Windows, CPython 3.10 (the same ABI as the bundle)."""
    step("installing the pinned packages")
    target = os.path.join(py, "Lib", "site-packages")
    subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "--no-warn-script-location", "--target", target,
                    "-r", os.path.join(ROOT, "requirements.txt")], check=True)


def java(app):
    """A Java runtime with only the modules Beagle uses."""
    jdk = os.path.dirname(os.path.dirname(shutil.which("jlink") or ""))
    if not jdk:
        sys.exit("jlink not found: install a JDK 17+ (only needed to build)")
    jar = os.path.join(ROOT, "data", "reference", "imputation", "beagle.jar")
    mods = "java.base"
    if os.path.exists(jar):
        out = subprocess.run([os.path.join(jdk, "bin", "jdeps"), "--print-module-deps", "--ignore-missing-deps", jar],
                             capture_output=True, text=True).stdout.strip()
        mods = out or mods
    step(f"java runtime with {mods}")
    subprocess.run([os.path.join(jdk, "bin", "jlink"), "--add-modules", mods, "--strip-debug", "--no-header-files",
                    "--no-man-pages", "--compress=zip-6", "--output", os.path.join(app, "jre")], check=True)


def code(app):
    step("copying the code")
    for d in CODE:
        shutil.copytree(os.path.join(ROOT, d), os.path.join(app, d),
                        ignore=lambda src, names: [n for n in names if n in SKIP_DIRS or n.endswith(".pyc")])
    for f in ("requirements.txt", "README.md"):
        shutil.copy2(os.path.join(ROOT, f), app)
    # No one's profile ships: the app starts empty, and "Add a person" fills it
    with open(os.path.join(app, "cluster_analysis", "profiles.json"), encoding="utf-8") as f:
        prof = json.load(f)
    prof["profiles"] = []
    with open(os.path.join(app, "cluster_analysis", "profiles.json"), "w", encoding="utf-8") as f:
        json.dump(prof, f, indent=1, ensure_ascii=False)
    for d in ("input", "output", "reference", "cache"):
        os.makedirs(os.path.join(app, "data", d), exist_ok=True)


def references(app):
    step("copying the analysis references from this machine")
    src = os.path.join(ROOT, "data", "reference")
    for dirpath, dirs, files in os.walk(src):
        rel = os.path.relpath(dirpath, src)
        dirs[:] = [d for d in dirs if not any(s in os.path.join(rel, d) for s in REF_SKIP)]
        for n in files:
            r = os.path.normpath(os.path.join(rel, n))
            if any(s in r for s in REF_SKIP) or n.endswith(".lock.json"):
                continue
            os.makedirs(os.path.join(app, "data", "reference", os.path.dirname(r)), exist_ok=True)
            shutil.copy2(os.path.join(dirpath, n), os.path.join(app, "data", "reference", r))


LAUNCH = r'''"""Starts the explorer on this machine and opens it in the browser. Closing this window stops it."""
import json, os, socket, subprocess, sys, time, urllib.request, webbrowser

APP = os.path.dirname(os.path.abspath(__file__))
os.environ["PATH"] = os.path.join(APP, "jre", "bin") + os.pathsep + os.environ.get("PATH", "")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
# The app's own lookup cache, in its data folder (the knowledge bundle goes here once it exists)
os.environ.setdefault("DNA_CACHE_DIR", os.path.join(APP, "data", "cache"))
# Where the imputation panel lives (settings.json, written by the build until the app downloads its own)
try:
    with open(os.path.join(APP, "settings.json"), encoding="utf-8") as f:
        for k, v in json.load(f).get("env", {}).items():
            os.environ.setdefault(k, v)
except (OSError, ValueError):
    pass

s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
url = f"http://127.0.0.1:{port}/"
print(f"{NAME} is starting...", flush=True)
proc = subprocess.Popen([sys.executable, "-m", "cluster_analysis.explorer", "serve", "--port", str(port)], cwd=APP)
for _ in range(600):
    if proc.poll() is not None:
        sys.exit(f"{NAME} stopped while starting (exit code {proc.returncode}).")
    try:
        urllib.request.urlopen(url, timeout=1); break
    except OSError:
        time.sleep(0.5)
webbrowser.open(url)
print(f"\n{NAME} is running at {url}\nIt runs on this computer only. Close this window to stop it.", flush=True)
try:
    proc.wait()
except KeyboardInterrupt:
    proc.terminate()
'''


def launcher(app, panel_root, cache=None):
    step("the launcher")
    with open(os.path.join(app, "launch.py"), "w", encoding="utf-8", newline="\n") as f:
        f.write(f"NAME = {APP_NAME!r}\n" + LAUNCH)
    with open(os.path.join(app, "Start.cmd"), "w", encoding="utf-8", newline="\r\n") as f:
        f.write(f'@echo off\ntitle {APP_NAME}\n"%~dp0python\\python.exe" "%~dp0launch.py"\n')
    env = {}
    if panel_root and os.path.isdir(panel_root):
        env = {"DNA_PANEL_ROOT": panel_root, "DNA_PANEL_DIR_1KGP_HC": os.path.join(panel_root, "bref3")}
    if cache:  # a test build reads an existing lookup cache instead of filling its own from the APIs
        env["DNA_CACHE_DIR"] = os.path.abspath(cache)
    with open(os.path.join(app, "settings.json"), "w", encoding="utf-8") as f:
        json.dump({"env": env}, f, indent=1)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", default="D:/DNA-Analyzer-build" if os.path.isdir("D:/") else os.path.join(ROOT, "dist"))
    ap.add_argument("--references", choices=("copy", "none"), default="copy")
    ap.add_argument("--cache", help="an existing lookup cache for a test build (e.g. cluster_analysis/cache); "
                                    "without it the app fills its own from the APIs, slowly")
    ap.add_argument("--panel", default=os.environ.get("DNA_PANEL_ROOT", r"D:\DNA-Analyzer-reference\1kGP_high_coverage_GRCh38"))
    a = ap.parse_args()
    if os.name != "nt":
        sys.exit("This build is for Windows; macOS and Linux follow (docs/architecture/production.md).")
    app = os.path.join(a.out, APP_NAME)
    cache = os.path.join(a.out, "_downloads")
    if os.path.exists(app):
        step(f"removing the previous build at {app}")
        shutil.rmtree(app)
    os.makedirs(cache, exist_ok=True)
    os.makedirs(app)
    packages(python_embed(app, cache))
    java(app)
    code(app)
    if a.references == "copy":
        references(app)
    launcher(app, a.panel, a.cache)
    size = sum(os.path.getsize(os.path.join(d, f)) for d, _, fs in os.walk(app) for f in fs)
    step(f"done: {app} ({size / 1e9:.2f} GB). Run Start.cmd")


if __name__ == "__main__":
    main()
