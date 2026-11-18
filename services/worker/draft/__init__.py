"""L-DRAFT: the live draft behind "Tell it" (BLD-C070 to BLD-C079).

The person's words arrive one message at a time. Each message is masked first (`adapters.hide_message`, DEC-103),
the unmasked words are sealed for their owner alone, and then the parts of the draft that the message could change
are run again (`runs`), each through the gateway (`run_agent`, non-negotiable 1), never over a part the person
changed by hand (`L-DRAFT.pins`). With `ai.all` off (D1 open, DEC-105) no part is run: every part is left for the
person to fill by hand, and the draft works fully without a model.
"""
