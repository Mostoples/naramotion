/* NaraMotion · Kelas Tari mode Kamera AI.
   Kamera/video → MediaPipe Pose (browser) → 17 titik COCO → model ONNX pengenal gerak dasar tari Bali
   + skor kemiripan terhadap gerak acuan per 10 segmen tubuh (sama dengan 10 titik NaraMotion).
   Fitur identik dengan pelatihan (ml/kaggle/train_gesture/train.py): normalisasi pinggul & panjang badan,
   64 frame, kanal per titik x, y, terlihat(0/1), vx·4, vy·4. Data acuan: Video Dataset of Woman/Male Basic Balinese
   Dance Movement (Mendeley Data, CC BY 4.0).
   Alur kamera: kalibrasi dulu (cahaya, badan utuh, jarak, posisi tengah, tahan 1,5 detik), baru latihan.
   Hemat daya: deteksi pose hanya pada frame video baru dan dibatasi 8–24 fps menurut kecepatan perangkat. */
(function (root) {
  'use strict';
  const T = 64, NK = 17, WIN_S = 5.5, THR = 0.3;
  const MP_URL = 'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14';
  const MP_MODEL = 'https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task';
  const ORT_URL = 'https://cdn.jsdelivr.net/npm/onnxruntime-web@1.20.1/dist/ort.min.js';
  // MediaPipe 33 titik → COCO 17 (hidung, mata, telinga, bahu, siku, pergelangan, pinggul, lutut, pergelangan kaki)
  const MP2COCO = [0, 2, 5, 7, 8, 11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28];
  // 10 segmen dalam 2D: [asal, ujung]; -1 = titik tengah pinggul, -2 = titik tengah bahu
  const SEG = { head: [-2, 0], torso: [-1, -2], uArmL: [5, 7], fArmL: [7, 9], uArmR: [6, 8], fArmR: [8, 10],
    thighL: [11, 13], shinL: [13, 15], thighR: [12, 14], shinR: [14, 16] };
  const SEGK = Object.keys(SEG), NS = SEGK.length;
  const BONES = [[5, 6], [5, 7], [7, 9], [6, 8], [8, 10], [5, 11], [6, 12], [11, 12], [11, 13], [13, 15], [12, 14], [14, 16], [0, 5], [0, 6]];
  const DATASETS = {
    putri: { label: 'Putri · 13 gerak', model: 'assets/ml/putri_body17_model.onnx', tpl: 'assets/ml/templates_putri_body17.json', tpl3: 'assets/ml/templates3d_putri.json' },
    putra: { label: 'Putra · 11 gerak', model: 'assets/ml/putra_body17_model.onnx', tpl: 'assets/ml/templates_putra_body17.json', tpl3: 'assets/ml/templates3d_putra.json' },
  };
  const CALIB_HOLD = 1500;
  // ---------- Skor 3D (tidak bergantung sudut kamera) ----------
  // titik dunia 3D MediaPipe (meter, y ke bawah) → kerangka badan; acuan dari SAM 3D Body (tools/build_3d_templates.py)
  const W3 = { nose: 0, earL: 7, earR: 8, shL: 11, shR: 12, elL: 13, elR: 14, wrL: 15, wrR: 16, hipL: 23, hipR: 24, knL: 25, knR: 26, anL: 27, anR: 28 };
  const SEG3 = ['head', 'torso', 'uArmL', 'fArmL', 'uArmR', 'fArmR', 'thighL', 'shinL', 'thighR', 'shinR'];
  const v3 = { sub: (a, b) => [a[0] - b[0], a[1] - b[1], a[2] - b[2]], add: (a, b) => [a[0] + b[0], a[1] + b[1], a[2] + b[2]], mul: (a, k) => [a[0] * k, a[1] * k, a[2] * k],
    dot: (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2], cross: (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]],
    unit: (a) => { const n = Math.hypot(a[0], a[1], a[2]) || 1; return [a[0] / n, a[1] / n, a[2] / n]; } };
  function feats3d(wl) {   // wl: 33 titik [x,y,z] MediaPipe → 10 vektor satuan (sama dengan frame_feats di Python)
    const g = (k) => { const p = wl[W3[k]]; return [p[0], -p[1], -p[2]]; };
    const pel = v3.mul(v3.add(g('hipL'), g('hipR')), 0.5), neck = v3.mul(v3.add(g('shL'), g('shR')), 0.5);
    const X = v3.unit(v3.sub(g('hipL'), g('hipR'))); let Y = v3.sub(neck, pel); Y = v3.unit(v3.sub(Y, v3.mul(X, v3.dot(Y, X)))); const Z = v3.cross(X, Y);
    const seg = (a, b) => { const d = v3.sub(b, a); return v3.unit([v3.dot(X, d), v3.dot(Y, d), v3.dot(Z, d)]); };
    const hc = v3.mul(v3.add(g('earL'), g('earR')), 0.5);
    return [seg(neck, v3.add(hc, v3.mul(v3.sub(g('nose'), hc), 0.5))), v3.unit(v3.sub(neck, pel)),
      seg(g('shL'), g('elL')), seg(g('elL'), g('wrL')), seg(g('shR'), g('elR')), seg(g('elR'), g('wrR')),
      seg(g('hipL'), g('knL')), seg(g('knL'), g('anL')), seg(g('hipR'), g('knR')), seg(g('knR'), g('anR'))];
  }
  const ang3 = (a, b) => Math.acos(Math.max(-1, Math.min(1, a[0] * b[0] + a[1] * b[1] + a[2] * b[2]))) * 57.29578;
  function compare3d(S, Rf) {   // S, Rf: 64 × 10 × 3 → DTW (pita ±20), galat sudut per segmen
    const n = S.length, m = Rf.length, W = m + 1, D = new Float64Array((n + 1) * W).fill(Infinity), C = new Float32Array(n * m); D[0] = 0;
    for (let i = 0; i < n; i++) for (let j = Math.max(0, i - 20); j < Math.min(m, i + 21); j++) { let s = 0; for (let k = 0; k < 10; k++) s += ang3(S[i][k], Rf[j][k]); C[i * m + j] = s / 10; }
    for (let i = 1; i <= n; i++) for (let j = Math.max(1, i - 20); j <= Math.min(m, i + 20); j++)
      D[i * W + j] = C[(i - 1) * m + j - 1] + Math.min(D[(i - 1) * W + j], D[i * W + j - 1], D[(i - 1) * W + j - 1]);
    let i = n, j = m; const err = new Float64Array(10); let cnt = 0;
    while (i > 0 && j > 0) { for (let k = 0; k < 10; k++) err[k] += ang3(S[i - 1][k], Rf[j - 1][k]); cnt++;
      const a = D[(i - 1) * W + j - 1], b = D[(i - 1) * W + j], c = D[i * W + j - 1]; if (a <= b && a <= c) { i--; j--; } else if (b <= c) i--; else j--; }
    const e = {}; SEG3.forEach((k, q) => { e[k] = err[q] / cnt; }); return { err: e, mean: Object.values(e).reduce((x, y) => x + y, 0) / 10 };
  }
  function resample3(F, n) {
    const out = [];
    for (let i = 0; i < n; i++) { const t = (i * (F.length - 1)) / (n - 1), i0 = Math.floor(t), i1 = Math.min(i0 + 1, F.length - 1), w = t - i0;
      out.push(F[i0].map((v, k) => v3.unit(v3.add(v3.mul(v, 1 - w), v3.mul(F[i1][k], w))))); }
    return out;
  }   // ms posisi benar berturut-turut sebelum latihan dibuka
  const pretty = (c) => c.replace(/_/g, ' ');

  function loadScript(src) {
    return new Promise((ok, no) => { const s = document.createElement('script'); s.src = src; s.onload = ok; s.onerror = () => no(new Error('gagal memuat ' + src)); document.head.appendChild(s); });
  }

  // ---------- Fitur (cermin dari train.py) ----------
  function normalise(frames) {
    const hips = [], torsos = [];
    for (const f of frames) {
      if (Math.min(f.s[5], f.s[6], f.s[11], f.s[12]) <= THR) continue;
      const hx = (f.k[11][0] + f.k[12][0]) / 2, hy = (f.k[11][1] + f.k[12][1]) / 2;
      const sx = (f.k[5][0] + f.k[6][0]) / 2, sy = (f.k[5][1] + f.k[6][1]) / 2;
      const L = Math.hypot(sx - hx, sy - hy); if (L > 1) { hips.push([hx, hy]); torsos.push(L); }
    }
    if (!torsos.length) return null;
    const med = (a) => { const b = a.slice().sort((x, y) => x - y); return b[b.length >> 1]; };
    const cx = med(hips.map((h) => h[0])), cy = med(hips.map((h) => h[1])), L = Math.max(med(torsos), 1);
    return frames.map((f) => f.k.map((p, j) => (f.s[j] < THR ? [0, 0, f.s[j]] : [(p[0] - cx) / L, (p[1] - cy) / L, f.s[j]])));
  }
  function resample(X, n) {
    const out = [];
    for (let i = 0; i < n; i++) {
      const t = (i * (X.length - 1)) / (n - 1), i0 = Math.floor(t), i1 = Math.min(i0 + 1, X.length - 1), w = t - i0;
      out.push(X[i0].map((p, j) => p.map((v, c) => v * (1 - w) + X[i1][j][c] * w)));
    }
    return out;
  }
  function features(R) {
    const data = new Float32Array(T * NK * 5);
    for (let t = 0; t < T; t++) for (let j = 0; j < NK; j++) {
      const p = R[t][j], q = R[Math.max(0, t - 1)][j], o = (t * NK + j) * 5;
      data[o] = p[0]; data[o + 1] = p[1]; data[o + 2] = p[2] >= THR ? 1 : 0; data[o + 3] = (p[0] - q[0]) * 4; data[o + 4] = (p[1] - q[1]) * 4;
    }
    return data;
  }

  // ---------- Perbandingan dengan gerak acuan ----------
  // Sudut 10 segmen per frame dihitung SEKALI (dulu dihitung ulang di setiap sel DTW → berat di ponsel).
  const pt = (F, i) => (i === -1 ? [(F[11][0] + F[12][0]) / 2, (F[11][1] + F[12][1]) / 2] : i === -2 ? [(F[5][0] + F[6][0]) / 2, (F[5][1] + F[6][1]) / 2] : F[i]);
  function anglesOf(frames) {
    const A = new Float32Array(frames.length * NS);
    frames.forEach((F, t) => SEGK.forEach((k, s) => { const a = pt(F, SEG[k][0]), b = pt(F, SEG[k][1]); A[t * NS + s] = Math.atan2(b[1] - a[1], b[0] - a[0]); }));
    return A;
  }
  function angDiff(a, b) { let d = Math.abs(a - b) % (2 * Math.PI); return (d > Math.PI ? 2 * Math.PI - d : d) * 57.29578; }
  function compare(SA, RA) {
    // DTW antar-frame (pita ±20) lalu galat sudut rata-rata per segmen di sepanjang jalur
    const n = SA.length / NS, m = RA.length / NS, W = m + 1;
    const D = new Float64Array((n + 1) * W).fill(Infinity), C = new Float32Array(n * m); D[0] = 0;
    for (let i = 0; i < n; i++) for (let j = Math.max(0, i - 20); j < Math.min(m, i + 21); j++) {
      let s = 0; for (let k = 0; k < NS; k++) s += angDiff(SA[i * NS + k], RA[j * NS + k]); C[i * m + j] = s / NS;
    }
    for (let i = 1; i <= n; i++) for (let j = Math.max(1, i - 20); j <= Math.min(m, i + 20); j++)
      D[i * W + j] = C[(i - 1) * m + j - 1] + Math.min(D[(i - 1) * W + j], D[i * W + j - 1], D[(i - 1) * W + j - 1]);
    let i = n, j = m; const path = [];
    while (i > 0 && j > 0) { path.push([i - 1, j - 1]); const a = D[(i - 1) * W + j - 1], b = D[(i - 1) * W + j], c = D[i * W + j - 1]; if (a <= b && a <= c) { i--; j--; } else if (b <= c) i--; else j--; }
    const err = {}; SEGK.forEach((k) => { err[k] = 0; });
    for (const [a, b] of path) SEGK.forEach((k, s) => { err[k] += angDiff(SA[a * NS + s], RA[b * NS + s]); });
    SEGK.forEach((k) => { err[k] /= path.length; });
    const mean = Object.values(err).reduce((x, y) => x + y, 0) / NS;
    return { err, mean, dtw: D[n * W + m] / (n + m) };
  }

  // ---------- Gambar ----------
  function drawSkel(ctx, F, map, color, width, ghost) {
    ctx.save(); ctx.strokeStyle = color; ctx.lineWidth = width; ctx.lineCap = 'round'; ctx.globalAlpha = ghost ? 0.5 : 1;
    for (const [a, b] of BONES) {
      const p = F[a], q = F[b]; if (!p || !q || (p[2] !== undefined && (p[2] < THR || q[2] < THR))) continue;
      const P = map(p), Q = map(q); ctx.beginPath(); ctx.moveTo(P[0], P[1]); ctx.lineTo(Q[0], Q[1]); ctx.stroke();
    }
    ctx.fillStyle = color;
    for (const i of [0, 9, 10, 15, 16]) { const p = F[i]; if (!p || (p[2] !== undefined && p[2] < THR)) continue; const P = map(p); ctx.beginPath(); ctx.arc(P[0], P[1], width * 1.3, 0, 7); ctx.fill(); }
    ctx.restore();
  }

  // ---------- Dukungan perangkat ----------
  function cameraSupport() {
    if (!root.isSecureContext) return 'Kamera hanya bisa dipakai di alamat https://. Buka naramotion.web.app langsung.';
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) return 'Peramban ini belum mendukung kamera web. Pakai Chrome, Edge, atau Safari versi terbaru, atau unggah video.';
    if (typeof WebAssembly !== 'object') return 'Peramban ini belum mendukung WebAssembly. Pakai Chrome, Edge, atau Safari versi terbaru.';
    return null;
  }
  function cameraError(e) {
    const n = e && e.name;
    if (n === 'NotAllowedError' || n === 'SecurityError') return 'Izin kamera ditolak. Izinkan kamera di pengaturan situs peramban, lalu tekan Nyalakan kamera lagi.';
    if (n === 'NotFoundError' || n === 'OverconstrainedError') return 'Kamera tidak ditemukan. Sambungkan kamera, atau unggah video latihanmu.';
    if (n === 'NotReadableError' || n === 'AbortError') return 'Kamera sedang dipakai aplikasi lain. Tutup aplikasi itu (Zoom, Meet, kamera bawaan), lalu coba lagi.';
    return 'Kamera tidak bisa dibuka: ' + ((e && e.message) || 'kesalahan tidak dikenal') + '. Kamu tetap bisa mengunggah video.';
  }

  function CameraCoach(el, opts) {
    const $ = (s) => el.querySelector(s);
    const video = $('#cam-video'), over = $('#cam-overlay'), octx = over.getContext('2d');
    const tplCv = $('#cam-template'), tctx = tplCv.getContext('2d');
    const status = $('#cam-status'), dsSel = $('#cam-dataset'), tgtSel = $('#cam-target');
    const calibBox = $('#cam-calib'), calibMsg = $('#calib-msg'), calibRing = $('#calib-ring'), calibPct = $('#calib-pct'), goBtn = $('#cam-go');
    const lumCv = document.createElement('canvas'); lumCv.width = 48; lumCv.height = 27; const lctx = lumCv.getContext('2d', { willReadFrequently: true });
    const st = { ds: 'putri', tpl: null, refA: {}, session: null, landmarker: null, buf: [], running: false, lastInfer: 0, result: null, tplT: 0, src: null,
      lastVT: -1, lastDetect: 0, detInt: 1000 / 24, detMs: 0, lm: null, calibrated: false, okSince: 0, lum: 128, lumAt: 0, lostSince: 0, busy: false };
    const PAL = opts.palette;
    root.NaraCamera._st = st;   // untuk QA otomatis (tools/qa_app.py)
    const say = (t) => { status.textContent = t; };

    dsSel.innerHTML = Object.entries(DATASETS).map(([k, d]) => `<option value="${k}">${d.label}</option>`).join('');
    dsSel.addEventListener('change', () => loadDataset(dsSel.value));
    tgtSel.addEventListener('change', () => { st.tplT = 0; });

    async function loadDataset(ds) {
      st.ds = ds; say('Memuat model gerak ' + DATASETS[ds].label + '…');
      try {
        if (!root.ort) await loadScript(ORT_URL);
        root.ort.env.wasm.wasmPaths = 'https://cdn.jsdelivr.net/npm/onnxruntime-web@1.20.1/dist/';
        root.ort.env.wasm.numThreads = root.crossOriginIsolated ? Math.min(4, navigator.hardwareConcurrency || 2) : 1;
        const [sess, tpl] = await Promise.all([root.ort.InferenceSession.create(DATASETS[ds].model, { executionProviders: ['wasm'] }),
          fetch(DATASETS[ds].tpl).then((r) => { if (!r.ok) throw new Error('templat belum tersedia'); return r.json(); })]);
        st.session = sess; st.tpl = tpl; st.refA = {}; st.tpl3 = null;
        fetch(DATASETS[ds].tpl3).then((r) => (r.ok ? r.json() : null)).then((j) => { if (j && st.ds === ds) st.tpl3 = j; }).catch(() => {});
        tgtSel.innerHTML = tpl.classes.map((c) => `<option value="${c}">${pretty(c)}</option>`).join('');
        say(st.running ? (st.calibrated ? 'Kamera aktif. Peragakan gerak.' : 'Kalibrasi kamera dulu.') : 'Model siap. Nyalakan kamera atau unggah video.');
      } catch (e) { say('Model belum bisa dimuat: ' + e.message + '. Periksa internet lalu muat ulang halaman.'); }
    }
    const refAngles = (c) => st.refA[c] || (st.refA[c] = st.tpl.templates[c].exemplars.map((ex) => anglesOf(ex)));

    async function ensureLandmarker() {
      if (st.landmarker) return;
      say('Memuat pendeteksi pose (MediaPipe)…');
      let vision;
      try { vision = await import(MP_URL + '/vision_bundle.mjs'); } catch (e) { throw new Error('pendeteksi pose tidak bisa dimuat di peramban ini. Perbarui peramban atau pakai Chrome'); }
      const fs = await vision.FilesetResolver.forVisionTasks(MP_URL + '/wasm');
      const make = (delegate) => vision.PoseLandmarker.createFromOptions(fs, { baseOptions: { modelAssetPath: MP_MODEL, delegate }, runningMode: 'VIDEO', numPoses: 1,
        minPoseDetectionConfidence: 0.5, minPosePresenceConfidence: 0.5, minTrackingConfidence: 0.5 });
      try { st.landmarker = await make('GPU'); } catch (e) { st.landmarker = await make('CPU'); }   // cadangan bila WebGL tidak tersedia
    }

    function setCalib(on) {
      calibBox.hidden = !on; goBtn.hidden = true; st.okSince = 0; st.calibDone = 0;
      if (on) { st.calibrated = false; calibMsg.textContent = 'Berdiri 2–3 meter dari kamera hingga seluruh badan terlihat.'; ringTo(0); }
    }
    function ringTo(p) { calibRing.style.setProperty('--p', p.toFixed(3)); calibPct.textContent = Math.round(p * 100) + '%'; }

    async function start(kind, file) {
      if (kind === 'camera') { const why = cameraSupport(); if (why) { say(why); return; } }
      try {
        await ensureLandmarker();
        stop(true);
        if (kind === 'camera') {
          try {
            st.src = await navigator.mediaDevices.getUserMedia({ audio: false, video: { facingMode: 'user', width: { ideal: 640 }, height: { ideal: 480 }, frameRate: { ideal: 30, max: 30 } } });
          } catch (e) {
            if (e && e.name === 'OverconstrainedError') st.src = await navigator.mediaDevices.getUserMedia({ video: true, audio: false }); else throw e;
          }
          video.srcObject = st.src; video.classList.add('is-mirror');
        } else {
          video.srcObject = null; video.src = URL.createObjectURL(file); video.loop = true; video.classList.remove('is-mirror');
        }
        video.muted = true; video.setAttribute('playsinline', '');
        await video.play(); st.running = true; st.buf = []; st.mode = kind; st.lastVT = -1; st.result = null; el.classList.add('is-live');
        if (kind === 'camera') { setCalib(true); say('Kalibrasi kamera: ikuti petunjuk di layar.'); }
        else { setCalib(false); st.calibrated = true; say('Menganalisis video…'); }
      } catch (e) { say(kind === 'camera' && e && e.name ? cameraError(e) : 'Tidak bisa memulai: ' + e.message + '.'); }
    }
    function stop(silent) {
      st.running = false; el.classList.remove('is-live'); calibBox.hidden = true; goBtn.hidden = true;
      if (st.src) { st.src.getTracks().forEach((t) => t.stop()); st.src = null; }
      video.pause(); const [w, h] = sizeCanvas(over); octx.clearRect(0, 0, w, h); if (!silent) say('Berhenti.');
    }
    $('#cam-start').addEventListener('click', () => start('camera'));
    $('#cam-file').addEventListener('change', (e) => { const f = e.target.files[0]; if (f) start('file', f); });
    $('#cam-stop').addEventListener('click', () => stop(false));
    goBtn.addEventListener('click', beginPractice);
    $('#cam-recalib').addEventListener('click', () => { if (st.running && st.mode === 'camera') { setCalib(true); say('Kalibrasi ulang.'); } });

    function sizeCanvas(cv) {
      const r = cv.getBoundingClientRect(), dpr = Math.min(1.5, devicePixelRatio || 1);
      if (cv.width !== Math.round(r.width * dpr)) { cv.width = Math.round(r.width * dpr); cv.height = Math.round(r.height * dpr); }
      return [cv.width, cv.height, dpr];
    }

    function drawTemplate(dt) {
      const [w, h, dpr] = sizeCanvas(tplCv); tctx.clearRect(0, 0, w, h);
      if (!st.tpl) return;
      const c = tgtSel.value || st.tpl.classes[0], ex = st.tpl.templates[c].exemplars;
      const M = ex[st.result && st.result.target === c ? st.result.best : 0];
      st.tplT = (st.tplT + dt * T / 5.5) % T;
      const F = M[Math.floor(st.tplT)].map((p) => [p[0], p[1], 1]);
      const sc = Math.min(w, h) / 4.2, map = (p) => [w / 2 + p[0] * sc, h * 0.62 + p[1] * sc];
      drawSkel(tctx, F, map, PAL.boneHi, 3 * dpr, false);
      if (st.result && st.result.stuLast) drawSkel(tctx, st.result.stuLast, map, PAL.node, 2 * dpr, true);
    }

    // ---------- Kalibrasi: cahaya, badan utuh, jarak, posisi tengah ----------
    function luminance(now) {
      if (now - st.lumAt < 400) return st.lum;
      st.lumAt = now;
      try { lctx.drawImage(video, 0, 0, 48, 27); const d = lctx.getImageData(0, 0, 48, 27).data; let s = 0; for (let i = 0; i < d.length; i += 4) s += 0.299 * d[i] + 0.587 * d[i + 1] + 0.114 * d[i + 2]; st.lum = s / (d.length / 4); } catch (e) { /* abaikan */ }
      return st.lum;
    }
    function calibChecks(lm, lum) {
      const vis = (i) => lm && (lm[i].visibility ?? 1) > 0.6 && lm[i].x > 0.02 && lm[i].x < 0.98 && lm[i].y > 0.01 && lm[i].y < 0.99;
      const C = { light: lum >= 55 && lum <= 228, body: false, dist: false, center: false }; let msg = '';
      if (lum < 55) msg = 'Ruangan terlalu gelap. Nyalakan lampu atau hadap ke jendela.';
      else if (lum > 228) msg = 'Terlalu silau. Jangan membelakangi jendela atau lampu terang.';
      if (!lm) return [C, msg || 'Badan belum terdeteksi. Berdiri di depan kamera.'];
      const head = vis(0), feet = vis(27) && vis(28), core = [11, 12, 23, 24].every(vis);
      C.body = head && feet && core;
      const top = Math.min(lm[0].y, lm[2].y, lm[5].y), bot = Math.max(lm[27].y, lm[28].y, lm[29] ? lm[29].y : 0, lm[30] ? lm[30].y : 0), hgt = bot - top;
      const hipX = (lm[23].x + lm[24].x) / 2;
      C.dist = C.body && hgt >= 0.4 && hgt <= 0.92; C.center = core && hipX > 0.3 && hipX < 0.7;
      if (!msg) {
        if (!feet && head && hgt > 0.6) msg = 'Terlalu dekat. Mundur sampai kaki terlihat.';
        else if (!head) msg = 'Kepala terpotong. Mundur atau turunkan posisi kamera.';
        else if (!feet) msg = 'Kaki belum terlihat. Mundur atau arahkan kamera sedikit ke bawah.';
        else if (!core) msg = 'Bahu dan pinggul belum terlihat jelas. Hadap kamera dan jangan tertutup benda.';
        else if (hgt < 0.4) msg = 'Terlalu jauh. Maju sedikit ke arah kamera.';
        else if (hgt > 0.92) msg = 'Terlalu dekat. Mundur sedikit.';
        else if (!C.center) msg = hipX <= 0.3 ? 'Geser ke kanan sampai berada di tengah bingkai.' : 'Geser ke kiri sampai berada di tengah bingkai.';
      }
      return [C, msg];
    }
    function drawGuide(w, h, ok) {
      // bingkai siluet tempat badan seharusnya berdiri
      const gh = h * 0.78, gw = gh * 0.42, x = (w - gw) / 2, y = h * 0.16;
      octx.save(); octx.setLineDash([10, 8]); octx.lineWidth = 3; octx.strokeStyle = ok ? PAL.ok || '#a3c476' : 'rgba(240,201,107,.85)';
      octx.beginPath(); octx.ellipse(w / 2, y + gh * 0.08, gw * 0.16, gh * 0.08, 0, 0, 7); octx.stroke();
      octx.beginPath(); octx.roundRect ? octx.roundRect(x, y + gh * 0.18, gw, gh * 0.82, 24) : octx.rect(x, y + gh * 0.18, gw, gh * 0.82); octx.stroke(); octx.restore();
    }
    function beginPractice() {
      if (st.calibrated) return;
      st.calibrated = true; st.calibDone = 0; calibBox.hidden = true; goBtn.hidden = true; st.buf = [];
      say('Latihan dimulai. Peragakan gerak; analisis tiap ½ detik.');
    }
    function calibStep(lm, now, w, h) {
      if (st.calibDone) {   // kalibrasi sudah lulus: kunci, hitung mundur lalu mulai otomatis
        const left = Math.ceil((st.calibDone + 3000 - now) / 1000);
        calibMsg.textContent = left > 0 ? `Kalibrasi selesai. Latihan dimulai dalam ${left}…` : 'Mulai!';
        if (left <= 0) beginPractice();
        return;
      }
      const [C, msg] = calibChecks(lm, luminance(now)), all = C.light && C.body && C.dist && C.center;
      calibBox.querySelectorAll('[data-c]').forEach((li) => li.classList.toggle('ok', !!C[li.dataset.c]));
      drawGuide(w, h, all);
      if (all) {
        if (!st.okSince) st.okSince = now;
        const p = Math.min(1, (now - st.okSince) / CALIB_HOLD); ringTo(p);
        calibMsg.textContent = p < 1 ? 'Bagus! Tahan posisi…' : 'Kalibrasi selesai. Gerakanmu terdeteksi dengan baik.';
        if (p >= 1) { st.calibDone = now; goBtn.hidden = false; say('Kalibrasi selesai. Gerakanmu terdeteksi dengan baik.'); }
      } else { st.okSince = 0; ringTo(0); goBtn.hidden = true; calibMsg.textContent = msg; }
    }

    function infer() {
      if (st.busy || !st.session || !st.tpl || st.buf.length < (st.mode === 'file' ? 10 : 24)) return;
      const buf = st.buf.slice();   // potret buffer: mode video mengosongkan st.buf saat video berulang sebelum analisis selesai
      const norm = normalise(buf); if (!norm) { say('Badan belum terlihat utuh. Mundur sedikit dari kamera.'); return; }
      const R = resample(norm, T);
      const tensor = new root.ort.Tensor('float32', features(R), [1, T, NK * 5]);
      st.busy = true;
      st.session.run({ x: tensor }).then((out) => {
        const prob = Array.from(out.prob.data), cls = st.tpl.classes;
        const top = prob.map((p, i) => [cls[i], p]).sort((a, b) => b[1] - a[1]).slice(0, 3);
        const target = tgtSel.value || cls[0];
        const SA = anglesOf(R.map((F) => F.map((p) => [p[0], p[1]])));
        // bandingkan dengan tiap exemplar gerak target, ambil yang paling mirip (sudut kamera / penari terdekat)
        let cmp = null, best = 0;
        refAngles(target).forEach((RA, i) => { const r = compare(SA, RA); if (!cmp || r.mean < cmp.mean) { cmp = r; best = i; } });
        const k = (st.tpl.calib && st.tpl.calib.k) || 2.1;   // galat median klip uji gerak benar → skor 85
        cmp.score = Math.max(0, Math.min(100, 100 - cmp.mean * k));
        if (top[0][0] !== target && top[0][1] > 0.6) cmp.score *= 0.6;   // AI yakin yang diperagakan gerak lain
        // skor 3D bila acuan 3D & titik dunia tersedia: tidak bergantung sudut kamera, galat per segmen dalam kerangka badan
        const w3 = buf.filter((f) => f.w).map((f) => feats3d(f.w));
        const cal3 = st.tpl3 && st.tpl3.calib;
        if (cal3 && cal3.enabled !== false && st.tpl3.templates[target] && w3.length >= Math.max(10, buf.length * 0.8)) {
          const S3 = resample3(w3, st.tpl3.T || 64); let c3 = null;
          for (const ex of st.tpl3.templates[target].exemplars) { const r = compare3d(S3, ex); if (!c3 || r.mean < c3.mean) c3 = r; }
          // skala terkalibrasi pada video penari asli: galat median gerak benar → 85, gerak lain → 50
          const own = cal3.median_err || 20, oth = Math.max(own + 4, cal3.other_median || own + 12);
          cmp.err = c3.err; cmp.mean = c3.mean; cmp.score = Math.max(0, Math.min(100, 85 - (c3.mean - own) * 35 / (oth - own))); cmp.mode = '3d';
          if (top[0][0] !== target && top[0][1] > 0.6) cmp.score *= 0.6;
        } else cmp.mode = '2d';
        st.result = { top, target, best, ...cmp, stuLast: R[T - 1] };
        opts.onResult && opts.onResult(st.result);
      }).catch((e) => say('Analisis gagal: ' + e.message)).finally(() => { st.busy = false; });
    }

    dsSel.value = 'putri';
    const key = (c) => c.toLowerCase().replace(/[^a-z]/g, '');
    return {
      activate() { if (!st.session) loadDataset(st.ds); const why = cameraSupport(); if (why) say(why + ' Unggah video tetap bisa dipakai.'); },
      async select(ds, move) {   // dari Arsip / Reels: pilih dataset & gerak target
        if (ds !== st.ds || !st.session) { dsSel.value = ds; await loadDataset(ds); }
        const hit = st.tpl && st.tpl.classes.find((c) => key(c) === key(move));
        if (hit) { tgtSel.value = hit; st.tplT = 0; }
      },
      deactivate() { stop(true); },
      tick(dt, now) {
        drawTemplate(dt);
        if (!st.running || !st.landmarker || video.readyState < 2) return;
        // deteksi hanya pada frame video baru dan dibatasi sesuai kecepatan perangkat
        const vt = video.currentTime;
        if (vt === st.lastVT || now - st.lastDetect < st.detInt) return;
        const [w, h, dpr] = sizeCanvas(over); octx.clearRect(0, 0, w, h);
        const t0 = performance.now(); const res = st.landmarker.detectForVideo(video, now); const ms = performance.now() - t0;
        st.detMs = st.detMs ? st.detMs * 0.9 + ms * 0.1 : ms;
        st.detInt = st.detMs > 60 ? 1000 / 8 : st.detMs > 35 ? 1000 / 12 : st.detMs > 20 ? 1000 / 18 : 1000 / 24;
        st.lastDetect = now;
        const lm = res.landmarks && res.landmarks[0], wl = res.worldLandmarks && res.worldLandmarks[0];
        if (st.mode === 'file' && st.lastVT >= 0 && vt + 0.2 < st.lastVT) { infer(); st.buf = []; }   // video berulang: tutup putaran
        st.lastVT = vt;
        if (st.mode === 'camera' && !st.calibrated) { calibStep(lm, now, w, h); }
        if (lm) {
          const vw = video.videoWidth, vh = video.videoHeight;
          const k = MP2COCO.map((i) => [lm[i].x * vw, lm[i].y * vh]), s = MP2COCO.map((i) => lm[i].visibility ?? 1);
          const scale = Math.max(w / vw, h / vh), ox = (w - vw * scale) / 2, oy = (h - vh * scale) / 2, mir = video.classList.contains('is-mirror');
          const map = (p) => [mir ? w - (ox + p[0] * scale) : ox + p[0] * scale, oy + p[1] * scale];
          drawSkel(octx, k.map((p, j) => [p[0], p[1], s[j]]), map, PAL.boneHi, 3 * dpr, false);
          if (!st.calibrated) return;
          st.lostSince = 0;
          st.buf.push({ k, s, t: now, w: wl ? wl.map((p) => [p.x, p.y, p.z]) : null });
          if (st.mode !== 'file') while (st.buf.length && now - st.buf[0].t > WIN_S * 1000) st.buf.shift();
          else while (st.buf.length > 600) st.buf.shift();
        } else if (st.calibrated && st.mode === 'camera') {
          if (!st.lostSince) st.lostSince = now;
          if (now - st.lostSince > 2000) say('Badan tidak terlihat. Kembali ke tengah bingkai, atau tekan Kalibrasi ulang.');
          return;
        }
        if (!st.calibrated) return;
        const enough = st.mode !== 'file' || (st.buf.length > 1 && (st.buf[st.buf.length - 1].t - st.buf[0].t) / 1000 > 0.8 * (video.duration || 0));
        if (enough && now - st.lastInfer > 600) { st.lastInfer = now; infer(); }
      },
    };
  }

  root.NaraCamera = { CameraCoach, DATASETS, _test: { normalise, resample, features, compare, anglesOf, feats3d, compare3d, resample3 } };
})(window);
