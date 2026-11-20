# cluster_analysis/pipeline.py
"""
Add a person: from a raw DNA file to their profile in the explorer, in one run.

    python -m cluster_analysis.pipeline inspect FILE                 # format, calls, sex: what the explorer shows first
    python -m cluster_analysis.pipeline add FILE --id NAME [--sex female|male]
    python -m cluster_analysis.pipeline status                       # every run's state
    python -m cluster_analysis.pipeline machine                      # this computer's specs and the time a run takes
    python -m cluster_analysis.pipeline abandon NAME                 # an unfinished run removed, with all it made

The explorer's "Add a person" dialog runs the same through the local server (explorer/__main__.py serve).

Stages, each resumable (a run that stopped or failed starts again at the stage it reached):
  check     the file's format and calls, Java, Beagle and the reference panel, free disk
  register  the file copied to data/input/<id>.<ext>, the person added to profiles.json
  impute    genome/impute.py: Beagle per chromosome, then the confidence-tiered CSV (~15 minutes)
  analyse   profiles.py run, one step at a time (themes, gene calls, systems, medicines, nutrition, lab tests, fitness,
            cancers); lookups come from the shared cache, so mostly offline
  explorer  explorer export (every profile's datasets) and the site rebuilt; the page picks it up on reload

Time estimates come from the machine: Beagle's share scales with the effective cores times the clock, the rest
(reading the site list, scoring the accuracy test, writing the tiered file) with the clock alone. They start from
the phases measured when XY was added (BASELINE) and switch to this machine's own runs once it has some (timings.json);
while a run imputes, the time left is extrapolated from how fast its chromosomes are going.

State is written to data/output/pipeline/<id>.json after every change (the page polls it), the full output to
<id>.log next to it. Nothing leaves the machine except the public identifiers the analysis already looks up.
"""
import argparse
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from genome import build as gbuild  # noqa: E402

STATE_DIR = os.path.join(ROOT, "data", "output", "pipeline")
INPUT = os.path.join(ROOT, "data", "input")
PROFILES = os.path.join(ROOT, "cluster_analysis", "profiles.json")
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,31}$")
CHROMS = [str(c) for c in range(1, 23)] + ["X"]
STEPS = [("themes", "Health themes"), ("genes", "Gene calls"), ("systems", "Body systems"), ("medicines", "Medicines"),
         ("nutrition", "Nutrition"), ("labtests", "Lab tests"), ("fitness", "Fitness"), ("cancers", "Cancer risk")]
# Share of the whole run each stage takes, for one progress bar (updated from timings.json once runs are recorded)
WEIGHT = {"check": 0.01, "register": 0.01, "impute": 0.55, "analyse": 0.38, "explorer": 0.05}
FREE_GB = 5


def now():
    return datetime.datetime.now().isoformat(timespec="seconds")


# --- the machine and the time a run takes -------------------------------------------------------------------------

# Phases measured adding XY on the first machine (i7-7700K: 4 cores, 8 threads, 4.2 GHz; Beagle 8 threads, 12 GB heap),
# 2026-11-17, from the run's log and file times: the accuracy test 1,028 s (a Beagle pass of ~526 s, the rest reading
# the site list and scoring), the Beagle pass 526 s, writing the tiered file 868 s; analysis 1,456 s, export 70 s.
BASELINE = {"cpu": "Intel(R) Core(TM) i7-7700K CPU @ 4.20GHz", "eff": 5.0, "ghz": 4.2,
            "validate": 1028, "beagle": 526, "write": 868, "analyse": 1456, "explorer": 70, "check": 2, "register": 1}
_CPU = []


def cpu_name():
    if not _CPU:
        name = None
        try:
            if os.name == "nt":
                import winreg
                k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0")
                name = winreg.QueryValueEx(k, "ProcessorNameString")[0].strip()
            elif os.path.exists("/proc/cpuinfo"):
                name = next((l.split(":", 1)[1].strip() for l in open("/proc/cpuinfo") if l.startswith("model name")), None)
        except OSError:
            pass
        import platform
        _CPU.append(name or platform.processor() or "Unknown processor")
    return _CPU[0]


def effective(physical, logical, threads):
    """Cores Beagle can use, counting a hyperthread as a quarter of a core (measured gains are 20-30%)."""
    real = min(threads, physical)
    return round(real + 0.25 * max(0, min(threads, logical) - physical), 2)


