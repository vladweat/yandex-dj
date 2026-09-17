"""Общий mood-лексикон: search validation и понижение SEO-title в scoring."""

MOOD_TITLE_DEMOTE_TOKENS = frozenset(
    {
        "sad",
        "emotional",
        "melancholic",
        "melancholy",
        "introspective",
        "depressing",
        "depressed",
        "lonely",
        "heartbreak",
        "cozy",
        "chill",
        "relaxing",
        "calm",
        "moody",
        "nostalgic",
    }
)

MOOD_SEARCH_BAIT_TOKENS = frozenset(
    {
        *MOOD_TITLE_DEMOTE_TOKENS,
        "heartbreaking",
        "peaceful",
        "romantic",
        "warm",
        "dreamy",
        "gentle",
        "soft",
        "sleepy",
        "quiet",
        "rainy",
    }
)
