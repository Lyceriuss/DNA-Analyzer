"""Genotype-specific findings from studies: the sentences that say what people with a given genotype got.

    morsels.for_variant("rs1815739", "ACTN3", "training")  ->  [{sentence, labels, numbers, pmid, title, type, year}]

For every well-known variant of a cluster (the whole public list, never chosen by the person's genotypes), Europe PMC
is searched for the variant with the cluster's words, the best abstracts are read, and only the sentences that name
a genotype group AND carry a number are kept: "XX homozygotes showed 20% greater gains", "TT genotype ... OR 2.55".
These are the same for everyone and cached.

apply() then runs on this machine: it turns the person's genotype into the labels papers use (CT and TC, the protein
letters RX for ACTN3 R577X, "T allele" carriers) and keeps the findings that name the person's own group. No model.
"""
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor

from cluster_analysis.agent import evidence

PKG = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AA = {"Ala": "A", "Arg": "R", "Asn": "N", "Asp": "D", "Cys": "C", "Gln": "Q", "Glu": "E", "Gly": "G", "His": "H", "Ile": "I",
      "Leu": "L", "Lys": "K", "Met": "M", "Phe": "F", "Pro": "P", "Ser": "S", "Thr": "T", "Trp": "W", "Tyr": "Y", "Val": "V"}
# Studies that report genotype groups: syntheses and primary studies over narrative reviews
WEIGHTS = {"meta-analysis": 3.0, "randomized controlled trial": 2.6, "systematic review": 1.8, "clinical trial": 2.2,
           "comparative study": 1.6, "journal article": 1.4, "review": 0.6}
EFFECT = re.compile(r"\b(higher|lower|greater|less|more|increase\w*|decrease\w*|reduc\w*|improv\w*|risk|protect\w*|"
                    r"benefit\w*|associated with|better|worse|gain\w*|response|responded)\b", re.I)
# How common a genotype is: not what the person asked (unless they did), so never a finding
DISTRIBUTION = re.compile(r"\b(distribution|frequenc\w*|prevalen\w*|hardy|were genotyped|genotyped for|proportion of|majority|"
                          r"observed as|\d+(?:\.\d+)?\s?% (?:had|carried|were|of)|% genotype|genotype \w{2} \(\d)", re.I)
# What a cluster's findings must be about: the outcome words of its field
TOPIC = {"muscle": re.compile(r"train\w*|exercis\w*|perform\w*|strength|power|endurance|muscl\w*|athlet\w*|injur\w*|recover\w*|"
                              r"vo2|sprint\w*|velocity|1rm|sport\w*|fatigue|damage|tendon\w*|ligament\w*|rupture|lean mass|creatine kinase", re.I)}
# A number that carries an effect: a percentage, a fold change, a ratio, a standardised difference
NUMBER = re.compile(r"(\d+(?:\.\d+)?\s?%|\d+(?:\.\d+)?[- ]?fold|\b(?:OR|HR|RR|SMD|MD|β|beta)\s?[=:]?\s?-?\d+(?:\.\d+)?|"
                    r"\d+(?:\.\d+)?\s?(?:kg|ml/kg/min|mL/kg/min|U/L|ng/mL|mmol/L|times))", re.I)
GROUP = re.compile(r"\b([ACGT]{2}|[A-Z]{2}|[ACGT]\s?allele|[A-Z]\s?allele|[A-Z]-allele|carriers?|homozygo\w+|heterozygo\w+|genotypes?)\b")
DOMAIN = {"muscle": "training OR exercise OR strength OR endurance OR athletes OR injury OR recovery OR muscle",
          "mind": "depression OR anxiety OR sleep OR mood OR cognition OR stress",
          "cancer": "cancer OR tumour OR risk",
          "fertility_female": "fertility OR pregnancy OR ovarian OR menstrual",
          "fertility_male": "fertility OR sperm OR testosterone"}
_PUBLIC = None


def variants(theme):
    """The public list of well-known variants of a cluster: the explorer's sport-variant list for Fitness, else the
    library variants whose gene is in the cluster (evidence/literature.json). Never the person's own."""
    if theme == "muscle":
        with open(os.path.join(PKG, "themes", "sport_snps.json"), encoding="utf-8") as f:
            return [(s["rsid"], s["gene"]) for s in json.load(f)["snps"]]
    path = os.path.join(PKG, "themes", f"theme_graph_{theme}.json")
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        genes = set(json.load(f)["genes"])
    with open(os.path.join(PKG, "evidence", "function_evidence.json"), encoding="utf-8") as f:
        fe = json.load(f)
    return [(x["rsid"], g) for x in fe for g in x.get("genes", [])[:1] if g in genes]


_GENES = {}


def _cluster_genes(theme):
    if theme not in _GENES:
        path = os.path.join(PKG, "themes", f"theme_graph_{theme}.json")
        _GENES[theme] = set()
        if theme and os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                _GENES[theme] = set(json.load(f)["genes"])
    return _GENES[theme]