def machine():
    """This computer as the imputation sees it, and the Beagle settings the pipeline gives it."""
    import psutil
    from genome import impute
    vm = psutil.virtual_memory()
    physical = psutil.cpu_count(logical=False) or 1
    logical = psutil.cpu_count() or physical
    freq = psutil.cpu_freq()
    ghz = round((freq.max or freq.current) / 1000, 2) if freq and (freq.max or freq.current) else BASELINE["ghz"]
    ram = vm.total / 2 ** 30
    heap = 12 if ram >= 16 else max(4, int(ram * 0.6))   # 12 GB is what genome/impute.py runs the panel with
    threads = logical
    P = impute.panel(gbuild.panel_name())
    disks = {}
    for label, where in (("project", ROOT), ("panel", P["dir"])):
        if os.path.isdir(where):
            drive = (os.path.splitdrive(os.path.abspath(where))[0] or "/").upper()
            disks.setdefault(drive, {"free_gb": round(shutil.disk_usage(where).free / 1e9, 1), "holds": []})["holds"].append(label)
    warnings = []
    if vm.available / 2 ** 30 < heap + 1:
        warnings.append(f"Only {vm.available / 2 ** 30:.1f} GB of memory is free and Beagle takes {heap} GB: closing other programs keeps it from slowing down.")
    return {"cpu": cpu_name(), "cores": physical, "threads": logical, "ghz": ghz, "ram_gb": round(ram, 1),
            "ram_free_gb": round(vm.available / 2 ** 30, 1), "beagle_threads": threads, "beagle_heap_gb": heap,
            "eff": effective(physical, logical, threads), "disks": disks, "warnings": warnings}


def timings():
    path = os.path.join(STATE_DIR, "timings.json")
    return json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {}


def plan(m=None, validate=True):
    """Seconds per stage for a run on this machine, and what they rest on."""
    m = m or machine()
    t = timings()
    own = [r for r in t.get("impute_runs", []) if r.get("cpu") == m["cpu"]][-3:]
    src = own or [BASELINE]
    avg = lambda k: sum(r[k] * r.get("ghz", BASELINE["ghz"]) * (r.get("eff", BASELINE["eff"]) if k == "beagle" else 1) for r in src) / len(src)
    beagle = avg("beagle") / (m["eff"] * m["ghz"])
    # the accuracy test is a Beagle pass of its own plus the reading and scoring around it
    other = sum((r["validate"] - r["beagle"]) * r.get("ghz", BASELINE["ghz"]) for r in src) / len(src) / m["ghz"]
    out = {"validate": round(beagle + other) if validate else 0, "beagle": round(beagle), "write": round(avg("write") / m["ghz"])}
    out["impute"] = out["validate"] + out["beagle"] + out["write"]
    for k in ("check", "register", "analyse", "explorer"):
        hist = t.get(k) or []
        out[k] = round(sum(hist) / len(hist)) if hist else BASELINE[k]
    steps = t.get("analyse_steps") or {}
    out["steps"] = {k: round(sum(v) / len(v)) for k, v in steps.items() if v}
    out["basis"] = "own" if own else "baseline"
    out["runs"] = len(own)
    return out


def _weights(s):
    """How much of a Beagle pass each chromosome is: its share of the file's calls (they follow chromosome length)."""
    per = s.get("facts", {}).get("check", {}).get("chromosomes") or {}
    w = {c: per.get(c) or 1 for c in CHROMS}
    tot = sum(w.values())
    return {c: v / tot for c, v in w.items()}


def _pass_left(clock, w, now_t, predicted, started, ends):
    """Seconds left of a Beagle pass. clock: chromosome -> time; ends=True when the time is its end (accuracy test),
    False when it is its start (the run). Extrapolated once two chromosomes are timed, else the prediction."""
    order = [c for c in CHROMS if c in clock]
    if ends:
        done = order
    else:
        done = order[:-1]   # a chromosome is done when the next one starts
    if len(order) >= 2:
        t0, t1 = clock[order[0]], clock[order[-1]]
        span = sum(w[c] for c in (order[1:] if ends else order[:-1]))
        rate = (t1 - t0) / span if span else None   # seconds per whole pass
        if rate:
            left = sum(w[c] for c in CHROMS if c not in done) * rate - (now_t - t1)
            return max(left, 0.03 * rate), rate / predicted if predicted else 1
    elapsed = now_t - (started or now_t)
    return max(predicted - elapsed, 0.1 * predicted), 1


def eta(s, pl):
    """Seconds left for a running run."""
    now_t = time.time()
    left = 0.0
    for st in s["stages"]:
        if st["state"] == "done" or (st["id"] == "impute" and s.get("lite")):
            continue
        k = st["id"]
        if st["state"] != "running":
            left += pl[k] if k != "impute" else pl["impute"]
            continue
        started = datetime.datetime.fromisoformat(st["started"]).timestamp() if st.get("started") else now_t
        if k == "impute":
            f = s.get("facts", {}).get("impute", {})
            w = _weights(s)
            part = f.get("part")
            if part == "validate":
                v, scale = _pass_left(f.get("vclock", {}), w, now_t, pl["beagle"], f.get("vstart"), True)
                left += v + pl["beagle"] * scale + pl["write"]
            elif part == "run" and f.get("phase") == "write":
                left += max(pl["write"] - (now_t - (f.get("wstart") or now_t)), 0.1 * pl["write"])
            elif part == "run":
                v, scale = _pass_left(f.get("rclock", {}), w, now_t, pl["beagle"], f.get("rstart"), False)
                left += v + pl["write"]
            else:
                left += max(pl["impute"] - (now_t - started), 0.1 * pl["impute"])
        elif k == "analyse":
            fa = s.get("facts", {}).get("analyse", {})
            done = st.get("steps_done", [])
            per = lambda step: pl["steps"].get(step, pl["analyse"] / len(STEPS))
            for step, _ in STEPS:
                if step in done:
                    continue
                if step == fa.get("current") and fa.get("step_started"):
                    left += max(per(step) - (now_t - fa["step_started"]), 0.1 * per(step))
                else:
                    left += per(step)
        else:
            left += max(pl[k] - (now_t - started), 0.1 * pl[k])
    return round(left)


