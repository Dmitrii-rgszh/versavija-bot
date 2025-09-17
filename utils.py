"""Utility helpers: transliterate Cyrillic to Latin and normalize callback strings."""
import re

# Simple transliteration map for Russian Cyrillic -> Latin (lowercase)
_TRANSLIT = {
    'а':'a','б':'b','в':'v','г':'g','д':'d','е':'e','ё':'e','ж':'zh','з':'z','и':'i','й':'i',
    'к':'k','л':'l','м':'m','н':'n','о':'o','п':'p','р':'r','с':'s','т':'t','у':'u','ф':'f',
    'х':'h','ц':'ts','ч':'ch','ш':'sh','щ':'shch','ъ':'','ы':'y','ь':'','э':'e','ю':'yu','я':'ya'
}

def transliterate(text: str) -> str:
    if not text:
        return ''
    out = []
    for ch in text:
        lower = ch.lower()
        if lower in _TRANSLIT:
            out.append(_TRANSLIT[lower])
        else:
            out.append(ch)
    return ''.join(out)


def normalize_callback(text: str) -> str:
    """Normalize arbitrary text into a callback-safe string.

    Steps:
    - transliterate Cyrillic to Latin
    - replace spaces and runs of non-alnum/_/- with underscore
    - lowercase
    - collapse multiple underscores, trim leading/trailing underscores
    - if empty, return 'btn'
    """
    if not text:
        return 'btn'
    t = transliterate(text)
    # keep ASCII letters, digits, underscore and hyphen; replace others with underscore
    t = re.sub(r'[^A-Za-z0-9_\-]+', '_', t)
    t = re.sub(r'_+', '_', t)
    t = t.strip('_')
    t = t.lower()
    if not t:
        return 'btn'
    return t
