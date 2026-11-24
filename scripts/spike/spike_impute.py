"""Targeted-imputation spike, step 2 (chr22): a small Li-Stephens imputer on the reduced panel (spike_extract.py), the
kind a phone could run, scored against HG00096's true genotypes together with Beagle's output on the full and the
reduced panel (both without HG00096).
  python spike_impute.py [K] [WINDOW]"""
import gzip, os, sys, time
import numpy as np

D = r"D:\DNA-Analyzer-build\spike"
K = int(sys.argv[1]) if len(sys.argv) > 1 else 64
W = int(sys.argv[2]) if len(sys.argv) > 2 else 400
OV = W // 4
EPS = 0.01
RHO = 4e-4   # 4 Ne c per bp, Ne = 10,000, 1 cM/Mb

z = np.load(os.path.join(D, "panel.npz"))
pos, H, truth = z["pos"], z["H"], z["truth"].sum(1).astype(float)
ref, alt = z["ref"], z["alt"]
# The chip genotypes Beagle saw (target.vcf)
g_at = {}
for line in open(os.path.join(D, "target.vcf")):
    if line[0] == "#":
        continue
    c = line.rstrip("\n").split("\t")
    g_at[int(c[1])] = {"0/0": 0, "0/1": 1, "1/1": 2}[c[9]]
mk = np.array([p in g_at for p in pos])
M = np.where(mk)[0]
Tg = np.where(~mk)[0]
G = np.array([g_at[int(pos[i])] for i in M])
af = H.mean(1)
maf = np.minimum(af, 1 - af)
print(f"{len(M)} markers, {len(Tg)} targets, {H.shape[1]} reference haplotypes; K={K}, window {W}", flush=True)


def window_posteriors(mi, hk):
    """Forward-backward over the markers mi with the K haplotypes hk: the K x K state posterior at each marker."""
    n = len(mi)
    Hm = H[np.ix_(mi, hk)].astype(np.int8)            # n x K
    g = G[np.searchsorted(M, mi)]
    d = np.diff(pos[mi], prepend=pos[mi[0]]).astype(float)
    s = 1 - np.exp(-RHO * d / K)
    def emit(t):
        e = Hm[t][:, None] + Hm[t][None, :]
        return np.where(e == g[t], 1 - EPS, EPS)
    def step(a, t):
        st = s[t]
        row, col, tot = a.sum(1), a.sum(0), a.sum()
        return (1 - st) ** 2 * a + (1 - st) * st / K * (row[:, None] + col[None, :]) + st * st / K / K * tot
    fw = np.empty((n, K, K))
    a = emit(0); a /= a.sum(); fw[0] = a
    for t in range(1, n):
        a = step(a, t) * emit(t); a /= a.sum(); fw[t] = a
    post = np.empty_like(fw)
    b = np.ones((K, K)); post[-1] = fw[-1] / fw[-1].sum()
    for t in range(n - 2, -1, -1):
        be = b * emit(t + 1)
        st = s[t + 1]
        row, col, tot = be.sum(1), be.sum(0), be.sum()
        b = (1 - st) ** 2 * be + (1 - st) * st / K * (row[:, None] + col[None, :]) + st * st / K / K * tot
        b /= b.sum()
        p = fw[t] * b; post[t] = p / p.sum()
    return post


t0 = time.time()
dos = np.full(len(pos), np.nan)
starts = list(range(0, len(M), W - 2 * OV))
for wi, st in enumerate(starts):
    mi = M[st:st + W]
    if len(mi) < 10:
        continue
    # The K haplotypes that best match the person's homozygous calls in this window
    g = G[st:st + W]
    hom = g != 1
    mism = (np.abs(H[mi[hom]].astype(np.int8) * 2 - g[hom][:, None]) == 2).sum(0)
    hk = np.argsort(mism + np.random.default_rng(wi).random(H.shape[1]) * 0.1)[:K]
    post = window_posteriors(mi, hk)
    rows, cols = post.sum(2), post.sum(1)              # n x K each
    # This window's core: its markers less the overlaps (all of it at the chromosome's ends)
    last = st + W >= len(M) or wi == len(starts) - 1
    lo = pos[mi[min(OV, len(mi) - 1)]] if st > 0 else -1
    hi = pos[mi[-OV]] if not last and len(mi) > OV else 1 << 40
    for t in Tg[(pos[Tg] >= lo) & (pos[Tg] < hi)]:
        j = np.searchsorted(pos[mi], pos[t])
        if j == 0:
            w0, w1, j0, j1 = 1.0, 0.0, 0, 0
        elif j >= len(mi):
            w0, w1, j0, j1 = 1.0, 0.0, len(mi) - 1, len(mi) - 1
        else:
            j0, j1 = j - 1, j
            span = pos[mi[j1]] - pos[mi[j0]]
            w1 = (pos[t] - pos[mi[j0]]) / span if span else 0.5
            w0 = 1 - w1
        h = H[t, hk].astype(float)
        dos[t] = w0 * (rows[j0] + cols[j0]) @ h + w1 * (rows[j1] + cols[j1]) @ h
    if wi % 5 == 0:
        print(f"window {wi + 1}/{len(starts)}, {round(time.time() - t0)} s", flush=True)
print(f"prototype: {round(time.time() - t0)} s", flush=True)


def beagle(path):
    out = np.full(len(pos), np.nan)
    if not os.path.exists(path):
        return None
    idx = {int(p): i for i, p in enumerate(pos)}
    with gzip.open(path, "rt") as f:
        for line in f:
            if line[0] == "#":
                continue
            c = line.split("\t", 10)
            i = idx.get(int(c[1]))
            if i is None or c[3] != ref[i] or c[4] != alt[i]:
                continue
            fmt = c[8].split(":"); v = c[9].rstrip("\n").split(":")
            if "DS" in fmt:
                out[i] = float(v[fmt.index("DS")])
            else:
                gt = v[0].replace("|", "/").split("/"); out[i] = sum(int(x) for x in gt)
    return out


def score(name, d):
    if d is None:
        print(f"{name}: no output"); return
    print(f"\n{name}")
    print(f"{'MAF':>12} {'n':>7} {'concord':>8} {'r2':>6} {'carriers':>9} {'found':>6}")
    for lo_, hi_ in ((0, .001), (.001, .005), (.005, .01), (.01, .05), (.05, .51)):
        sel = (~mk) & ~np.isnan(d) & (maf >= lo_) & (maf < hi_)
        if not sel.any():
            continue
        dd, tt = d[sel], truth[sel]
        conc = (np.rint(dd) == tt).mean()
        r2 = np.corrcoef(dd, tt)[0, 1] ** 2 if tt.std() > 0 and dd.std() > 0 else float("nan")
        # the minor allele: carriers of it, and how many the call found
        minor = np.where(af[sel] <= 0.5, tt, 2 - tt) > 0
        found = (np.where(af[sel] <= 0.5, np.rint(dd), 2 - np.rint(dd)) > 0) & minor
        print(f"{lo_:>5}-{hi_:<6} {sel.sum():>7} {conc:>8.4f} {r2:>6.3f} {minor.sum():>9} {found.sum() / max(1, minor.sum()):>6.2f}")


score(f"prototype (K={K}, reduced panel)", dos)
score("Beagle, full panel without HG00096", beagle(os.path.join(D, "beagle_full.vcf.gz")))
score("Beagle, reduced panel without HG00096", beagle(os.path.join(D, "beagle_reduced.vcf.gz")))