# --- inspecting a file ----------------------------------------------------------------------------------------------

def inspect(path):
    """What the dialog shows before a run: the format, the number of calls per chromosome, sex from the X chromosome."""
    from genome import formats
    from genome.loader import person_label
    from cluster_analysis.profiles import PAR
    fmt = formats.detect(path)
    n = nocall = 0
    per = {}
    het = xn = 0
    for rsid, chrom, pos, gt in formats.rows(path):
        n += 1
        if not gt or "-" in gt or "0" in gt:
            nocall += 1
            continue
        per[chrom] = per.get(chrom, 0) + 1
        if chrom == "X" and pos is not None and not any(a <= pos <= b for a, b in PAR) and len(gt) == 2:
            xn += 1
            het += gt[0] != gt[1]
    h = het / xn if xn >= 1000 else None   # a raw file has ~15,000 X calls; too few say nothing about sex
    sex = None if h is None else "female" if h > 0.05 else "male"
    problems = []
    if fmt == "imputed":
        problems.append("This is an already imputed file; choose the raw file from the DNA test.")
    elif fmt not in ("myheritage", "ancestry", "23andme"):
        problems.append("The format isn't recognised: MyHeritage, AncestryDNA and 23andMe raw files are supported.")
    if n and n - nocall < 100_000:
        problems.append(f"Only {n - nocall:,} calls: a raw file from a DNA test has around 600,000.")
    if sex is None:
        problems.append("No X chromosome calls, so sex can't be read from the DNA; choose it below.")
    return {"file": os.path.basename(path), "format": fmt, "calls": n, "called": n - nocall, "chromosomes": per,
            "x_heterozygosity": None if h is None else round(h, 4), "sex": sex, "suggested_id": suggest_id(person_label(path)),
            "problems": problems}


def profiles():
    return json.load(open(PROFILES, encoding="utf-8"))["profiles"]


def suggest_id(name):
    base = re.sub(r"[^A-Za-z0-9_-]", "_", name or "person").strip("_-")[:28] or "person"
    taken = {p["id"] for p in profiles()}
    if base not in taken:
        return base
    i = 2
    while f"{base}_{i}" in taken:
        i += 1
    return f"{base}_{i}"


# --- the state file -------------------------------------------------------------------------------------------------

class Run:
    def __init__(self, pid):
        os.makedirs(STATE_DIR, exist_ok=True)
        self.path = os.path.join(STATE_DIR, pid + ".json")
        self.log_path = os.path.join(STATE_DIR, pid + ".log")
        self.s = None
        if os.path.exists(self.path):
            with open(self.path, encoding="utf-8") as f:
                self.s = json.load(f)

    def new(self, pid, src, sex):
        stages = [{"id": "check", "label": "Checking the file"}, {"id": "register", "label": "Adding the person"},
                  {"id": "impute", "label": "Imputation",
                   "parts": [f"check chr{c}" for c in CHROMS] + [f"chr{c}" for c in CHROMS] + ["finalize"]},
                  {"id": "analyse", "label": "Analysis", "parts": [s for s, _ in STEPS]},
                  {"id": "explorer", "label": "Loading into the explorer", "parts": ["export", "build"]}]
        for st in stages:
            st.update(state="pending", done_parts=0, detail="", started=None, ended=None)
        self.s = {"id": pid, "source": os.path.basename(src), "src": os.path.abspath(src), "sex": sex, "state": "running", "started": now(),
                  "updated": now(), "ended": None, "progress": 0.0, "error": None, "pid": os.getpid(), "stages": stages,
                  "facts": {"check": {}, "impute": {}, "analyse": {}, "explorer": {}}}
        self.save()

    def facts(self, sid):
        """What a stage has found so far, for the dialog's pictures: numbers read from the tools' own output."""
        return self.s.setdefault("facts", {}).setdefault(sid, {})

    def stage(self, sid):
        return next(st for st in self.s["stages"] if st["id"] == sid)

    def save(self):
        done = 0.0
        for st in self.s["stages"]:
            w = WEIGHT[st["id"]]
            if st["state"] == "done":
                done += w
            elif st["state"] == "running" and st.get("parts"):
                done += w * st["done_parts"] / len(st["parts"])
        self.s["progress"] = round(min(done, 1.0), 4)
        self.s["updated"] = now()
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.s, f, ensure_ascii=False, indent=1)
        # Windows refuses to replace a file another process has open (the server reading the status): try again shortly
        for i in range(20):
            try:
                os.replace(tmp, self.path)
                return
            except PermissionError:
                time.sleep(0.05 * (i + 1))
        os.replace(tmp, self.path)

    def log(self, line):
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(line.rstrip("\n") + "\n")

    def begin(self, sid, detail=""):
        st = self.stage(sid)
        st.update(state="running", detail=detail, started=st["started"] or now())
        self.save()

    def finish(self, sid, detail=None):
        st = self.stage(sid)
        st.update(state="done", ended=now())
        if st.get("parts"):
            st["done_parts"] = len(st["parts"])
        if detail is not None:
            st["detail"] = detail
        self.save()

    def fail(self, sid, message):
        if sid:
            self.stage(sid).update(state="failed", ended=now())
        self.s.update(state="failed", error=message, ended=now())
        self.save()


