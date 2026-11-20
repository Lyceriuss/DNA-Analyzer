"""How Ask answers speak: in risk and evidence, never clinical advice (the user's rule, 2026-11-19).

The explorer says what a genotype means for a risk, an exposure or a response, and what the evidence shows. It never
tells the person what to do clinically: no "see a doctor", "ask for a test", "tell your pharmacist", no dose or drug
instruction, no "you should". A guideline's content is reported as a fact about the guideline ("the CPIC guideline
lists a lower starting dose for this group"), not as an instruction. Prevention is reported as risk factors ("tobacco
smoking is a known cause"), not as commands.

RULE goes into every prompt that writes text for the person; advice() finds what breaks it, so the explanation is sent
back to be rephrased (tools.t_answer) and readings that break it are not kept (categories.py, interpret.py).
"""
import re

RULE = ("Speak only in risk and evidence: what this genotype means for a risk, an exposure, a level or a response, and "
        "how strong the evidence is. Never give clinical advice: no 'see a doctor', 'ask for a test', 'tell your doctor or "
        "pharmacist', no dose or drug instruction, no 'you should', 'consider', 'avoid' or 'make sure'. Report a guideline "
        "as a fact about the guideline ('the CPIC guideline lists a lower starting dose for this group'), and prevention as "
        "risk factors ('tobacco smoking is a known cause'), never as an instruction.")

ADVICE = re.compile(
    r"\b(see|ask|tell|talk to|consult|speak (to|with)|check with|contact|visit|inform) (a |your )?(doctor|gp|physician|"
    r"pharmacist|clinician|healthcare|health care|specialist|prescriber)|"
    r"\b(get|ask for|request|have) (a |an |your )?(blood |lab |genetic |pharmacogenetic )?(test|tested|checked|screening|screened)\b|"
    r"\byou should\b|\byou may want to\b|\bit is (wise|advisable)\b|\bmake sure\b|\bwe recommend\b|"
    r"\b(consider|try) (taking|asking|getting|using|switching|reducing|avoiding|lowering)\b|"
    r"\b(do not|don't|never) (smoke|take|use|drink|exceed)\b|\bavoid (taking|using|drinking|smoking)\b|"
    r"\bstart (at|with|on) \d|\b(take|use) (no more than|the lowest)\b|\bsettles (it|them)\b", re.I)


# A sentence that starts as an instruction ("Test first.", "Re-test after 2-3 months", "- Avoid high doses")
IMPERATIVE = re.compile(r"^\W*(test|re-?test|avoid|take|start|stop|adjust|increase|reduce|lower|raise|supplement|use|"
                        r"ask|check|limit|keep|choose|switch|aim|eat|drink|get|seek|monitor|discuss|follow|skip)\b", re.I)
# A dose or threshold given as what to do, not attributed to a guideline or a study
DOSE = re.compile(r"\b\d[\d.,–-]*\s?(iu|mg|µg|mcg|g)\b(?:\s?(a|per) day|\s?daily|/day)?", re.I)
ATTRIBUTED = re.compile(r"guideline|cpic|dpwg|label|nnr|recommendation|study|trial|meta-analys|participants|patients|"
                        r"group|arm|cohort|were given|received", re.I)
DECIDING = re.compile(r"\b(is|are) (reasonable|indicated|clearly indicated|advisable|sensible|a (good|common|low-risk) choice)\b|"
                      r"\bpractical approach\b|\bwhat to do\b|\bthe real decision-maker\b", re.I)


# --- Ranks (the user's rule, 2026-11-20) --------------------------------------------------------------------------
# Where a person's score ranks is said only when the question asks for it, and it comes last: it is context, not the
# answer. "Top" is the favourable end and "bottom" the unfavourable one, so a low genetic risk is "top 3%" and a high
# one "bottom 2%" (a "3rd percentile" reads like a race placing). A score with no better side: "highest/lowest X%".

RANK_RULE = ("Don't say where the person's scores rank (percentiles, top or bottom X%) unless the question asks how they "
             "rank, score or compare. When it does, use the result's rank as given: 'top X%' is the favourable end and "
             "'bottom X%' the unfavourable one (a low risk is 'top 3%', a high risk 'bottom 2%'), never 'the 95th "
             "percentile', put it after the findings, and say which of the person's variants put the score there (they "
             "are in the result's details). Unless asked, the person's scores (favourable, lowered) are context: at most "
             "one sentence, at the end of the summary, and the last section of the explanation, never the first.")
ASKED = re.compile(r"percentil|\brank|\bscor(e|es|ing)\b|compar|\btop\b|\bbottom\b|where do i (stand|rank|fall)|how (high|low)|"
                   r"\bodds\b|\brisk\b|prone|likely|chance", re.I)
ORDINAL = re.compile(r"\b\d{1,3}(st|nd|rd|th)\s+(percentile|centile)\b|\bpercentiles?\b|^\s*\d{1,3}(st|nd|rd|th)\s*$", re.I)
PERSONAL_RANK = re.compile(r"\b(you|your|you're|yours)\b[^.!?]{0,80}\b(top|bottom|highest|lowest)\s+\d{1,2}\s?%|"
                           r"\b(top|bottom)\s+\d{1,2}\s?%[^.!?]{0,40}\b(you|your)\b", re.I)


def rank_words(p, higher="better"):
    """A percentile as people read it, top being the favourable end: higher better, 95 -> 'top 5%', 19 -> 'bottom 19%';
    higher worse (a risk), 3 -> 'top 3%', 98 -> 'bottom 2%'; no better side, 'highest 5%' / 'lowest 3%'; 40-60 'around
    the middle'."""
    p = round(p)
    if 40 < p < 60:
        return "normal (near the European baseline)"
    high = p >= 60
    share = max(100 - p, 1) if high else max(p, 1)
    if higher not in ("better", "worse"):
        return f"{'highest' if high else 'lowest'} {share}%"
    good = high == (higher == "better")
    return f"{'top' if good else 'bottom'} {share}%"


def ranks_asked(question, aim=None):
    """Whether the question asks where the person ranks (or is a risk question, where the rank is the answer)."""
    return aim == "risk" or bool(ASKED.search(question or ""))


def rank_problems(text, asked):
    """What breaks the rank rule in a text: an ordinal percentile always; a personal rank when it wasn't asked."""
    found = []
    m = ORDINAL.search(text or "")
    if m:
        found.append(f"'{m.group(0)}': write ranks as 'top X%' or 'bottom X%' of Europeans" if asked else
                     f"'{m.group(0)}': the question doesn't ask where the person ranks, so leave ranks out")
    m = PERSONAL_RANK.search(text or "")
    if m and not asked:
        found.append(f"'{m.group(0)[:50]}': the question doesn't ask where the person ranks, so leave ranks out")
    return found


def advice(text):
    """The phrases in a text that give clinical advice, or []: advising phrases, sentences that start as an
    instruction, doses not attributed to a guideline or study, and verdicts on what is reasonable to do."""
    found = {m.group(0) for m in ADVICE.finditer(text or "")} | {m.group(0) for m in DECIDING.finditer(text or "")}
    for s in re.split(r"(?<=[.!?:])\s+|\n+", text or ""):
        if IMPERATIVE.search(s):
            found.add(s.strip()[:60])
        if DOSE.search(s) and not ATTRIBUTED.search(s):
            found.add(DOSE.search(s).group(0))
    return sorted(found)
