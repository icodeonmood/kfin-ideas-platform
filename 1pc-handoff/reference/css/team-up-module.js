/* ==== R27 team up (begin) ==== */
// One Team up, everywhere: a request with a note the lead reads, and, if you like, one of your ideas brought along.
// R39: your ideas are a multi-select, collapsed and empty until you pick; one button, Send; the cross closes.
// The lead approves or declines from their Inbox (CrewRequest). Until then the button reads "Waiting for <lead>", with Withdraw.
var TU_MINE = {
  k1: { title: 'Investors call to ask why a redemption was rejected', meta: 'IDEA-2026-001481, with the review desk' },
  k2: { title: 'Plain words for transaction rejections', meta: 'IDEA-2026-001471, being built' },
  none: { title: 'Don’t bring one', meta: 'Send just the note' }
};
var TU_NOTES = {
  c1: 'I take these calls at our Hyderabad branch every day, about 40 a day, and most are about R07. I can bring the call log and real examples of what investors ask.',
  c2: 'I take rejection calls at the Hyderabad branch every day. I can share real examples of what investors ask, so the script starts from them.',
  c3: 'Our Hyderabad branch can count queue times for two weeks. I sit at the service desk and can run it.',
  c4: 'Investors call our branch when a nominee change stalls. I can log those calls so you can see how often it happens.',
  c5: 'I have seen the three KYC screens disagree at our branch. I can share examples, with personal details hidden.'
};
function tuCur(self) { return Object.assign({ open: null, step: 'compose', notes: {}, bring: {}, pending: [], on: [] }, self.tuSeed || {}, self.state.tu || {}); }
function tuSet(self, o) { self.setState({ tu: Object.assign({}, tuCur(self), o) }); }
function tuFocus(id) { setTimeout(function () { var el = typeof document !== 'undefined' && document.getElementById(id); if (!el) return; try { el.focus({ preventScroll: true }); } catch (e) { el.focus(); } try { if (el.setSelectionRange) el.setSelectionRange(el.value.length, el.value.length); } catch (e) {} }, 80); }
function tuStart(self, id) { var s = tuCur(self); if (s.pending.indexOf(id) >= 0 || s.on.indexOf(id) >= 0) return; tuSet(self, { open: id, step: 'compose', bringOpen: false }); tuFocus('rq-note'); }
function tuPending(self, id) { return tuCur(self).pending.indexOf(id) >= 0; }
function tuOn(self, id) { return tuCur(self).on.indexOf(id) >= 0; }
function tuWithdraw(self, id) { var s = tuCur(self); tuSet(self, { pending: s.pending.filter(function (x) { return x !== id; }), open: null }); }
function tuFirst(t) { return t.lead.split(' ')[0]; }
// T: { id: { lead, leadIni, leadT, title, note, opts, bring, mine, legend, optional, onSend(bringKey), onWithdraw() } }
function tuVals(self, T) {
  var st = tuCur(self), id = st.open, t = id ? T[id] : null;
  if (!t) return { tuOpen: false, tuCompose: false, tuSent: false, tu: { first: '', title: '', leadIni: '', leadT: '', note: '', ideas: [], hint: '', hintCls: '', off: 'true', bringTitle: '', legend: '', priv: '', optional: false } };
  var first = tuFirst(t);
  var note = st.notes[id] != null ? st.notes[id] : t.note;
  var n = note.trim().length;
  var multi = (t.opts || ['k1', 'k2', 'none']).indexOf('this') < 0;
  var bk = multi ? 'none' : (st.bring[id] || t.bring || 'none');
  var sel = multi && Array.isArray(st.bring[id]) ? st.bring[id] : [];
  var mine = Object.assign({}, TU_MINE, t.mine || {});
  var bring = mine[bk];
  var titles = multi ? sel.map(function (k) { return mine[k] ? mine[k].title : ''; }) : (bk !== 'none' && bk !== 'sep' && bring ? [bring.title] : []);
  var bn = titles.length;
  var close = function () { tuSet(self, { open: null }); };
  return {
    tuOpen: true, tuCompose: st.step === 'compose', tuSent: st.step === 'sent',
    tu: {
      first: first, title: t.title, leadIni: t.leadIni, leadT: t.leadT, note: note,
      setNote: function (e) { var o = Object.assign({}, tuCur(self).notes); o[id] = e.target.value; tuSet(self, { notes: o }); },
      hint: n < 30 ? 'Add a little more: at least 30 characters.' : (st.notes[id] == null ? 'We drafted this from your idea. Change anything you like.' : 'Looks good.'),
      hintCls: n < 30 ? 'warn' : '',
      legend: multi ? 'Bring your ideas along' : (t.legend || 'Bring one of your ideas along'), optional: t.optional !== false,
      ideas: (t.opts || ['k1', 'k2', 'none']).filter(function (k) { return !multi || k !== 'none'; }).map(function (k) { var o = mine[k], on = multi ? sel.indexOf(k) >= 0 : k === bk; return { title: o.title, meta: o.meta, on: on, pick: function () { var b = Object.assign({}, tuCur(self).bring); if (multi) { var c = Array.isArray(b[id]) ? b[id].slice() : [], i = c.indexOf(k); if (i >= 0) c.splice(i, 1); else c.push(k); b[id] = c; } else b[id] = k; tuSet(self, { bring: b }); } }; }),
      bringOpen: !!st.bringOpen, bringOpenA: st.bringOpen ? 'true' : 'false',
      toggleBring: function () { tuSet(self, { bringOpen: !tuCur(self).bringOpen }); },
      bringSummary: !bn ? 'None picked' : (bn === 1 ? titles[0] : bn + ' ideas picked'), bringSumCls: bn ? 'on' : '',
      priv: first + ' sees your name, your note' + (!bn ? '.' : (bn > 1 ? ' and the ideas you bring.' : ' and the idea you bring.')),
      off: n < 30 ? 'true' : 'false',
      send: function () { if (n < 30) { tuFocus('rq-note'); return; } var s = tuCur(self); tuSet(self, { step: 'sent', pending: s.pending.indexOf(id) < 0 ? s.pending.concat([id]) : s.pending }); if (t.onSend) t.onSend(multi ? sel : bk); tuFocus('rq-sh'); },
      cancel: close, done: close,
      withdraw: function () { tuWithdraw(self, id); if (t.onWithdraw) t.onWithdraw(); },
      key: function (e) { if (e.key === 'Escape') close(); },
      hasBring: bn > 0, bringTitle: titles.join(' and '), bringLine: 'Bringing ' + titles.map(function (x) { return '\u201c' + x + '\u201d'; }).join(' and '),
      sentLine: first + ' reads your note' + (!bn ? '' : (bn > 1 ? ' and the ideas you brought' : ' and the idea you brought')) + ', then approves or declines. You’ll hear in your Inbox.'
    }
  };
}
/* ==== R27 team up (end) ==== */