def stream(run, sid, cmd, on_line=None):
    """Runs a command, its output to the log; on_line sees each line (for progress). Raises on a non-zero exit."""
    run.log(f"$ {' '.join(cmd)}")
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"}
    p = subprocess.Popen(cmd, cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                         encoding="utf-8", errors="replace", bufsize=1)
    tail = []
    for line in p.stdout:
        run.log(line)
        tail = (tail + [line.rstrip()])[-12:]
        if on_line:
            on_line(line)
    if p.wait():
        raise RuntimeError("\n".join(tail[-6:]) or f"{cmd[2] if len(cmd) > 2 else cmd[0]} stopped with code {p.returncode}")


# --- the stages -----------------------------------------------------------------------------------------------------

def imputation_problems():
    """What stops imputation on this machine (Java, Beagle, the panel); empty when it can run. Lite mode needs none."""
    from genome import impute
    problems = []
    if shutil.which("java") is None:
        problems.append("Java isn't installed: imputation runs Beagle, which needs Java 11 or newer.")
    if not os.path.exists(os.path.join(impute.REF, "beagle.jar")):
        problems.append("Beagle is missing (data/reference/imputation/beagle.jar).")
    P = impute.panel(gbuild.panel_name())
    if not os.path.isdir(P["dir"]):
        problems.append(f"The reference panel ({P['label']}, about 14 GB) isn't on this computer.")
    return problems


def preflight(src, lite=False):
    from genome import impute
    problems = []
    if lite:
        free = shutil.disk_usage(ROOT).free / 1e9
        return [f"Only {free:.1f} GB free on {os.path.splitdrive(ROOT)[0] or ROOT}; a person needs about 1 GB."] if free < 1 else []
    if shutil.which("java") is None:
        problems.append("Java isn't installed: imputation runs Beagle, which needs Java 11 or newer.")
    if not os.path.exists(os.path.join(impute.REF, "beagle.jar")):
        problems.append("Beagle is missing (data/reference/imputation/beagle.jar): run scripts/fetch_imputation_reference.sh.")
    P = impute.panel(gbuild.panel_name())
    if not os.path.isdir(P["dir"]):
        problems.append(f"The reference panel ({P['label']}) isn't at {P['dir']}: is the disk connected?")
    for where in {ROOT, P["dir"]} if os.path.isdir(P["dir"]) else {ROOT}:
        free = shutil.disk_usage(where).free / 1e9
        if free < FREE_GB:
            problems.append(f"Only {free:.1f} GB free on {os.path.splitdrive(where)[0] or where}; a person needs about {FREE_GB} GB.")
    return problems