def _sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+(?=[A-Z(])", text or "") if 30 <= len(s.strip()) <= 480]


def for_variant(rsid, gene, theme="muscle", dom=None, topic_re=None):
    """Sentences from the strongest papers on a variant that name a genotype group and a number. theme sets the
    search words and the outcome words a finding must use; dom and topic_re give them directly (a question's topic)."""
    dom = dom if dom is not None else DOMAIN.get(theme, "")
    q = f'("{rsid}" OR {gene}) AND (genotype OR polymorphism OR allele OR variant)' + (f" AND ({dom})" if dom else "")
    papers = evidence.search(q, size=50, read=15, boost=(gene,), weights=WEIGHTS)
    out = []
    for p in papers:
        text = p["title"] + " " + p["abstract"]
        if gene.lower() not in text.lower() and rsid not in text:
            continue
        kind = next((t for t in WEIGHTS if t in p["types"]), "journal article")
        for s in _sentences(p["abstract"]):
            if evidence.NOISE.search(s):
                continue
            if DISTRIBUTION.search(s):
                continue
            # A sentence about another gene's genotype ("the CC genotype ... of IL-6") counts only if it names this one
            others = {x for x in re.findall(r"\b[A-Z][A-Z0-9]{1,7}(?:-\d+)?\b", s)
                      if re.search(r"\d", x) or "-" in x or x in _cluster_genes(theme)} - {gene, rsid.upper()}
            if others and gene.lower() not in s.lower() and rsid not in s:
                continue
            # ... and one that names another variant is about that variant
            if set(re.findall(r"\brs\d+\b", s)) - {rsid}:
                continue
            if re.search(r"\b(were|was) (used|applied|performed|assessed|measured|calculated)\b|\bmodel(l)?ing\b", s, re.I):
                continue
            # The 95% of a confidence interval is not an effect
            nums = [n for n in NUMBER.findall(s) if not re.fullmatch(r"9[05]\s?%", n.strip())]
            groups = [g for g in GROUP.findall(s) if g not in ("OR", "HR", "RR", "MD", "CI", "SD", "SE", "BMI", "UK", "US", "DNA", "RNA", "PCR")]
            # A genotype group with a number, or at least with the direction of an effect
            # A genotype group, the direction of an effect, and the field's own outcome (training, injury, ...)
            topic = topic_re or TOPIC.get(theme)
            if groups and EFFECT.search(s) and any(g not in ("genotype", "genotypes") for g in groups) \
                    and (topic is None or topic.search(s)):
                out.append({"rsid": rsid, "gene": gene, "sentence": s, "labels": groups, "numbers": nums, "pmid": p["pmid"],
                            "title": p["title"], "type": kind, "year": p["year"], "cited": p["cited"],
                            "url": f"https://europepmc.org/article/MED/{p['pmid']}"})
    return out


def cached(theme):
    """({rsid: [findings]}, [(rsid, gene) not researched yet]): only what earlier searches cached, so it is instant."""
    from cluster_analysis import sources
    import hashlib
    have, todo = {}, []
    for rs, gene in variants(theme):
        dom = DOMAIN.get(theme, "")
        q = f'("{rs}" OR {gene}) AND (genotype OR polymorphism OR allele OR variant)' + (f" AND ({dom})" if dom else "")
        key = json.dumps({"q": q, "size": 50, "read": 15, "boost": [gene], "w": WEIGHTS}, sort_keys=True)
        path = os.path.join(sources.CACHE_DIR, f"agent_evidence2_{hashlib.sha1(key.encode('utf-8')).hexdigest()[:16]}.json")
        if os.path.exists(path):
            have[rs] = for_variant(rs, gene, theme)
        else:
            todo.append((rs, gene))
    return have, todo


_RUNNING = set()


def prefetch(theme, workers=4):
    """Researches the cluster's variants not cached yet, in a background thread (one at a time per cluster)."""
    import threading
    if theme in _RUNNING:
        return False
    _RUNNING.add(theme)

    def work():
        try:
            research(theme, workers, only=cached(theme)[1])
        finally:
            _RUNNING.discard(theme)
    threading.Thread(target=work, daemon=True).start()
    return True


def research(theme, workers=6, only=None):
    """{rsid: [findings]} for every well-known variant of a cluster (cached per search)."""
    vs = only if only is not None else variants(theme)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        got = list(pool.map(lambda v: (v[0], _safe(v[0], v[1], theme)), vs))
    return {rs: m for rs, m in got if m}


def _safe(rsid, gene, theme):
    try:
        return for_variant(rsid, gene, theme)
    except Exception:
        return []


def labels(gt, ref, alt, amino=None):
    """The ways papers name a person's genotype: CT and TC, the protein letters (RX for ACTN3 R577X: R for the C allele,
    X for the stop), and "T allele" or "X allele" for each allele they carry."""
    if not gt or len(gt) != 2:
        return set()
    out = {gt, gt[::-1]}
    out |= {f"{a} allele" for a in set(gt)} | {f"{a}-allele" for a in set(gt)} | {f"{a}allele" for a in set(gt)}
    if amino and "/" in amino and ref and alt:
        r, a = amino.split("/", 1)
        conv = lambda x: "X" if x in ("*", "Ter") else AA.get(x, x if len(x) == 1 else None)
        r, a = conv(r), conv(a)
        if r and a and r != a:
            prot = "".join(r if b == ref else a if b == alt else "?" for b in gt)
            if "?" not in prot:
                out |= {prot, prot[::-1]} | {f"{x} allele" for x in set(prot)} | {f"{x}-allele" for x in set(prot)}
    return out


def apply(findings, gt, ref, alt, amino=None):
    """The findings that name the person's own genotype group, strongest first."""
    mine = labels(gt, ref, alt, amino)
    hits = []
    for m in findings:
        said = set(m["labels"])
        named = [x for x in said if x in mine]
        if not named:
            continue
        score = WEIGHTS.get(m["type"], 1) + (2.0 if m["numbers"] else 0) + 0.3 * len(m["numbers"]) + (0.3 if (m.get("year") or "0") >= "2015" else 0)
        hits.append({**m, "yours": sorted(named), "score": round(score, 2)})
    hits.sort(key=lambda m: -m["score"])
    return hits
