"""Builds the desktop app for Windows or Linux: a folder that runs on a machine with nothing installed, and with
--installer the file people download (docs/architecture/production.md, Phase 1).

    python scripts/build_desktop.py                      # a test build for this machine (uses its panel and cache)
    python scripts/build_desktop.py --release --installer               # Windows: dist/DNA-Analyzer-<v>-setup.exe
    python scripts/build_desktop.py --release --installer --target linux   # Linux: DNA-Analyzer-<v>-linux-x86_64.tar.gz

What goes in:
  python/      Windows: the embeddable Python 3.10 from python.org. Linux: a standalone CPython 3.10 build
               (python-build-standalone). The pinned packages (requirements.txt) for that platform.
  jre/         a Java runtime for Beagle. Windows: trimmed with jlink from this machine's JDK. Linux: the Eclipse
               Temurin 17 JRE.
  app code     cluster_analysis/ and genome/, only files git doesn't ignore (so nothing personal can slip in), not
               frozen: the pipeline's own `python -m` steps run unchanged.
  data/        empty input and output folders; the analysis references (GRCh37 extras and the panel left out); with
               --release the knowledge bundle in data/knowledge/, installed on first start from the page.
  launch.py    scripts/launch.py: opens the browser on the running app, or starts it (no window from the shortcuts;
               output in data/logs/) and opens the browser when it answers.
  app.ico      the icon of the shortcuts and the installer, drawn here (icon(); needs Pillow on the build machine).
  README.txt   how to use it, in three lines.

Never copied: anyone's DNA files, results, profiles or the lookup cache. The app starts with no people. A test build
(no --release) points settings.json at this machine's imputation panel and, with --cache, its lookup cache.
"""
import argparse
import glob
import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import urllib.request
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from cluster_analysis.version import NAME as APP_NAME, VERSION  # noqa: E402

PY_VERSION = "3.10.11"     # the last 3.10 release with a Windows embeddable build; matches the 3.10 the code runs on
PY_URL = f"https://www.python.org/ftp/python/{PY_VERSION}/python-{PY_VERSION}-embed-amd64.zip"
PBS_API = "https://api.github.com/repos/astral-sh/python-build-standalone/releases"
JRE_LINUX = "https://api.adoptium.net/v3/binary/latest/17/ga/linux/x64/jre/hotspot/normal/eclipse"
CODE = ("cluster_analysis", "genome")
REF_SKIP = ("grch37", "GRCh37", os.path.join("imputation", "panel"), os.path.join("imputation", "sites.vcf.gz"),
            os.path.join("imputation", "sites_"))
ISCC = [os.path.expandvars(p) for p in (r"%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe",
                                        r"%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe", r"%ProgramFiles%\Inno Setup 6\ISCC.exe")]


def step(msg):
    print(f"== {msg}", flush=True)


def download(url, dest):
    if not os.path.exists(dest):
        step(f"downloading {url}")
        req = urllib.request.Request(url, headers={"User-Agent": f"{APP_NAME}-build"})
        with urllib.request.urlopen(req, timeout=120) as r, open(dest + ".part", "wb") as f:
            shutil.copyfileobj(r, f, 1 << 20)
        os.replace(dest + ".part", dest)
    return dest


# --- Python -----------------------------------------------------------------------------------

def python_windows(app, cache):
    """The embeddable Python, with its path file opened up: the app root and site-packages on sys.path."""
    z = download(PY_URL, os.path.join(cache, os.path.basename(PY_URL)))
    py = os.path.join(app, "python")
    with zipfile.ZipFile(z) as f:
        f.extractall(py)
    pth = next(n for n in os.listdir(py) if n.endswith("._pth"))
    with open(os.path.join(py, pth), "w", encoding="utf-8", newline="\n") as f:
        # The zip of the standard library, the folder, the packages, the app's code (its parent), and site
        f.write(f"{pth.replace('._pth', '.zip')}\n.\nLib\\site-packages\n..\nimport site\n")
    return os.path.join(py, "Lib", "site-packages")


