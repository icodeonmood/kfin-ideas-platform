/* ==== R33 draft loader (begin) ==== */
// The draft is built by six independent services, called together the moment your words arrive.
// mean: each service's mean response time in ms (p50 over the last 7 days, from monitoring). demo: when it answers in this prototype.
// Weight = a service's share of the summed means, so slower parts move the bar more.
// While a part waits, its progress rises along 0.9 x (1 - e^(-t / mean)): always moving, never full on its own.
// When it answers it counts as full. The bar is the weighted sum: it never pauses, never moves back, and stays under 97% until all six are in.
var DL_PARTS = [
  { k: 'title', label: 'Title', mean: 1800, demo: 1700, slow: 'the title is taking longer' },
  { k: 'often', label: 'How often', mean: 900, demo: 1000, slow: 'how often is taking longer' },
  { k: 'who', label: 'Who it affects', mean: 1200, demo: 1300, slow: 'who it affects is taking longer' },
  { k: 'value', label: 'What it’s worth', mean: 1500, demo: 1600, slow: 'what it’s worth is taking longer' },
  { k: 'area', label: 'Area', mean: 700, demo: 650, slow: 'the area is taking longer' },
  { k: 'similar', label: 'Similar ideas', mean: 2600, demo: 2900, slow: 'still looking for similar ideas' }
];
var DL_SUM = DL_PARTS.reduce(function (s, x) { return s + x.mean; }, 0);
function draftLoad(t, mode) {
  var p = 0, ready = 0, left = 0, slow = '', done = {}, at = {}, end = 0;
  DL_PARTS.forEach(function (x) {
    var due = mode === 'Slow similar ideas' && x.k === 'similar' ? x.mean * 3 : x.demo;
    var w = x.mean / DL_SUM, ok = t >= due;
    done[x.k] = ok; at[x.k] = due; end = Math.max(end, due);
    if (ok) { p += w; ready += 1; }
    else {
      p += w * 0.9 * (1 - Math.exp(-Math.max(t, 0) / x.mean));
      left = Math.max(left, x.mean - t);
      if (t > x.mean * 1.5) slow = x.slow;
    }
  });
  var all = ready === DL_PARTS.length, shown = all ? 1 : Math.min(p, 0.97);
  var note = all ? 'All 6 parts are in' : ready + ' of 6 ready, ' + (slow || (left > 1000 ? 'about ' + Math.ceil(left / 1000) + ' seconds left' : 'almost there'));
  return { p: shown.toFixed(4), pct: Math.round(shown * 100), ready: ready, all: all, done: done, at: at, end: end, note: note,
    title: all ? 'Your draft is ready' : 'Building your draft', cls: all ? 'all' : '' };
}
// while the loader runs, a part that hasn't answered shows its skeleton, and nothing can be sent yet
function ldApply(m, LD) {
  m.ldSim = false;
  if (!LD || !LD.on) return m;
  var wait = function (o) { return Object.assign({}, o, { show: false, has: false, skel: true, hint: false, canEdit: false, canAct: false, why: '', editing: false, isText: false, isChips: false, isWho: false }); };
  if (!LD.done.title) { m.titleRow = wait(m.titleRow); m.sumRow = Object.assign({}, m.sumRow, { has: false, skel: true, hint: false }); }
  m.rows = m.rows.map(function (r) { return LD.done[r.key] ? r : wait(r); });
  if (!LD.done.similar && m.A && m.A.similar) { m.ldSim = !!m.showDraft; m.A = Object.assign({}, m.A, { similar: false }); }
  m.ready = false;
  m.dstat = { t: 'Updating', c: 'ing' };
  m.receipt = 'Each part appears as soon as it\u2019s ready. You can keep writing meanwhile.';
  return m;
}
/* ==== R33 draft loader (end) ==== */