def add(src, pid, sex=None, lite=False):
    """lite: the measured variants only, no imputation (minutes instead of an hour; no Java, panel or large memory).
    The imputation can be added later by adding the person again without it."""
    run = Run(pid)
    if run.s and run.s["state"] == "running" and pid_alive(run.s.get("pid")):
        raise SystemExit(f"{pid} is already being added")
    if not (run.s and run.s["state"] in ("failed", "cancelled")):
        run.new(pid, src, sex)
        run.s["lite"] = bool(lite)
    else:  # resume: the stages done stay done, in the mode the run started in
        lite = run.s.get("lite", False)
        run.s.update(state="running", error=None, ended=None, pid=os.getpid())
        for st in run.s["stages"]:
            if st["state"] in ("failed", "running"):
                st["state"] = "pending"
        run.save()
    run.log(f"--- {now()} {'resumed' if run.s['started'] != run.s['updated'] else 'started'}: {pid} from {src}")
    sid = None
    try:
        # check
        sid = "check"
        if run.stage(sid)["state"] != "done":
            run.begin(sid, "Reading the file")
            info = inspect(src)
            run.log(json.dumps({k: v for k, v in info.items() if k != "chromosomes"}))
            hard = [p for p in info["problems"] if not p.startswith("No X chromosome")]
            if hard:
                raise RuntimeError(hard[0])
            sex = info["sex"] or sex   # the X chromosome decides when it can; the dialog asks only when it can't
            if sex not in ("female", "male"):
                raise RuntimeError("Sex couldn't be read from the DNA; choose it in the dialog.")
            pre = preflight(src, lite)
            if pre:
                raise RuntimeError(pre[0])
            run.s["sex"] = sex
            run.facts("check").update({k: info[k] for k in ("format", "calls", "called", "chromosomes", "x_heterozygosity")}, sex=sex)
            names = {"myheritage": "MyHeritage", "ancestry": "AncestryDNA", "23andme": "23andMe"}
            run.finish(sid, f"{names.get(info['format'], info['format'])}, {info['called']:,} calls, {sex}")
        sex = run.s["sex"]
        # register
        sid = "register"
        dest = os.path.join(INPUT, pid + re.search(r"(\.(csv|txt|tsv))?(\.(gz|zip))?$", os.path.basename(src), re.I).group(0).lower())
        if run.stage(sid)["state"] != "done":
            run.begin(sid)
            if os.path.abspath(src) != os.path.abspath(dest):
                shutil.copyfile(src, dest)
            register(pid, sex, os.path.relpath(dest, ROOT).replace(os.sep, "/"), lite)
            if os.path.abspath(src).startswith(os.path.join(STATE_DIR, "uploads")):
                shutil.rmtree(os.path.dirname(os.path.abspath(src)), ignore_errors=True)
            run.finish(sid, os.path.relpath(dest, ROOT).replace(os.sep, "/"))
        # impute
        sid = "impute"
        st = run.stage(sid)
        if st["state"] != "done" and lite:
            # No imputation: the measured calls moved to the analysis build (genome/lite.py), under a minute
            run.begin(sid, "Moving the measured calls to the analysis build")
            f = run.facts("impute")
            f["skipped"] = True

            def on_lite(line):
                m = re.match(r"([\d,]+) measured calls written", line)
                if m:
                    f["measured"] = num(m.group(1))
                m = re.match(r"([\d,]+) calls couldn't be moved to", line)
                if m:
                    f["lost"] = num(m.group(1))
            stream(run, sid, [sys.executable, "-m", "genome.lite", dest], on_lite)
            run.finish(sid, "Measured variants only")
        if st["state"] != "done":
            from genome import impute
            P = impute.panel(gbuild.panel_name())
            out = os.path.join(impute.OUT, pid) if P["name"] == impute.DEFAULT_PANEL else os.path.join(impute.OUT, pid, P["name"])
            n = len(CHROMS)
            f = run.facts("impute")
            m = machine()
            beagle_args = ["--threads", str(m["beagle_threads"]), "--memory", f"{m['beagle_heap_gb']}g"]
            f["machine"] = {k: m[k] for k in ("cpu", "cores", "threads", "ghz", "ram_gb", "beagle_threads", "beagle_heap_gb", "eff")}
            ph = f.setdefault("phases", {})
            # 1. How well imputation works for this person: every 10th measured SNP hidden and imputed back
            #    (calibration.json, which the confidence tiers come from)
            if not os.path.exists(os.path.join(out, "calibration.json")):
                run.begin(sid, "Measuring accuracy: starting Beagle")
                f.update(part="validate", vstart=time.time(), vclock={})

                def on_validate(line):
                    if line.startswith("Reading the 1000 Genomes site list"):
                        st["detail"] = "Matching the file to the reference panel (a few minutes)"
                        f["phase"] = "sites"
                        run.save()
                    m = re.match(r"chr(\w+): ([\d,]+)/([\d,]+) hidden calls recovered", line)
                    if m:
                        f["phase"] = "validate"
                        f.setdefault("hidden", {})[m.group(1)] = [num(m.group(2)), num(m.group(3))]
                        f["vclock"][m.group(1)] = round(time.time(), 1)
                        st["done_parts"] = CHROMS.index(m.group(1)) + 1
                        st["detail"] = f"Measuring accuracy: chromosome {m.group(1)} done ({st['done_parts']} of {n})"
                        run.save()
                stream(run, sid, [sys.executable, "-m", "genome.impute", dest, "--validate", "10", *beagle_args], on_validate)
                ph["validate"] = round(time.time() - f["vstart"])
            # 2. The imputation itself, then the confidence-tiered CSV
            st["done_parts"] = n
            run.begin(sid, "Imputing: starting Beagle")
            f.update(part="run", rstart=time.time(), rclock={})

            def on_impute(line):
                if line.startswith("Reading the 1000 Genomes site list"):
                    st["detail"] = "Matching the file to the reference panel (a few minutes)"
                    f["phase"] = "sites"
                    run.save()
                m = re.match(r"([\d,]+) calls couldn't be moved to", line)
                if m:
                    f["lost"] = num(m.group(1))
                m = re.match(r"chr(\w+): ([\d,]+) imputed calls kept", line)
                if m:
                    f.setdefault("kept", {})[m.group(1)] = num(m.group(2))
                    run.save()
                m = re.match(r"\s*(not_excluded|high|medium|low|untested):\s+([\d,]+) / ([\d,]+)", line)
                if m:
                    f.setdefault("tiers", {})[m.group(1)] = [num(m.group(2)), num(m.group(3))]
                    run.save()
                m = re.match(r"chr(\w+): ([\d,]+) of ([\d,]+) calls match the panel; imputing", line)
                if m:
                    f["phase"], f["current"] = "impute", m.group(1)
                    f["rclock"][m.group(1)] = round(time.time(), 1)
                    f.setdefault("matched", {})[m.group(1)] = [num(m.group(2)), num(m.group(3))]
                    st["done_parts"] = n + CHROMS.index(m.group(1))
                    st["detail"] = f"Imputing chromosome {m.group(1)} ({CHROMS.index(m.group(1)) + 1} of {n})"
                    run.save()
                elif line.startswith("Variants ClinVar and ClinPGx") or line.startswith("Looking up allele"):
                    st["done_parts"] = 2 * n
                    if f.get("phase") != "write":
                        f["wstart"] = time.time()
                    f["phase"], f["current"] = "write", None
                    st["detail"] = "Writing the imputed file with confidence tiers"
                    run.save()
            stream(run, sid, [sys.executable, "-m", "genome.impute", dest, *beagle_args], on_impute)
            end = time.time()
            first = f["rclock"].get(CHROMS[0])
            if first and f.get("wstart"):
                ph["beagle"] = round(f["wstart"] - first)
                ph["write"] = round(end - f["wstart"] + (first - f["rstart"]))
            f["phase"] = "done"
            run.finish(sid, "Done")
        # analyse
        sid = "analyse"
        st = run.stage(sid)
        if st["state"] != "done":
            run.begin(sid)
            done = st.get("steps_done", [])
            for i, (step, label) in enumerate(STEPS):
                if step in done:
                    continue
                st["done_parts"], st["detail"] = i, f"{label} ({i + 1} of {len(STEPS)})"
                run.save()
                fa = run.facts("analyse")
                fa["current"], fa["step_started"] = step, time.time()
                sf = fa.setdefault(step, {})
                sf.clear()
                stream(run, sid, [sys.executable, "-m", "cluster_analysis.profiles", "run", "--person", pid, "--steps", step],
                       lambda line, sf=sf: read_step(line, sf) and run.save())
                fa.setdefault("step_times", {})[step] = round(time.time() - fa["step_started"])
                done.append(step)
                st["steps_done"] = done
                run.save()
            run.facts("analyse")["current"] = None
            run.finish(sid, "Done")
        # explorer
        sid = "explorer"
        st = run.stage(sid)
        if st["state"] != "done":
            run.begin(sid, "Writing the datasets")
            fe = run.facts("explorer")
            fe.update(datasets=0, rows=0)

            def on_export(line):
                m = re.match(r"\W*Wrote (\w+)\.json \((\d+) rows\)", line)
                if m:
                    fe["datasets"] += 1
                    fe["rows"] += int(m.group(2))
                    run.save()
            stream(run, sid, [sys.executable, "-m", "cluster_analysis.explorer", "export"], on_export)
            st["done_parts"], st["detail"] = 1, "Rebuilding the page"
            run.save()
            stream(run, sid, [sys.executable, "-m", "cluster_analysis.explorer", "site"])
            run.finish(sid, "Done")
        run.s.update(state="done", ended=now())
        run.save()
        record_timings(run.s)
        run.log(f"--- {now()} done")
    except KeyboardInterrupt:
        run.s.update(state="cancelled", ended=now())
        run.save()
        raise
    except Exception as e:
        run.log(f"!!! {e}")
        run.fail(sid, str(e))
        raise SystemExit(f"{pid}: {e}")


