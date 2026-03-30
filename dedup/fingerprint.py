"""
Paragraph fingerprinting for near-duplicate detection.

Uses word-level trigram sets (Jaccard similarity) to catch paragraph-level
plagiarism or self-repetition across articles.

Functions:
    fingerprint_paragraph(text) -> set of word trigrams
    jaccard_similarity(set_a, set_b) -> float in [0, 1]
    fingerprint_article(text) -> list of (paragraph_index, trigram_set, first_20_words)
"""

import re
from typing import List, Set, Tuple


def _tokenize(text: str) -> List[str]:
    """Lowercase and split text into word tokens.

    Strips punctuation so that 'stocks,' and 'stocks' produce the same token.
    """
    # Remove everything except word characters and whitespace.
    cleaned = re.sub(r"[^\w\s]", "", text.lower())
    return cleaned.split()


def fingerprint_paragraph(text: str) -> Set[Tuple[str, ...]]:
    """Generate a set of word trigrams from *text*.

    A trigram is a sliding window of 3 consecutive words.
    Short paragraphs (<3 words) return an empty set.

    Args:
        text: A single paragraph of text.

    Returns:
        Set of 3-tuples, each containing three consecutive lowercase words.
    """
    tokens = _tokenize(text)
    if len(tokens) < 3:
        return set()
    return {
        (tokens[i], tokens[i + 1], tokens[i + 2])
        for i in range(len(tokens) - 2)
    }


def jaccard_similarity(set_a: Set, set_b: Set) -> float:
    """Compute the Jaccard index between two sets.

    J(A, B) = |A intersection B| / |A union B|

    Returns 0.0 if both sets are empty.

    Args:
        set_a: First trigram set.
        set_b: Second trigram set.

    Returns:
        Float in [0.0, 1.0]. 1.0 = identical sets.
    """
    if not set_a and not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union


def fingerprint_article(
    text: str,
) -> List[Tuple[int, Set[Tuple[str, ...]], str]]:
    """Fingerprint every paragraph in an article.

    Splits text on double-newlines. Skips empty paragraphs.

    Args:
        text: Full article text.

    Returns:
        List of tuples:
            (paragraph_index, trigram_set, first_20_words_string)
        where paragraph_index is 0-based.
    """
    paragraphs = text.split("\n\n")
    results: List[Tuple[int, Set[Tuple[str, ...]], str]] = []

    for idx, para in enumerate(paragraphs):
        stripped = para.strip()
        if not stripped:
            continue

        trigrams = fingerprint_paragraph(stripped)
        words = stripped.split()
        first_20 = " ".join(words[:20])

        results.append((idx, trigrams, first_20))

    return results
