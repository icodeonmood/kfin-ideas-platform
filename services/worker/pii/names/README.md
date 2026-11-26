# Name lexicons (KFin recogniser)

Common Indian given names and surnames, used by `pii/detect.py` to recognise person names that the small
English NER model labels as organisations or places. These are public, generic name lists, not records of any
person. Matching a name here only means "tag this as a person before any model call"; it never blocks.

Grow the lists from reviewer corrections (a person name that reached the model untagged). Keep one name per
line, lower case. Names that are also common English words (for example "will", "grace") are left out.

In lower case (BLD-C251, DEC-142) a name counts only as a known given name followed by a known surname ("ravi kumar"): one word alone never does, since many names are everyday words too.