def num(s):
    return int(s.replace(",", ""))


# The research sources a step's output names, as the dialog's source chips show them (docs/architecture/sources.md)
SOURCES = [("GWAS Catalog", "GWAS Catalog"), ("Reactome", "Reactome"), ("ClinVar", "ClinVar"), ("ClinPGx", "ClinPGx"),
           ("1000 Genomes", "1000 Genomes"), ("Ensembl VEP", "Ensembl VEP"), ("GTEx", "GTEx"), ("UniProt", "UniProt"),
           ("STRING", "STRING"), ("Europe PMC", "Europe PMC"), ("CPIC", "CPIC"), ("DPWG", "DPWG"), ("drug label", "Drug labels"),
           ("PGS Catalog", "PGS Catalog")]
THEME_NAMES = {}


def theme_name(tid):
    if not THEME_NAMES:
        import glob
        for p in glob.glob(os.path.join(ROOT, "cluster_analysis", "themes", "theme_graph_*.json")):
            d = json.load(open(p, encoding="utf-8"))
            THEME_NAMES[d.get("theme") or os.path.basename(p)[12:-5]] = d.get("name")
    return THEME_NAMES.get(tid) or tid


def read_step(line, f):
    """Numbers an analysis step prints (profiles.py run's tools), into the step's facts. True when something changed."""
    import ast
    line = line.rstrip()
    changed = False
    for key, name in SOURCES:
        if key in line and name not in f.setdefault("sources", []):
            f["sources"].append(name)
            changed = True
    m = re.match(r"== \S+: \S*theme_graph (\w+)", line)
    if m:
        f.setdefault("themes", []).append({"id": m.group(1), "name": theme_name(m.group(1))})
        return True
    m = re.match(r"\s*(\d+) genes: (\d+) with a mechanism", line)
    if m and f.get("themes"):
        f["themes"][-1]["theme_genes"] = int(m.group(1))
        return True
    m = re.search(r"(\d+) SNPs of the file fall in theme genes; (\d+) have a .* finding, in (\d+) genes", line)
    if m and f.get("themes"):
        f["themes"][-1].update(snps=int(m.group(1)), findings=int(m.group(2)), genes=int(m.group(3)))
        return True
    m = re.match(r"(\d+) genes: UniProt", line)
    if m:
        f.update(genes=int(m.group(1)), read=0)
        return True
    m = re.match(r"\s+(\d+)/(\d+)$", line)
    if m:
        f["read"] = int(m.group(1))
        return True
    m = re.match(r"Reading ([\d,]+) (?:variants|SNPs) from", line)
    if m:
        f["variants"] = num(m.group(1))
        return True
    m = re.match(r"Done \S+: (\{.*\}) ->", line)
    if m:
        f.update(calls=ast.literal_eval(m.group(1)), read=f.get("genes"))
        return True
    m = re.search(r"(\d+) genes read, (\d+) changed in a system, (\d+) systems, (\d+) STRING pairs", line)
    if m:
        f.update(read=int(m.group(1)), changed=int(m.group(2)), systems=int(m.group(3)), pairs=int(m.group(4)))
        f.setdefault("sources", []).extend(n for n in ("Reactome", "STRING") if n not in f["sources"])  # its systems are Reactome's
        return True
    m = re.search(r"(\d+) drug genes, (\d+) drug annotations \((\d+) guideline-level", line)
    if m:
        f.update(drug_genes=int(m.group(1)), annotations=int(m.group(2)), differs=int(m.group(3)))
        return True
    m = re.match(r"   ([A-Z][A-Z0-9]+)\s+(\S+/\S+)\s+(.+)$", line)
    if m:
        f.setdefault("diplotypes", []).append([m.group(1), m.group(2), m.group(3)])
        return True
    m = re.match(r"\s*(\d+) guidelines:", line)
    if m:
        f["guidelines"] = int(m.group(1))
        return True
    m = re.match(r"\s*(\d+) drug labels:", line)
    if m:
        f["labels"] = int(m.group(1))
        return True
    m = re.match(r"wrote .*[/\\](\w+?)_(nutrients|tests|findings|steps)\.json: (\d+) rows", line)
    if m:
        f[m.group(2)] = int(m.group(3))
        return True
    m = re.search(r"sport_snps\.json: (\d+) variants", line)
    if m:
        f["sport_snps"] = int(m.group(1))
        return True
    return changed


