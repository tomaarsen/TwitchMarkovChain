import re
from typing import List
from nltk.tokenize.destructive import NLTKWordTokenizer
from nltk.tokenize.treebank import TreebankWordDetokenizer
from copy import deepcopy

class MarkovChainTokenizer(NLTKWordTokenizer):
    # Starting quotes.
    STARTING_QUOTES = [
        (re.compile(u"([«“‘„]|[`]+)", re.U), r" \1 "),
        # (re.compile(r"^\""), r"``"), # Custom for MarkovChain: Don't use `` as starting quotes
        (re.compile(r"(``)"), r" \1 "),
        (re.compile(r"([ \(\[{<])(\"|\'{2})"), r"\1 '' "),
        (re.compile(r"(?i)(\')(?!re|ve|ll|m|t|s|d)(\w)\b", re.U), r"\1 \2"),
    ]

    PUNCTUATION = [
        (re.compile(r"’"), r"'"),
        (re.compile(r'([^\.])(\.)([\]\)}>"\'' u"»”’ " r"]*)\s*$",
                    re.U), r"\1 \2 \3 "),
        (re.compile(r"([:,])([^\d])"), r" \1 \2"),
        (re.compile(r"([:,])$"), r" \1 "),
        # See https://github.com/nltk/nltk/pull/2322
        (re.compile(r"\.{2,}", re.U), r" \g<0> "),
        # Custom for MarkovChain: Removed the "@"
        (re.compile(r"[;#$%&]"), r" \g<0> "),
        (
            re.compile(r'([^\.])(\.)([\]\)}>"\']*)\s*$'),
            r"\1 \2\3 ",
        ),  # Handles the final period.
        (re.compile(r"[?!]"), r" \g<0> "),
        (re.compile(r"([^'])' "), r"\1 ' "),
        # See https://github.com/nltk/nltk/pull/2322
        (re.compile(r"[*]", re.U), r" \g<0> "),
    ]


EMOTICON_RE = re.compile(r"""
(
    [<>]?
    [:;=8]                     # eyes
    [\-o\*\']?                 # optional nose
    [\)\]\(\[dDpP/\:\}\{@\|\\] # mouth
    |
    [\)\]\(\[dDpP/\:\}\{@\|\\] # mouth
    [\-o\*\']?                 # optional nose
    [:;=8]                     # eyes
    [<>]?
    |
    <3                         # heart
)""", re.VERBOSE | re.I | re.UNICODE)

_tokenize = MarkovChainTokenizer().tokenize
_detokenize = TreebankWordDetokenizer().tokenize

def tokenize(sentence: str) -> List[str]:
    """Word tokenize, separating commas, dots, apostrophes, etc.

    Uses nltk's `NLTKWordTokenizer`, but does not consider "@" to be punctuation.
    Also doesn't convert "hello" to ``hello'', but to ''hello''.

    Furthermore, doesn't split emoticons, i.e. "<3" or ":)"

    Args:
        sentence (str): Input sentence.

    Returns:
        List[str]: Tokenized output of the sentence.
    """
    
    output = []

    match = EMOTICON_RE.search(sentence)
    while match:
        output += _tokenize(sentence[:match.start()].strip())
        output += [match.group()]
        sentence = sentence[match.end():].strip()
        match = EMOTICON_RE.search(sentence)

    output += _tokenize(sentence)

    return output

def detokenize(tokenized: List[str]) -> str:
    """Detokenize a tokenized list of words and punctuation.

    Converted in a less naïve way than `" ".join(tokenized)`

    Preprocess tokenized by placing spaces before the 1st, 3rd, 5th, etc. quote,
    and by placing spaces after the 2nd, 4th, 6th, etc. quote.
    Then, ["He", "said", "''", "heya", "!", "''", "yesterday", "."] will be detokenized to
    > He said ''heya!'' yesterday.
    instead of 
    > He said''heya!''yesterday.

    Args:
        tokenized (List[str]): Input tokens, e.g. ["Hello", ",", "I", "'m", "Tom"]

    Returns:
        str: The correct string sentence, e.g. "Hello, I'm Tom"
    """
    indices = [index for index, token in enumerate(tokenized) if token in ("''", "'", '"')]
    # Replace '' with ", works better with more recent NLTK versions
    tokenized_copy = [token if token != "''" else '"' for token in tokenized]
    # We get the reverse of the enumerate, as we modify the list we took the indices from
    enumerated = list(enumerate(indices))

    for i, index in enumerated[::-1]:
        # Opening quote
        if i % 2 == 0:
            # If there is another word, merge with that word and prepend a space
            if len(tokenized) > index + 1:
                tokenized_copy[index: index + 2] = ["".join(tokenized_copy[index: index + 2])]

        # Closing quote
        else:
            # If there is a previous word, merge with that word and append a space
            if index > 0:
                tokenized_copy[index - 1: index + 1] = ["".join(tokenized_copy[index - 1: index + 1])]
    
    return _detokenize(tokenized_copy).strip()