/* NaraMotion · Kelas Tari mode Kamera AI.
   Kamera/video → MediaPipe Pose (browser) → 17 titik COCO → model ONNX pengenal gerak dasar tari Bali
   + skor kemiripan terhadap gerak acuan (rata-rata dataset) per 10 segmen tubuh (sama dengan 10 node NaraMotion).
   Fitur identik dengan pelatihan (ml/kaggle/train_gesture/train.py): normalisasi pinggul & panjang badan, skor<0,3 → 0,
   64 frame, kanal per titik x, y, skor, vx·4, vy·4. Data acuan: Video Dataset of Woman/Male Basic Balinese Dance
   Movement (Mendeley Data, CC BY 4.0). */
(function (root) {
  'use strict';
  const T = 64, NK = 17, WIN_S = 5.5, THR = 0.3;
  const MP_URL = 'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14';
  const MP_MODEL = 'https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task';
  const ORT_URL = 'https://cdn.jsdelivr.net/npm/onnxruntime-web@1.20.1/dist/ort.min.js';
  // MediaPipe 33 titik → COCO 17 (hidung, mata, telinga, bahu, siku, pergelangan, pinggul, lutut, pergelangan kaki)
  const MP2COCO = [0, 2, 5, 7, 8, 11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28];
  // 10 node NaraMotion dalam 2D: [asal, ujung]; -1 = titik tengah pinggul, -2 = titik tengah bahu
  const SEG = { head: [-2, 0], torso: [-1, -2], uArmL: [5, 7], fArmL: [7, 9], uArmR: [6, 8], fArmR: [8, 10],
    thighL: [11, 13], shinL: [13, 15], thighR: [12, 14], shinR: [14, 16] };
  const BONES = [[5, 6], [5, 7], [7, 9], [6, 8], [8, 10], [5, 11], [6, 12], [11, 12], [11, 13], [13, 15], [12, 14], [14, 16], [0, 5], [0, 6]];
  const DATASETS = {
    putri: { label: 'Putri · 13 gerak', model: 'assets/ml/putri_body17_model.onnx', tpl: 'assets/ml/templates_putri_body17.json' },
    putra: { label: 'Putra · 11 gerak', model: 'assets/ml/putra_body17_model.onnx', tpl: 'assets/ml/templates_putra_body17.json' },
  };
  const pretty = (c) => c.replace(/_/g, ' ');

  function loadScript(src) {
    return new Promise((ok, no) => { const s = document.createElement('script'); s.src = src; s.onload = ok; s.onerror = () => no(new Error('gagal memuat ' + src)); document.head.appendChild(s); });
  }

  // ---------- Fitur (cermin dari train.py) ----------
  function normalise(frames) {
    // frames: [{k: [[x,y]*17] piksel, s: [17]}] → array T' × 17 × 3
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
  const pt = (F, i) => (i === -1 ? [(F[11][0] + F[12][0]) / 2, (F[11][1] + F[12][1]) / 2] : i === -2 ? [(F[5][0] + F[6][0]) / 2, (F[5][1] + F[6][1]) / 2] : F[i]);
  function segAngle(F, s) { const a = pt(F, s[0]), b = pt(F, s[1]); return Math.atan2(b[1] - a[1], b[0] - a[0]); }
  function angDiff(a, b) { let d = Math.abs(a - b) % (2 * Math.PI); return (d > Math.PI ? 2 * Math.PI - d : d) * 180 / Math.PI; }
  function frameDist(A, B) { let s = 0; for (const k in SEG) s += angDiff(segAngle(A, SEG[k]), segAngle(B, SEG[k])); return s / 10; }
  function compare(stu, ref) {
    // DTW antar-frame (64×64) lalu galat sudut rata-rata per segmen di sepanjang jalur
    const n = stu.length, m = ref.length, D = Array.from({ length: n + 1 }, () => new Float64Array(m + 1).fill(Infinity));
    const C = stu.map((a) => ref.map((b) => frameDist(a, b))); D[0][0] = 0;
    for (let i = 1; i <= n; i++) for (let j = Math.max(1, i - 20); j <= Math.min(m, i + 20); j++)
      D[i][j] = C[i - 1][j - 1] + Math.min(D[i - 1][j], D[i][j - 1], D[i - 1][j - 1]);
    let i = n, j = m; const path = [];
    while (i > 0 && j > 0) { path.push([i - 1, j - 1]); const a = D[i - 1][j - 1], b = D[i - 1][j], c = D[i][j - 1]; if (a <= b && a <= c) { i--; j--; } else if (b <= c) i--; else j--; }
    const err = {}; for (const k in SEG) err[k] = 0;
    for (const [a, b] of path) for (const k in SEG) err[k] += angDiff(segAngle(stu[a], SEG[k]), segAngle(ref[b], SEG[k]));
    for (const k in SEG) err[k] /= path.length;
    const mean = Object.values(err).reduce((x, y) => x + y, 0) / 10;
    return { err, mean, dtw: D[n][m] / (n + m) };
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

  function CameraCoach(el, opts) {
    const $ = (s) => el.querySelector(s);
    const video = $('#cam-video'), over = $('#cam-overlay'), octx = over.getContext('2d');
    const tplCv = $('#cam-template'), tctx = tplCv.getContext('2d');
    const status = $('#cam-status'), dsSel = $('#cam-dataset'), tgtSel = $('#cam-target');
    const st = { ds: 'putri', tpl: null, session: null, landmarker: null, buf: [], running: false, lastInfer: 0, result: null, tplT: 0, src: null };
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
        const [sess, tpl] = await Promise.all([root.ort.InferenceSession.create(DATASETS[ds].model, { executionProviders: ['wasm'] }),
          fetch(DATASETS[ds].tpl).then((r) => { if (!r.ok) throw new Error('templat belum tersedia'); return r.json(); })]);
        st.session = sess; st.tpl = tpl;
        tgtSel.innerHTML = tpl.classes.map((c) => `<option value="${c}">${pretty(c)}</option>`).join('');
        say(st.running ? 'Kamera aktif. Peragakan gerak; analisis tiap ½ detik.' : 'Model siap. Nyalakan kamera atau unggah video.');
      } catch (e) { say('Model belum bisa dimuat: ' + e.message); }
    }

    async function ensureLandmarker() {
      if (st.landmarker) return;
      say('Memuat pendeteksi pose (MediaPipe)…');
      const vision = await import(MP_URL + '/vision_bundle.mjs');
      const fs = await vision.FilesetResolver.forVisionTasks(MP_URL + '/wasm');
      const make = (delegate) => vision.PoseLandmarker.createFromOptions(fs, { baseOptions: { modelAssetPath: MP_MODEL, delegate }, runningMode: 'VIDEO', numPoses: 1 });
      try { st.landmarker = await make('GPU'); } catch (e) { st.landmarker = await make('CPU'); }   // cadangan bila WebGL tidak tersedia
    }

    async function start(kind, file) {
      try {
        await ensureLandmarker();
        stop(true);
        if (kind === 'camera') {
          st.src = await navigator.mediaDevices.getUserMedia({ video: { width: 960, height: 540 }, audio: false });
          video.srcObject = st.src; video.classList.add('is-mirror');
        } else {
          video.srcObject = null; video.src = URL.createObjectURL(file); video.loop = true; video.classList.remove('is-mirror');
        }
        await video.play(); st.running = true; st.buf = []; st.mode = kind; st.lastVT = null; el.classList.add('is-live');
        say(kind === 'camera' ? 'Kamera aktif. Berdiri utuh di bingkai lalu peragakan gerak.' : 'Menganalisis video…');
      } catch (e) { say('Tidak bisa memulai: ' + e.message); }
    }
    function stop(silent) {
      st.running = false; el.classList.remove('is-live');
      if (st.src) { st.src.getTracks().forEach((t) => t.stop()); st.src = null; }
      video.pause(); if (!silent) say('Berhenti.');
    }
    $('#cam-start').addEventListener('click', () => start('camera'));
    $('#cam-file').addEventListener('change', (e) => { const f = e.target.files[0]; if (f) start('file', f); });
    $('#cam-stop').addEventListener('click', () => stop(false));

    function sizeCanvas(cv) {
      const r = cv.getBoundingClientRect(), dpr = Math.min(2, devicePixelRatio || 1);
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

    function infer() {
      if (!st.session || !st.tpl || st.buf.length < (st.mode === 'file' ? 10 : 30)) return;   // file pendek / perangkat lambat
      const norm = normalise(st.buf); if (!norm) { say('Badan belum terlihat utuh — mundur sedikit dari kamera.'); return; }
      const R = resample(norm, T);
      const tensor = new root.ort.Tensor('float32', features(R), [1, T, NK * 5]);
      st.session.run({ x: tensor }).then((out) => {
        const prob = Array.from(out.prob.data), cls = st.tpl.classes;
        const top = prob.map((p, i) => [cls[i], p]).sort((a, b) => b[1] - a[1]).slice(0, 3);
        const target = tgtSel.value || cls[0];
        const stu = R.map((F) => F.map((p) => [p[0], p[1]]));
        // bandingkan dengan tiap exemplar gerak target, ambil yang paling mirip (sudut kamera / penari terdekat)
        let cmp = null, best = 0;
        st.tpl.templates[target].exemplars.forEach((ex, i) => { const r = compare(stu, ex); if (!cmp || r.mean < cmp.mean) { cmp = r; best = i; } });
        // skor terkalibrasi: galat median klip uji gerak benar → 85 (lihat calib di templat)
        const k = (st.tpl.calib && st.tpl.calib.k) || 2.1;
        cmp.score = Math.max(0, Math.min(100, 100 - cmp.mean * k));
        if (top[0][0] !== target && top[0][1] > 0.6) cmp.score *= 0.6;   // AI yakin yang diperagakan gerak lain
        st.result = { top, target, best, ...cmp, stuLast: R[T - 1] };
        opts.onResult && opts.onResult(st.result);
      }).catch((e) => say('Analisis gagal: ' + e.message));
    }

    dsSel.value = 'putri';
    const key = (c) => c.toLowerCase().replace(/[^a-z]/g, '');
    return {
      activate() { if (!st.session) loadDataset(st.ds); },
      async select(ds, move) {   // dari Arsip: pilih dataset & gerak target
        if (ds !== st.ds || !st.session) { dsSel.value = ds; await loadDataset(ds); }
        const hit = st.tpl && st.tpl.classes.find((c) => key(c) === key(move));
        if (hit) { tgtSel.value = hit; st.tplT = 0; }
      },
      deactivate() { stop(true); },
      tick(dt, now) {
        drawTemplate(dt);
        const [w, h, dpr] = sizeCanvas(over); octx.clearRect(0, 0, w, h);
        if (!st.running || !st.landmarker || video.readyState < 2) return;
        const res = st.landmarker.detectForVideo(video, now);
        const lm = res.landmarks && res.landmarks[0];
        if (lm) {
          const vw = video.videoWidth, vh = video.videoHeight;
          const k = MP2COCO.map((i) => [lm[i].x * vw, lm[i].y * vh]), s = MP2COCO.map((i) => lm[i].visibility ?? 1);
          const vt = video.currentTime;
          if (st.mode === 'file' && st.lastVT != null && vt + 0.2 < st.lastVT) { infer(); st.buf = []; }   // video berulang: tutup putaran
          st.lastVT = vt;
          st.buf.push({ k, s, t: now });
          if (st.mode !== 'file') while (st.buf.length && now - st.buf[0].t > WIN_S * 1000) st.buf.shift();
          else while (st.buf.length > 600) st.buf.shift();
          // gambar kerangka di atas video (ikuti object-fit: cover dan cermin)
          const scale = Math.max(w / vw, h / vh), ox = (w - vw * scale) / 2, oy = (h - vh * scale) / 2, mir = video.classList.contains('is-mirror');
          const map = (p) => [mir ? w - (ox + p[0] * scale) : ox + p[0] * scale, oy + p[1] * scale];
          drawSkel(octx, k.map((p, j) => [p[0], p[1], s[j]]), map, PAL.boneHi, 3 * dpr, false);
        }
        const enough = st.mode !== 'file' || (st.buf.length > 1 && (st.buf[st.buf.length - 1].t - st.buf[0].t) / 1000 > 0.8 * (video.duration || 0));
        if (enough && now - st.lastInfer > 500) { st.lastInfer = now; infer(); }
      },
    };
  }

  root.NaraCamera = { CameraCoach, DATASETS, _test: { normalise, resample, features, compare } };
})(window);
