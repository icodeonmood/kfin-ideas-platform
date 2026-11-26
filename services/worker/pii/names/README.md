# Name lexicons (KFin recogniser)

Common Indian given names and surnames, used by `pii/detect.py` to recognise person names that the small
English NER model labels as organisations or places. These are public, generic name lists, not records of any
person. Matching a name here only means "tag this as a person before any model call"; it never blocks.

Grow the lists from reviewer corrections (a person name that reached the model untagged). Keep one name per
line, lower case. Names that are also common English words (for example "will", "grace") are left out.

`devanagari.tsv` (DEC-139 (d), BLD-C247) holds the same kind of names written in Devanagari, one per line with its
kind (`given` or `surname`), and the `stop` words that end a name in Hindi (postpositions, "and", the verbs that
follow a name, the respectful "जी", and the honorifics). Devanagari has no capitals, so a name is a word in the table;
a given name takes one unknown word after it and a surname one before it, never a stop word. Names that are also
everyday Hindi words are left out, as English words are left out of the Latin lists. Other scripts wait for r8.
