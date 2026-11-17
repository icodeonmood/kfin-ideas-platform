"""The 1% Club's public side and the person's own side of it (lane E): the Wall (S-WALL, L-WALL), the Ones (S-ONE,
L-ONES, C-ONES-FAN data), what shipped ideas changed (L-IMPACT, read side) and Profile (S-H6).

Who sees what follows `P-PRODUCT.privacy` (DEC-104): everyone signed in reads the Wall, which carries an idea's
short summary, area, kind and stage, and the sharer's name unless they hid it in Profile; never their own words,
never points. A One's own dashboard and a person's profile and points are theirs alone.

Other lanes call these entry points (SHIP_PLAN §5a), never the tables:
  - `wall.ones.induct_for_idea(conn, idea_uuid, actor=…)`: L-ONES.rules/1, after a measurement lands (lane A);
  - `wall.ones.mark_founding`, `wall.ones.remove_one`, `wall.ones.approve_brief`: the admin path (DEC-106);
  - `wall.ones.one_cards(conn)`: the OneCard shape the Wall, Home's fan and the office screen all read;
  - `wall.common.on_wall_sql(alias)`: the one filter "Take off the Wall" changes (lane A, DEC-106).
"""
