"""Readability and on-page SEO scoring.

Both scores are computed locally — no external SEO service is involved. `seo_score` is a
transparent heuristic over things we can actually verify about a post (does the keyword appear,
is there a CTA, is the hashtag count sane, does it read easily), **not** a search-ranking
prediction. Treat it as a drafting aid, not a ranking guarantee.
"""

from __future__ import annotations

import re

_VOWELS = "aeiouy"

# Flesch Reading Ease bands.
_BANDS: tuple[tuple[float, str], ...] = (
    (90.0, "very easy"),
    (80.0, "easy"),
    (70.0, "fairly easy"),
    (60.0, "plain english"),
    (50.0, "fairly difficult"),
    (30.0, "difficult"),
)
# Social copy should land here — plain English or better.
TARGET_READABILITY = 60.0


def _sentences(text: str) -> list[str]:
    return [s for s in re.split(r"[.!?]+", text) if s.strip()]


def _words(text: str) -> list[str]:
    return re.findall(r"[A-Za-z']+", text)


def count_syllables(word: str) -> int:
    """Approximate syllable count by counting vowel groups.

    A heuristic, not a dictionary lookup: good enough for a readability band, and it keeps
    the scorer dependency-free.
    """
    word = word.lower().strip("'")
    if not word:
        return 0
    groups = re.findall(rf"[{_VOWELS}]+", word)
    count = len(groups)
    # Trailing silent 'e' ("make" is one syllable, not two).
    if word.endswith("e") and not word.endswith(("le", "ee")) and count > 1:
        count -= 1
    return max(1, count)


def flesch_reading_ease(text: str) -> float:
    """Flesch Reading Ease, 0-100 (higher is easier). Returns 0.0 for empty text."""
    words = _words(text)
    sentences = _sentences(text)
    if not words or not sentences:
        return 0.0
    syllables = sum(count_syllables(word) for word in words)
    score = 206.835 - 1.015 * (len(words) / len(sentences)) - 84.6 * (syllables / len(words))
    return round(max(0.0, min(100.0, score)), 1)


def readability_label(score: float) -> str:
    for threshold, label in _BANDS:
        if score >= threshold:
            return label
    return "very difficult"


def seo_score(
    *,
    body: str,
    primary_keyword: str,
    hashtags: list[str],
    hashtag_target: int,
    has_cta: bool,
    readability: float,
    word_range: tuple[int, int] | None = None,
) -> dict[str, object]:
    """Score a post 0-100 across five checks, returning the score plus what to fix.

    Each check is worth 20 points and reports a human-readable suggestion when it fails, so
    the number is always explainable rather than an opaque grade.
    """
    words = _words(body)
    checks: list[tuple[str, bool, str]] = []

    keyword_present = bool(primary_keyword) and primary_keyword.lower() in body.lower()
    checks.append(
        (
            "keyword",
            keyword_present,
            f"Work the primary keyword '{primary_keyword}' into the copy.",
        )
    )

    # Within 60% of the platform's hashtag target counts as healthy.
    enough_hashtags = len(hashtags) >= max(1, int(hashtag_target * 0.6))
    checks.append(
        (
            "hashtags",
            enough_hashtags,
            f"Add hashtags — {len(hashtags)} of a target {hashtag_target}.",
        )
    )

    checks.append(("cta", has_cta, "Add a call to action."))

    reads_well = readability >= TARGET_READABILITY
    checks.append(
        (
            "readability",
            reads_well,
            "Shorten sentences and prefer simpler words — this reads as "
            f"'{readability_label(readability)}'.",
        )
    )

    if word_range:
        low, high = word_range
        right_length = low <= len(words) <= high
        detail = f"Aim for {low}-{high} words; this is {len(words)}."
    else:
        right_length = bool(words)
        detail = "Add some copy."
    checks.append(("length", right_length, detail))

    passed = [name for name, ok, _ in checks if ok]
    suggestions = [msg for _, ok, msg in checks if not ok]
    return {
        "score": round(len(passed) / len(checks) * 100),
        "passed": passed,
        "suggestions": suggestions,
    }