def python_linux(app, cache):
    """A relocatable CPython 3.10 for x86-64 Linux (glibc), from python-build-standalone's newest release with one."""
    with urllib.request.urlopen(urllib.request.Request(PBS_API + "?per_page=20", headers={"User-Agent": f"{APP_NAME}-build"}), timeout=60) as r:
        releases = json.load(r)
    asset = next(a for rel in releases for a in rel["assets"]
                 if a["name"].startswith("cpython-3.10.") and a["name"].endswith("-x86_64-unknown-linux-gnu-install_only.tar.gz"))
    step(f"standalone Python: {asset['name']}")
    t = download(asset["browser_download_url"], os.path.join(cache, asset["name"]))
    with tarfile.open(t) as f:
        f.extractall(app)   # -> app/python
    with open(os.path.join(app, "python", "PYTHON_BUILD.txt"), "w", encoding="utf-8") as f:
        f.write(asset["name"] + "\n")
    site = glob.glob(os.path.join(app, "python", "lib", "python3.10", "site-packages"))[0]
    # The app's code (the folder above python/) on sys.path, as the Windows ._pth does
    with open(os.path.join(site, "app.pth"), "w", encoding="utf-8", newline="\n") as f:
        f.write("../../../..\n")
    return site


def packages(target, site, cache=None):
    """The pinned packages for the target, installed with this machine's pip."""
    step(f"installing the pinned packages for {target}")
    req = os.path.join(ROOT, "requirements.txt")
    base = [sys.executable, "-m", "pip", "install", "--quiet", "--no-warn-script-location", "--target", site]
    if target == "windows" and os.name == "nt":
        subprocess.run(base + ["-r", req], check=True)
        return
    # Another platform: uv resolves for the target (pip would read the dependencies' platform markers, such as mcp's
    # pywin32 on Windows, for this machine instead)
    uv = shutil.which("uv")
    if not uv:
        sys.exit("uv not found (pip install uv): it installs the packages for another platform")
    subprocess.run([uv, "pip", "install", "--quiet", "--python", sys.executable, "--target", site,
                    "--python-platform", "x86_64-manylinux_2_17", "--python-version", "3.10", "--only-binary", ":all:", "-r", req], check=True)


# --- Java ------------------------------------------------------------------------------------

def java_windows(app):
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


def java_linux(app, cache):
    t = download(JRE_LINUX, os.path.join(cache, "temurin-17-jre-linux-x64.tar.gz"))
    with tarfile.open(t) as f:
        top = f.getnames()[0].split("/")[0]
        f.extractall(app)
    os.replace(os.path.join(app, top), os.path.join(app, "jre"))
    step(f"java runtime: {top}")


# --- Code, references, knowledge -----------------------------------------------------------

def shipped_files():
    """The code's files git doesn't ignore: tracked, or new and not ignored. Ignored paths are where personal output
    lives (data/, caches), so this keeps them out by construction."""
    out = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z", "--", *CODE],
                         cwd=ROOT, capture_output=True, check=True).stdout.decode("utf-8")
    return [f for f in out.split("\0") if f and os.path.isfile(os.path.join(ROOT, f)) and "__pycache__" not in f
            and "/outreach/" not in f]


