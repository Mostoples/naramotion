/* NaraMotion · halaman depan: video pembuka, feed video contoh tari (gaya Reels/TikTok), galeri sejarah tari. */
(function () {
  'use strict';
  const $ = (s, r = document) => r.querySelector(s), $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // ---------- Video pembuka: 16:9 di layar lebar, 9:16 di ponsel ----------
  const iv = $('#intro-vid');
  if (iv) {
    const tall = window.matchMedia('(max-aspect-ratio: 4/5)').matches;
    iv.poster = tall ? 'assets/hero/hero_9x16.jpg' : 'assets/hero/hero_16x9.jpg';
    if (!reduce) { iv.src = tall ? 'assets/hero/hero_9x16.mp4' : 'assets/hero/hero_16x9.mp4'; iv.play().catch(() => {}); }
    $('#intro-pause').addEventListener('click', (e) => {
      if (iv.paused) { if (!iv.src) iv.src = tall ? 'assets/hero/hero_9x16.mp4' : 'assets/hero/hero_16x9.mp4'; iv.play().catch(() => {}); e.currentTarget.textContent = 'Jeda video'; }
      else { iv.pause(); e.currentTarget.textContent = 'Putar video'; }
    });
    if (reduce) $('#intro-pause').textContent = 'Putar video';
  }

  // ---------- Galeri sejarah ----------
  const H = window.NaraHistory || [], hist = $('#hist-cards'), dlg = $('#hist-dlg');
  function openHistory(id) {
    const h = H.find((x) => x.id === id); if (!h || !dlg) return;
    $('#hist-body', dlg).innerHTML = `<p class="eyebrow">${esc(h.type)}</p><h2 class="h2" id="hist-title">${esc(h.name)}</h2><p class="hist-region">${esc(h.region)}</p>
      <p class="lead">${esc(h.lead)}</p>${h.sections.map(([t, p]) => `<h3>${esc(t)}</h3><p>${esc(p)}</p>`).join('')}
      <p class="fine">Ringkasan dari sumber umum (ensiklopedia tari, katalog Warisan Budaya Takbenda Kemendikbud). Mohon diverifikasi guru tari untuk bahan ajar resmi.</p>`;
    if (dlg.showModal) dlg.showModal(); else dlg.setAttribute('open', '');
  }
  if (hist) {
    hist.innerHTML = H.map((h, i) => `<button type="button" class="hist-card frame${i === 0 ? ' is-first' : ''}" data-hist="${h.id}">
      <span class="hist-type">${esc(h.type)}</span><span class="hist-name">${esc(h.name)}</span><span class="hist-region">${esc(h.region)}</span>
      <span class="hist-lead">${esc(h.lead)}</span><span class="hist-go">Baca sejarahnya →</span></button>`).join('');
    hist.addEventListener('click', (e) => { const b = e.target.closest('[data-hist]'); if (b) openHistory(b.dataset.hist); });
    $('#hist-close').addEventListener('click', () => dlg.close ? dlg.close() : dlg.removeAttribute('open'));
    dlg.addEventListener('click', (e) => { if (e.target === dlg) dlg.close(); });
  }
  window.NaraOpenHistory = openHistory;

  // ---------- Feed video contoh tari ----------
  const feed = $('#reels-feed'); if (!feed) return;
  let items = [], filter = 'all';
  const io = 'IntersectionObserver' in window ? new IntersectionObserver((ents) => ents.forEach((en) => {
    const v = en.target.querySelector('video'); if (!v) return;
    if (en.isIntersecting && en.intersectionRatio > 0.6) { if (!v.src) v.src = v.dataset.src; v.play().catch(() => {}); }
    else v.pause();
  }), { root: feed, threshold: [0, 0.6, 1] }) : null;

  function render() {
    const list = items.filter((r) => filter === 'all' || (filter === 'jawa' ? !r.ds : r.ds === filter));
    feed.innerHTML = list.map((r, i) => `<article class="reel" aria-label="${esc(r.title)}">
      <video muted loop playsinline preload="none" poster="assets/reels/${esc(r.file)}.jpg" data-src="assets/reels/${esc(r.file)}.mp4"></video>
      <div class="reel-info">
        <p class="reel-count">${i + 1} / ${list.length}</p>
        <h3>${esc(r.title)}</h3><p class="reel-region">${esc(r.region)}</p><p class="reel-note">${esc(r.note)}</p>
        <div class="reel-acts">
          ${r.ds ? `<button type="button" class="btn btn-gold btn-sm" data-practice="${esc(r.ds)}" data-move="${esc(r.move)}">Latih gerak ini</button>` : `<a class="btn btn-gold btn-sm" href="#studio">Lihat di Studio</a>`}
          <button type="button" class="btn btn-line btn-sm" data-hist="${r.ds ? 'bali-dasar' : esc(r.id)}">Sejarah</button>
        </div>
      </div></article>`).join('');
    feed.scrollTop = 0;
    if (io) $$('.reel', feed).forEach((el) => io.observe(el));
    else $$('video', feed).forEach((v) => { v.src = v.dataset.src; });
  }
  feed.addEventListener('click', (e) => {
    const p = e.target.closest('[data-practice]');
    if (p) { window.dispatchEvent(new CustomEvent('nara:practice', { detail: { ds: p.dataset.practice, move: p.dataset.move } })); return; }
    const h = e.target.closest('[data-hist]'); if (h) { openHistory(h.dataset.hist); return; }
    const v = e.target.closest('.reel') && e.target.closest('.reel').querySelector('video');
    if (v && !e.target.closest('.reel-info')) { if (v.paused) v.play().catch(() => {}); else v.pause(); }
  });
  $$('[data-reels]').forEach((b) => b.addEventListener('click', () => {
    filter = b.dataset.reels; $$('[data-reels]').forEach((x) => x.setAttribute('aria-pressed', String(x === b))); render();
  }));
  const wrap = $('#reels-wrap');
  // layar penuh: pindahkan feed ke <body> agar berada di atas bilah atas (latar batik membuat konteks tumpuk sendiri)
  const home = document.createComment('reels'); wrap.parentNode.insertBefore(home, wrap);
  $('#reels-full').addEventListener('click', () => { document.body.appendChild(wrap); wrap.classList.add('is-full'); document.body.classList.add('no-scroll'); $('#reels-exit').focus(); });
  $('#reels-exit').addEventListener('click', () => { wrap.classList.remove('is-full'); home.parentNode.insertBefore(wrap, home.nextSibling); document.body.classList.remove('no-scroll'); $('#reels-full').focus(); });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && wrap.classList.contains('is-full')) $('#reels-exit').click();
    if (!wrap.classList.contains('is-full') || (e.key !== 'ArrowDown' && e.key !== 'ArrowUp')) return;
    e.preventDefault(); feed.scrollBy({ top: (e.key === 'ArrowDown' ? 1 : -1) * feed.clientHeight, behavior: reduce ? 'auto' : 'smooth' });
  });
  fetch('assets/reels/reels.json').then((r) => r.json()).then((j) => { items = j; render(); })
    .catch(() => { feed.innerHTML = '<p class="reel-empty">Video contoh belum bisa dimuat. Muat ulang halaman untuk mencoba lagi.</p>'; });
})();
