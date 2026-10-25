"""How much each screened row can bear, worked out in code from its Zetaris counts (a, b, c, d) and never by a
model. A row with few reports can have a high PRR and a chi-squared above 4 by chance, so the agents and the
dossier see the expected count, the PRR's interval and the shrunk information component beside it. These are
shown, never used to rank.

  a  reports naming the drug and the reaction    b  reports naming the drug, not the reaction
  c  other reports naming the reaction           d  other reports naming neither
"""
import math

THIN_REPORTS = 5  # fewer reports than this is thin evidence, whatever the statistics say


def expected(a: int, b: int, c: int, d: int) -> float:
    """Reports naming the drug and the reaction if the two were independent, E = (a+b)(a+c)/N."""
    n = a + b + c + d
    return (a + b) * (a + c) / n if n else 0.0


def prr_interval(a: int, b: int, c: int, d: int) -> tuple[float, float] | None:
    """The PRR's 95% interval by the usual log method (as in Evans et al. 2001):
    exp(ln PRR +/- 1.96 * sqrt(1/a - 1/(a+b) + 1/c - 1/(c+d))). None when a or c is 0."""
    if a <= 0 or c <= 0:
        return None
    prr = (a / (a + b)) / (c / (c + d))
    se = math.sqrt(1 / a - 1 / (a + b) + 1 / c - 1 / (c + d))
    return math.exp(math.log(prr) - 1.96 * se), math.exp(math.log(prr) + 1.96 * se)


def information_component(a: int, b: int, c: int, d: int) -> tuple[float, float]:
    """IC and IC025, the lower end of its 95% credibility interval, by the closed-form approximation in
    Norén, Hopstadius and Bate, "Shrinkage observed-to-expected ratios for robust and transparent large-scale
    pattern discovery", Stat Methods Med Res 2013;22:57-69 (doi 10.1177/0962280211403604), equations 12 and 13
    with alpha1 = alpha2 = 1/2:
      IC    = log2((O + 0.5) / (E + 0.5))
      IC025 = IC - 3.3 * (O + 0.5)^(-1/2) - 2 * (O + 0.5)^(-3/2)
    with O = a and E = expected(). Adding 0.5 to both counts shrinks the ratio towards 1 when counts are small.
    The paper puts the approximation's error in the second decimal against the exact Gamma percentile once
    O + 0.5 exceeds 1, which always holds here (the screen needs 3 reports). IC025 above 0 is the usual threshold."""
    o, e = a + 0.5, expected(a, b, c, d) + 0.5
    ic = math.log2(o / e)
    return ic, ic - 3.3 * o ** -0.5 - 2 * o ** -1.5


def assess(a: int, b: int, c: int, d: int) -> dict:
    """The numbers for one row, rounded for the prompts and the dossier, and whether it is thin evidence, meaning
    fewer than 5 reports (EMA's floor for established drugs) or IC025 at or below 0."""
    ic, ic025 = information_component(a, b, c, d)
    ci = prr_interval(a, b, c, d)
    reasons = ([f"fewer than {THIN_REPORTS} reports"] if a < THIN_REPORTS else []) + \
              (["IC025 at or below 0"] if ic025 <= 0 else [])
    return {"expected": round(expected(a, b, c, d), 2), "prr_ci95": [round(x, 2) for x in ci] if ci else None,
            "ic": round(ic, 2), "ic025": round(ic025, 2), "thin_evidence": bool(reasons), "thin_reasons": reasons}


def of(signal) -> dict:
    """assess() for a Signal from the screen."""
    return assess(signal.a, signal.b, signal.c, signal.d)
