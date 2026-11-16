/* ==== motion v1 engine (begin) ==== */
/* ==== motion v1 engine ====
   GSAP 3.13 (Flip, SplitText, ScrollTrigger, CustomEase) loads from a CDN for layout morphs, word reveals and scroll scenes.
   The first frame of every screen, arrivals from another screen, presses and sparks use the browser's own animation API,
   so nothing waits on a download and everything still moves if the CDN is blocked. Reduced motion turns all of it off. */
var MO = (function () {
  if (typeof window === 'undefined' || typeof document === 'undefined') { var noop = function () {}; return { boot: noop, demo: noop, replayWords: noop, countOne: noop, burst: noop, when: noop, reduced: function () { return true; } }; }
  var W = window, D = document;
  if (W.__MO) return W.__MO;
  var M = W.__MO = { v: 1, file: '', cfg: {} };
  var RMQ = W.matchMedia ? W.matchMedia('(prefers-reduced-motion: reduce)') : null;
  function reduced() { return !!(RMQ && RMQ.matches) || D.documentElement.hasAttribute('data-reduce-motion'); }
  function now() { return W.performance && performance.now ? performance.now() : Date.now(); }
  function raf(f) { return (W.requestAnimationFrame || setTimeout)(f); }
  function txt(el) { return el ? (el.getAttribute('aria-label') || el.textContent || '').replace(/\s+/g, ' ').trim() : ''; }
  function vis(el) { var r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0; }
  var T0 = now(), booted = false;
  M.reduced = reduced;
  var EASE = { out: 'cubic-bezier(.16,1,.3,1)', emph: 'cubic-bezier(.05,.7,.1,1)', acc: 'cubic-bezier(.3,0,.8,.15)', snap: 'cubic-bezier(.2,0,0,1)',
    spring: 'linear(0,.009,.035 2.1%,.141,.281 6.7%,.723 12.9%,.938 16.7%,1.017,1.077,1.121,1.149 24.3%,1.159,1.163,1.161,1.154 29.9%,1.129 32.8%,1.051 39.6%,1.017 43.1%,.991,.977 51%,.974 53.8%,.975 57.1%,.997 69.8%,1.003 76.9%,1.004 83.8%,1)' };
  function ani(el, kf, o) { try { return el.animate(kf, o); } catch (e) { return null; } }

  /* ---------- GSAP, from the CDN ---------- */
  var BASES = ['https://cdn.jsdelivr.net/npm/gsap@3.13.0/dist/', 'https://cdnjs.cloudflare.com/ajax/libs/gsap/3.13.0/'];
  var FILES = ['gsap.min.js', 'CustomEase.min.js', 'Flip.min.js', 'ScrollTrigger.min.js', 'SplitText.min.js'];
  var waits = [], loading = false;
  function ready() {
    var g = W.gsap; if (!g || M.g) return;
    var plug = [W.Flip, W.ScrollTrigger, W.SplitText, W.CustomEase].filter(Boolean);
    try { g.registerPlugin.apply(g, plug); } catch (e) {}
    var ce = W.CustomEase;
    var mk = function (n, v, fb) { try { if (ce) ce.create(n, v); else throw 0; } catch (e) { M.ease[n] = fb; return; } M.ease[n] = n; };
    M.ease = {};
    mk('mo.out', '0.16,1,0.3,1', 'expo.out'); mk('mo.emph', '0.05,0.7,0.1,1', 'power4.out'); mk('mo.acc', '0.3,0,0.8,0.15', 'power3.in'); mk('mo.snap', '0.2,0,0,1', 'power3.out');
    M.g = g; M.Flip = W.Flip || null; M.ST = W.ScrollTrigger || null; M.Split = W.SplitText || null;
    var w = waits; waits = [];
    w.forEach(function (f) { try { f(g); } catch (e) { if (W.console) console.warn('[motion]', e); } });
  }
  function load() {
    if (M.g) return; if (W.gsap && W.Flip && W.SplitText) { ready(); return; }
    if (loading) return; loading = true;
    var bi = 0, fi = W.gsap ? 1 : 0;
    function next() {
      if (fi >= FILES.length) { ready(); return; }
      var name = FILES[fi].replace('.min.js', '');
      if (fi > 0 && W[name]) { fi++; next(); return; }
      var s = D.createElement('script'); s.src = BASES[bi] + FILES[fi]; s.async = false; s.crossOrigin = 'anonymous';
      s.onload = function () { fi++; next(); };
      s.onerror = function () { if (s.parentNode) s.parentNode.removeChild(s); if (bi < BASES.length - 1) { bi++; next(); } else { M.failed = true; if (W.gsap) ready(); } };
      (D.head || D.documentElement).appendChild(s);
    }
    next();
  }
  M.when = function (fn) { if (M.g) { try { fn(M.g); } catch (e) {} } else waits.push(fn); };

  /* ---------- the layer drawn above the board, outside its DOM ---------- */
  function fx() {
    var f = D.getElementById('mo-fx');
    if (!f) { f = D.createElement('div'); f.id = 'mo-fx'; f.setAttribute('aria-hidden', 'true'); D.documentElement.appendChild(f); }
    return f;
  }
  function shell() { return D.querySelector('.pc') || D.body; }
  function content() {
    var s = shell(), ph = s.classList.contains('ph') ? s : s.querySelector('.ph');
    return ph || s;
  }

  /* ---------- colour helpers for ghosts ---------- */
  function rgba(c) { var m = /rgba?\(([^)]+)\)/.exec(c || ''); if (!m) return null; var p = m[1].split(/[ ,\/]+/).filter(Boolean).map(parseFloat); return { r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1 }; }
  function lum(c) { return (0.2126 * c.r + 0.7152 * c.g + 0.0722 * c.b) / 255; }
  function solidBg(el) {
    var n = el, guard = 0;
    while (n && n.nodeType === 1 && guard++ < 8) {
      var cs = getComputedStyle(n), c = rgba(cs.backgroundColor);
      if (c && c.a >= 0.55) return 'rgb(' + Math.round(c.r) + ',' + Math.round(c.g) + ',' + Math.round(c.b) + ')';
      if (cs.backgroundImage && cs.backgroundImage !== 'none' && /gradient/.test(cs.backgroundImage) && c && c.a > 0) break;
      n = n.parentElement;
    }
    var fg = rgba(getComputedStyle(el).color);
    return fg && lum(fg) > 0.7 ? '#18191D' : '#FFFFFF';
  }

  /* ---------- 1. leaving a screen: remember what was tapped, so the next screen can grow out of it ---------- */
  var KEY = 'mo-nav';
  var CARD = '.qrow,.irow,.irow2,.jcard,.icard,.card,.pcard,.wcard,.tile,.sb-dr,[role="row"],li,article';
  function cardOf(a) {
    if (a.classList.contains('ink') || a.classList.contains('sb-new')) return null;
    var r = a.getBoundingClientRect();
    if (!a.classList.contains('btn') && r.width >= 180 && r.height >= 56) return a;
    var c = a.closest(CARD); if (!c) return null;
    var cr = c.getBoundingClientRect();
    if (cr.height < 44 || cr.width * cr.height > innerWidth * innerHeight * 0.55) return null;
    return c;
  }
  function classify(a) {
    if (a.closest('.sb-new,.fab,.tab.share')) return 'portal';
    if (a.closest('.sbar .sb-nav,.sbar .sb-top,.sbar .sb-me,.sbar .sb-va,.tabs,.tnav,.anav,.ptop .brand,.pnav .brand')) return 'peer';
    if (a.closest('.back,.crumb,.pback,[rel="prev"]') || /^(‹|<|←)?\s*back\b/i.test(txt(a))) return 'back';
    if (cardOf(a)) return 'expand';
    if (a.classList.contains('ink')) return 'portal';
    return 'fwd';
  }
  function titleOf(el) {
    var cands = el.querySelectorAll('.it,.ttl,.title,.io,.jt,.wt,h2,h3,h4,b,strong,.t');
    for (var i = 0; i < cands.length; i++) { var t = txt(cands[i]); if (t.length > 12 && t.length < 120 && vis(cands[i])) return cands[i]; }
    return null;
  }
  function onNav(e) {
    if (e.button || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    var a = e.target && e.target.closest ? e.target.closest('a[href]') : null; if (!a) return;
    var m = /([^\/#?]+\.dc\.html)/.exec(a.getAttribute('href') || ''); if (!m) return;
    var kind = classify(a), src = kind === 'expand' ? cardOf(a) : a, r = src.getBoundingClientRect(), cs = getComputedStyle(src);
    var rec = { to: m[1], from: M.file, kind: kind, at: Date.now(), vw: innerWidth, vh: innerHeight,
      x: e.clientX || r.left + r.width / 2, y: e.clientY || r.top + r.height / 2,
      r: [r.left, r.top, r.width, r.height], rad: parseFloat(cs.borderTopLeftRadius) || 0, bg: solidBg(src) };
    if (kind === 'expand') {
      var t = titleOf(src);
      if (t) { var tr = t.getBoundingClientRect(), tcs = getComputedStyle(t);
        rec.t = { s: txt(t), r: [tr.left, tr.top, tr.width, tr.height], fs: parseFloat(tcs.fontSize), fw: tcs.fontWeight, ff: tcs.fontFamily, c: tcs.color, ls: tcs.letterSpacing }; }
    }
    try { sessionStorage.setItem(KEY, JSON.stringify(rec)); } catch (er) {}
    if (reduced()) return;
    if (kind === 'expand') ani(src, [{ scale: 1 }, { scale: 0.985 }, { scale: 1 }], { duration: 260, easing: EASE.snap });
  }

  /* ---------- 2. arriving: grow out of the tapped card, or flood from the tapped button ---------- */
  function scaleRect(rec) {
    var sx = innerWidth / (rec.vw || innerWidth), sy = innerHeight / (rec.vh || innerHeight);
    return { l: rec.r[0] * sx, t: rec.r[1] * sy, w: rec.r[2] * sx, h: rec.r[3] * sy };
  }
  function layoutRect(el) {
    var x = 0, y = 0, n = el;
    while (n) { x += n.offsetLeft || 0; y += n.offsetTop || 0; n = n.offsetParent; }
    var se = D.scrollingElement || D.documentElement;
    return { left: x - se.scrollLeft, top: y - se.scrollTop, width: el.offsetWidth, height: el.offsetHeight };
  }
  function firstHead() {
    var hs = content().querySelectorAll('h1,.mtitle,.h1,.mi-t,.hello');
    for (var i = 0; i < hs.length; i++) { var r = hs[i].getBoundingClientRect(); if (r.width > 0 && r.top < innerHeight && r.bottom > 0) return hs[i]; }
    return null;
  }
  function area() {
    var l = 0, b = 0, sb = D.querySelector('.sbar'), tb = D.querySelector('.ph > .tabs,.pc.ph > .tabs');
    if (sb) { var r = sb.getBoundingClientRect(); if (r.width && r.right < innerWidth * 0.5) l = r.right; }
    if (tb) { var q = tb.getBoundingClientRect(); if (q.height && q.top > innerHeight * 0.5) b = Math.max(0, innerHeight - q.top); }
    return { l: l, b: b };
  }
  function ghost(bg) {
    var A = area(), g = D.createElement('div'); g.className = 'mo-ghost'; g.style.background = bg;
    g.style.left = A.l + 'px'; g.style.bottom = A.b + 'px'; fx().appendChild(g); return { g: g, A: A };
  }
  function expandIn(rec) {
    var f = fx(), R = scaleRect(rec), gh = ghost(rec.bg), g = gh.g, vw = innerWidth - gh.A.l, vh = innerHeight - gh.A.b;
    R.l -= gh.A.l;
    var from = 'inset(' + Math.max(0, R.t) + 'px ' + Math.max(0, vw - R.l - R.w) + 'px ' + Math.max(0, vh - R.t - R.h) + 'px ' + Math.max(0, R.l) + 'px round ' + rec.rad + 'px)';
    var full = 'inset(0px 0px 0px 0px round 0px)';
    var a = ani(g, [{ clipPath: from, opacity: 1 }, { clipPath: full, opacity: 1, offset: 0.62 }, { clipPath: full, opacity: 0 }], { duration: 900, easing: EASE.snap, fill: 'forwards' });
    if (a) a.onfinish = function () { g.remove(); }; else g.remove();
    if (rec.t) {
      var h = firstHead(), tt = D.createElement('p'); tt.className = 'mo-ghost-t'; tt.textContent = rec.t.s;
      var sx = innerWidth / (rec.vw || innerWidth), sy = innerHeight / (rec.vh || innerHeight);
      var tl = rec.t.r[0] * sx, ttop = rec.t.r[1] * sy;
      tt.style.cssText = 'left:0;top:0;font-size:' + rec.t.fs + 'px;font-weight:' + rec.t.fw + ';font-family:' + rec.t.ff + ';color:' + rec.t.c + ';letter-spacing:' + rec.t.ls + ';line-height:1.2;max-width:' + Math.max(rec.t.r[2], 200) + 'px;white-space:normal';
      f.appendChild(tt);
      var to = null;
      if (h) { var hr = layoutRect(h), hcs = getComputedStyle(h); var k = parseFloat(hcs.fontSize) / rec.t.fs;
        if (k > 0.4 && k < 6) to = { x: hr.left, y: hr.top, k: k, c: hcs.color }; }
      var kf = to
        ? [{ transform: 'translate(' + tl + 'px,' + ttop + 'px) scale(1)', opacity: 1, color: rec.t.c }, { transform: 'translate(' + to.x + 'px,' + to.y + 'px) scale(' + to.k + ')', opacity: 1, color: to.c, offset: 0.82 }, { transform: 'translate(' + to.x + 'px,' + to.y + 'px) scale(' + to.k + ')', opacity: 0, color: to.c }]
        : [{ transform: 'translate(' + tl + 'px,' + ttop + 'px)', opacity: 1 }, { transform: 'translate(' + tl + 'px,' + (ttop - 12) + 'px)', opacity: 0 }];
      var b = ani(tt, kf, { duration: to ? 860 : 420, easing: EASE.out, fill: 'forwards' });
      if (b) b.onfinish = function () { tt.remove(); }; else tt.remove();
      if (to && h) ani(h, [{ opacity: 0 }, { opacity: 0, offset: 0.78 }, { opacity: 1 }], { duration: 900, fill: 'backwards', composite: 'replace' });
    }
  }
  function portalIn(rec) {
    var R = scaleRect(rec), gh = ghost(rec.bg), g = gh.g, vw = innerWidth - gh.A.l, vh = innerHeight - gh.A.b;
    var x = Math.max(0, R.l + R.w / 2 - gh.A.l), y = R.t + R.h / 2, r1 = Math.hypot(Math.max(x, vw - x), Math.max(y, vh - y)) + 40;
    var a = ani(g, [{ clipPath: 'circle(' + Math.max(R.h / 2, 18) + 'px at ' + x + 'px ' + y + 'px)' }, { clipPath: 'circle(' + r1 + 'px at ' + x + 'px ' + y + 'px)' }], { duration: 480, easing: EASE.emph, fill: 'forwards' });
    if (!a) { g.remove(); return; }
    a.onfinish = function () {
      g.style.clipPath = 'none'; try { a.cancel(); } catch (e) {}
      var b = ani(g, [{ transform: 'translateY(0)' }, { transform: 'translateY(-101%)' }], { duration: 620, easing: 'cubic-bezier(.76,0,.24,1)', fill: 'forwards' });
      if (b) b.onfinish = function () { g.remove(); }; else g.remove();
    };
  }
  function arrive() {
    var rec = null;
    try { rec = JSON.parse(sessionStorage.getItem(KEY) || 'null'); } catch (e) {}
    if (!rec || rec.to !== M.file || Date.now() - rec.at > 4000) return null;
    try { sessionStorage.removeItem(KEY); } catch (e) {}
    if (reduced()) return rec;
    D.documentElement.classList.add('mo-a-' + rec.kind);
    if (rec.kind === 'expand') expandIn(rec); else if (rec.kind === 'portal') portalIn(rec);
    return rec;
  }

  /* ---------- 3. touch: magnetic primary buttons, a springy press, light that follows the pointer on glass ---------- */
  var MAG = '.btn.ink,.sb-new,.fab';
  var PRESS = '.btn,.chip,.sb-new,.fab,.mic,.icb,.tab,.irow,.opt2,.send,.mtb,.mtab,.copy,.cclip,.hstarter,.starter,.lchip,.lmk,.sgb,.jcard,[role="radio"],[role="checkbox"],[role="tab"]';
  var magEl = null, tiltEl = null, pressEl = null, pressAni = null, spotEl = null;
  function onMove(e) {
    if (reduced() || e.pointerType === 'touch') return;
    var t = e.target; if (!t || !t.closest) return;
    var m = t.closest(MAG);
    if (m !== magEl) { if (magEl) magEl.style.translate = ''; magEl = m; }
    if (m && m.getAttribute('aria-disabled') !== 'true') {
      var r = m.getBoundingClientRect(), dx = (e.clientX - r.left - r.width / 2) / (r.width / 2), dy = (e.clientY - r.top - r.height / 2) / (r.height / 2);
      m.style.translate = (dx * 5).toFixed(2) + 'px ' + (dy * 3.5).toFixed(2) + 'px';
    }
    var gl = t.closest('.glass,.mread,.mlist');
    if (gl !== spotEl) { if (spotEl && spotEl.__moBase) spotEl.style.backgroundImage = ''; spotEl = gl || null; }
    if (gl) {
      if (gl.__moBase === undefined) { var bi = getComputedStyle(gl).backgroundImage; gl.__moBase = /gradient/.test(bi) && /255, 255, 255/.test(bi) ? bi : (bi === 'none' && /rgba\(255, 255, 255/.test(getComputedStyle(gl).backgroundColor) ? 'none' : ''); }
      if (gl.__moBase) { var gr = gl.getBoundingClientRect();
        gl.style.backgroundImage = 'radial-gradient(520px circle at ' + (e.clientX - gr.left).toFixed(0) + 'px ' + (e.clientY - gr.top).toFixed(0) + 'px, rgba(255,255,255,.6), rgba(255,255,255,0) 60%)' + (gl.__moBase !== 'none' ? ', ' + gl.__moBase : ''); }
    }
    var ts = M.cfg.tilt && t.closest(M.cfg.tilt);
    if (ts !== tiltEl) { if (tiltEl && M.g) M.g.to(tiltEl, { rotationX: 0, rotationY: 0, duration: 0.8, ease: 'elastic.out(1,0.5)', overwrite: 'auto' }); tiltEl = ts || null; }
    if (ts && M.g) { var q = ts.getBoundingClientRect(), px = (e.clientX - q.left) / q.width - 0.5, py = (e.clientY - q.top) / q.height - 0.5;
      M.g.to(ts, { rotationY: px * 9, rotationX: -py * 7, transformPerspective: 900, duration: 0.5, ease: 'power3.out', overwrite: 'auto' }); }
  }
  function onDown(e) {
    if (reduced()) return; var t = e.target; if (!t || !t.closest) return;
    var p = t.closest(PRESS); if (!p || p.getAttribute('aria-disabled') === 'true') return;
    if (pressAni) { try { pressAni.cancel(); } catch (er) {} }
    pressEl = p; pressAni = ani(p, [{ scale: 1 }, { scale: p.offsetWidth > 260 ? 0.985 : 0.955 }], { duration: 110, easing: EASE.snap, fill: 'forwards' });
  }
  function onUp() {
    var p = pressEl, d = pressAni; pressEl = null; pressAni = null; if (!p) return;
    var from = p.offsetWidth > 260 ? 0.985 : 0.955;
    if (d) { try { d.cancel(); } catch (e) {} }
    if (!p.isConnected) return;
    ani(p, [{ scale: from }, { scale: 1 }], { duration: 560, easing: EASE.spring });
  }

  /* ---------- 4. the 1% spark: a burst of slashes when something is sent, shared or joined ---------- */
  var COMMIT = /^(send|share|share it|team up|submit|sign in|send code|post|join|confirm|answer)\b/i;
  var SPARK = ['#395DED', '#F46835', '#8964E7', '#12B76A', '#F8B348', '#E25798'];
  function burst(x, y, n) {
    if (reduced()) return; var f = fx(); n = n || 18;
    var w = D.createElement('i'); w.className = 'mo-wave'; w.style.transform = 'translate(' + x + 'px,' + y + 'px)'; f.appendChild(w);
    var wa = ani(w, [{ transform: 'translate(' + x + 'px,' + y + 'px) scale(1)', opacity: 0.9 }, { transform: 'translate(' + x + 'px,' + y + 'px) scale(9)', opacity: 0 }], { duration: 700, easing: EASE.out, fill: 'forwards' });
    if (wa) wa.onfinish = function () { w.remove(); };
    for (var i = 0; i < n; i++) {
      var s = D.createElement('i'); s.className = 'mo-spark'; s.style.background = SPARK[i % SPARK.length]; f.appendChild(s);
      var ang = (i / n) * Math.PI * 2 + Math.random() * 0.5, d = 46 + Math.random() * 70, dx = Math.cos(ang) * d, dy = Math.sin(ang) * d, deg = ang * 180 / Math.PI + 90;
      var sa = ani(s, [{ transform: 'translate(' + x + 'px,' + y + 'px) rotate(' + deg + 'deg) scale(.4)', opacity: 1 },
        { transform: 'translate(' + (x + dx * 0.8) + 'px,' + (y + dy * 0.8) + 'px) rotate(' + deg + 'deg) scale(1)', opacity: 1, offset: 0.45 },
        { transform: 'translate(' + (x + dx) + 'px,' + (y + dy + 26) + 'px) rotate(' + (deg + 40) + 'deg) scale(.2)', opacity: 0 }],
        { duration: 760 + Math.random() * 360, easing: EASE.out, fill: 'forwards' });
      if (sa) sa.onfinish = (function (el) { return function () { el.remove(); }; })(s); else s.remove();
    }
  }
  M.burst = burst;
  function onClickBubble(e) {
    var t = e.target; if (!t || !t.closest) return;
    var b = t.closest('button,a.btn,.send'); if (!b || b.getAttribute('aria-disabled') === 'true' || b.disabled) return;
    if (!(b.classList.contains('ink') || b.classList.contains('send')) || !COMMIT.test(txt(b))) return;
    var r = b.getBoundingClientRect(); burst(e.clientX || r.left + r.width / 2, e.clientY || r.top + r.height / 2);
  }

  /* ---------- 5. in-screen changes: Flip morphs layouts, tabs slide, new things fade in, closed things fade out ---------- */
  var FLIPS = '.qrow,.irow,.irow2,.jcard,.card,.pcard,.wcard,.tile,.chip,.opt2,.mtab,.mtb,.isec,.lchip,.lmk,.sgb,.hstarter,[role="row"],[role="listitem"],[role="tab"],li,.btn,.sendrow,.due,.pill';
  var GROUPS = '[role="tablist"],[role="radiogroup"],.mtabs,.mseg,.sorts,.ifil,.chips,.opts,.fbar,.segs';
  function flipTargets(root, extra) {
    var sel = FLIPS + (extra ? ',' + extra : ''), all = root.querySelectorAll(sel), out = [], vh = innerHeight, cap = innerWidth * innerHeight * 0.3;
    for (var i = 0; i < all.length && out.length < 180; i++) {
      var el = all[i];
      if (el.closest('#mo-fx,.sbar,.tabs,.mo-leaving,[data-mo-own]')) continue;
      var r = el.getBoundingClientRect();
      if (!r.width || !r.height || r.bottom < -vh || r.top > vh * 2) continue;
      if (!extra || !el.matches(extra)) { if (r.width * r.height > cap) continue; }
      out.push(el);
    }
    return out;
  }
  function selected(g) { return g.querySelector('[aria-selected="true"],[aria-pressed="true"],[aria-checked="true"]'); }
  function groupsBefore(root) {
    var gs = root.querySelectorAll(GROUPS), out = [];
    for (var i = 0; i < gs.length; i++) { var s = selected(gs[i]); if (s) out.push({ g: gs[i], el: s, r: s.getBoundingClientRect() }); }
    return out;
  }
  function slideSelection(before) {
    before.forEach(function (b) {
      if (!b.g.isConnected) return;
      var n = selected(b.g); if (!n || n === b.el && b.el.isConnected) return;
      var nr = n.getBoundingClientRect(); if (!nr.width) return;
      var after = getComputedStyle(n, '::after');
      if (after && after.content && after.content !== 'none' && after.content !== 'normal' && after.position === 'absolute') {
        var dx = b.r.left - nr.left, k = b.r.width / nr.width;
        ani(n, [{ transform: 'translateX(' + dx + 'px) scaleX(' + k + ')', transformOrigin: '0 50%' }, { transform: 'translateX(0) scaleX(1)', transformOrigin: '0 50%' }], { duration: 520, easing: EASE.spring, pseudoElement: '::after' });
      } else {
        var f = fx(), ring = D.createElement('i'); ring.className = 'mo-ring'; ring.style.borderRadius = getComputedStyle(n).borderTopLeftRadius; f.appendChild(ring);
        var ra = ani(ring, [{ left: b.r.left + 'px', top: b.r.top + 'px', width: b.r.width + 'px', height: b.r.height + 'px', opacity: 1 },
          { left: nr.left + 'px', top: nr.top + 'px', width: nr.width + 'px', height: nr.height + 'px', opacity: 1, offset: 0.8 },
          { left: nr.left + 'px', top: nr.top + 'px', width: nr.width + 'px', height: nr.height + 'px', opacity: 0 }], { duration: 460, easing: EASE.snap, fill: 'forwards' });
        if (ra) ra.onfinish = function () { ring.remove(); }; else ring.remove();
        ani(n, [{ scale: 0.94 }, { scale: 1 }], { duration: 560, easing: EASE.spring });
      }
    });
  }
  /* rows whose content moved to another row (lists re-rendered in place) glide by what they say, not by which node they are */
  var ROWS = 'li,[role="row"],.qrow,.irow,.irow2,.isec,.jc,.pcard';
  function rowKey(el) { return (el.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 90); }
  function rowsBefore(root) {
    var all = root.querySelectorAll(ROWS), out = [];
    for (var i = 0; i < all.length && out.length < 140; i++) { var el = all[i]; if (el.closest('#mo-fx,.sbar,.tabs,.mo-leaving,[data-mo-own]')) continue; var r = el.getBoundingClientRect(); if (!r.height || r.height > 260 || r.bottom < 0 || r.top > innerHeight * 1.5) continue; out.push({ el: el, k: rowKey(el), r: r }); }
    return out;
  }
  function slideRows(before, root) {
    if (!before || !before.length) return;
    var map = {}; before.forEach(function (b) { if (b.k) (map[b.k] = map[b.k] || []).push(b); });
    var all = root.querySelectorAll(ROWS), n = 0;
    for (var i = 0; i < all.length && n < 60; i++) {
      var el = all[i], k = rowKey(el), olds = map[k]; if (!olds || !olds.length) continue;
      var o = olds.shift(); if (o.el === el) continue;
      var r = el.getBoundingClientRect(), dx = o.r.left - r.left, dy = o.r.top - r.top;
      if (Math.abs(dx) + Math.abs(dy) < 3) continue;
      ani(el, [{ translate: dx + 'px ' + dy + 'px' }, { translate: '0 0' }], { duration: 560, easing: EASE.snap }); n++;
    }
  }
  var pend = null;
  function preFlip(e) {
    if (reduced()) return;
    var t = e.target; if (!t || !t.closest) return;
    if (e.type === 'keydown' && !(e.key === 'Enter' && !e.shiftKey && t.matches && t.matches('textarea,input'))) return;
    if (t.closest('a[href]') && /\.dc\.html/.test(t.closest('a[href]').getAttribute('href') || '')) return;
    var root = content(); if (!root.contains(t) && !t.closest('#mo-fx')) return;
    var ctl = e.type === 'keydown' ? t : t.closest('button,[role="button"],[role="tab"],[role="radio"],[role="checkbox"],summary,label,a[href^="#"],[aria-pressed],.irow');
    if (!ctl) return;
    var label = txt(ctl), dir = /^(back|previous|prev)\b/i.test(label) ? -1 : (/^(next|continue|looks right|done|save|send|share|start|add|team up)\b/i.test(label) || e.type === 'keydown' ? 1 : 0);
    var sel = groupsBefore(root), rows = rowsBefore(root);
    var st = null;
    if (M.Flip) { try { st = M.Flip.getState(flipTargets(root, M.cfg.flip)); } catch (er) { st = null; } }
    if (mo) mo.takeRecords();
    pend = { st: st, sel: sel, rows: rows, dir: dir, t: now(), ran: false };
    setTimeout(function () { if (pend && now() - pend.t > 280) pend = null; }, 320);
  }
  function runFlip() {
    var p = pend; if (!p || p.ran) return; p.ran = true; pend = null;
    slideSelection(p.sel);
    try { slideRows(p.rows, content()); } catch (er) {}
    if (!p.st || !M.Flip) return;
    var root = content(), html = D.documentElement;
    html.classList.add('mo-flipping');
    try {
      M.Flip.from(p.st, {
        targets: flipTargets(root, M.cfg.flip), duration: 0.6, ease: M.ease['mo.snap'], nested: true, prune: true, simple: true,
        onEnter: function (els) { return M.g.fromTo(els, { autoAlpha: 0, x: 26 * p.dir, y: p.dir ? 0 : 12, filter: 'blur(4px)' }, { autoAlpha: 1, x: 0, y: 0, filter: 'blur(0px)', duration: 0.5, ease: M.ease['mo.out'], stagger: 0.03, clearProps: 'opacity,visibility,transform,filter' }); },
        onComplete: function () { html.classList.remove('mo-flipping'); }
      });
    } catch (er) { html.classList.remove('mo-flipping'); }
    if (mo) mo.takeRecords();
  }
  var OVL = '.mwrap,.pvwrap,.snack,.dtoast,.lmpop,.qmenu,.ipop,[role="menu"],.vhint,.pop';
  function ghostOut(node, parent, next) {
    if (reduced() || !parent || !parent.isConnected || node.nodeType !== 1) return;
    if (!(node.matches(OVL))) return;
    node.classList.add('mo-leaving'); node.setAttribute('aria-hidden', 'true'); node.setAttribute('inert', '');
    try { parent.insertBefore(node, next && next.parentNode === parent ? next : null); } catch (e) { return; }
    var box = node.querySelector('.mbox,.pvm'), ph = !!node.closest('.ph');
    var a = ani(node, [{ opacity: 1 }, { opacity: 0 }], { duration: 240, easing: EASE.acc, fill: 'forwards' });
    if (box) ani(box, ph ? [{ translate: '0 0' }, { translate: '0 40%' }] : [{ scale: 1, translate: '0 0' }, { scale: 0.96, translate: '0 8px' }], { duration: 240, easing: EASE.acc, fill: 'forwards' });
    else ani(node, [{ scale: 1 }, { scale: 0.96 }], { duration: 200, easing: EASE.acc, fill: 'forwards' });
    var done = function () { if (node.parentNode) node.parentNode.removeChild(node); };
    if (a) a.onfinish = done; else done();
  }
  function enterIn(nodes) {
    var n = 0;
    nodes.forEach(function (el) {
      if (n > 14 || el.nodeType !== 1 || el.closest('#mo-fx,.mo-leaving,[data-mo-own]') || el.classList.contains('mo-leaving')) return;
      if (/^(SCRIPT|STYLE|LINK|BR|SPAN|B|I|EM|STRONG|SVG|PATH)$/i.test(el.tagName)) return;
      var cs = getComputedStyle(el); if (cs.animationName && cs.animationName !== 'none') return;
      if (cs.position === 'fixed' || cs.display === 'contents') return;
      var r = el.getBoundingClientRect(); if (r.height < 14 || r.bottom < 0 || r.top > innerHeight) return;
      ani(el, [{ opacity: 0, translate: '0 10px', filter: 'blur(3px)' }, { opacity: 1, translate: '0 0', filter: 'blur(0)' }], { duration: 420, delay: n * 28, easing: EASE.out, fill: 'backwards' });
      n++;
    });
  }
  var mo = null;
  function watch() {
    if (mo || !W.MutationObserver) return;
    mo = new MutationObserver(function (list) {
      if (W.__moDebug) W.__moDebug(list, pend);
      var flipped = false;
      if (pend && !pend.ran) { flipped = !!(pend.st && M.Flip); runFlip(); }
      if (reduced()) return;
      var added = [];
      list.forEach(function (m) {
        if (m.type !== 'childList') return;
        Array.prototype.forEach.call(m.removedNodes, function (nd) { if (nd.nodeType === 1 && !nd.classList.contains('mo-leaving')) ghostOut(nd, m.target, m.nextSibling); });
        if (now() - T0 > 1400) Array.prototype.forEach.call(m.addedNodes, function (nd) { if (nd.nodeType === 1 && !nd.classList.contains('mo-leaving')) added.push(nd); });
      });
      if (added.length && !flipped) enterIn(added);
    });
    mo.observe(D.body, { childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: ['aria-selected', 'aria-pressed', 'aria-checked', 'aria-expanded', 'class', 'value', 'open', 'hidden'] });
  }

  /* ---------- 6. GSAP scenes: word-by-word hero lines, scroll reveals, parallax light, counting numbers ---------- */
  function splitHeads() {
    var els = D.querySelectorAll('[data-mo-split]'); if (!els.length) return;
    if (!M.Split || now() - T0 > 1000 || reduced()) return;
    D.documentElement.classList.add('mo-split-on');
    Array.prototype.forEach.call(els, function (el, i) {
      try {
        var sp = M.Split.create ? M.Split.create(el, { type: 'lines,words', mask: 'lines', linesClass: 'mo-ln', wordsClass: 'mo-w', aria: 'auto' }) : new M.Split(el, { type: 'lines,words' });
        M.g.from(sp.words, { yPercent: 115, rotate: 2.5, opacity: 0, duration: 1.15, ease: M.ease['mo.out'], stagger: 0.055, delay: 0.12 + i * 0.15 });
      } catch (e) { el.style.opacity = 1; }
    });
  }
  function scrollScenes() {
    if (!M.ST || reduced()) return;
    var g = M.g, se = D.scrollingElement || D.documentElement;
    if (se.scrollHeight < innerHeight * 1.25) return;
    var root = content(), sel = M.cfg.reveal || '.card,.glass,.icard,.jcard,.wcard,section > h2,section > .h2,article,.isec,li.step,.slab,.qa > *';
    var all = root.querySelectorAll(sel), below = [];
    for (var i = 0; i < all.length; i++) {
      var el = all[i], r = el.getBoundingClientRect();
      if (r.top < innerHeight * 0.95 || r.height > innerHeight * 1.4 || el.closest('.sbar,#mo-fx,.tabs,.reveal')) continue;
      if (below.some(function (b) { return b.contains(el); })) continue;
      below.push(el);
    }
    if (below.length) {
      g.set(below, { autoAlpha: 0, y: 56 });
      M.ST.batch(below, { start: 'top 92%', once: true, onEnter: function (b) { g.to(b, { autoAlpha: 1, y: 0, duration: 1.05, ease: M.ease['mo.out'], stagger: 0.09, overwrite: true, clearProps: 'transform' }); } });
      setTimeout(function () { below.forEach(function (el) { if (el.getBoundingClientRect().top < innerHeight && +getComputedStyle(el).opacity < 0.05) g.set(el, { autoAlpha: 1, y: 0 }); }); }, 6000);
    }
    var orbs = D.querySelectorAll('.amb i,.aurora i');
    Array.prototype.forEach.call(orbs, function (o, i) {
      g.to(o, { '--mo-py': (i % 2 ? -1 : 1) * (60 + i * 30) + 'px', ease: 'none', scrollTrigger: { start: 0, end: 'max', scrub: 0.8 } });
    });
  }
  function countUp() {
    var sel = M.cfg.count; if (!sel || reduced()) return;
    var els = D.querySelectorAll(sel);
    Array.prototype.forEach.call(els, function (el, i) {
      var tn = el.firstChild; if (!tn || tn.nodeType !== 3) return;
      var raw = tn.nodeValue, m = /^([^\d]*)([\d,]+(?:\.\d+)?)(.*)$/.exec(raw); if (!m) return;
      var end = parseFloat(m[2].replace(/,/g, '')), dec = (m[2].split('.')[1] || '').length, comma = m[2].indexOf(',') >= 0;
      if (!isFinite(end) || end === 0) return;
      var fmt = function (v) { var s = v.toFixed(dec); if (comma) s = Number(s).toLocaleString('en-IN', { minimumFractionDigits: dec, maximumFractionDigits: dec }); return m[1] + s + m[3]; };
      var st = null, dur = 1300 + i * 120;
      var step = function (ts) { if (st === null) st = ts; var k = Math.min(1, (ts - st) / dur), e = 1 - Math.pow(1 - k, 4);
        if (tn.parentNode !== el) return; tn.nodeValue = fmt(end * e); if (k < 1) raf(step); else tn.nodeValue = raw; };
      tn.nodeValue = fmt(0); setTimeout(function () { raf(step); }, 260 + i * 60);
    });
  }

  /* ---------- boot, once per screen ---------- */
  M.boot = function (file, cfg) {
    var html = D.documentElement, changed = file && file !== M.file;
    if (changed && M.file) ['mo-a-expand', 'mo-a-portal', 'mo-a-peer', 'mo-a-fwd', 'mo-a-back', 'mo-cine', 'mo-split-on'].forEach(function (c) { html.classList.remove(c); });
    M.file = file || M.file; M.cfg = cfg || {};
    html.classList.add('mo-js');
    if (M.cfg.cine) html.classList.add('mo-cine');
    fx();
    if (!booted) {
      booted = true;
      W.addEventListener('click', onNav, true);
      W.addEventListener('click', preFlip, true);
      W.addEventListener('keydown', preFlip, true);
      W.addEventListener('click', onClickBubble, false);
      D.addEventListener('pointermove', onMove, { passive: true });
      D.addEventListener('pointerdown', onDown, { passive: true });
      W.addEventListener('pointerup', onUp, { passive: true });
      W.addEventListener('pointercancel', onUp, { passive: true });
      D.addEventListener('dragstart', onUp, { passive: true });
    }
    T0 = now();
    arrive();
    watch();
    countUp();
    load();
    M.when(function () { splitHeads(); setTimeout(scrollScenes, 60); if (M.cfg.scene && M.scenes[M.cfg.scene]) M.scenes[M.cfg.scene](M.g); });
  };
  /* ---------- specimens for the Motion board ---------- */
  M.demo = function (kind, el) {
    if (!el || reduced()) return;
    var r = el.getBoundingClientRect(), cs = getComputedStyle(el);
    var rec = { vw: innerWidth, vh: innerHeight, r: [r.left, r.top, r.width, r.height], rad: parseFloat(cs.borderTopLeftRadius) || 0, bg: kind === 'portal' ? '#111111' : solidBg(el), kind: kind };
    if (kind === 'expand') { expandIn(rec); return; }
    if (kind === 'portal') { portalIn(rec); return; }
    var kf = { peer: [{ opacity: 0, scale: 0.975 }, { opacity: 1, scale: 1 }], fwd: [{ opacity: 0, translate: '48px 0' }, { opacity: 1, translate: '0 0' }], back: [{ opacity: 0, translate: '-48px 0' }, { opacity: 1, translate: '0 0' }] }[kind];
    if (kf) Array.prototype.forEach.call(el.children, function (c, i) { ani(c, kf, { duration: 460, delay: i * 40, easing: EASE.out, fill: 'backwards' }); });
  };
  M.replayWords = function (el) {
    if (!el || reduced() || !M.g) return;
    var ws = el.querySelectorAll('.mo-w'); if (!ws.length) return;
    M.g.fromTo(ws, { yPercent: 115, rotate: 2.5, opacity: 0 }, { yPercent: 0, rotate: 0, opacity: 1, duration: 1.15, ease: M.ease['mo.out'], stagger: 0.055 });
  };
  M.countOne = function (el) { var keep = M.cfg.count; M.cfg.count = null; if (el) { el.setAttribute('data-mo-c', '1'); M.cfg.count = '[data-mo-c]'; countUp(); el.removeAttribute('data-mo-c'); } M.cfg.count = keep; };
  M.scenes = {};
  return M;
})();
/* ==== motion v1 engine (end) ==== */
