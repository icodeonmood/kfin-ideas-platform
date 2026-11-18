"""Find your crew (L-CREW, S-H2, A-API.team-up `GET /crew` and the passes): the deck of colleagues' ideas a person
could help with, one reason per card, filters with live counts, passes with undo and reset, "Your crews", and the
top three for Home.

For whoever builds `GET /home` (A-API.home `crew: { total, top: CrewCard[3] }`):

    crew.deck.home(conn, user_id: str, limit: int = 3, now: datetime | None = None) -> {"total": int, "top": [CrewCard]}

or over HTTP, `GET /internal/crew?user_id=…&limit=3` (the deck response with `items` cut to three, `total` whole).
"""