def leftovers(pid):
    """Everything a run for pid writes, by exact name (a pattern like theme_XY_* would also catch XY_1's files), in the
    current build only: the input copy, the imputation, the site cache, the analysis outputs, the run's state and log."""
    from genome import impute
    entry = next((p for p in profiles() if p["id"] == pid), None)
    paths = []
    if entry and entry.get("dna"):
        dna = os.path.abspath(os.path.join(ROOT, entry["dna"]))
        if os.path.dirname(dna) == os.path.abspath(INPUT) and os.path.basename(dna).split(".")[0] == pid:
            paths.append(dna)
    paths.append(os.path.join(impute.OUT, pid))
    paths += [os.path.join(impute.REF, f"sites_{pid}.tsv.gz")] + [os.path.join(impute.REF, f"sites_{pid}_{n}.tsv.gz") for n in impute.PANELS]
    out = os.path.join(ROOT, gbuild.OUTPUT)
    theme_name("")
    paths += [os.path.join(out, f"gene_calls_{pid}.json"), os.path.join(out, "profiles", pid)]
    paths += [os.path.join(out, f"theme_{pid}_{t}.json") for t in THEME_NAMES]
    run = Run(pid)
    paths += [run.path, run.log_path]
    src = (run.s or {}).get("src") or ""
    if os.path.abspath(src).startswith(os.path.join(STATE_DIR, "uploads") + os.sep):
        paths.append(os.path.dirname(os.path.abspath(src)))
    return entry, [p for p in paths if os.path.exists(p)]


def abandon(pid, force=False):
    """Removes a person whose run didn't finish: every file the run made and the profile entry. A finished person is
    kept (its run is only dismissed); force is for an unfinished person whose run record is already gone."""
    run = Run(pid)
    entry = next((p for p in profiles() if p["id"] == pid), None)
    if run.s and run.s["state"] == "running" and pid_alive(run.s.get("pid")):
        raise ValueError(f"{pid} is still running; stop it first.")
    if run.s and run.s["state"] == "done":
        raise ValueError(f"{pid} was added in full; a finished person isn't removed this way.")
    if not run.s and not (force and entry and entry.get("added")):
        raise ValueError(f"No unfinished run for {pid}.")
    if not run.s and os.path.isdir(os.path.join(ROOT, gbuild.OUTPUT, "profiles", pid)):
        raise ValueError(f"{pid} has analysis results; without its run record it isn't removed this way.")
    entry, paths = leftovers(pid)
    for p in paths:
        for attempt in range(10):   # Beagle (java) can hold its files for a moment after it is stopped
            try:
                shutil.rmtree(p) if os.path.isdir(p) else os.remove(p)
                break
            except FileNotFoundError:
                break
            except OSError:
                if attempt == 9:
                    raise
                time.sleep(1)
    if entry:
        unregister(pid)
    from cluster_analysis.explorer.__main__ import DATASETS
    shown = os.path.join(DATASETS, "profiles.json")
    try:
        rebuild = any(r.get("id") == pid for r in json.load(open(shown, encoding="utf-8")))
    except (OSError, ValueError):
        rebuild = False
    return {"removed": [os.path.relpath(p, ROOT).replace(os.sep, "/") for p in paths], "profile": bool(entry), "rebuild": rebuild}