def code(app):
    step("copying the code")
    files = shipped_files()
    for f in files:
        dest = os.path.join(app, f)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.copy2(os.path.join(ROOT, f), dest)
    for f in ("requirements.txt", "LICENSE"):
        if os.path.exists(os.path.join(ROOT, f)):
            shutil.copy2(os.path.join(ROOT, f), app)
    # The repository's README is for developers; the program folder gets how to use it
    with open(os.path.join(app, "README.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write(README.format(name=APP_NAME, version=VERSION, lower=APP_NAME.lower()))
    # No one's profile ships: the app starts empty, and "Add a person" fills it
    with open(os.path.join(app, "cluster_analysis", "profiles.json"), encoding="utf-8") as f:
        prof = json.load(f)
    prof["profiles"] = []
    with open(os.path.join(app, "cluster_analysis", "profiles.json"), "w", encoding="utf-8") as f:
        json.dump(prof, f, indent=1, ensure_ascii=False)
    for d in ("input", "output", "reference", "cache", "knowledge"):
        os.makedirs(os.path.join(app, "data", d), exist_ok=True)
    print(f"   {len(files):,} files")


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


def knowledge(app, path):
    files = sorted(glob.glob(os.path.join(path, "knowledge-*.zip"))) if os.path.isdir(path) else [path]
    if not files or not os.path.exists(files[-1]):
        sys.exit(f"no knowledge bundle at {path}: python -m cluster_analysis.knowledge build")
    step(f"knowledge bundle {os.path.basename(files[-1])}")
    shutil.copy2(files[-1], os.path.join(app, "data", "knowledge"))


# --- Launchers -------------------------------------------------------------------------------

LAUNCH = os.path.join(ROOT, "scripts", "launch.py")

README = """{name} {version}

How to use it:
1. Install it: run {name}-{version}-setup.exe (on Linux: ./install.sh).
2. Start it from the {name} icon on the desktop or in the Start menu (on Linux: the applications menu).
3. Your browser opens on the app. It runs on this computer only: your DNA file is never uploaded.

Starting it again while it runs just opens the browser on it. To stop it: "Stop {name}" in the Start menu
(on Linux: {lower} --stop); signing out stops it too. For troubleshooting only, "Troubleshoot (console).cmd"
(start.sh) runs it in a console window that shows what it does, until that window is closed.

Your people, DNA files and results are in the data folder next to this file, and a log in data/logs/ if something
goes wrong. An update keeps them; uninstalling asks before deleting them.
"""

LINUX_START = """#!/bin/sh
# Starts {name}: the explorer on this computer, opened in the browser. In a terminal Ctrl+C stops it;
# with --background it runs on (--stop stops it). See launch.py.
HERE="$(dirname "$(readlink -f "$0")")"
exec "$HERE/python/bin/python3" "$HERE/launch.py" "$@"
"""

LINUX_INSTALL = """#!/bin/sh
# Installs {name} {version} for this user: the program in ~/.local/share/{name}, a menu entry, and a command
# ~/.local/bin/{lower}. An earlier install's data (people, results, the lookup cache) is kept.
set -e
HERE="$(dirname "$(readlink -f "$0")")"
DEST="${{XDG_DATA_HOME:-$HOME/.local/share}}/{name}"
mkdir -p "$DEST"
# The profile list is the person's: kept across the update
if [ -f "$DEST/cluster_analysis/profiles.json" ]; then cp "$DEST/cluster_analysis/profiles.json" "$DEST/profiles.keep.json"; fi
for d in python jre cluster_analysis genome data/reference data/knowledge; do rm -rf "$DEST/$d"; done
for f in "$HERE"/*; do
  n="$(basename "$f")"
  case "$n" in
    data) mkdir -p "$DEST/data"; cp -rn "$f"/. "$DEST/data/" ;;   # the person's data is never overwritten; the
                                                                  # references and bundle were removed above, so they are new
    install.sh) ;;
    *) cp -r "$f" "$DEST/" ;;
  esac
done
if [ -f "$DEST/profiles.keep.json" ]; then mv "$DEST/profiles.keep.json" "$DEST/cluster_analysis/profiles.json"; fi
mkdir -p "$HOME/.local/bin" "${{XDG_DATA_HOME:-$HOME/.local/share}}/applications"
ln -sf "$DEST/start.sh" "$HOME/.local/bin/{lower}"
cat > "${{XDG_DATA_HOME:-$HOME/.local/share}}/applications/{lower}.desktop" <<EOF
[Desktop Entry]
Type=Application
Name={name}
Comment=Reads a DNA file on this computer
Exec=$DEST/start.sh --background
Icon=$DEST/app.png
Terminal=false
Categories=Science;
EOF
echo "{name} {version} installed in $DEST. Start it from the menu or with: {lower}"
"""


def _pil():
    try:
        from PIL import Image, ImageDraw
        return Image, ImageDraw
    except ImportError:
        sys.exit("Pillow not found (pip install pillow): it draws the app icon (only needed to build)")


def _gradient(w, h):
    """Teal at the top left to deep blue at the bottom right: the logo's background."""
    Image, _ = _pil()
    top, bottom = (13, 148, 136), (30, 58, 138)
    g = Image.new("RGBA", (w, h))
    px = g.load()
    for y in range(h):
        for x in range(w):
            t = (y / h) * 0.75 + (x / w) * 0.25
            px[x, y] = tuple(round(a + (b - a) * t) for a, b in zip(top, bottom)) + (255,)
    return g


def _helix(d, cx, top, bottom, amp, width, turns, pairs, phase):
    """A double helix with depth: the strands' points and the base pairs' rungs drawn back to front, the back mixed
    with the deep blue behind it. Each pair is two complementary colours."""
    import math
    BASES = [(251, 191, 36), (244, 114, 182), (96, 165, 250), (52, 211, 153)]
    items, n = [], 900
    for strand, ph in enumerate((0.0, math.pi)):
        for i in range(n + 1):
            a = 2 * math.pi * turns * i / n + ph + phase
            items.append((math.cos(a), "s", cx + amp * math.sin(a), top + (bottom - top) * i / n, strand))
    for k in range(pairs):
        t = (k + 0.5) / pairs
        a = 2 * math.pi * turns * t + phase
        y = top + (bottom - top) * t
        x1, z1, x2, z2 = cx + amp * math.sin(a), math.cos(a), cx + amp * math.sin(a + math.pi), math.cos(a + math.pi)
        for j in range(161):
            u = j / 160
            items.append((z1 + (z2 - z1) * u - 0.02, "r", x1 + (x2 - x1) * u, y, BASES[k % 4] if u < 0.5 else BASES[(k + 2) % 4]))
    items.sort(key=lambda it: it[0])
    for z, kind, x, y, extra in items:
        near = (z + 1) / 2
        base = ((255, 255, 255) if extra == 0 else (186, 230, 253)) if kind == "s" else extra
        col = tuple(round(v * (0.5 + 0.5 * near) + b * (0.5 - 0.5 * near)) for v, b in zip(base, (22, 78, 130))) + (255,)
        r = width / 2 * (0.8 + 0.2 * near) if kind == "s" else width * 0.22
        d.ellipse((x - r, y - r, x + r, y + r), fill=col)


def _logo(small=False, s=1024):
    """The square logo: the helix on the gradient, rounded. small: the strands alone, thicker (16-32 px)."""
    Image, ImageDraw = _pil()
    mask = Image.new("L", (s, s), 0)
    ImageDraw.Draw(mask).rounded_rectangle((24, 24, s - 24, s - 24), radius=220, fill=255)
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    img.paste(_gradient(s, s), (0, 0), mask)
    if small:
        _helix(ImageDraw.Draw(img), s / 2, 170, s - 170, 250, 150, turns=1.0, pairs=0, phase=0.0)
    else:
        _helix(ImageDraw.Draw(img), s / 2, 140, s - 140, 250, 78, turns=1.25, pairs=9, phase=0.6)
    return img


def icon(folder):
    """The app's icon, drawn: a double helix with coloured base pairs on a teal-to-blue rounded square. app.ico for
    Windows (the strands alone at 16-32 px, where the pairs would blur), app.png for Linux menus."""
    Image, _ = _pil()
    big, small = _logo(), _logo(small=True)
    frames = {sz: (small if sz <= 32 else big).resize((sz, sz), Image.LANCZOS) for sz in (16, 24, 32, 48, 64, 128, 256)}
    ico = os.path.join(folder, "app.ico")
    frames[256].save(ico, sizes=[(sz, sz) for sz in frames], append_images=[frames[sz] for sz in frames if sz != 256])
    frames[256].save(os.path.join(folder, "app.png"))
    return ico


def wizard_images(folder):
    """The install wizard's pictures, as Inno Setup wants them (24-bit BMP, at 100% and 200%): the tall one on the
    welcome and finish pages (a long helix) and the small one at the top right of the other pages (the logo)."""
    Image, ImageDraw = _pil()
    os.makedirs(folder, exist_ok=True)
    side, corner = [], []
    for scale in (1, 2):
        w, h, k = 164 * scale, 314 * scale, 3
        img = _gradient(w * k, h * k)
        _helix(ImageDraw.Draw(img), w * k / 2, 30 * scale * k, (h - 30 * scale) * k, 47 * scale * k, 13 * scale * k,
               turns=2.6, pairs=20, phase=0.3)
        p = os.path.join(folder, f"wizard_{scale}x.bmp")
        img.resize((w, h), Image.LANCZOS).convert("RGB").save(p)
        side.append(p)
        sz = 55 * scale
        bg = Image.new("RGBA", (sz, sz), (255, 255, 255, 255))   # the wizard's header is white
        bg.alpha_composite(_logo(small=scale == 1).resize((sz, sz), Image.LANCZOS))
        p = os.path.join(folder, f"wizard_small_{scale}x.bmp")
        bg.convert("RGB").save(p)
        corner.append(p)
    return side, corner


def launcher(app, target, test_env):
    step("the launcher")
    shutil.copyfile(LAUNCH, os.path.join(app, "launch.py"))
    icon(app)
    if target == "windows":
        with open(os.path.join(app, "Troubleshoot (console).cmd"), "w", encoding="utf-8", newline="\r\n") as f:
            f.write(f'@echo off\ntitle {APP_NAME}\n"%~dp0python\\python.exe" "%~dp0launch.py"\n')
    else:
        for name, text in (("start.sh", LINUX_START), ("install.sh", LINUX_INSTALL)):
            p = os.path.join(app, name)
            with open(p, "w", encoding="utf-8", newline="\n") as f:
                f.write(text.format(name=APP_NAME, version=VERSION, lower=APP_NAME.lower()))
            os.chmod(p, 0o755)
    env = dict(test_env)
    if os.environ.get("DNA_UPDATE_URL"):
        env["DNA_UPDATE_URL"] = os.environ["DNA_UPDATE_URL"]
    with open(os.path.join(app, "settings.json"), "w", encoding="utf-8") as f:
        json.dump({"version": VERSION, "env": env}, f, indent=1)


# --- Installers ------------------------------------------------------------------------------

ISS = r"""; {name} {version}: a per-user install (no administrator rights), written by scripts/build_desktop.py
#define AppName "{name}"
#define AppVersion "{version}"
[Setup]
AppId={{{{8E1F6C0B-4C1D-4E55-9A63-2F5D2E7A9B11}}
AppName={{#AppName}}
AppVersion={{#AppVersion}}
AppPublisher={{#AppName}}
DefaultDirName={{localappdata}}\{{#AppName}}
DisableDirPage=yes
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir={out}
OutputBaseFilename={{#AppName}}-{{#AppVersion}}-setup
Compression=lzma2/max
SolidCompression=yes
LZMAUseSeparateProcess=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayName={{#AppName}}
UninstallDisplayIcon={{app}}\app.ico
SetupIconFile={app}\app.ico
WizardStyle=modern
WizardImageFile={wizard}
WizardSmallImageFile={wizard_small}
{sign}
[Messages]
FinishedLabel=[name] is installed.%n%nStart it from the [name] icon on the desktop or in the Start menu: it opens in its own window. It runs on this computer only.%n%nTo stop it, choose "Stop [name]" in the Start menu.
[Files]
; The program: replaced on every update
Source: "{app}\*"; DestDir: "{{app}}"; Excludes: "\data\*,\cluster_analysis\profiles.json"; Flags: recursesubdirs ignoreversion
; The person's things: written once, never by an update
Source: "{app}\cluster_analysis\profiles.json"; DestDir: "{{app}}\cluster_analysis"; Flags: onlyifdoesntexist uninsneveruninstall
; The public references and the knowledge bundle: program data, replaced by an update
Source: "{app}\data\reference\*"; DestDir: "{{app}}\data\reference"; Flags: recursesubdirs ignoreversion
Source: "{app}\data\knowledge\*"; DestDir: "{{app}}\data\knowledge"; Flags: recursesubdirs ignoreversion skipifsourcedoesntexist
[Dirs]
Name: "{{app}}\data\input"
Name: "{{app}}\data\output"
Name: "{{app}}\data\cache"
[Icons]
; pythonw: no console window; the launcher opens the browser on the running app or starts it (launch.py)
Name: "{{userprograms}}\{{#AppName}}"; Filename: "{{app}}\python\pythonw.exe"; Parameters: {q3}{{app}}\launch.py{q3}; WorkingDir: "{{app}}"; IconFilename: "{{app}}\app.ico"; Comment: "Reads a DNA file on this computer"
Name: "{{userdesktop}}\{{#AppName}}"; Filename: "{{app}}\python\pythonw.exe"; Parameters: {q3}{{app}}\launch.py{q3}; WorkingDir: "{{app}}"; IconFilename: "{{app}}\app.ico"; Comment: "Reads a DNA file on this computer"; Tasks: desktopicon
Name: "{{userprograms}}\Stop {{#AppName}}"; Filename: "{{app}}\python\pythonw.exe"; Parameters: {q3}{{app}}\launch.py{q}{q} --stop{q}; WorkingDir: "{{app}}"; IconFilename: "{{app}}\app.ico"; Comment: "Stops {{#AppName}} running in the background"
[Tasks]
Name: "desktopicon"; Description: "A desktop shortcut"
[Run]
Filename: "{{app}}\python\pythonw.exe"; Parameters: {q3}{{app}}\launch.py{q3}; WorkingDir: "{{app}}"; Description: "Start {{#AppName}}"; Flags: postinstall nowait skipifsilent
[UninstallRun]
; A running server holds the program's files
Filename: "{{app}}\python\pythonw.exe"; Parameters: {q3}{{app}}\launch.py{q}{q} --stop{q}; WorkingDir: "{{app}}"; Flags: runhidden waituntilterminated; RunOnceId: "StopServer"
[UninstallDelete]
Type: files; Name: "{{app}}\data\server.json"
Type: filesandordirs; Name: "{{app}}\python"
Type: filesandordirs; Name: "{{app}}\jre"
Type: filesandordirs; Name: "{{app}}\cluster_analysis"
Type: filesandordirs; Name: "{{app}}\genome"
Type: filesandordirs; Name: "{{app}}\data\reference"
Type: filesandordirs; Name: "{{app}}\data\knowledge"
[Code]
// An update: a running server holds the program's files, so it is stopped first (an older launcher without
// --stop would start one instead, so it is left alone)
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  Launch: AnsiString;
  Code: Integer;
begin
  Result := '';
  if LoadStringFromFile(ExpandConstant('{{app}}\launch.py'), Launch) and (Pos('--stop', Launch) > 0) then
    Exec(ExpandConstant('{{app}}\python\pythonw.exe'), AddQuotes(ExpandConstant('{{app}}\launch.py')) + ' --stop',
         ExpandConstant('{{app}}'), SW_HIDE, ewWaitUntilTerminated, Code);
end;

// The data folder (people, DNA files, results) is the person's: removed only when they say so
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
    // Suppressible: a silent uninstall (/SUPPRESSMSGBOXES) answers No and keeps the data
    if SuppressibleMsgBox('Also delete the people, DNA files and results in ' + ExpandConstant('{{app}}\data') + '?' + #13#10 +
              'Choose No to keep them for a later install.', mbConfirmation, MB_YESNO or MB_DEFBUTTON2, IDNO) = IDYES then
    begin
      DelTree(ExpandConstant('{{app}}\data'), True, True, True);
      DeleteFile(ExpandConstant('{{app}}\cluster_analysis\profiles.json'));
      RemoveDir(ExpandConstant('{{app}}\cluster_analysis'));
      RemoveDir(ExpandConstant('{{app}}'));
    end;
end;
"""


def write_iss(app, out):
    """The Inno Setup script for the staged folder `app`, written to out/<name>.iss (no build: see installer_windows)."""
    sign = ""
    if os.environ.get("SIGNTOOL"):   # e.g. signtool sign /fd sha256 /tr http://timestamp... /f cert.pfx /p ... $f
        sign = f"SignTool=custom {os.environ['SIGNTOOL']}\nSignedUninstaller=yes"
    iss = os.path.join(out, f"{APP_NAME}.iss")
    side, corner = wizard_images(os.path.join(out, "wizard"))
    with open(iss, "w", encoding="utf-8-sig", newline="\r\n") as f:
        f.write(ISS.format(name=APP_NAME, version=VERSION, app=app, out=out, sign=sign, q='"', q3='"' * 3,
                           wizard=",".join(side), wizard_small=",".join(corner)))
    return iss


def installer_windows(app, out):
    iscc = next((p for p in ISCC if os.path.exists(p)), None)
    if not iscc:
        sys.exit("Inno Setup 6 not found: winget install JRSoftware.InnoSetup --scope user")
    iss = write_iss(app, out)
    step("the installer (Inno Setup)")
    args = [iscc, "/Q"]
    if os.environ.get("SIGNTOOL"):
        args.append(f"/Scustom={os.environ['SIGNTOOL']}")
    subprocess.run(args + [iss], check=True)
    return os.path.join(out, f"{APP_NAME}-{VERSION}-setup.exe")


def installer_linux(app, out):
    step("the Linux tarball")
    name = f"{APP_NAME}-{VERSION}-linux-x86_64"
    path = os.path.join(out, name + ".tar.gz")

    def mode(ti):
        # Executables keep their bit (built on Windows, where the files have none)
        rel = ti.name.split("/", 1)[-1]
        if ti.isfile() and (rel in ("start.sh", "install.sh", "jre/lib/jspawnhelper", "jre/lib/jexec") or "/bin/" in "/" + rel):
            ti.mode = 0o755
        return ti
    with tarfile.open(path, "w:gz", compresslevel=6) as t:
        t.add(app, arcname=name, filter=mode)
    return path


def sha256(path):
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def _writable(fn, path, _):
    """rmtree's retry for read-only files (the JRE tarball's licence texts on Windows)."""
    import stat
    os.chmod(path, stat.S_IWRITE)
    fn(path)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--target", choices=("windows", "linux"), default="windows" if os.name == "nt" else "linux")
    ap.add_argument("--out", default="D:/DNA-Analyzer-build" if os.path.isdir("D:/") else os.path.join(ROOT, "dist"))
    ap.add_argument("--references", choices=("copy", "none"), default="copy")
    ap.add_argument("--release", action="store_true", help="for other people: the knowledge bundle in, no paths to this machine")
    ap.add_argument("--knowledge", default=None, help="the bundle (a file or the folder of builds); default <out>/knowledge")
    ap.add_argument("--installer", action="store_true", help="also the file people download")
    ap.add_argument("--cache", help="test build: an existing lookup cache instead of filling its own from the APIs")
    ap.add_argument("--panel", default=os.environ.get("DNA_PANEL_ROOT", r"D:\DNA-Analyzer-reference\1kGP_high_coverage_GRCh38"),
                    help="test build: this machine's imputation panel")
    a = ap.parse_args()
    if a.target == "windows" and os.name != "nt":
        sys.exit("The Windows build needs Windows (the embeddable Python's packages and jlink).")
    if a.target == "linux" and platform.machine().lower() not in ("amd64", "x86_64"):
        sys.exit("The Linux build is for x86-64.")
    app = os.path.join(a.out, APP_NAME if a.target == "windows" else f"{APP_NAME}-linux")
    cache = os.path.join(a.out, "_downloads")
    if os.path.exists(app):
        step(f"removing the previous build at {app}")
        shutil.rmtree(app, onerror=_writable)
    os.makedirs(cache, exist_ok=True)
    os.makedirs(app)
    if a.target == "windows":
        packages("windows", python_windows(app, cache), cache)
        java_windows(app)
    else:
        packages("linux", python_linux(app, cache), cache)
        java_linux(app, cache)
    code(app)
    if a.references == "copy":
        references(app)
    test_env = {}
    if a.release:
        knowledge(app, a.knowledge or os.path.join(a.out, "knowledge"))
    else:
        if a.panel and os.path.isdir(a.panel):
            test_env = {"DNA_PANEL_ROOT": a.panel, "DNA_PANEL_DIR_1KGP_HC": os.path.join(a.panel, "bref3")}
        if a.cache:
            test_env["DNA_CACHE_DIR"] = os.path.abspath(a.cache)
    launcher(app, a.target, test_env)
    size = sum(os.path.getsize(os.path.join(d, f)) for d, _, fs in os.walk(app) for f in fs)
    step(f"built: {app} ({size / 1e9:.2f} GB)")
    if a.installer:
        dist = os.path.join(a.out, "dist")
        os.makedirs(dist, exist_ok=True)
        path = installer_windows(app, dist) if a.target == "windows" else installer_linux(app, dist)
        digest = sha256(path)
        with open(path + ".sha256", "w", encoding="utf-8") as f:
            f.write(f"{digest}  {os.path.basename(path)}\n")
        step(f"installer: {path} ({os.path.getsize(path) / 1e6:,.0f} MB), sha256 {digest[:16]}…")


if __name__ == "__main__":
    main()
