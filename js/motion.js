// NaraMotion — model gerak tari, simulasi sensor 9-DoF MARG, dan renderer kanvas.
(function (root) {
  'use strict';

  const TAU = Math.PI * 2;
  const add = (a, b) => [a[0] + b[0], a[1] + b[1], a[2] + b[2]];
  const sub = (a, b) => [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
  const mul = (a, k) => [a[0] * k, a[1] * k, a[2] * k];
  const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
  const cross = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
  const len = (a) => Math.hypot(a[0], a[1], a[2]);
  const norm = (a) => { const l = len(a) || 1; return [a[0] / l, a[1] / l, a[2] / l]; };
  function rotX(v, a) { const c = Math.cos(a), s = Math.sin(a); return [v[0], v[1] * c - v[2] * s, v[1] * s + v[2] * c]; }
  function rotY(v, a) { const c = Math.cos(a), s = Math.sin(a); return [v[0] * c + v[2] * s, v[1], -v[0] * s + v[2] * c]; }
  function rotZ(v, a) { const c = Math.cos(a), s = Math.sin(a); return [v[0] * c - v[1] * s, v[0] * s + v[1] * c, v[2]]; }

  // Parameter gaya: tempo (siklus/detik), lengan, siku, ukel, goyang, tekuk lutut (mendhak), angkat kaki, hentakan.
  const DANCES = [
    { id: 'gambyong', name: 'Gambyong', region: 'Surakarta, Jawa Tengah', character: 'Luwes dan lembut',
      about: 'Tari penyambutan yang menonjolkan kelenturan tangan, gerak ukel, dan permainan sampur, dengan posisi mendhak yang stabil.',
      motifs: ['Laku telu', 'Ukel karna', 'Seblak sampur', 'Kebyok sampur'],
      p: { tempo: 0.3, armBase: 0.45, armRange: 0.55, flex: 0.45, elbow: 1.25, ukel: 1.5, sway: 0.06, bend: 0.12, twist: 0.18, knee: 0.38, lift: 0.25, stamp: 0, head: 0.22, asym: 1.0 } },
    { id: 'bedhaya', name: 'Bedhaya Ketawang', region: 'Keraton Surakarta, Jawa Tengah', character: 'Sakral dan sangat lambat',
      about: 'Tarian sakral keraton yang dibawakan sembilan penari. Geraknya lambat, simetris, dan penuh kendali, sehingga menguji ketelitian sensor pada gerak halus.',
      motifs: ['Sembahan', 'Lumaksana', 'Sindhet', 'Kapang-kapang'],
      p: { tempo: 0.12, armBase: 0.3, armRange: 0.45, flex: 0.35, elbow: 1.0, ukel: 1.1, sway: 0.03, bend: 0.06, twist: 0.1, knee: 0.42, lift: 0.1, stamp: 0, head: 0.1, asym: 0.2 } },
    { id: 'serimpi', name: 'Serimpi', region: 'Keraton Yogyakarta & Surakarta', character: 'Anggun dan tertata',
      about: 'Tari keraton yang dibawakan empat penari putri. Polanya simetris dengan perpindahan berat badan yang halus dan tangan nyempurit.',
      motifs: ['Sembahan', 'Nyempurit', 'Ulap-ulap', 'Lumaksana'],
      p: { tempo: 0.18, armBase: 0.4, armRange: 0.5, flex: 0.4, elbow: 1.15, ukel: 1.3, sway: 0.05, bend: 0.08, twist: 0.14, knee: 0.4, lift: 0.15, stamp: 0, head: 0.16, asym: 0.6 } },
    { id: 'pendet', name: 'Pendet', region: 'Bali', character: 'Ceria dan ekspresif',
      about: 'Tari penyambutan dari Bali dengan posisi tangan agem yang tinggi, tatapan seledet yang tajam, dan getaran jari yang cepat.',
      motifs: ['Agem kanan', 'Agem kiri', 'Seledet', 'Nyeregseg'],
      p: { tempo: 0.42, armBase: 1.2, armRange: 0.3, flex: 0.25, elbow: 1.5, ukel: 2.0, sway: 0.07, bend: 0.1, twist: 0.22, knee: 0.5, lift: 0.2, stamp: 0, head: 0.35, asym: 1.4 } },
    { id: 'jaipong', name: 'Jaipongan', region: 'Karawang & Bandung, Jawa Barat', character: 'Dinamis dan enerjik',
      about: 'Tari kreasi Sunda yang lahir pada akhir 1970-an. Geraknya cepat, dengan patahan bahu dan pinggul yang tegas mengikuti kendang.',
      motifs: ['Bukaan', 'Pencugan', 'Ngala', 'Mincid'],
      p: { tempo: 0.62, armBase: 0.7, armRange: 0.8, flex: 0.6, elbow: 1.3, ukel: 1.8, sway: 0.11, bend: 0.18, twist: 0.32, knee: 0.34, lift: 0.45, stamp: 0.4, head: 0.3, asym: 1.8 } },
    { id: 'remo', name: 'Remo', region: 'Jombang & Surabaya, Jawa Timur', character: 'Gagah dan tegas',
      about: 'Tari pembuka yang gagah dengan hentakan kaki gedrug dan gelang kerincing. Hentakan kakinya menghasilkan lonjakan akselerasi yang jelas pada sensor.',
      motifs: ['Gedrug', 'Tepisan', 'Sabetan sampur', 'Hentak bahu'],
      p: { tempo: 0.5, armBase: 0.85, armRange: 0.6, flex: 0.5, elbow: 0.9, ukel: 1.2, sway: 0.08, bend: 0.1, twist: 0.25, knee: 0.48, lift: 0.6, stamp: 1, head: 0.28, asym: 2.2 } },
  ];

  function angles(p, t) {
    const ph = TAU * p.tempo * t;
    const s1 = Math.sin(ph);
    const lw = (k) => { const v = Math.max(0, Math.sin(ph + k)); return Math.pow(v, 2 + 4 * p.stamp); };
    return {
      sway: -p.sway * s1,
      bend: p.bend * Math.sin(ph + 0.7),
      twist: p.twist * Math.sin(ph * 0.5),
      knee: p.knee + 0.05 * Math.sin(ph * 2),
      head: p.head * Math.sin(ph * 0.5 + 0.4),
      lAb: p.armBase + p.armRange * (0.5 + 0.5 * s1),
      rAb: p.armBase + p.armRange * (0.5 + 0.5 * Math.sin(ph + p.asym)),
      lFl: p.flex * (0.6 + 0.4 * Math.sin(ph * 0.5 + 1.1)),
      rFl: p.flex * (0.6 + 0.4 * Math.sin(ph * 0.5 + 1.1 + p.asym)),
      lEl: p.elbow * (0.55 + 0.45 * Math.sin(ph + 0.5)),
      rEl: p.elbow * (0.55 + 0.45 * Math.sin(ph + 0.5 + p.asym)),
      lWr: p.ukel * Math.sin(ph * 2),
      rWr: p.ukel * Math.sin(ph * 2 + p.asym),
      lLift: p.lift * lw(0),
      rLift: p.lift * lw(Math.PI),
    };
  }

  const SEG = { thigh: 0.44, shin: 0.43, upper: 0.29, fore: 0.25, hand: 0.09 };

  function skeleton(a) {
    const drop = (SEG.thigh + SEG.shin) * (1 - Math.cos(a.knee));
    const pelvis = [a.sway, 0.06 + SEG.thigh + SEG.shin - drop, 0];
    const T = (v) => add(pelvis, rotY(rotZ(v, a.bend), a.twist));
    const J = { pelvis };
    J.spine = T([0, 0.2, 0]);
    J.chest = T([0, 0.4, 0]);
    J.neck = T([0, 0.55, 0]);
    J.head = T([0, 0.69, 0]);
    J.nose = T(add([0, 0.69, 0], rotY([0, 0, 0.1], a.head)));

    for (const [s, k] of [[1, 'L'], [-1, 'R']]) {
      const ab = s > 0 ? a.lAb : a.rAb, fl = s > 0 ? a.lFl : a.rFl;
      const el = s > 0 ? a.lEl : a.rEl, wr = s > 0 ? a.lWr : a.rWr;
      const sh = [0.19 * s, 0.52, 0];
      const d1 = rotX(rotZ([0, -1, 0], s * ab), -fl);
      const elbow = add(sh, mul(d1, SEG.upper));
      const d2 = rotX(rotZ([0, -1, 0], s * Math.min(ab + el * 0.55, 2.4)), -(fl + el));
      const wrist = add(elbow, mul(d2, SEG.fore));
      const d3 = norm(rotZ(rotX(d2, -0.6), s * (0.4 + 0.6 * wr)));
      const hand = add(wrist, mul(d3, SEG.hand));
      J['shoulder' + k] = T(sh); J['elbow' + k] = T(elbow); J['wrist' + k] = T(wrist); J['hand' + k] = T(hand);
      J['uArm' + k] = mul(add(J['shoulder' + k], J['elbow' + k]), 0.5);
      J['fArm' + k] = add(mul(J['elbow' + k], 0.4), mul(J['wrist' + k], 0.6));

      const lift = s > 0 ? a.lLift : a.rLift;
      const hip = add(pelvis, rotY([0.1 * s, 0, 0], a.twist * 0.4));
      const turn = s * 0.38; // tanjak: telapak membuka ke luar
      const th = a.knee + lift * 0.7;
      const knee = add(hip, mul(rotY(rotX([0, -1, 0], -th), turn), SEG.thigh));
      const ankle = add(knee, mul(rotY(rotX([0, -1, 0], -th + 2 * a.knee + lift * 1.1), turn), SEG.shin));
      J['hip' + k] = hip; J['knee' + k] = knee; J['ankle' + k] = ankle;
      J['toe' + k] = add(ankle, rotY([0, -0.04, 0.13], turn));
      J['thigh' + k] = mul(add(hip, knee), 0.5);
      J['shin' + k] = mul(add(knee, ankle), 0.5);
    }
    return J;
  }

  // 10 node IMU: kepala, badan, 2 per lengan (atas/bawah), 2 per kaki (paha/betis); sensor di tengah segmen.
  const NODES = [
    { id: 'head', label: 'Kepala', at: 'head', seg: ['neck', 'head'] },
    { id: 'torso', label: 'Badan', at: 'chest', seg: ['pelvis', 'chest'] },
    { id: 'uArmL', label: 'Lengan atas kiri', at: 'uArmL', seg: ['shoulderL', 'elbowL'] },
    { id: 'fArmL', label: 'Lengan bawah kiri', at: 'fArmL', seg: ['elbowL', 'wristL'] },
    { id: 'uArmR', label: 'Lengan atas kanan', at: 'uArmR', seg: ['shoulderR', 'elbowR'] },
    { id: 'fArmR', label: 'Lengan bawah kanan', at: 'fArmR', seg: ['elbowR', 'wristR'] },
    { id: 'thighL', label: 'Paha kiri', at: 'thighL', seg: ['hipL', 'kneeL'] },
    { id: 'shinL', label: 'Betis kiri', at: 'shinL', seg: ['kneeL', 'ankleL'] },
    { id: 'thighR', label: 'Paha kanan', at: 'thighR', seg: ['hipR', 'kneeR'] },
    { id: 'shinR', label: 'Betis kanan', at: 'shinR', seg: ['kneeR', 'ankleR'] },
  ];
  const nodeById = Object.fromEntries(NODES.map((n) => [n.id, n]));

  function segDir(J, node) { return norm(sub(J[node.seg[1]], J[node.seg[0]])); }

  // Arah istirahat tiap segmen: tungkai menunjuk ke bawah, kepala/dada ke atas, panggul ke samping.
  const REST = {
    up: [[1, 0, 0], [0, 1, 0]],
    down: [[1, 0, 0], [0, -1, 0]],
    side: [[0, 0, 1], [1, 0, 0]],
  };
  const restOf = (node) => (node.id === 'head' || node.id === 'torso' ? REST.up : REST.down);

  // Frame sensor = rotasi minimal (Rodrigues) dari arah istirahat ke arah segmen saat ini; kontinu tanpa lompatan.
  function frameOf(J, node) {
    const y = segDir(J, node);
    const [x0, y0] = restOf(node);
    const z0 = cross(x0, y0);
    const axis = cross(y0, y), s = len(axis), c = dot(y0, y);
    if (s < 1e-6) return c > 0 ? [x0, y0, z0] : [mul(x0, -1), mul(y0, -1), z0];
    const k = mul(axis, 1 / s);
    const R = (v) => add(add(mul(v, c), mul(cross(k, v), s)), mul(k, dot(k, v) * (1 - c)));
    return [R(x0), y, R(z0)];
  }

  function quatFromFrame(F) {
    const [x, y, z] = F;
    const m00 = x[0], m01 = y[0], m02 = z[0], m10 = x[1], m11 = y[1], m12 = z[1], m20 = x[2], m21 = y[2], m22 = z[2];
    const tr = m00 + m11 + m22;
    let w, qx, qy, qz, S;
    if (tr > 0) { S = Math.sqrt(tr + 1) * 2; w = 0.25 * S; qx = (m21 - m12) / S; qy = (m02 - m20) / S; qz = (m10 - m01) / S; }
    else if (m00 > m11 && m00 > m22) { S = Math.sqrt(1 + m00 - m11 - m22) * 2; w = (m21 - m12) / S; qx = 0.25 * S; qy = (m01 + m10) / S; qz = (m02 + m20) / S; }
    else if (m11 > m22) { S = Math.sqrt(1 + m11 - m00 - m22) * 2; w = (m02 - m20) / S; qx = (m01 + m10) / S; qy = 0.25 * S; qz = (m12 + m21) / S; }
    else { S = Math.sqrt(1 + m22 - m00 - m11) * 2; w = (m10 - m01) / S; qx = (m02 + m20) / S; qy = (m12 + m21) / S; qz = 0.25 * S; }
    return w < 0 ? [-w, -qx, -qy, -qz] : [w, qx, qy, qz];
  }

  function euler(q) {
    const [w, x, y, z] = q, d = 180 / Math.PI;
    return [
      Math.atan2(2 * (w * x + y * z), 1 - 2 * (x * x + y * y)) * d,
      Math.asin(Math.max(-1, Math.min(1, 2 * (w * y - z * x)))) * d,
      Math.atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z)) * d,
    ];
  }

  // Gaya spesifik saat diam menunjuk ke atas; medan bumi di Jawa ±44 µT, inklinasi ±−32° (utara = −z).
  const GRAV = [0, 9.81, 0];
  const B_EARTH = [0, 23, -37];
  const noise = (k) => (Math.random() + Math.random() + Math.random() - 1.5) * k;

  // Sumber gerak: parameter tari prosedural (objek p) atau fungsi t → J (rekaman mocap, lihat clipSource).
  const jointsAt = (src, t) => (typeof src === 'function' ? src(t) : skeleton(angles(src, t)));

  function sensors(src, t, nodeId) {
    const h = 0.01;
    const node = nodeById[nodeId];
    const Jm = jointsAt(src, t - h), J0 = jointsAt(src, t), Jp = jointsAt(src, t + h);
    const pm = Jm[node.at], p0 = J0[node.at], pp = Jp[node.at];
    const accW = add(mul(add(sub(pp, mul(p0, 2)), pm), 1 / (h * h)), GRAV);
    const F0 = frameOf(J0, node), F1 = frameOf(Jp, node);
    let w = [0, 0, 0];
    for (let i = 0; i < 3; i++) w = add(w, cross(F0[i], F1[i]));
    w = mul(w, 0.5 / h);
    const toBody = (v) => [dot(v, F0[0]), dot(v, F0[1]), dot(v, F0[2])];
    const deg = 180 / Math.PI;
    const acc = toBody(accW).map((v) => v + noise(0.08));
    const gyr = toBody(w).map((v) => v * deg + noise(0.6));
    const mag = toBody(B_EARTH).map((v) => v + noise(0.4));
    return { acc, gyr, mag, q: quatFromFrame(F0), J: J0 };
  }

  function angleBetween(a, b) { return Math.acos(Math.max(-1, Math.min(1, dot(a, b)))) * 180 / Math.PI; }

  const BONES = [
    ['pelvis', 'spine'], ['spine', 'chest'], ['chest', 'neck'], ['neck', 'head'],
    ['neck', 'shoulderL'], ['shoulderL', 'elbowL'], ['elbowL', 'wristL'], ['wristL', 'handL'],
    ['neck', 'shoulderR'], ['shoulderR', 'elbowR'], ['elbowR', 'wristR'], ['wristR', 'handR'],
    ['pelvis', 'hipL'], ['hipL', 'kneeL'], ['kneeL', 'ankleL'], ['ankleL', 'toeL'],
    ['pelvis', 'hipR'], ['hipR', 'kneeR'], ['kneeR', 'ankleR'], ['ankleR', 'toeR'],
  ];

  // ---------- Renderer ----------
  function Stage(canvas, opt) {
    this.c = canvas;
    this.ctx = canvas.getContext('2d');
    this.opt = opt || {};
    this.pal = this.opt.palette;
    this.yaw = this.opt.yaw != null ? this.opt.yaw : 0.5;
    this.pitch = 0.22;
    this.autoRotate = this.opt.autoRotate || 0;
    this.trails = {};
    this.w = 0; this.h = 0; this.dpr = 1;
    const fit = () => {
      const r = canvas.getBoundingClientRect();
      this.dpr = Math.min(2, window.devicePixelRatio || 1);
      this.w = r.width; this.h = r.height;
      canvas.width = Math.max(1, Math.round(r.width * this.dpr));
      canvas.height = Math.max(1, Math.round(r.height * this.dpr));
    };
    if ('ResizeObserver' in window) new ResizeObserver(fit).observe(canvas);
    window.addEventListener('resize', fit);
    fit();
    let dragX = null;
    canvas.addEventListener('pointerdown', (e) => { dragX = e.clientX; canvas.setPointerCapture(e.pointerId); });
    canvas.addEventListener('pointermove', (e) => { if (dragX == null) return; this.yaw += (e.clientX - dragX) * 0.01; dragX = e.clientX; });
    const end = () => { dragX = null; };
    canvas.addEventListener('pointerup', end);
    canvas.addEventListener('pointercancel', end);
  }

  Stage.prototype.project = function (p) {
    let v = rotY(sub(p, [0, 0.85, 0]), this.yaw);
    v = rotX(v, this.pitch);
    const s0 = Math.min(this.h * 0.8 / 1.85, this.w * 0.9 / 1.7);
    const D = 3.4, s = s0 * D / (D - v[2]);
    return [this.w / 2 + v[0] * s, this.h * 0.5 - v[1] * s, s];
  };

  Stage.prototype.tick = function (dt) { if (this.autoRotate) this.yaw += this.autoRotate * dt; };

  Stage.prototype.drawGround = function () {
    const ctx = this.ctx, P = this.pal;
    ctx.save();
    ctx.lineWidth = 1;
    for (const [r, a] of [[0.95, 0.55], [0.62, 0.3]]) {
      ctx.strokeStyle = P.ring; ctx.globalAlpha = a;
      ctx.beginPath();
      for (let i = 0; i <= 72; i++) {
        const t = i / 72 * TAU, q = this.project([Math.cos(t) * r, 0, Math.sin(t) * r]);
        i ? ctx.lineTo(q[0], q[1]) : ctx.moveTo(q[0], q[1]);
      }
      ctx.stroke();
    }
    ctx.globalAlpha = 0.6;
    for (let i = 0; i < 36; i++) {
      const t = i / 36 * TAU, long = i % 9 === 0;
      const a = this.project([Math.cos(t) * 0.95, 0, Math.sin(t) * 0.95]);
      const b = this.project([Math.cos(t) * (long ? 1.08 : 1.01), 0, Math.sin(t) * (long ? 1.08 : 1.01)]);
      ctx.beginPath(); ctx.moveTo(a[0], a[1]); ctx.lineTo(b[0], b[1]); ctx.stroke();
    }
    ctx.globalAlpha = 0.85;
    ctx.fillStyle = P.text;
    ctx.font = '500 10px "IBM Plex Mono", monospace';
    ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    for (const [lbl, x, z] of [['U', 0, -1.2], ['S', 0, 1.2], ['T', 1.2, 0], ['B', -1.2, 0]]) {
      const q = this.project([x, 0, z]);
      ctx.fillText(lbl, q[0], q[1]);
    }
    ctx.restore();
  };

  Stage.prototype.drawBody = function (J, color, width, glow) {
    const ctx = this.ctx, P = this.pal;
    const pr = {};
    for (const k in J) pr[k] = this.project(J[k]);
    ctx.save();
    ctx.lineCap = 'round'; ctx.lineJoin = 'round';
    ctx.strokeStyle = color;
    if (glow) { ctx.shadowColor = P.glow; ctx.shadowBlur = 14; }

    // Sampur: selendang dari pinggang ke kedua tangan
    if (glow) {
      ctx.save();
      ctx.shadowBlur = 0;
      ctx.strokeStyle = P.sampur; ctx.globalAlpha = 0.75; ctx.lineWidth = width * 1.6;
      for (const k of ['L', 'R']) {
        const a = pr['hip' + k], b = pr['hand' + k], kn = pr['knee' + k];
        ctx.beginPath(); ctx.moveTo(a[0], a[1]);
        ctx.quadraticCurveTo((a[0] + b[0]) / 2, Math.max(a[1], b[1]) + (kn[1] - a[1]) * 0.5, b[0], b[1]);
        ctx.stroke();
      }
      ctx.restore();
    }

    ctx.lineWidth = width;
    ctx.beginPath();
    for (const [a, b] of BONES) { ctx.moveTo(pr[a][0], pr[a][1]); ctx.lineTo(pr[b][0], pr[b][1]); }
    ctx.stroke();
    if (J.fingers) {   // jari dari SAM 3D Body: garis tipis per ruas
      ctx.save(); ctx.lineWidth = Math.max(1, width * 0.45); ctx.shadowBlur = glow ? 6 : 0; ctx.beginPath();
      for (const ch of J.fingers) ch.forEach((p, i) => { const q = this.project(p); i ? ctx.lineTo(q[0], q[1]) : ctx.moveTo(q[0], q[1]); });
      ctx.stroke(); ctx.restore();
    }

    const hd = pr.head, r = 0.095 * hd[2];
    ctx.lineWidth = width;
    ctx.beginPath(); ctx.arc(hd[0], hd[1], r, 0, TAU); ctx.stroke();
    // Sanggul di belakang kepala
    const back = this.project(add(J.head, mul(sub(J.head, J.nose), 1.05)));
    ctx.fillStyle = color;
    ctx.beginPath(); ctx.arc(back[0], back[1] + r * 0.2, r * 0.45, 0, TAU); ctx.fill();
    if (glow) {
      const nz = pr.nose;
      ctx.fillStyle = P.boneHi;
      ctx.beginPath(); ctx.arc(nz[0], nz[1], Math.max(1.5, r * 0.18), 0, TAU); ctx.fill();
    }
    ctx.restore();
    return pr;
  };

  Stage.prototype.draw = function (J, o) {
    o = o || {};
    const ctx = this.ctx, d = this.dpr, P = this.pal;
    ctx.setTransform(d, 0, 0, d, 0, 0);
    ctx.clearRect(0, 0, this.w, this.h);
    if (!this.w) return;
    this.drawGround();
    if (o.ghost) this.drawBody(o.ghost, P.ghost, 2, false);

    for (const key of o.trail || []) {
      const tr = this.trails[key] || (this.trails[key] = []);
      tr.push(J[key]);
      if (tr.length > 70) tr.shift();
      ctx.save();
      ctx.strokeStyle = P.boneHi; ctx.lineWidth = 1.4;
      for (let i = 1; i < tr.length; i++) {
        const a = this.project(tr[i - 1]), b = this.project(tr[i]);
        ctx.globalAlpha = (i / tr.length) * 0.55;
        ctx.beginPath(); ctx.moveTo(a[0], a[1]); ctx.lineTo(b[0], b[1]); ctx.stroke();
      }
      ctx.restore();
    }

    const pr = this.drawBody(J, P.bone, o.width || 3, true);

    for (const n of NODES) {
      if (o.nodes === false) break;
      const q = pr[n.at], on = n.id === o.active;
      const sz = on ? 6 : 4;
      ctx.save();
      ctx.translate(q[0], q[1]); ctx.rotate(Math.PI / 4);
      ctx.fillStyle = on ? P.node : P.ink;
      ctx.strokeStyle = P.node; ctx.lineWidth = 1.5;
      ctx.fillRect(-sz, -sz, sz * 2, sz * 2); ctx.strokeRect(-sz, -sz, sz * 2, sz * 2);
      ctx.restore();
      if (on) {
        const pulse = (performance.now() / 900) % 1;
        ctx.save();
        ctx.strokeStyle = P.node; ctx.globalAlpha = 1 - pulse; ctx.lineWidth = 1;
        ctx.beginPath(); ctx.arc(q[0], q[1], 8 + pulse * 16, 0, TAU); ctx.stroke();
        ctx.globalAlpha = 1; ctx.fillStyle = P.boneHi;
        ctx.font = '500 11px "IBM Plex Mono", monospace';
        ctx.fillText(n.label, q[0] + 14, q[1] - 10);
        ctx.restore();
      }
    }
  };

  // ---------- Rekaman mocap → kerangka NaraMotion ----------
  // Q: kuaternion global [w,x,y,z] per segmen (kerangka SMPL: y ke atas, kiri penari = +x). Arah istirahat:
  // badan/kepala +y, lengan kiri +x / kanan −x, tungkai −y. Panjang tulang memakai SEG NaraMotion; kaki dikunci ke lantai.
  function rotq(q, v) {
    const [w, x, y, z] = q, tx = 2 * (y * v[2] - z * v[1]), ty = 2 * (z * v[0] - x * v[2]), tz = 2 * (x * v[1] - y * v[0]);
    return [v[0] + w * tx + (y * tz - z * ty), v[1] + w * ty + (z * tx - x * tz), v[2] + w * tz + (x * ty - y * tx)];
  }
  function poseFromQuats(Q) {
    const b = Q.badan, k = Q.kepala, pelvis = [0, 0, 0], J = { pelvis };
    J.spine = add(pelvis, rotq(b, [0, 0.2, 0])); J.chest = add(pelvis, rotq(b, [0, 0.4, 0])); J.neck = add(pelvis, rotq(b, [0, 0.55, 0]));
    J.head = add(J.neck, rotq(k, [0, 0.14, 0])); J.nose = add(J.head, rotq(k, [0, 0, 0.1]));
    for (const [s, K, side] of [[1, 'L', 'ki'], [-1, 'R', 'ka']]) {
      J['shoulder' + K] = add(pelvis, rotq(b, [0.19 * s, 0.52, 0]));
      J['elbow' + K] = add(J['shoulder' + K], mul(rotq(Q['lengan_atas_' + side], [s, 0, 0]), SEG.upper));
      const fd = rotq(Q['lengan_bawah_' + side], [s, 0, 0]);
      J['wrist' + K] = add(J['elbow' + K], mul(fd, SEG.fore)); J['hand' + K] = add(J['wrist' + K], mul(fd, SEG.hand));
      J['uArm' + K] = mul(add(J['shoulder' + K], J['elbow' + K]), 0.5);
      J['fArm' + K] = add(mul(J['elbow' + K], 0.4), mul(J['wrist' + K], 0.6));
      J['hip' + K] = add(pelvis, rotq(b, [0.1 * s, 0, 0]));
      J['knee' + K] = add(J['hip' + K], mul(rotq(Q['paha_' + side], [0, -1, 0]), SEG.thigh));
      J['ankle' + K] = add(J['knee' + K], mul(rotq(Q['betis_' + side], [0, -1, 0]), SEG.shin));
      J['toe' + K] = add(J['ankle' + K], rotq(Q['betis_' + side], [0, -0.04, 0.13]));
      J['thigh' + K] = mul(add(J['hip' + K], J['knee' + K]), 0.5); J['shin' + K] = mul(add(J['knee' + K], J['ankle' + K]), 0.5);
    }
    const lift = 0.06 - Math.min(J.ankleL[1], J.ankleR[1]);
    for (const n in J) J[n] = [J[n][0], J[n][1] + lift, J[n][2]];
    return J;
  }
  // clip: { hz, nodes: { kepala: [[w,x,y,z], …], … } } → fungsi t → J (berulang, interpolasi linear antar-frame)
  function clipSource(clip) {
    const names = Object.keys(clip.nodes), N = clip.nodes[names[0]].length;
    const frames = Array.from({ length: N }, (_, i) => poseFromQuats(Object.fromEntries(names.map((n) => [n, clip.nodes[n][i]]))));
    return (t) => {
      const f = ((t * clip.hz) % N + N) % N, i0 = Math.floor(f), i1 = (i0 + 1) % N, w = f - i0, A = frames[i0], B = frames[i1], J = {};
      for (const n in A) J[n] = [A[n][0] + (B[n][0] - A[n][0]) * w, A[n][1] + (B[n][1] - A[n][1]) * w, A[n][2] + (B[n][2] - A[n][2]) * w];
      return J;
    };
  }

  // clip posisi (SAM 3D Body): { hz, joints: { nama: [[x,y,z], …] }, fingers: [frame][rantai][titik][3] } → fungsi t → J.
  // Rantai jari disimpan sebagai properti tak-terhitung J.fingers agar perhitungan sendi/sensor tidak terganggu.
  function positionSource(clip) {
    const names = Object.keys(clip.joints), N = clip.joints[names[0]].length;
    const lerp3 = (a, b, w) => [a[0] + (b[0] - a[0]) * w, a[1] + (b[1] - a[1]) * w, a[2] + (b[2] - a[2]) * w];
    return (t) => {
      const f = ((t * clip.hz) % N + N) % N, i0 = Math.floor(f), i1 = (i0 + 1) % N, w = f - i0, J = {};
      for (const n of names) J[n] = lerp3(clip.joints[n][i0], clip.joints[n][i1], w);
      for (const k of ['L', 'R']) {
        J['uArm' + k] = mul(add(J['shoulder' + k], J['elbow' + k]), 0.5);
        J['fArm' + k] = add(mul(J['elbow' + k], 0.4), mul(J['wrist' + k], 0.6));
        J['thigh' + k] = mul(add(J['hip' + k], J['knee' + k]), 0.5);
        J['shin' + k] = mul(add(J['knee' + k], J['ankle' + k]), 0.5);
      }
      if (clip.fingers) Object.defineProperty(J, 'fingers', { enumerable: false, value: clip.fingers[i0].map((ch, c) => ch.map((p, j) => lerp3(p, clip.fingers[i1][c][j], w))) });
      return J;
    };
  }

  root.NaraMotion = { DANCES, NODES, angles, skeleton, sensors, jointsAt, poseFromQuats, clipSource, positionSource, segDir, frameOf, quatFromFrame, euler, angleBetween, Stage, nodeById };
})(window);