def rebuild_explorer():
    for cmd in (["export"], ["site"]):
        subprocess.run([sys.executable, "-m", "cluster_analysis.explorer", *cmd], cwd=ROOT, check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def unregister(pid):
    raw = open(PROFILES, "rb").read().decode()
    data = json.loads(raw)
    _write_profiles(raw, data, [p for p in data["profiles"] if p["id"] != pid])


def _write_profiles(raw, data, rows):
    # one profile per line, as the file is written by hand
    body = ",\n".join("    " + json.dumps(p, ensure_ascii=False) for p in rows)
    out = "{\n  \"about\": " + json.dumps(data["about"], ensure_ascii=False) + ",\n  \"profiles\": [\n" + body + "\n  ]\n}\n"
    if "\r\n" in raw:
        out = out.replace("\n", "\r\n")
    open(PROFILES, "wb").write(out.encode())


def register(pid, sex, dna, lite=False):
    raw = open(PROFILES, "rb").read().decode()
    data = json.loads(raw)
    row = {"id": pid, "sex": sex, "dna": dna, "added": now()[:10], **({"lite": True} if lite else {})}
    _write_profiles(raw, data, [p for p in data["profiles"] if p["id"] != pid] + [row])


def record_timings(s):
    """How long each stage took, so the next run's estimate is real (kept per machine)."""
    path = os.path.join(STATE_DIR, "timings.json")
    t = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {}
    for st in s["stages"]:
        if st["started"] and st["ended"]:
            sec = (datetime.datetime.fromisoformat(st["ended"]) - datetime.datetime.fromisoformat(st["started"])).total_seconds()
            t.setdefault(st["id"], []).append(round(sec))
            t[st["id"]] = t[st["id"]][-5:]
    f = s.get("facts", {})
    ph, mc = f.get("impute", {}).get("phases", {}), f.get("impute", {}).get("machine")
    if mc and all(k in ph for k in ("validate", "beagle", "write")):
        t.setdefault("impute_runs", []).append({**{k: mc[k] for k in ("cpu", "eff", "ghz", "beagle_threads")}, **ph})
        t["impute_runs"] = t["impute_runs"][-10:]
    for step, sec in f.get("analyse", {}).get("step_times", {}).items():
        t.setdefault("analyse_steps", {}).setdefault(step, []).append(sec)
        t["analyse_steps"][step] = t["analyse_steps"][step][-5:]
    json.dump(t, open(path, "w", encoding="utf-8"), indent=1)


def pid_alive(pid):
    if not pid:
        return False
    try:
        import psutil
        return psutil.pid_exists(pid) and "python" in psutil.Process(pid).name().lower()
    except Exception:
        return False


def status():
    """Every run, newest first; a run marked running whose process is gone is shown as stopped."""
    out = []
    if os.path.isdir(STATE_DIR):
        for f in os.listdir(STATE_DIR):
            if f.endswith(".json") and f != "timings.json":
                try:
                    with open(os.path.join(STATE_DIR, f), encoding="utf-8") as fh:
                        s = json.load(fh)
                except (OSError, json.JSONDecodeError):
                    continue
                if s.get("state") == "running" and not pid_alive(s.get("pid")):
                    s["state"], s["error"] = "failed", s.get("error") or "The run stopped (the computer or server was restarted). Resume it to continue."
                out.append(s)
    m = machine()
    pl = plan(m)
    for s in out:
        if s.get("state") == "running":
            needs = not any(st["id"] == "impute" and st["state"] == "done" for st in s["stages"]) and \
                "validate" in (s.get("facts", {}).get("impute", {}).get("part") or "validate")
            s["eta"] = eta(s, plan(m, validate=needs))
    return {"runs": sorted(out, key=lambda s: s.get("started") or "", reverse=True), "machine": m, "plan": pl,
            "imputation": {"problems": imputation_problems()},
            "typical": {k: pl[k] for k in ("check", "register", "impute", "analyse", "explorer")}}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=("inspect", "add", "status", "machine", "abandon", "rebuild"))
    ap.add_argument("--force", action="store_true", help="abandon: also when the run record is gone (an unfinished, pipeline-added person)")
    ap.add_argument("file", nargs="?")
    ap.add_argument("--id")
    ap.add_argument("--sex", choices=("female", "male"))
    ap.add_argument("--lite", action="store_true", help="add: measured variants only, no imputation")
    a = ap.parse_args()
    if a.command == "inspect":
        print(json.dumps(inspect(a.file), indent=1, ensure_ascii=False))
    elif a.command == "abandon":
        pid = a.file
        r = abandon(pid, force=a.force)
        print(json.dumps(r, indent=1))
        if r["rebuild"]:
            rebuild_explorer()
    elif a.command == "rebuild":
        rebuild_explorer()
    elif a.command == "machine":
        m = machine()
        print(json.dumps({"machine": m, "plan": plan(m)}, indent=1, ensure_ascii=False))
    elif a.command == "status":
        print(json.dumps(status(), indent=1, ensure_ascii=False))
    else:
        if not a.file or not a.id or not ID_RE.match(a.id):
            raise SystemExit("add needs FILE and --id (letters, digits, _ and -, up to 32)")
        add(a.file, a.id, a.sex, a.lite)
