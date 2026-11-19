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
