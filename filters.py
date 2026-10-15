"""Matching rules for ads."""
import re
import unicodedata

# Zero-width characters are common in Sinhala text (e.g. the joiner in ශිෂ්‍යා) and
# vary between keyboards, so strip them before comparing.
_INVISIBLE = dict.fromkeys(map(ord, "​‌‍﻿"))


def normalize(text):
    text = unicodedata.normalize("NFC", text or "").translate(_INVISIBLE).casefold()
    return re.sub(r"\s+", " ", text)


def price_ok(price, minimum, maximum):
    """minimum is inclusive, maximum is exclusive."""
    return price is not None and minimum <= price < maximum


def excluded_keyword(text, keywords, allow_phrases=()):
    """Return the first excluded keyword found in text, or None.

    allow_phrases (e.g. "girl or boy") are removed first, so an ad open to
    everyone is not excluded just because it mentions girls.
    """
    haystack = normalize(text)
    for phrase in allow_phrases:
        haystack = haystack.replace(normalize(phrase), " ")
    for keyword in keywords:
        if normalize(keyword) in haystack:
            return keyword
    return None
