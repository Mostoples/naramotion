// NaraMotion — logika aplikasi: navigasi, Studio Rekam, Kelas Tari, Arsip, sinkronisasi Firebase.
(function () {
  'use strict';
  const M = window.NaraMotion;
  const $ = (s, r) => (r || document).querySelector(s);
  const $$ = (s, r) => Array.from((r || document).querySelectorAll(s));
  const css = getComputedStyle(document.documentElement);
  const tok = (n) => css.getPropertyValue(n).trim();
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const fmt = (v, d) => v.toFixed(d).replace('.', ',');
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  const PAL = {
    bone: tok('--gold'), boneHi: tok('--gold-bright'), glow: tok('--gold'), ghost: tok('--ghost'),
    ring: tok('--gold-deep'), text: tok('--muted'), node: tok('--gold-bright'), ink: tok('--ink'), sampur: tok('--sogan'), ok: tok('--ok'),
  };
  const danceById = Object.fromEntries(M.DANCES.map((d) => [d.id, d]));

  function toast(msg) {
    const el = $('#toast');
    el.textContent = msg; el.hidden = false;
    clearTimeout(toast.t); toast.t = setTimeout(() => { el.hidden = true; }, 3200);
  }

  // ---------- Autentikasi: Firebase Auth (email/kata sandi + Google) ----------
  const Auth = (() => {
    const cfg = window.NARA_FIREBASE;
    const subs = [];
    let auth = null, user = null, ready = false;
    if (window.firebase && cfg) {
      try {
        firebase.initializeApp(cfg);
        auth = firebase.auth();
        auth.languageCode = 'id';
        auth.onAuthStateChanged((u) => { user = u; ready = true; subs.forEach((f) => f(u)); });
      } catch (e) { auth = null; }
    }
    if (!auth) ready = true;
    const MSG = {
      'auth/invalid-email': 'Format email tidak valid.',
      'auth/missing-password': 'Isi kata sandi terlebih dahulu.',
      'auth/user-not-found': 'Email atau kata sandi salah.',
      'auth/wrong-password': 'Email atau kata sandi salah.',
      'auth/invalid-credential': 'Email atau kata sandi salah.',
      'auth/invalid-login-credentials': 'Email atau kata sandi salah.',
      'auth/email-already-in-use': 'Email ini sudah terdaftar. Silakan masuk.',
      'auth/weak-password': 'Kata sandi minimal 6 karakter.',
      'auth/operation-not-allowed': 'Metode login ini belum diaktifkan di Firebase Console.',
      'auth/configuration-not-found': 'Metode login belum diaktifkan di Firebase Console.',
      'auth/popup-closed-by-user': 'Jendela login Google ditutup sebelum selesai.',
      'auth/cancelled-popup-request': 'Jendela login Google ditutup sebelum selesai.',
      'auth/popup-blocked': 'Jendela pop-up diblokir peramban. Izinkan pop-up untuk situs ini, lalu coba lagi.',
      'auth/unauthorized-domain': 'Domain ini belum diizinkan di pengaturan Firebase Authentication.',
      'auth/too-many-requests': 'Terlalu banyak percobaan. Tunggu beberapa menit lalu coba lagi.',
      'auth/network-request-failed': 'Koneksi gagal. Periksa internet lalu coba lagi.',
      'auth/user-disabled': 'Akun ini dinonaktifkan. Hubungi admin tim.',
    };
    return {
      get user() { return user; },
      get ready() { return ready; },
      get available() { return !!auth; },
      onChange(f) { subs.push(f); if (ready) f(user); },
      token() { return user ? user.getIdToken() : Promise.resolve(null); },
      name(u) { u = u || user; return u ? (u.displayName || (u.email || '').split('@')[0] || 'Pengguna') : ''; },
      message(err) { return MSG[err && err.code] || 'Gagal memproses permintaan (' + ((err && err.code) || 'tidak diketahui') + ').'; },
      signIn(email, pass) { return auth.signInWithEmailAndPassword(email, pass); },
      async signUp(name, email, pass) {
        const cred = await auth.createUserWithEmailAndPassword(email, pass);
        if (name) { await cred.user.updateProfile({ displayName: name }); user = auth.currentUser; subs.forEach((f) => f(user)); }
        return cred;
      },
      google() { return auth.signInWithPopup(new firebase.auth.GoogleAuthProvider()); },
      reset(email) { return auth.sendPasswordResetEmail(email); },
      signOut() { return auth.signOut(); },
    };
  })();

  // ---------- Penyimpanan sesi: Firebase RTDB (REST, dengan token login) dan cadangan lokal ----------
  const Store = (() => {
    const DB = (window.NARA_FIREBASE || {}).databaseURL;
    const LKEY = 'naramotion.sessions.v1';
    let mode = 'checking';
    const local = {
      read() { try { return JSON.parse(localStorage.getItem(LKEY)) || []; } catch (e) { return []; } },
      write(list) { try { localStorage.setItem(LKEY, JSON.stringify(list)); } catch (e) { /* penyimpanan diblokir */ } },
    };
    async function req(path, opt) {
      const token = await Auth.token();
      const url = DB + path + (token ? (path.includes('?') ? '&' : '?') + 'auth=' + encodeURIComponent(token) : '');
      const r = await fetch(url, Object.assign({ headers: { 'Content-Type': 'application/json' } }, opt));
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.json();
    }
    return {
      get mode() { return mode; },
      reset() { mode = 'checking'; },
      async list() {
        if (DB) {
          try {
            const data = await req('/sessions.json?orderBy=%22createdAt%22&limitToLast=50');
            mode = 'cloud';
            return Object.entries(data || {}).map(([id, s]) => Object.assign({ id }, s)).sort((a, b) => b.createdAt - a.createdAt);
          } catch (e) { mode = 'local'; }
        } else mode = 'local';
        return local.read().map(({ frames, ...meta }) => meta);
      },
      async save(meta, frames) {
        if (mode === 'checking') await this.list();
        if (mode === 'cloud') {
          try {
            // Metadata dulu: aturan database mengizinkan /frames hanya untuk pemilik sesi yang sudah ada.
            const { id, ...body } = meta;
            await req('/sessions/' + id + '.json', { method: 'PUT', body: JSON.stringify(body) });
            await req('/frames/' + id + '.json', { method: 'PUT', body: JSON.stringify(JSON.stringify(frames)) });
            return 'cloud';
          } catch (e) { mode = 'local'; }
        }
        const list = local.read(); list.unshift(Object.assign({}, meta, { frames })); local.write(list.slice(0, 20));
        return 'local';
      },
      async frames(id) {
        const l = local.read().find((s) => s.id === id);
        if (l) return l.frames;
        const s = await req('/frames/' + id + '.json');
        return s ? JSON.parse(s) : [];
      },
      async remove(id) {
        const list = local.read(), next = list.filter((s) => s.id !== id);
        if (next.length !== list.length) { local.write(next); return; }
        await req('/frames/' + id + '.json', { method: 'DELETE' });
        await req('/sessions/' + id + '.json', { method: 'DELETE' });
      },
    };
  })();

  // ---------- Navigasi ----------
  const APP_VIEWS = { studio: 'Studio Rekam', kelas: 'Kelas Tari', arsip: 'Arsip Nusantara', auth: 'Masuk' };
  let view = 'landing', wanted = 'studio';
  function route() {
    const h = location.hash.slice(1);
    let appView = h === 'masuk' ? 'auth' : APP_VIEWS[h] && h !== 'auth' ? h : null;
    // Ruang kerja wajib login; landing tetap publik.
    if (appView && appView !== 'auth' && Auth.available && !Auth.user) { wanted = appView; appView = 'auth'; }
    if (appView === 'auth' && Auth.user) { appView = wanted; history.replaceState(null, '', '#' + appView); }
    if (view === 'kelas' && appView !== 'kelas') Kelas.leave();   // matikan kamera saat meninggalkan Kelas
    $('#landing').hidden = !!appView;
    $('#app').hidden = !appView;
    if (appView) {
      view = appView;
      $('#app-title').textContent = APP_VIEWS[appView];
      for (const k of Object.keys(APP_VIEWS)) $('#view-' + k).hidden = k !== appView;
      $('#app-tabs').hidden = appView === 'auth';
      $$('.tabs a').forEach((a) => a.setAttribute('aria-selected', String(a.dataset.tab === appView)));
      $$('.bottom-nav a').forEach((a) => (a.dataset.tab === appView ? a.setAttribute('aria-current', 'page') : a.removeAttribute('aria-current')));
      window.scrollTo(0, 0);
      if (appView === 'auth') AuthUI.show();
      if (appView === 'arsip') Arsip.refresh();
    } else {
      view = 'landing';
      const target = h && document.getElementById(h);
      if (target) requestAnimationFrame(() => target.scrollIntoView());
    }
  }
  window.addEventListener('hashchange', () => { closeMenu(); route(); });

  // Menu seluler
  const menuBtn = $('#menu-btn'), siteNav = $('#site-nav');
  function closeMenu() { siteNav.classList.remove('is-open'); menuBtn.setAttribute('aria-expanded', 'false'); }
  menuBtn.addEventListener('click', () => {
    const open = !siteNav.classList.contains('is-open');
    siteNav.classList.toggle('is-open', open); menuBtn.setAttribute('aria-expanded', String(open));
  });
  siteNav.addEventListener('click', (e) => { if (e.target.closest('a')) closeMenu(); });
  document.addEventListener('click', (e) => { if (!e.target.closest('#site-nav, #menu-btn')) closeMenu(); });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeMenu(); });

  // ---------- Form masuk / daftar ----------
  const AuthUI = (() => {
    const form = $('#auth-form'), nameWrap = $('#f-name-wrap'), nameEl = $('#f-name');
    const emailEl = $('#f-email'), passEl = $('#f-pass'), errEl = $('#auth-error');
    const submit = $('#auth-submit'), google = $('#auth-google'), resetBtn = $('#auth-reset'), note = $('#auth-note');
    let mode = 'login';
    function setMode(m) {
      mode = m;
      $$('#auth-switch button').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.mode === m)));
      nameWrap.hidden = m !== 'signup';
      submit.textContent = m === 'signup' ? 'Daftar' : 'Masuk';
      passEl.autocomplete = m === 'signup' ? 'new-password' : 'current-password';
      resetBtn.hidden = m === 'signup';
      error('');
    }
    function error(msg) { errEl.textContent = msg; errEl.hidden = !msg; }
    function busy(on) { [submit, google, resetBtn].forEach((b) => (b.disabled = on)); }
    $('#auth-switch').addEventListener('click', (e) => { const b = e.target.closest('[data-mode]'); if (b) setMode(b.dataset.mode); });

    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const email = emailEl.value.trim(), pass = passEl.value, name = nameEl.value.trim();
      if (mode === 'signup' && name.length < 2) return error('Isi nama lengkap (minimal 2 huruf).');
      if (!email) return error('Isi email terlebih dahulu.');
      if (pass.length < 6) return error('Kata sandi minimal 6 karakter.');
      busy(true); error('');
      try {
        if (mode === 'signup') await Auth.signUp(name, email, pass);
        else await Auth.signIn(email, pass);
        passEl.value = '';
        toast(mode === 'signup' ? 'Akun dibuat. Selamat datang di NaraMotion.' : 'Berhasil masuk.');
      } catch (err) { error(Auth.message(err)); }
      busy(false);
    });
    google.addEventListener('click', async () => {
      busy(true); error('');
      try { await Auth.google(); toast('Berhasil masuk dengan Google.'); } catch (err) { error(Auth.message(err)); }
      busy(false);
    });
    resetBtn.addEventListener('click', async () => {
      const email = emailEl.value.trim();
      if (!email) return error('Isi email dulu, lalu tekan "Lupa kata sandi?" lagi.');
      busy(true);
      try { await Auth.reset(email); error(''); toast('Tautan atur ulang kata sandi dikirim ke ' + email + '.'); }
      catch (err) { error(Auth.message(err)); }
      busy(false);
    });
    return {
      show() {
        const label = { studio: 'Studio Rekam', kelas: 'Kelas Tari', arsip: 'Arsip Nusantara' }[wanted];
        note.textContent = Auth.ready ? `Masuk untuk membuka ${label}.` : 'Memeriksa status login…';
      },
    };
  })();

  // Bar atas mengikuti status login.
  Auth.onChange((u) => {
    const chip = $('#user-chip');
    chip.hidden = !u; $('#btn-logout').hidden = !u; $('#btn-login').hidden = !!u;
    if (u) {
      const nm = Auth.name(u);
      chip.innerHTML = `<span class="av" aria-hidden="true">${esc(nm.charAt(0).toUpperCase())}</span><span class="nm">${esc(nm)}</span>`;
      chip.title = u.email || nm;
    }
    Store.reset();
    Promise.resolve().then(route); // tunggu semua modul selesai didefinisikan
  });
  $('#btn-logout').addEventListener('click', async () => { await Auth.signOut(); toast('Kamu sudah keluar.'); });

  function fillSelect(sel, value) {
    sel.innerHTML = M.DANCES.map((d) => `<option value="${d.id}">${esc(d.name)} — ${esc(d.region)}</option>`).join('');
    sel.value = value;
  }

  // ---------- Hero ----------
  const Hero = (() => {
    const stage = new M.Stage($('#hero-canvas'), { palette: PAL, yaw: 0.35, autoRotate: reduced ? 0 : 0.18 });
    let t = 0, idx = 0, sinceSwap = 0;
    const name = $('#hero-dance'), region = $('#hero-region');
    function label() { const d = M.DANCES[idx]; name.textContent = d.name; region.textContent = '· ' + d.region; }
    label();
    return {
      tick(dt) {
        if (!reduced) { t += dt; sinceSwap += dt; }
        if (sinceSwap > 14) { sinceSwap = 0; idx = (idx + 1) % M.DANCES.length; stage.trails = {}; label(); }
        stage.tick(dt);
        const J = M.skeleton(M.angles(M.DANCES[idx].p, t + 1.3));
        stage.draw(J, { trail: ['handL', 'handR'], nodes: true, active: null, width: 2.6 });
      },
    };
  })();

  // ---------- Osiloskop sensor ----------
  function Scope(canvas, range, readEl) {
    const ctx = canvas.getContext('2d');
    const N = 240, buf = [[], [], []];
    const colors = [tok('--axis-x'), tok('--axis-y'), tok('--axis-z')];
    let w = 0, h = 0, dpr = 1;
    const fit = () => { const r = canvas.getBoundingClientRect(); dpr = Math.min(2, devicePixelRatio || 1); w = r.width; h = r.height; canvas.width = Math.max(1, w * dpr); canvas.height = Math.max(1, h * dpr); };
    if ('ResizeObserver' in window) new ResizeObserver(fit).observe(canvas);
    fit();
    return {
      push(v) {
        for (let i = 0; i < 3; i++) { buf[i].push(v[i]); if (buf[i].length > N) buf[i].shift(); }
        readEl.textContent = v.map((x) => (x >= 0 ? ' ' : '') + x.toFixed(1)).join('  ');
      },
      clear() { buf.forEach((b) => (b.length = 0)); },
      draw() {
        if (!w) return;
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        ctx.clearRect(0, 0, w, h);
        const padL = 34, y = (v) => h / 2 - (v / range) * (h / 2 - 8);
        ctx.font = '400 9px "IBM Plex Mono", monospace';
        ctx.textAlign = 'right'; ctx.textBaseline = 'middle';
        for (const g of [-range, -range / 2, 0, range / 2, range]) {
          ctx.strokeStyle = g === 0 ? 'rgba(212,169,76,.35)' : 'rgba(212,169,76,.1)';
          ctx.beginPath(); ctx.moveTo(padL, y(g)); ctx.lineTo(w, y(g)); ctx.stroke();
          if (g !== range / 2 && g !== -range / 2) { ctx.fillStyle = PAL.text; ctx.fillText(String(g), padL - 6, y(g)); }
        }
        const dx = (w - padL) / (N - 1);
        for (let i = 0; i < 3; i++) {
          const b = buf[i]; if (b.length < 2) continue;
          ctx.strokeStyle = colors[i]; ctx.lineWidth = 1.4;
          ctx.beginPath();
          const off = N - b.length;
          for (let j = 0; j < b.length; j++) {
            const px = padL + (off + j) * dx, py = y(Math.max(-range, Math.min(range, b[j])));
            j ? ctx.lineTo(px, py) : ctx.moveTo(px, py);
          }
          ctx.stroke();
          const last = b[b.length - 1];
          ctx.fillStyle = colors[i];
          ctx.beginPath(); ctx.arc(w - 2, y(Math.max(-range, Math.min(range, last))), 2.5, 0, Math.PI * 2); ctx.fill();
        }
      },
    };
  }

  // ---------- Studio ----------
  const Studio = (() => {
    const stage = new M.Stage($('#studio-canvas'), { palette: PAL, yaw: 0.5, autoRotate: reduced ? 0 : 0.12 });
    const sel = $('#studio-dance');
    const st = { dance: 'gambyong', node: 'fArmR', t: 0, speed: 1, playing: true, rec: false, recT: 0, frames: [], lastRec: -1 };
    const scopes = {
      acc: Scope($('#scope-acc'), 20, $('#r-acc')),
      gyr: Scope($('#scope-gyr'), 250, $('#r-gyr')),
      mag: Scope($('#scope-mag'), 60, $('#r-mag')),
    };
    fillSelect(sel, st.dance);
    sel.addEventListener('change', () => { st.dance = sel.value; stage.trails = {}; });
    // Rekaman mocap AIST++ (CC BY 4.0) diputar sebagai sumber gerak nyata: kerangka & sensor sintetis 10 node.
    fetch('assets/ml/studio_clips.json').then((r) => (r.ok ? r.json() : null)).then((data) => {
      if (!data || !data.clips) return;
      const og = document.createElement('optgroup'); og.label = 'Rekaman mocap · AIST++ (CC BY 4.0)';
      for (const c of data.clips) {
        const id = 'aist-' + c.name.slice(0, 3);
        danceById[id] = { id, name: c.genre + ' (AIST++)', region: 'Rekaman mocap AIST++', motifs: ['Genre ' + c.genre, 'Rekaman 60 fps', 'Penari profesional'],
          p: { tempo: 0.25 }, clip: M.clipSource(c) };
        og.insertAdjacentHTML('beforeend', `<option value="${id}">${esc(c.genre)} — rekaman mocap</option>`);
      }
      sel.appendChild(og);
    }).catch(() => {});

    // Gerak dasar Bali dalam 3D (SAM 3D Body dari video dataset Mendeley, CC BY 4.0), lengkap dengan jari
    fetch('assets/ml/sam3d_clips.json').then((r) => (r.ok ? r.json() : null)).then((data) => {
      if (!data || !data.clips) return;
      // satu optgroup per kelompok (putri/putra): 24 gerak dasar, masing-masing satu klip representatif
      const groups = {};
      for (const c of data.clips) {
        const id = 'sam3d-' + c.name, ds = c.ds || 'putri';
        const og = groups[ds] || (groups[ds] = Object.assign(document.createElement('optgroup'), { label: `Gerak dasar Bali ${ds} · 3D dari video (SAM 3D Body)` }));
        danceById[id] = { id, name: `${c.gerak} (${ds}, 3D)`, region: `Bali · gerak dasar ${ds} · pose 3D dari video`, motifs: [c.gerak, 'Pose 3D dari video', 'Lengkap dengan jari'],
          p: { tempo: 0.25 }, clip: M.positionSource(c) };
        og.insertAdjacentHTML('beforeend', `<option value="${id}">${esc(c.gerak)} — ${ds}</option>`);
      }
      const first = sel.querySelector('optgroup');
      for (const og of Object.values(groups)) sel.insertBefore(og, first);
    }).catch(() => {});

    const list = $('#node-list');
    list.innerHTML = M.NODES.map((n) => `<button type="button" class="node-btn" data-node="${n.id}" aria-pressed="${n.id === st.node}"><i></i>${esc(n.label)}</button>`).join('');
    list.addEventListener('click', (e) => {
      const b = e.target.closest('[data-node]'); if (!b) return;
      st.node = b.dataset.node;
      $$('.node-btn', list).forEach((x) => x.setAttribute('aria-pressed', String(x === b)));
      $('#q-node').textContent = M.nodeById[st.node].label;
      Object.values(scopes).forEach((s) => s.clear());
    });

    $('#studio-speed').addEventListener('click', (e) => {
      const b = e.target.closest('[data-speed]'); if (!b) return;
      st.speed = parseFloat(b.dataset.speed);
      $$('#studio-speed button').forEach((x) => x.setAttribute('aria-pressed', String(x === b)));
    });
    const playBtn = $('#studio-play');
    playBtn.addEventListener('click', () => { st.playing = !st.playing; playBtn.textContent = st.playing ? 'Jeda' : 'Putar'; });
    const camBtn = $('#studio-cam');
    camBtn.textContent = 'Putar kamera: ' + (stage.autoRotate ? 'aktif' : 'mati');
    camBtn.addEventListener('click', () => { stage.autoRotate = stage.autoRotate ? 0 : 0.12; camBtn.textContent = 'Putar kamera: ' + (stage.autoRotate ? 'aktif' : 'mati'); });

    const recBtn = $('#studio-rec'), recLabel = $('#studio-rec-label'), recInfo = $('#studio-rec-info');
    recBtn.addEventListener('click', () => (st.rec ? stopRec() : startRec()));
    function startRec() {
      st.rec = true; st.recT = 0; st.frames = []; st.lastRec = -1;
      recBtn.classList.add('is-rec'); recLabel.textContent = 'Hentikan'; recInfo.hidden = false;
      if (!st.playing) playBtn.click();
    }
    async function stopRec() {
      st.rec = false;
      recBtn.classList.remove('is-rec'); recLabel.textContent = 'Rekam'; recInfo.hidden = true;
      if (st.frames.length < 10) { toast('Rekaman terlalu singkat. Rekam minimal satu detik.'); return; }
      const d = danceById[st.dance];
      const meta = {
        id: Date.now().toString(36) + Math.random().toString(36).slice(2, 6),
        dance: d.id, danceName: d.name, createdAt: Date.now(),
        duration: Math.round(st.recT * 10) / 10, frameCount: st.frames.length, rate: 20, nodes: M.NODES.length,
        uid: Auth.user ? Auth.user.uid : 'lokal', ownerName: Auth.name() || 'Perangkat ini',
      };
      const where = await Store.save(meta, st.frames);
      toast(where === 'cloud' ? 'Sesi tersimpan ke Arsip (Firebase).' : 'Sesi tersimpan di peramban ini.');
    }

    const q = ['w', 'x', 'y', 'z'].map((k) => $('#q-' + k));
    const e = ['r', 'p', 'y'].map((k) => $('#e-' + k));
    const clock = $('#studio-clock');
    const motifList = $('#motif-list');
    let motifShown = '', uiTimer = 0;

    function renderMotifs(d, t) {
      const cyc = t * d.p.tempo, idx = Math.floor(cyc) % d.motifs.length;
      const frac = cyc - Math.floor(cyc);
      const top = 0.72 + 0.24 * Math.sin(Math.PI * frac);
      const nxt = (1 - top) * (0.35 + 0.5 * frac);
      const rest = Math.max(0, 1 - top - nxt);
      const rows = [[d.motifs[idx], top], [d.motifs[(idx + 1) % d.motifs.length], nxt], [d.motifs[(idx + 2) % d.motifs.length], rest]];
      const key = rows.map((r) => r[0] + Math.round(r[1] * 100)).join('|');
      if (key === motifShown) return;
      motifShown = key;
      motifList.innerHTML = rows.map(([n, c]) => `<li><span>${esc(n)}</span><b>${Math.round(c * 100)}%</b><span class="bar"><span style="width:${(c * 100).toFixed(1)}%"></span></span></li>`).join('');
    }

    return {
      setDance(id) { st.dance = id; sel.value = id; stage.trails = {}; },
      tick(dt) {
        if (st.playing) st.t += dt * st.speed;
        stage.tick(dt);
        const d = danceById[st.dance];
        const s = M.sensors(d.clip || d.p, st.t, st.node);
        stage.draw(s.J, { trail: [M.nodeById[st.node].at], active: st.node });
        if (st.playing) { scopes.acc.push(s.acc); scopes.gyr.push(s.gyr); scopes.mag.push(s.mag); }
        Object.values(scopes).forEach((x) => x.draw());

        if (st.rec && st.playing) {
          st.recT += dt;
          if (st.recT - st.lastRec >= 0.05) {
            st.lastRec = st.recT;
            const J = s.J;
            st.frames.push(M.NODES.map((n) => M.quatFromFrame(M.frameOf(J, n)).map((v) => Math.round(v * 1000) / 1000)));
          }
          if (st.recT >= 60) stopRec();
        }

        uiTimer += dt;
        if (uiTimer > 0.1) {
          uiTimer = 0;
          s.q.forEach((v, i) => (q[i].textContent = v.toFixed(3)));
          M.euler(s.q).forEach((v, i) => (e[i].textContent = Math.round(v) + '°'));
          const m = Math.floor(st.t / 60), sec = st.t % 60;
          clock.textContent = String(m).padStart(2, '0') + ':' + sec.toFixed(1).padStart(4, '0');
          if (st.rec) recInfo.textContent = '● REC ' + String(Math.floor(st.recT / 60)).padStart(2, '0') + ':' + String(Math.floor(st.recT % 60)).padStart(2, '0') + ' · ' + st.frames.length + ' frame';
          renderMotifs(d, st.t);
        }
      },
    };
  })();

  // ---------- Kelas ----------
  const Kelas = (() => {
    const ref = new M.Stage($('#kelas-ref'), { palette: PAL, yaw: 0.45 });
    const stu = new M.Stage($('#kelas-stu'), { palette: PAL, yaw: 0.45 });
    const sel = $('#kelas-dance'), skillEl = $('#kelas-skill'), skillVal = $('#kelas-skill-val');
    const st = { dance: 'gambyong', t: 0, playing: true, skill: 0.55, err: {}, score: 0, hist: [], refBuf: [], stuBuf: [], acc: 0, lag: 0, dtw: 0, fbT: 0, sampT: 0 };
    fillSelect(sel, st.dance);
    sel.addEventListener('change', () => { st.dance = sel.value; reset(); });
    function skillLabel(v) { return v < 0.35 ? 'Pemula' : v < 0.7 ? 'Menengah' : 'Mahir'; }
    skillEl.addEventListener('input', () => { st.skill = skillEl.value / 100; skillVal.textContent = skillLabel(st.skill); });
    const playBtn = $('#kelas-play');
    playBtn.addEventListener('click', () => { st.playing = !st.playing; playBtn.textContent = st.playing ? 'Jeda' : 'Putar'; });
    function reset() { st.hist = []; st.refBuf = []; st.stuBuf = []; st.err = {}; }

    // Mode Kamera AI (js/camera.js): pengenal gerak dasar tari Bali + skor terhadap gerak acuan
    const view = $('#view-kelas'), camBlock = $('#kelas-cam'), badge = $('#kelas-badge');
    st.mode = 'sim';
    const cam = window.NaraCamera ? window.NaraCamera.CameraCoach(camBlock, { palette: PAL, onResult: camResult }) : null;
    $('#kelas-mode').addEventListener('click', (e) => {
      const b = e.target.closest('[data-mode]'); if (!b || !cam) return;
      st.mode = b.dataset.mode;
      $$('#kelas-mode button').forEach((x) => x.setAttribute('aria-pressed', String(x === b)));
      const isCam = st.mode === 'cam';
      view.classList.toggle('is-cam', isCam); camBlock.hidden = !isCam;
      badge.textContent = isCam ? 'Kamera · AI di perangkat' : 'Siswa contoh · data simulasi';
      if (isCam) cam.activate(); else { cam.deactivate(); reset(); }
    });
    const camScore = $('#cam-score'), camGrade = $('#cam-grade'), camTop = $('#cam-top');
    function camResult(r) {
      const sc = Math.round(r.score);
      camScore.textContent = sc;
      const hit = r.top[0][0] === r.target;
      camGrade.textContent = (sc >= 85 ? 'Sangat mirip acuan' : sc >= 70 ? 'Baik, sedikit lagi' : sc >= 50 ? 'Perlu latihan' : 'Ikuti gerak acuan') + (hit ? '' : ' · terbaca sebagai ' + r.top[0][0].replace(/_/g, ' '));
      camTop.innerHTML = r.top.map(([c, p]) => `<li><span>${esc(c.replace(/_/g, ' '))}</span><b>${Math.round(p * 100)}%</b><span class="bar"><span style="width:${(p * 100).toFixed(1)}%"></span></span></li>`).join('');
      for (const n of M.NODES) st.err[n.id] = st.err[n.id] == null ? r.err[n.id] : st.err[n.id] * 0.6 + r.err[n.id] * 0.4;
      st.lag = 0; renderRows(); renderFeedback();
    }

    const rows = $('#joint-rows');
    rows.innerHTML = M.NODES.map((n) => `<tr data-n="${n.id}"><th scope="row">${esc(n.label)}</th><td class="num">0,0°</td><td><div class="ebar"><span></span></div></td><td><span class="chip ok">Tepat</span></td></tr>`).join('');
    const rowEls = Object.fromEntries($$('tr', rows).map((tr) => [tr.dataset.n, { num: tr.children[1], bar: $('span', tr.children[2]), chip: $('.chip', tr) }]));

    function studentAngles(p, t, skill) {
      const k = 1 - skill;
      const a = M.angles(p, t - k * 0.34);
      a.knee *= 1 - 0.5 * k;
      a.lAb += k * 0.32 * Math.sin(t * 1.3);
      a.rAb -= k * 0.22;
      a.lEl *= 1 - 0.35 * k;
      a.rFl += k * 0.3 * Math.sin(t * 0.9 + 1);
      a.lWr *= 1 - 0.6 * k; a.rWr *= 1 - 0.6 * k;
      a.bend += k * 0.14 * Math.sin(t * 0.7);
      a.head *= 1 - 0.6 * k;
      a.rLift *= 1 - 0.5 * k;
      return a;
    }

    function estimateLag(r, s) {
      let best = 0, bestE = Infinity;
      const n = r.length;
      for (let L = 0; L <= 15; L++) {
        let e = 0;
        for (let i = L; i < n; i++) { const d = r[i - L] - s[i]; e += d * d; }
        e /= Math.max(1, n - L);
        if (e < bestE) { bestE = e; best = L; }
      }
      return best / 30;
    }
    function dtw(a, b) {
      const n = a.length, m = b.length;
      let prev = new Float64Array(m + 1).fill(Infinity), cur = new Float64Array(m + 1);
      prev[0] = 0;
      for (let i = 1; i <= n; i++) {
        cur.fill(Infinity);
        for (let j = 1; j <= m; j++) cur[j] = Math.abs(a[i - 1] - b[j - 1]) + Math.min(prev[j], cur[j - 1], prev[j - 1]);
        [prev, cur] = [cur, prev];
      }
      return prev[m] / (n + m);
    }

    const ADVICE = {
      head: 'Jaga arah pandangan dan gerak kepala tetap halus; kepala belum mengikuti irama maestro.',
      torso: 'Tegakkan badan. Condong tubuh ke samping masih terlalu besar.',
      uArmL: 'Atur lengan atas kiri: bukaan bahu belum sama dengan maestro.',
      fArmL: 'Perhatikan lengan bawah kiri: posisi siku dan ukel belum sesuai maestro.',
      uArmR: 'Atur lengan atas kanan: angkat sedikit dari badan seperti maestro.',
      fArmR: 'Perhatikan lengan bawah kanan: angkat sedikit dan perjelas ukel.',
      thighL: 'Paha kiri kurang menekuk; turunkan badan agar mendhak lebih dalam.',
      shinL: 'Tekuk lutut kiri lebih dalam agar posisi mendhak stabil.',
      thighR: 'Paha kanan kurang menekuk; jaga tumpuan saat berpindah berat badan.',
      shinR: 'Tekuk lutut kanan lebih dalam dan atur angkatan kaki kanan.',
    };
    const fbEl = $('#feedback');
    function renderFeedback() {
      const items = [];
      if (st.lag > 0.08) items.push(['', `Gerakanmu tertinggal sekitar ${fmt(st.lag, 2)} detik dari maestro. Dengarkan ketukan kendang dan mulai gerak sedikit lebih awal.`]);
      const worst = M.NODES.map((n) => [n.id, st.err[n.id] || 0]).sort((a, b) => b[1] - a[1]);
      for (const [id, e] of worst.slice(0, 2)) if (e > 12) items.push(['', ADVICE[id] + ` (galat ${fmt(e, 1)}°)`]);
      const good = worst.filter(([, e]) => e < 8).map(([id]) => M.nodeById[id].label.toLowerCase());
      if (good.length) items.push(['good', `Sudah tepat: ${good.slice(0, 3).join(', ')}. Pertahankan.`]);
      if (!items.length) items.push(['good', 'Gerakan sudah sangat dekat dengan maestro. Lanjutkan ke ragam gerak berikutnya.']);
      fbEl.innerHTML = items.map(([c, t]) => `<li class="${c}">${esc(t)}</li>`).join('');
    }

    const arc = $('#gauge-arc'), num = $('#score-num'), grade = $('#score-grade');
    const lagEl = $('#m-lag'), dtwEl = $('#m-dtw');
    const spark = $('#score-spark'), sctx = spark.getContext('2d');
    function drawSpark() {
      const r = spark.getBoundingClientRect(), dpr = Math.min(2, devicePixelRatio || 1);
      if (!r.width) return;
      spark.width = r.width * dpr; spark.height = r.height * dpr;
      sctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      const w = r.width, h = r.height, H = st.hist;
      sctx.strokeStyle = 'rgba(212,169,76,.12)';
      for (const g of [0.25, 0.5, 0.75]) { sctx.beginPath(); sctx.moveTo(0, h * g); sctx.lineTo(w, h * g); sctx.stroke(); }
      if (H.length < 2) return;
      const x = (i) => (i / 59) * (w - 6), y = (v) => h - 4 - (v / 100) * (h - 8);
      const grd = sctx.createLinearGradient(0, 0, 0, h);
      grd.addColorStop(0, 'rgba(212,169,76,.35)'); grd.addColorStop(1, 'rgba(212,169,76,0)');
      sctx.beginPath(); sctx.moveTo(x(0), h);
      H.forEach((v, i) => sctx.lineTo(x(i), y(v)));
      sctx.lineTo(x(H.length - 1), h); sctx.closePath(); sctx.fillStyle = grd; sctx.fill();
      sctx.beginPath(); H.forEach((v, i) => (i ? sctx.lineTo(x(i), y(v)) : sctx.moveTo(x(i), y(v))));
      sctx.strokeStyle = PAL.boneHi; sctx.lineWidth = 1.5; sctx.stroke();
      sctx.fillStyle = PAL.boneHi;
      sctx.beginPath(); sctx.arc(x(H.length - 1), y(H[H.length - 1]), 3, 0, Math.PI * 2); sctx.fill();
    }

    const api = {
      setDance(id) { st.dance = id; sel.value = id; reset(); },
      leave() { if (cam && st.mode === 'cam') cam.deactivate(); },
      openCam(ds, move) {
        if (!cam) return;
        if (st.mode !== 'cam') $('#kelas-mode [data-mode="cam"]').click();
        cam.select(ds, move);
      },
      tick(dt) {
        if (st.mode === 'cam') { cam.tick(dt, performance.now()); return; }
        if (st.playing) st.t += dt;
        const p = danceById[st.dance].p;
        const Jr = M.skeleton(M.angles(p, st.t));
        const Js = M.skeleton(studentAngles(p, st.t, st.skill));
        ref.draw(Jr, { nodes: false, trail: ['handR'] });
        stu.draw(Js, { ghost: Jr, nodes: false, trail: ['handR'] });
        if (!st.playing) return;

        let sum = 0;
        for (const n of M.NODES) {
          const e = M.angleBetween(M.segDir(Jr, n), M.segDir(Js, n));
          st.err[n.id] = st.err[n.id] == null ? e : st.err[n.id] * 0.92 + e * 0.08;
          sum += st.err[n.id];
        }
        const mean = sum / M.NODES.length;
        const target = Math.max(0, Math.min(100, 100 - mean * 2.1));
        st.score = st.score * 0.94 + target * 0.06;

        st.sampT += dt;
        while (st.sampT >= 1 / 30) {
          st.sampT -= 1 / 30;
          st.refBuf.push(Jr.wristR[1]); st.stuBuf.push(Js.wristR[1]);
          if (st.refBuf.length > 90) { st.refBuf.shift(); st.stuBuf.shift(); }
        }

        st.acc += dt;
        if (st.acc >= 0.5) {
          st.acc = 0;
          if (st.refBuf.length > 40) { st.lag = estimateLag(st.refBuf, st.stuBuf); st.dtw = dtw(st.refBuf, st.stuBuf) * 100; }
          st.hist.push(st.score); if (st.hist.length > 60) st.hist.shift();
          const sc = Math.round(st.score);
          num.textContent = sc;
          arc.style.strokeDashoffset = String(314.16 * (1 - sc / 100));
          arc.style.stroke = sc >= 80 ? tok('--gold-bright') : sc >= 60 ? tok('--gold') : tok('--sogan');
          grade.textContent = sc >= 85 ? 'Sangat mirip maestro' : sc >= 70 ? 'Baik, sedikit lagi' : sc >= 50 ? 'Perlu latihan' : 'Ulangi bersama maestro';
          lagEl.textContent = fmt(st.lag, 2) + ' s';
          dtwEl.textContent = fmt(st.dtw, 2);
          renderRows();
          drawSpark();
          st.fbT += 0.5;
          if (st.fbT >= 1.5) { st.fbT = 0; renderFeedback(); }
        }
      },
    };
    function renderRows() {
      for (const n of M.NODES) {
        const e = st.err[n.id] || 0, r = rowEls[n.id];
        const cls = e < 10 ? 'ok' : e < 25 ? 'warn' : 'bad';
        r.num.textContent = fmt(e, 1) + '°';
        r.bar.style.width = Math.min(100, (e / 45) * 100) + '%';
        r.bar.style.background = tok('--' + cls);
        r.chip.className = 'chip ' + cls;
        r.chip.textContent = cls === 'ok' ? 'Tepat' : cls === 'warn' ? 'Mendekati' : 'Perbaiki';
      }
    }
    return api;
  })();

  // ---------- Arsip ----------
  const Arsip = (() => {
    const cards = $('#dance-cards');
    cards.innerHTML = M.DANCES.map((d) => `
      <article class="dcard frame">
        <h3>${esc(d.name)}</h3>
        <p class="region">${esc(d.region)}</p>
        <p class="char">${esc(d.character)}</p>
        <p>${esc(d.about)}</p>
        <div class="chips">${d.motifs.map((m) => `<span>${esc(m)}</span>`).join('')}</div>
        <div class="acts">
          <button type="button" class="btn btn-gold btn-sm" data-go="studio" data-d="${d.id}">Rekam di Studio</button>
          <button type="button" class="btn btn-line btn-sm" data-go="kelas" data-d="${d.id}">Latihan</button>
        </div>
      </article>`).join('');
    cards.addEventListener('click', (e) => {
      const b = e.target.closest('[data-go]'); if (!b) return;
      (b.dataset.go === 'studio' ? Studio : Kelas).setDance(b.dataset.d);
      location.hash = b.dataset.go;
    });

    // Gerak dasar tari Bali (dataset Mendeley, CC BY 4.0) → latihan langsung di Kelas · Kamera AI
    const BALI = [
      { ds: 'putri', name: 'Gerak dasar putri', region: 'Bali · 9 penari, 1.740 video', moves: ['Agem Kanan', 'Agem Kiri', 'Ulap-Ulap', 'Ngegol', 'Seledet', 'Nyalud', 'Nyeregseg', 'Ngelung', 'Ngeseh', 'Tapak Sirangpada', 'Ngeed', 'Ngelo', 'Ngumbang'] },
      { ds: 'putra', name: 'Gerak dasar putra', region: 'Bali · 4 penari, 828 video', moves: ['Agem Kanan', 'Agem Kiri', 'Gandang-Gandang', 'Malpal', 'Nayog', 'Nepuk Kampuh', 'Oyod', 'Piles', 'Seledet', 'Tapak Sirang Pada', 'Ulap-Ulap'] },
    ];
    $('#bali-cards').innerHTML = BALI.map((b) => `
      <article class="dcard frame">
        <h3>${esc(b.name)}</h3>
        <p class="region">${esc(b.region)}</p>
        <p>Pilih satu gerak untuk dilatih di depan kamera. AI mengenali gerakmu dan membandingkannya dengan contoh acuan dari penari Bali.</p>
        <div class="chips">${b.moves.map((m) => `<button type="button" class="chip-btn" data-ds="${b.ds}" data-move="${esc(m)}">${esc(m)}</button>`).join('')}</div>
        <p class="fine">Data: Hendrawan dkk., Mendeley Data, CC BY 4.0.</p>
      </article>`).join('');
    $('#bali-cards').addEventListener('click', (e) => {
      const b = e.target.closest('[data-move]'); if (!b) return;
      location.hash = 'kelas'; Kelas.openCam(b.dataset.ds, b.dataset.move);
    });

    // Animasi 3D semua gerak (Motion2MixamoRig) · satu klip per gerak
    (function animGallery() {
      const mv = $('#anim-mv'), vid = $('#anim-vid'), moves = $('#anim-moves'); if (!mv) return;
      const LIMITED = { 'putri__Seledet': 'Seledet adalah gerak mata dan kepala yang direkam dari dekat, jadi animasi tubuhnya hanya sedikit bergerak.',
        'putra__Seledet': 'Seledet adalah gerak mata dan kepala yang direkam dari dekat, jadi animasi tubuhnya hanya sedikit bergerak.',
        'putri__Tapak_Sirangpada': 'Video Tapak Sirangpada lebih banyak menampilkan kaki, jadi gerak tubuh bagian atas pada karakter kurang akurat.' };
      let list = [], ds = 'putri', cur = null, srcMode = 'rig';
      function show(key) {
        const r = list.find((x) => x.key === key); if (!r) return; cur = r;
        const glb = srcMode === 'rig' && r.rig ? r.rig : `assets/ml/anim/m2mr/${r.key}.glb`;
        mv.src = glb; mv.alt = `Animasi 3D gerak ${r.gerak} (${r.ds})`;
        $('#anim-arena').href = `arena.html?gerak=${encodeURIComponent(r.key)}`;
        const dl = $('#anim-dl'); dl.href = glb; dl.setAttribute('download', `naramotion_${r.key}_${srcMode}.glb`);
        vid.src = `assets/ml/anim/m2mr/${r.key}.mp4`; vid.play().catch(() => {});
        const clip = (srcMode === 'rig' && r.rig_clip ? r.rig_clip : r.clip).replace(/_/g, ' ');
        $('#anim-cap').textContent = `${r.gerak} · ${r.ds} · klip ${clip} · ${srcMode === 'rig' ? 'rig dari SAM 3D Body' : 'Motion2MixamoRig'}`;
        const w = $('#anim-warn'); w.hidden = !LIMITED[r.key]; w.textContent = LIMITED[r.key] || '';
        moves.querySelectorAll('[data-akey]').forEach((b) => b.setAttribute('aria-pressed', b.dataset.akey === key));
      }
      function renderMoves() {
        const rows = list.filter((x) => x.ds === ds);
        moves.innerHTML = rows.map((r) => `<button type="button" class="chip-btn" data-akey="${esc(r.key)}" aria-pressed="false">${esc(r.gerak)}</button>`).join('');
        document.querySelectorAll('[data-ads]').forEach((b) => b.setAttribute('aria-selected', b.dataset.ads === ds));
        if (rows[0]) show(rows[0].key);
      }
      document.querySelectorAll('[data-ads]').forEach((b) => b.addEventListener('click', () => { ds = b.dataset.ads; renderMoves(); }));
      document.querySelectorAll('[data-asrc]').forEach((b) => b.addEventListener('click', () => {
        srcMode = b.dataset.asrc; document.querySelectorAll('[data-asrc]').forEach((x) => x.setAttribute('aria-pressed', String(x === b)));
        if (cur) show(cur.key);
      }));
      moves.addEventListener('click', (e) => { const b = e.target.closest('[data-akey]'); if (b) show(b.dataset.akey); });
      $('#anim-practice').addEventListener('click', () => { if (!cur) return; location.hash = 'kelas'; Kelas.openCam(cur.ds, cur.gerak); });
      fetch('assets/ml/anim/m2mr/index.json').then((r) => r.json()).then((j) => { list = j; renderMoves(); })
        .catch(() => { $('#anim-cap').textContent = 'Animasi 3D belum bisa dimuat. Muat ulang halaman untuk mencoba lagi.'; });
    })();

    // dari feed video contoh (js/landing.js): langsung latihan gerak itu di Kamera AI
    window.addEventListener('nara:practice', (e) => { location.hash = 'kelas'; Kelas.openCam(e.detail.ds, e.detail.move); });

    $('#landing-dances').innerHTML = M.DANCES.map((d) => `
      <article><h3>${esc(d.name)}</h3><p class="region">${esc(d.region)}</p><p>${esc(d.character)}. ${esc(d.motifs.slice(0, 3).join(', '))}.</p></article>`).join('');

    const table = $('#sessions-table'), tbody = $('#session-rows'), empty = $('#sessions-empty'), sync = $('#sync-status');
    let sessions = [];
    const armed = new Set();
    function render() {
      empty.hidden = sessions.length > 0; table.hidden = sessions.length === 0;
      tbody.innerHTML = sessions.map((s) => {
        const dt = new Date(s.createdAt);
        const when = dt.toLocaleDateString('id-ID', { day: 'numeric', month: 'short', year: 'numeric' }) + ' ' + dt.toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit' });
        const mine = !Auth.available || s.uid === 'lokal' || (Auth.user && s.uid === Auth.user.uid);
        return `<tr><td class="mono" data-label="Waktu">${esc(when)}</td><td data-label="Tari">${esc(s.danceName || s.dance)}</td><td data-label="Oleh">${esc(s.ownerName || '—')}${mine ? '<span class="tag">kamu</span>' : ''}</td><td class="mono" data-label="Durasi">${fmt(+s.duration || 0, 1)} s</td><td class="mono" data-label="Frame">${+s.frameCount || 0}</td>
          <td><div class="acts"><button type="button" class="btn btn-line btn-sm" data-copy="${esc(s.id)}">Salin JSON</button>
          ${mine ? `<button type="button" class="btn btn-line btn-sm" data-del="${esc(s.id)}">${armed.has(s.id) ? 'Yakin hapus?' : 'Hapus'}</button>` : ''}</div></td></tr>`;
      }).join('');
    }
    tbody.addEventListener('click', async (e) => {
      const c = e.target.closest('[data-copy]'), d = e.target.closest('[data-del]');
      if (c) {
        const s = sessions.find((x) => x.id === c.dataset.copy);
        try {
          const frames = await Store.frames(s.id);
          const json = JSON.stringify({ format: 'naramotion-quat-v1', nodes: M.NODES.map((n) => n.id), order: 'w,x,y,z', session: s, frames });
          await navigator.clipboard.writeText(json);
          toast(`Data ${frames.length} frame tersalin ke clipboard.`);
        } catch (err) { toast('Gagal menyalin data. Izinkan akses papan klip, lalu coba lagi.'); }
      } else if (d) {
        const id = d.dataset.del;
        if (!armed.has(id)) { armed.add(id); render(); setTimeout(() => { armed.delete(id); render(); }, 4000); return; }
        try { await Store.remove(id); sessions = sessions.filter((x) => x.id !== id); armed.delete(id); render(); toast('Sesi dihapus.'); }
        catch (err) { toast('Gagal menghapus sesi. Coba lagi.'); }
      }
    });
    return {
      async refresh() {
        sync.textContent = 'Memuat sesi…';
        sessions = await Store.list();
        sync.textContent = Store.mode === 'cloud'
          ? 'Tersinkron dengan Firebase Realtime Database. Sesi dapat dilihat dari perangkat lain.'
          : 'Firebase tidak terjangkau. Sesi disimpan di peramban ini saja.';
        render();
      },
    };
  })();

  // ---------- Loop utama ----------
  let last = performance.now();
  function frame(now) {
    const dt = Math.min(0.05, (now - last) / 1000); last = now;
    if (view === 'landing') Hero.tick(dt);
    else if (view === 'studio') Studio.tick(dt);
    else if (view === 'kelas') Kelas.tick(dt);
    requestAnimationFrame(frame);
  }
  route();
  requestAnimationFrame(frame);
})();
