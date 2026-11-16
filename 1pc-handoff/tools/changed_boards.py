#!/usr/bin/env python3
"""Which boards changed since the pack was built, and which modules depend on them.

Usage:  python3 tools/changed_boards.py <folder with the new *.dc.html boards>

Compares each board's sha256 (first 16 hex characters) with manifest.json and prints, for every board that
changed, was added or was removed: its screen, and the components, journeys and other modules that depend on
that screen. Use the output as the checklist for the next CHANGELOG entry.
"""
import hashlib, json, os, sys, glob

here = os.path.dirname(os.path.abspath(__file__))
man = json.load(open(os.path.join(here, '..', 'manifest.json')))
if len(sys.argv) < 2:
    sys.exit(__doc__)
new = {}
for p in glob.glob(os.path.join(sys.argv[1], '*.dc.html')):
    new[os.path.basename(p)[:-8]] = hashlib.sha256(open(p, 'rb').read()).hexdigest()[:16]
mods = {m['id']: m for m in man['modules']}
old = man['boards']
changed = sorted(b for b in new if b in old and new[b] != old[b]['sha'])
added = sorted(b for b in new if b not in old)
removed = sorted(b for b in old if b not in new)
print('baseline: canvas v%s, %s' % (man['baseline']['canvas_version'], man['baseline']['date']))
print('changed: %d, added: %d, removed: %d, unchanged: %d' % (len(changed), len(added), len(removed), len(new) - len(changed) - len(added)))
for label, group in (('CHANGED', changed), ('ADDED', added), ('REMOVED', removed)):
    for b in group:
        sid = old.get(b, {}).get('screen')
        print('\n%s  %s  ->  %s' % (label, b, sid or '(no screen module yet)'))
        if sid and sid in mods:
            m = mods[sid]
            print('   file:        %s (rev %s)' % (m['file'], m['rev']))
            print('   depends on:  %s' % ', '.join(m['depends_on']))
            print('   used by:     %s' % ', '.join(m['used_by']))
if not (changed or added or removed):
    print('\nNo board changed. Nothing to write.')
