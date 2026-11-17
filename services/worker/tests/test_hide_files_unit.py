"""L-HIDE.files/1 (non-negotiable 4, DEC-103, BLD-C107): only a person's switch-off lets a file skip the gatekeeper.

An automatic switch-off (the gateway's own, the eval runner's on a golden-set regression, the watcher's, or an
unknown actor) is a failure: the file stays `checking` and waits, and is never `checked` on patterns alone.
"""

import pytest

from hide.files import switched_off_by_person


@pytest.mark.parametrize(
    "actor", ["process:gateway", "process:eval", "process:watch", "process:anything", None, ""]
)
def test_L_HIDE_files_1_an_automatic_or_unknown_switch_off_is_not_a_choice(actor: str | None) -> None:
    assert switched_off_by_person(actor) is False


@pytest.mark.parametrize("actor", ["7f8e2c1a-0000-4000-8000-000000000001", "admin:infosec"])
def test_L_HIDE_files_1_a_person_switching_the_gatekeeper_off_is_a_choice(actor: str) -> None:
    assert switched_off_by_person(actor) is True
