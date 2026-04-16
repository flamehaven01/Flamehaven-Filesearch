"""
Language-aware text processing for FLAMEHAVEN FileSearch multilingual support.

Handles:
- Language detection (langdetect, 55+ languages)
- Language-aware tokenization (jieba for CJK Chinese)
- Multilingual stopword sets (inlined for zero extra deps)
"""

import logging
from typing import List, Optional, Set

logger = logging.getLogger(__name__)

# --- Inlined stopwords for major languages ---
# Source: https://github.com/stopwords-iso (MIT)
_STOPWORDS: dict = {
    "en": {
        "a",
        "an",
        "the",
        "and",
        "or",
        "in",
        "of",
        "to",
        "for",
        "by",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "have",
        "has",
        "do",
        "does",
        "will",
        "would",
        "could",
        "should",
        "with",
        "this",
        "that",
        "it",
        "from",
        "at",
        "as",
        "on",
        "but",
        "not",
        "what",
        "how",
        "who",
        "find",
        "get",
        "search",
        "about",
        "where",
    },
    "zh": {
        "的",
        "了",
        "在",
        "是",
        "我",
        "有",
        "和",
        "就",
        "不",
        "人",
        "都",
        "一",
        "一个",
        "上",
        "也",
        "很",
        "到",
        "说",
        "要",
        "去",
        "你",
        "会",
        "着",
        "没有",
        "看",
        "好",
        "自己",
        "这",
    },
    "ko": {
        "이",
        "가",
        "은",
        "는",
        "의",
        "을",
        "를",
        "에",
        "에서",
        "로",
        "으로",
        "와",
        "과",
        "도",
        "만",
        "하다",
        "있다",
        "없다",
        "그",
        "저",
        "이런",
        "그런",
        "어떤",
        "때",
        "것",
        "수",
        "등",
        "및",
    },
    "ja": {
        "の",
        "に",
        "は",
        "を",
        "た",
        "が",
        "で",
        "て",
        "と",
        "し",
        "れ",
        "さ",
        "ある",
        "いる",
        "も",
        "する",
        "から",
        "な",
        "こと",
        "として",
        "い",
        "や",
        "れる",
        "など",
        "なっ",
        "ない",
        "この",
        "ため",
    },
    "de": {
        "der",
        "die",
        "das",
        "und",
        "in",
        "ist",
        "von",
        "mit",
        "auf",
        "für",
        "nicht",
        "ein",
        "eine",
        "einer",
        "ich",
        "sie",
        "es",
        "den",
        "dem",
        "des",
        "zu",
        "im",
        "an",
        "als",
        "bei",
        "auch",
    },
    "fr": {
        "le",
        "la",
        "les",
        "de",
        "du",
        "des",
        "et",
        "en",
        "un",
        "une",
        "est",
        "que",
        "qui",
        "pas",
        "sur",
        "par",
        "pour",
        "dans",
        "au",
        "avec",
        "se",
        "il",
        "elle",
        "nous",
        "vous",
        "ils",
    },
    "es": {
        "el",
        "la",
        "los",
        "las",
        "de",
        "del",
        "y",
        "en",
        "un",
        "una",
        "es",
        "que",
        "por",
        "con",
        "no",
        "se",
        "su",
        "para",
        "al",
        "lo",
        "como",
        "pero",
        "sus",
        "le",
        "ya",
        "o",
    },
}

# Languages that need character-level or CJK-specific segmentation
_CJK_LANGS = {"zh", "zh-cn", "zh-tw"}
_SPACE_LANGS = {"en", "ko", "de", "fr", "es", "it", "pt", "nl", "ru", "ar"}


def detect_language(text: str) -> Optional[str]:
    """Detect the primary language of text. Returns ISO 639-1 code or None."""
    if not text or len(text.strip()) < 10:
        return None
    try:
        from langdetect import detect, DetectorFactory

        DetectorFactory.seed = 42  # deterministic
        return detect(text)
    except Exception:
        return None


def tokenize(text: str, lang: Optional[str] = None) -> List[str]:
    """
    Language-aware word tokenization.

    - Chinese (zh, zh-cn, zh-tw): jieba word segmentation
    - Japanese (ja): character bigrams + whitespace split
    - All others: whitespace split (Korean has spaces; European langs too)
    """
    if not text:
        return []

    lang_key = (lang or "").lower()

    if lang_key in _CJK_LANGS:
        return _tokenize_chinese(text)
    if lang_key == "ja":
        return _tokenize_japanese(text)

    # Default: whitespace tokenization
    return text.split()


def get_stopwords(lang: Optional[str]) -> Set[str]:
    """Return stopword set for the given language code."""
    if not lang:
        return _STOPWORDS.get("en", set())
    # Normalize zh-cn / zh-tw -> zh
    key = "zh" if lang.startswith("zh") else lang.lower()
    return _STOPWORDS.get(key, _STOPWORDS.get("en", set()))


def _tokenize_chinese(text: str) -> List[str]:
    """
    Segment Chinese text using jieba cut_for_search mode.

    cut_for_search generates both compound words AND their sub-components
    (e.g., '搜索引擎' -> ['搜索', '索引', '引擎', '搜索引擎']),
    giving much better recall for search indexing than cut().
    Falls back to char bigrams if jieba is not installed.
    """
    try:
        import jieba

        jieba.setLogLevel(logging.WARNING)
        return [t for t in jieba.cut_for_search(text) if t.strip()]
    except ImportError:
        logger.warning(
            "[LangProcessor] jieba not installed; using char bigrams for Chinese. "
            "Run: pip install flamehaven-filesearch[multilingual]"
        )
        return _char_bigrams(text)


def extract_keywords_chinese(text: str, top_k: int = 10) -> List[str]:
    """
    Extract top-k Chinese keywords via jieba TF-IDF (jieba.analyse).

    Returns empty list if jieba is not installed.
    """
    try:
        from jieba import analyse

        return analyse.extract_tags(text, topK=top_k)
    except ImportError:
        return []


def _tokenize_japanese(text: str) -> List[str]:
    """Japanese tokenization via character bigrams + whitespace split."""
    tokens = text.split()
    result = []
    for token in tokens:
        if len(token) > 1:
            result.extend(_char_bigrams(token))
        else:
            result.append(token)
    return result if result else _char_bigrams(text)


def _char_bigrams(text: str) -> List[str]:
    """Generate character bigrams as fallback for CJK texts."""
    return [text[i : i + 2] for i in range(len(text) - 1)] or list(text)
