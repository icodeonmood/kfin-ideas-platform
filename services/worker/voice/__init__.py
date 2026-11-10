"""Voice notes in quick capture (DEC-096): a recording becomes text the person corrects, and the recording goes.

`voice.numbers` turns spoken digits into digits so the personal-data patterns still see them; `voice.service`
accepts a recording, transcribes it through `gateway.speech`, holds the text briefly (encrypted) and deletes
everything on time.
"""
