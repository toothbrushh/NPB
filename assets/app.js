/* NPB 日本職棒賽程戰績 — 純前端，讀取 data/ 底下由爬蟲產生的靜態 JSON */
'use strict';

const TEAMS = {
  G: { lg: 'C', zh: '讀賣巨人', s: '巨人', ja: '読売ジャイアンツ', color: '#F97709', city: '東京都', founded: 1934, home: '東京巨蛋', site: 'https://www.giants.jp/', wiki: ['讀賣巨人', '読売ジャイアンツ'] },
  T: { lg: 'C', zh: '阪神虎', s: '阪神', ja: '阪神タイガース', color: '#FFE201', city: '兵庫縣西宮市', founded: 1935, home: '阪神甲子園球場', site: 'https://hanshintigers.jp/', wiki: ['阪神虎', '阪神タイガース'] },
  DB: { lg: 'C', zh: '橫濱DeNA海灣之星', s: 'DeNA', ja: '横浜DeNAベイスターズ', color: '#0055A5', city: '神奈川縣橫濱市', founded: 1949, home: '橫濱球場', site: 'https://www.baystars.co.jp/', wiki: ['橫濱DeNA海灣之星', '横浜DeNAベイスターズ'] },
  C: { lg: 'C', zh: '廣島東洋鯉魚', s: '廣島', ja: '広島東洋カープ', color: '#E50012', city: '廣島縣廣島市', founded: 1949, home: 'MAZDA Zoom-Zoom 球場廣島', site: 'https://www.carp.co.jp/', wiki: ['廣島東洋鯉魚', '広島東洋カープ'] },
  S: { lg: 'C', zh: '東京養樂多燕子', s: '養樂多', ja: '東京ヤクルトスワローズ', color: '#00AB5C', city: '東京都', founded: 1950, home: '明治神宮野球場', site: 'https://www.yakult-swallows.co.jp/', wiki: ['東京養樂多燕子', '東京ヤクルトスワローズ'] },
  D: { lg: 'C', zh: '中日龍', s: '中日', ja: '中日ドラゴンズ', color: '#002569', city: '愛知縣名古屋市', founded: 1936, home: '萬特力巨蛋名古屋', site: 'https://dragons.jp/', wiki: ['中日龍', '中日ドラゴンズ'] },
  H: { lg: 'P', zh: '福岡軟銀鷹', s: '軟銀', ja: '福岡ソフトバンクホークス', color: '#F5C700', city: '福岡縣福岡市', founded: 1938, home: '瑞穗PayPay巨蛋福岡', site: 'https://www.softbankhawks.co.jp/', wiki: ['福岡軟銀鷹', '福岡ソフトバンクホークス'] },
  F: { lg: 'P', zh: '北海道日本火腿鬥士', s: '火腿', ja: '北海道日本ハムファイターズ', color: '#01609A', city: '北海道北廣島市', founded: 1946, home: 'ES CON FIELD HOKKAIDO', site: 'https://www.fighters.co.jp/', wiki: ['北海道日本火腿鬥士', '北海道日本ハムファイターズ'] },
  M: { lg: 'P', zh: '千葉羅德海洋', s: '羅德', ja: '千葉ロッテマリーンズ', color: '#221815', city: '千葉縣千葉市', founded: 1949, home: 'ZOZO海洋球場', site: 'https://www.marines.co.jp/', wiki: ['千葉羅德海洋', '千葉ロッテマリーンズ'] },
  E: { lg: 'P', zh: '東北樂天金鷲', s: '樂天', ja: '東北楽天ゴールデンイーグルス', color: '#85010F', city: '宮城縣仙台市', founded: 2004, home: '樂天移動最強公園宮城', site: 'https://www.rakuteneagles.jp/', wiki: ['東北樂天金鷲', '東北楽天ゴールデンイーグルス'] },
  B: { lg: 'P', zh: '歐力士猛牛', s: '歐力士', ja: 'オリックス・バファローズ', color: '#000019', city: '大阪府大阪市', founded: 1936, home: '京瓷巨蛋大阪', site: 'https://www.buffaloes.co.jp/', wiki: ['歐力士猛牛', 'オリックス・バファローズ'] },
  L: { lg: 'P', zh: '埼玉西武獅', s: '西武', ja: '埼玉西武ライオンズ', color: '#1F366A', city: '埼玉縣所澤市', founded: 1950, home: 'BELLUNA巨蛋', site: 'https://www.seibulions.jp/', wiki: ['埼玉西武獅', '埼玉西武ライオンズ'] },
  CL: { lg: '', zh: '中央聯盟選拔', s: '央聯', color: '#0b6bcb' },
  PL: { lg: '', zh: '太平洋聯盟選拔', s: '洋聯', color: '#1d9a6c' },
};
const LEAGUES = { C: '中央聯盟', P: '太平洋聯盟' };
const WD = ['日', '一', '二', '三', '四', '五', '六'];
const STAGE_ORDER = ['cs1', 'cs', 'cs2', 'js'];
const STATUS = { final: '終', scheduled: '未賽', postponed: '延賽' };

const state = { seasons: [], year: null, sched: null, players: null, tab: 'schedule',
  filterTeam: '', filterStage: 'all', boxCache: {} };

const $ = (s, r = document) => r.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const team = c => TEAMS[c] || { zh: c, s: c, color: '#888', lg: '' };
// 球隊徽章：assets/logos/{代碼}.svg（可替換成官方圖檔，見 README）
const logo = (c, size = 22) => TEAMS[c]
  ? `<img class="logo" src="assets/logos/${c}.svg" width="${size}" height="${size}" alt="" loading="lazy">`
  : `<span class="dot" style="background:#888"></span>`;
const dot = c => logo(c);
const teamLink = (c, label = team(c).zh) => TEAMS[c]?.lg ? `<a class="tlink" href="#/${state.year}/teams/${c}">${esc(label)}</a>` : esc(label);
// 與爬蟲 player_key() 相同規則
const playerKey = (pid, t, name) => pid || `${t}_${String(name).replace(/[^0-9A-Za-z\u4e00-\u9fff\u3041-\u3093\u30a1-\u30ff\u3005]/g, '')}`;
const playerLink = (key, label) => `<a class="plink" href="#/${state.year}/player/${encodeURIComponent(key)}">${esc(label)}</a>`;
const todayJST = () => new Date(Date.now() + 9 * 3600e3).toISOString().slice(0, 10);
const pct = (w, l) => (w + l ? (w / (w + l)).toFixed(3).replace(/^0/, '') : '.000');

async function getJSON(url) {
  const r = await fetch(url, { cache: 'no-cache' });
  if (!r.ok) throw new Error(`${url}: ${r.status}`);
  return r.json();
}

/* ------------------------------------------------------------ 路由 */
function parseHash() {
  const [, y, tab, extra] = location.hash.split('/');
  return { y: +y || null, tab: tab || 'schedule', extra: extra && decodeURIComponent(extra) };
}
function go(tab, year = state.year) { location.hash = `#/${year}/${tab}`; }

async function route() {
  const h = parseHash();
  const year = h.y && state.seasons.some(s => s.year === h.y) ? h.y : state.seasons[0]?.year;
  if (!year) return renderNoData();
  if (year !== state.year) await loadSeason(year);
  state.tab = h.tab === 'game' ? state.tab : h.tab;
  if (h.tab !== 'game') state.extra = h.extra;
  $('#season').value = year;
  document.querySelectorAll('#tabs a').forEach(a => {
    a.classList.toggle('active', a.dataset.tab === (state.tab === 'player' ? 'players' : state.tab));
    a.href = `#/${year}/${a.dataset.tab}`;
  });
  render();
  if (h.tab === 'game' && h.extra) openGame(h.extra);
}

async function loadSeason(year) {
  $('#app').innerHTML = '<p class="empty">載入中…</p>';
  state.year = year;
  state.sched = await getJSON(`data/${year}/schedule.json`);
  state.players = null;
  state.boxCache = {};
  $('#updated').textContent = `資料更新：${(state.sched.updated || '').replace('T', ' ')}` +
    (state.sched.complete ? '（本季已完結，資料已封存）' : '');
}

function render() {
  const fn = { schedule: renderSchedule, standings: renderStandings, postseason: renderPostseason,
    players: renderPlayers, teams: renderTeams, player: renderPlayer }[state.tab] || renderSchedule;
  window.scrollTo(0, 0);
  fn();
}

function renderNoData() {
  $('#app').innerHTML = `<div class="notice">
    <h2>尚無資料</h2>
    <p>請到 GitHub 儲存庫的 <b>Actions → Update NPB data → Run workflow</b> 執行爬蟲，
    例如輸入 <code>2015-current</code> 抓取 2015 年至今的資料。完成後重新整理此頁。</p></div>`;
}

/* ------------------------------------------------------------ 共用元件 */
function gameCard(g, opts = {}) {
  const fin = g.status === 'final';
  const aw = fin && g.awayScore > g.homeScore, hw = fin && g.homeScore > g.awayScore;
  const cls = (w, l) => (fin ? (w ? 'win' : l ? 'lose' : '') : '');
  const stageTag = g.stage !== 'regular' ? `<span class="tag post">${esc(g.stageName)}</span>` : '';
  const mid = fin
    ? `<div class="score">${g.awayScore} - ${g.homeScore}</div><div class="status">${g.awayScore === g.homeScore ? '和局' : '終'}</div>`
    : g.status === 'postponed'
      ? `<div class="score">-</div><span class="tag ppd">延賽/中止</span>`
      : `<div class="score" style="font-size:16px">${esc(g.time || 'TBD')}</div><div class="status">未賽</div>`;
  const venue = g.venue ? `${esc(g.venue)}${g.venueSource === 'home' ? '（預定）' : ''}` : '';
  const extra = [g.winP && `勝 ${esc(g.winP)}`, g.loseP && `敗 ${esc(g.loseP)}`, g.saveP && `S ${esc(g.saveP)}`].filter(Boolean).join(' ');
  return `<div class="game ${g.hasBox ? 'clickable' : ''}" ${g.hasBox ? `data-game="${esc(g.id)}"` : ''} title="${g.hasBox ? '點擊查看單場數據' : ''}">
    <div class="team away ${cls(aw, hw)}" title="${esc(team(g.away).zh)}">${logo(g.away, 28)}<span class="nm">${esc(team(g.away).s)}</span></div>
    <div class="mid">${mid}</div>
    <div class="team home ${cls(hw, aw)}" title="${esc(team(g.home).zh)}"><span class="nm">${esc(team(g.home).s)}</span>${logo(g.home, 28)}</div>
    <div class="meta"><span>${opts.date ? esc(g.date.slice(5)) + ' ' : ''}${venue}</span><span>${stageTag} ${extra}</span></div>
  </div>`;
}

function bindGameClicks(root = $('#app')) {
  root.querySelectorAll('[data-game]').forEach(el =>
    el.addEventListener('click', () => { location.hash = `#/${state.year}/game/${el.dataset.game}`; }));
}

function teamChips(selected, onPick) {
  const all = Object.keys(TEAMS).filter(c => TEAMS[c].lg);
  return `<button class="chip ${!selected ? 'on' : ''}" data-team="">全部球隊</button>` +
    all.map(c => `<button class="chip ${selected === c ? 'on' : ''}" data-team="${c}">${dot(c)} ${team(c).s}</button>`).join('');
}

/* ------------------------------------------------------------ 賽程 */
function renderSchedule() {
  const games = state.sched.games;
  const today = todayJST();
  let list = games.filter(g =>
    (!state.filterTeam || g.away === state.filterTeam || g.home === state.filterTeam) &&
    (state.filterStage === 'all' || (state.filterStage === 'post' ? !['regular', 'allstar'].includes(g.stage) : g.stage === state.filterStage)));

  const next = games.find(g => g.status === 'scheduled' && g.date >= today);
  const lastDone = [...games].reverse().find(g => g.status === 'final');
  const done = games.filter(g => g.status === 'final').length;
  const hero = `<div class="hero">
    <div class="hero-card"><div class="label">賽季進度</div><div class="big">${done} / ${games.length} 場</div>
      <div class="status">${state.sched.complete ? '本季已結束' : '進行中'}</div></div>
    ${next ? `<div class="hero-card"><div class="label">下一場</div><div class="big">${next.date.slice(5).replace('-', '/')} ${esc(next.time || '')}</div>
      <div>${esc(team(next.away).s)} @ ${esc(team(next.home).s)} · ${esc(next.venue || '')} <span id="countdown"></span></div></div>` : ''}
    ${lastDone ? `<div class="hero-card"><div class="label">最新賽果 · ${lastDone.date.slice(5).replace('-', '/')}</div>
      <div class="big">${esc(team(lastDone.away).s)} ${lastDone.awayScore} - ${lastDone.homeScore} ${esc(team(lastDone.home).s)}</div>
      <div class="status">${esc(lastDone.stageName)}</div></div>` : ''}
  </div>`;

  const stages = [['all', '全部'], ['regular', '例行賽'], ['post', '季後賽'], ['allstar', '明星賽']];
  const toolbar = `<div class="toolbar">${stages.map(([k, v]) =>
    `<button class="chip ${state.filterStage === k ? 'on' : ''}" data-stage="${k}">${v}</button>`).join('')}</div>
    <div class="toolbar">${teamChips(state.filterTeam)}</div>`;

  const byMonth = new Map();
  for (const g of list) {
    const m = g.date.slice(0, 7);
    if (!byMonth.has(m)) byMonth.set(m, new Map());
    const d = byMonth.get(m);
    if (!d.has(g.date)) d.set(g.date, []);
    d.get(g.date).push(g);
  }
  let body = '';
  for (const [m, days] of byMonth) {
    body += `<section class="month" id="m-${m}"><div class="month-title">${m.replace('-', ' 年 ')} 月</div>`;
    for (const [d, gs] of days) {
      const wd = WD[new Date(d + 'T12:00:00Z').getUTCDay()];
      body += `<div class="day ${d === today ? 'today' : ''}" ${d === today ? 'id="today"' : ''}>
        <div class="day-date">${+d.slice(5, 7)}/${+d.slice(8)}<small>週${wd}</small></div>
        <div class="games">${gs.map(g => gameCard(g)).join('')}</div></div>`;
    }
    body += '</section>';
  }
  $('#app').innerHTML = hero + toolbar + (body || '<p class="empty">沒有符合條件的比賽</p>');
  $('#app').querySelectorAll('[data-stage]').forEach(b => b.onclick = () => { state.filterStage = b.dataset.stage; renderSchedule(); });
  $('#app').querySelectorAll('[data-team]').forEach(b => b.onclick = () => { state.filterTeam = b.dataset.team; renderSchedule(); });
  bindGameClicks();
  if (next) startCountdown(next);
  // 本季進行中時，自動捲到今天或最近一個比賽日
  if (!state.sched.complete && !state._scrolled) {
    state._scrolled = true;
    const target = $('#today') || [...document.querySelectorAll('.day')].find(el => el.querySelector('.status')?.textContent === '未賽');
    target?.scrollIntoView({ block: 'center' });
  }
}

let cdTimer;
function startCountdown(g) {
  clearInterval(cdTimer);
  const t = new Date(`${g.date}T${g.time || '18:00'}:00+09:00`).getTime();
  const tick = () => {
    const el = $('#countdown');
    if (!el) return clearInterval(cdTimer);
    let s = Math.max(0, Math.floor((t - Date.now()) / 1000));
    const d = Math.floor(s / 86400); s %= 86400;
    const h = Math.floor(s / 3600); s %= 3600;
    el.textContent = `· 倒數 ${d ? d + '天 ' : ''}${String(h).padStart(2, '0')}:${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`;
  };
  tick();
  cdTimer = setInterval(tick, 1000);
}

/* ------------------------------------------------------------ 戰績 */
function computeStandings(games) {
  const rec = {};
  const get = c => rec[c] ??= { code: c, W: 0, L: 0, T: 0, RS: 0, RA: 0, hW: 0, hL: 0, aW: 0, aL: 0, iW: 0, iL: 0, iT: 0, seq: [], left: 0 };
  for (const g of games) {
    if (g.stage !== 'regular' || !TEAMS[g.away]?.lg || !TEAMS[g.home]?.lg) continue;
    const a = get(g.away), h = get(g.home);
    if (g.status === 'scheduled') { a.left++; h.left++; continue; }
    if (g.status !== 'final') continue;
    const inter = TEAMS[g.away].lg !== TEAMS[g.home].lg;
    a.RS += g.awayScore; a.RA += g.homeScore; h.RS += g.homeScore; h.RA += g.awayScore;
    const res = g.awayScore > g.homeScore ? ['W', 'L'] : g.awayScore < g.homeScore ? ['L', 'W'] : ['T', 'T'];
    [[a, res[0], 'a'], [h, res[1], 'h']].forEach(([t, r, side]) => {
      t[r]++;
      if (r !== 'T') t[side + r]++;
      if (inter) t['i' + r]++;
      t.seq.push({ r, date: g.date });
    });
  }
  const out = {};
  for (const lg of ['C', 'P']) {
    const rows = Object.values(rec).filter(r => TEAMS[r.code].lg === lg)
      .sort((x, y) => (y.W / (y.W + y.L || 1)) - (x.W / (x.W + x.L || 1)) || (y.W - x.W));
    const top = rows[0];
    rows.forEach((r, i) => {
      r.rank = i + 1;
      r.GB = i === 0 ? '-' : (((top.W - r.W) + (r.L - top.L)) / 2).toFixed(1).replace(/\.0$/, '');
      const prev = rows[i - 1];
      r.GBprev = i === 0 ? '-' : (((prev.W - r.W) + (r.L - prev.L)) / 2).toFixed(1).replace(/\.0$/, '');
      const last = r.seq.slice(-10);
      r.last10 = last;
      let k = r.seq.length - 1, n = 0;
      const kind = r.seq[k]?.r;
      while (k >= 0 && r.seq[k].r === kind) { n++; k--; }
      r.streak = kind ? `${n}${{ W: '連勝', L: '連敗', T: '和' }[kind]}` : '';
    });
    out[lg] = rows;
  }
  return out;
}

function renderStandings() {
  const st = computeStandings(state.sched.games);
  const table = rows => `<div class="table-wrap"><table class="data">
    <thead><tr><th>#</th><th class="l">球隊</th><th>場</th><th>勝</th><th>敗</th><th>和</th><th>勝率</th><th>勝差</th>
    <th>主場</th><th>客場</th><th>交流戰</th><th>得分</th><th>失分</th><th>得失差</th><th>剩餘</th><th class="l">近10場</th><th>連續</th></tr></thead>
    <tbody>${rows.map(r => `<tr class="${r.rank === 1 ? 'lead' : ''}">
      <td class="rank">${r.rank}</td>
      <td class="l">${dot(r.code)} <a href="#/${state.year}/teams/${r.code}">${esc(team(r.code).zh)}</a></td>
      <td>${r.W + r.L + r.T}</td><td>${r.W}</td><td>${r.L}</td><td>${r.T}</td>
      <td><b>${pct(r.W, r.L)}</b></td><td title="與前一名差 ${r.GBprev}">${r.GB}</td>
      <td>${r.hW}-${r.hL}</td><td>${r.aW}-${r.aL}</td><td>${r.iW}-${r.iL}-${r.iT}</td>
      <td>${r.RS}</td><td>${r.RA}</td><td>${r.RS - r.RA > 0 ? '+' : ''}${r.RS - r.RA}</td><td>${r.left}</td>
      <td class="l"><span class="form">${r.last10.map(x => `<i class="${x.r}">${{ W: '勝', L: '敗', T: '和' }[x.r]}</i>`).join('')}</span></td>
      <td>${r.streak}</td></tr>`).join('')}</tbody></table></div>`;
  let html = '';
  for (const lg of ['C', 'P']) {
    html += `<h2><span class="tag ${lg.toLowerCase()}">${lg}</span> ${LEAGUES[lg]} ${state.year}</h2>`;
    html += st[lg].length ? table(st[lg]) : '<p class="empty">尚無比賽結果</p>';
    html += `<h3>貯金走勢（勝場 − 敗場）</h3><div class="chart" id="chart-${lg}"></div>`;
  }
  html += '<p class="status" style="color:var(--muted);font-size:12px">排名依勝率（勝 ÷ (勝+敗)，和局不計）。勝差 = ((首位勝 − 勝) + (敗 − 首位敗)) ÷ 2。季後賽、明星賽不列入。</p>';
  $('#app').innerHTML = html;
  for (const lg of ['C', 'P']) drawRace($(`#chart-${lg}`), st[lg]);
}

/* 貯金走勢圖：每隊一條線，x = 日期，y = 勝 − 敗 */
const SERIES = ['var(--s1)', 'var(--s2)', 'var(--s3)', 'var(--s4)', 'var(--s5)', 'var(--s6)'];
function drawRace(el, rows) {
  if (!el || !rows.length) return;
  const codes = Object.keys(TEAMS).filter(c => TEAMS[c].lg === TEAMS[rows[0].code].lg); // 顏色跟隨球隊、固定順序
  const dates = [...new Set(rows.flatMap(r => r.seq.map(s => s.date)))].sort();
  if (dates.length < 2) { el.innerHTML = ''; return; }
  const series = codes.map(c => {
    const r = rows.find(x => x.code === c);
    let v = 0, i = 0;
    const pts = [];
    for (const d of dates) {
      while (r && i < r.seq.length && r.seq[i].date <= d) { v += r.seq[i].r === 'W' ? 1 : r.seq[i].r === 'L' ? -1 : 0; i++; }
      pts.push(v);
    }
    return { c, pts };
  });
  const W = 1000, H = 300, P = { l: 40, r: 28, t: 12, b: 26 };
  const all = series.flatMap(s => s.pts);
  const lo = Math.min(0, ...all), hi = Math.max(0, ...all);
  const x = i => P.l + (i / (dates.length - 1)) * (W - P.l - P.r);
  const y = v => P.t + (hi - v) / ((hi - lo) || 1) * (H - P.t - P.b);
  const step = Math.max(5, Math.ceil((hi - lo) / 6 / 5) * 5);
  let grid = '';
  for (let v = Math.ceil(lo / step) * step; v <= hi; v += step) {
    grid += `<line x1="${P.l}" x2="${W - P.r}" y1="${y(v)}" y2="${y(v)}" stroke="var(--line)" ${v === 0 ? '' : 'stroke-dasharray="2 4"'}/>
      <text x="${P.l - 6}" y="${y(v) + 4}" text-anchor="end" font-size="11" fill="var(--muted)">${v > 0 ? '+' : ''}${v}</text>`;
  }
  const months = [];
  dates.forEach((d, i) => { if (i === 0 || d.slice(5, 7) !== dates[i - 1].slice(5, 7)) months.push([i, +d.slice(5, 7)]); });
  grid += months.map(([i, m]) => `<text x="${x(i)}" y="${H - 6}" font-size="11" fill="var(--muted)">${m}月</text>`).join('');
  const lines = series.map((s, k) => `<path d="${s.pts.map((v, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join('')}"
    fill="none" stroke="${SERIES[k]}" stroke-width="2" stroke-linejoin="round" data-c="${s.c}"/>`).join('');
  const legend = series.map((s, k) => `<span class="lg"><i style="background:${SERIES[k]}"></i>${esc(team(s.c).s)}</span>`).join('');
  el.innerHTML = `<div class="chart-legend">${legend}</div>
    <div class="chart-box"><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="貯金走勢">${grid}${lines}
    <line class="xh" y1="${P.t}" y2="${H - P.b}" stroke="var(--muted)" stroke-width="1" visibility="hidden"/></svg>
    <div class="tip" hidden></div></div>`;
  const svg = el.querySelector('svg'), tip = el.querySelector('.tip'), xh = el.querySelector('.xh');
  svg.addEventListener('pointermove', e => {
    const rc = svg.getBoundingClientRect();
    const fx = (e.clientX - rc.left) / rc.width * W;
    const i = Math.max(0, Math.min(dates.length - 1, Math.round((fx - P.l) / (W - P.l - P.r) * (dates.length - 1))));
    xh.setAttribute('x1', x(i)); xh.setAttribute('x2', x(i)); xh.setAttribute('visibility', 'visible');
    const sorted = series.map((s, k) => ({ ...s, k, v: s.pts[i] })).sort((a, b) => b.v - a.v);
    tip.hidden = false;
    tip.innerHTML = `<b>${dates[i]}</b>` + sorted.map(s =>
      `<div><i style="background:${SERIES[s.k]}"></i>${esc(team(s.c).s)}<span>${s.v > 0 ? '+' : ''}${s.v}</span></div>`).join('');
    const left = (x(i) / W) * rc.width;
    tip.style.left = `${left > rc.width / 2 ? left - tip.offsetWidth - 12 : left + 12}px`;
  });
  svg.addEventListener('pointerleave', () => { tip.hidden = true; xh.setAttribute('visibility', 'hidden'); });
}

/* ------------------------------------------------------------ 季後賽 */
function renderPostseason() {
  const post = state.sched.games.filter(g => STAGE_ORDER.includes(g.stage));
  if (!post.length) {
    $('#app').innerHTML = '<p class="empty">本年度尚無季後賽賽程</p>';
    return;
  }
  const groups = new Map();
  for (const g of post) {
    const lg = g.stage === 'js' ? 'JS' : (TEAMS[g.home]?.lg || '');
    const key = `${g.stage}|${lg}|${[g.away, g.home].sort().join('-')}`;
    if (!groups.has(key)) groups.set(key, { stage: g.stage, name: g.stageName, lg, games: [] });
    groups.get(key).games.push(g);
  }
  const sorted = [...groups.values()].sort((a, b) =>
    STAGE_ORDER.indexOf(a.stage) - STAGE_ORDER.indexOf(b.stage) || a.lg.localeCompare(b.lg));
  let html = '<h2>季後賽</h2><p class="status" style="color:var(--muted)">高潮系列賽（CS）第一階段 3 戰 2 勝；最終階段 6 戰 4 勝（聯盟冠軍先取 1 勝優勢，不計入下方比賽數）。日本一系列賽 7 戰 4 勝。</p>';
  let cur = '';
  for (const s of sorted) {
    const title = s.stage === 'js' ? s.name : `${LEAGUES[s.lg] || ''} ${s.name}`;
    if (title !== cur) { html += `<h3>${esc(title)}</h3>`; cur = title; }
    const teams = [...new Set(s.games.flatMap(g => [g.home, g.away]))];
    const wins = Object.fromEntries(teams.map(t => [t, 0]));
    let ties = 0;
    for (const g of s.games) {
      if (g.status !== 'final') continue;
      if (g.awayScore === g.homeScore) ties++;
      else wins[g.awayScore > g.homeScore ? g.away : g.home]++;
    }
    html += `<div class="series"><div class="series-head">
      <div>${teams.map(t => `${dot(t)} <b>${esc(team(t).zh)}</b>`).join(' vs ')}</div>
      <div class="series-score">${teams.map(t => `${esc(team(t).s)} ${wins[t]}`).join(' – ')}${ties ? `（和 ${ties}）` : ''}</div></div>
      <div class="series-games">${s.games.map((g, i) => `<span class="sg" ${g.hasBox ? `data-game="${esc(g.id)}"` : ''}>
        第${i + 1}戰 ${g.date.slice(5).replace('-', '/')} ${esc(team(g.away).s)}
        <b>${g.status === 'final' ? `${g.awayScore}-${g.homeScore}` : g.status === 'postponed' ? '延賽' : esc(g.time || 'vs')}</b>
        ${esc(team(g.home).s)}</span>`).join('')}</div></div>`;
  }
  $('#app').innerHTML = html;
  bindGameClicks();
}

/* ------------------------------------------------------------ 個人成績 */
async function renderPlayers() {
  const p = await loadPlayers();
  if (!p.batting?.length && !p.pitching?.length) { $('#app').innerHTML = '<p class="empty">本年度尚無個人成績資料</p>'; return; }
  const mode = state.pMode || 'batting';
  const gp = Math.max(1, ...computeTeamGames());
  const batCols = [['name', '選手', 'l'], ['team', '球隊', 'l'], ['G', '場'], ['AB', '打數'], ['R', '得分'], ['H', '安打'], ['HR', '全壘打'], ['RBI', '打點'], ['BB', '四壞'], ['SO', '三振'], ['SB', '盜壘'], ['AVG', '打擊率']];
  const pitCols = [['name', '選手', 'l'], ['team', '球隊', 'l'], ['G', '出賽'], ['W', '勝'], ['L', '敗'], ['SV', '救援'], ['IP', '局數'], ['H', '被安打'], ['BB', '四壞'], ['SO', '三振'], ['R', '失分'], ['ER', '責失'], ['NP', '用球數'], ['ERA', '防禦率']];
  const cols = mode === 'batting' ? batCols : pitCols;
  // 有資料的欄位才顯示（不同年度頁面格式可能缺某些欄）
  const rows0 = p[mode] || [];
  const shown = cols.filter(([k]) => ['name', 'team', 'G', 'AVG', 'ERA', 'IP'].includes(k) || rows0.some(r => r[k]));
  state.pSort ??= {};
  const sort = state.pSort[mode] || (mode === 'batting' ? { k: 'AVG', d: -1 } : { k: 'ERA', d: 1 });
  const qual = state.pQual ?? true;
  let rows = rows0.filter(r => (!state.filterTeam || r.team === state.filterTeam));
  // 規定打席/投球局數：每隊比賽數 × 3.1（打席以打數近似）/ × 1.0
  if (qual && (sort.k === 'AVG' || sort.k === 'ERA')) {
    rows = rows.filter(r => mode === 'batting' ? r.AB >= gp * 2.7 : r.OUTS >= gp * 3);
  }
  const val = (r, k) => (k === 'IP' ? r.OUTS : r[k]);
  rows = [...rows].sort((a, b) => {
    const va = val(a, sort.k), vb = val(b, sort.k);
    if (va == null) return 1; if (vb == null) return -1;
    return typeof va === 'string' ? va.localeCompare(vb) * sort.d : (va - vb) * sort.d;
  }).slice(0, 200);
  const fmt = (r, k) => k === 'name' ? playerLink(r.key || playerKey(r.id, r.team, r.name), r.name)
    : k === 'team' ? `${dot(r.team)} ${teamLink(r.team, team(r.team).s)}`
    : k === 'AVG' ? (r.AVG == null ? '-' : r.AVG.toFixed(3).replace(/^0/, ''))
      : k === 'ERA' ? (r.ERA == null ? '-' : r.ERA.toFixed(2)) : esc(r[k]);
  $('#app').innerHTML = `<h2>${state.year} 個人成績（例行賽）</h2>
    <div class="toolbar">
      <button class="chip ${mode === 'batting' ? 'on' : ''}" data-mode="batting">打擊</button>
      <button class="chip ${mode === 'pitching' ? 'on' : ''}" data-mode="pitching">投手</button>
      <label class="chip"><input type="checkbox" id="qual" ${qual ? 'checked' : ''}> 只看達規定${mode === 'batting' ? '打席' : '投球局數'}者（排序打擊率/防禦率時）</label>
    </div>
    <div class="toolbar">${teamChips(state.filterTeam)}</div>
    <div class="table-wrap"><table class="data"><thead><tr><th>#</th>${shown.map(([k, n, c]) =>
      `<th class="sortable ${c || ''} ${sort.k === k ? 'sorted' : ''}" data-k="${k}">${n}${sort.k === k ? (sort.d > 0 ? ' ▲' : ' ▼') : ''}</th>`).join('')}</tr></thead>
    <tbody>${rows.map((r, i) => `<tr><td class="rank">${i + 1}</td>${shown.map(([k, , c]) => `<td class="${c || ''}">${fmt(r, k)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>
    <p style="color:var(--muted);font-size:12px">由每場比賽的成績表累計而成，可能與官方年度成績有些微差異。</p>`;
  $('#app').querySelectorAll('[data-mode]').forEach(b => b.onclick = () => { state.pMode = b.dataset.mode; renderPlayers(); });
  $('#app').querySelectorAll('[data-team]').forEach(b => b.onclick = () => { state.filterTeam = b.dataset.team; renderPlayers(); });
  $('#qual').onchange = e => { state.pQual = e.target.checked; renderPlayers(); };
  $('#app').querySelectorAll('th[data-k]').forEach(th => th.onclick = () => {
    const k = th.dataset.k;
    const lowBetter = ['name', 'team'].includes(k) || (mode === 'pitching' && ['ERA', 'L', 'H', 'BB', 'ER', 'R'].includes(k));
    state.pSort[mode] = sort.k === k ? { k, d: -sort.d } : { k, d: lowBetter ? 1 : -1 };
    renderPlayers();
  });
}

function computeTeamGames() {
  const n = {};
  for (const g of state.sched.games) {
    if (g.stage !== 'regular' || g.status !== 'final') continue;
    n[g.away] = (n[g.away] || 0) + 1; n[g.home] = (n[g.home] || 0) + 1;
  }
  return Object.values(n);
}

/* ------------------------------------------------------------ 維基百科（照片、故事） */
// 瀏覽器端直接呼叫維基百科 REST API（支援 CORS）；中文優先（台灣正體），找不到再用日文
async function wiki(titles) {
  for (const [lang, t] of titles) {
    if (!t) continue;
    const ck = `wiki:${lang}:${t}`;
    try {
      const c = sessionStorage.getItem(ck);
      if (c) { const v = JSON.parse(c); if (v) return v; continue; }
    } catch { /* 無法使用 sessionStorage 時略過快取 */ }
    let v = null;
    try {
      const r = await fetch(`https://${lang}.wikipedia.org/api/rest_v1/page/summary/${encodeURIComponent(t)}`,
        { headers: lang === 'zh' ? { 'Accept-Language': 'zh-tw' } : {} });
      if (r.ok) {
        const j = await r.json();
        if (j.type !== 'disambiguation' && j.extract) {
          v = { title: j.title, text: j.extract, img: j.thumbnail?.source, url: j.content_urls?.desktop?.page, lang };
        }
      }
    } catch { /* 網路錯誤 */ }
    try { sessionStorage.setItem(ck, JSON.stringify(v)); } catch { /* ignore */ }
    if (v) return v;
  }
  return null;
}

function storyCard(el, w, fallbackText) {
  if (!el) return;
  if (!w) { el.innerHTML = fallbackText ? `<p class="muted">${fallbackText}</p>` : ''; return; }
  el.innerHTML = `<div class="story">
    ${w.img ? `<img src="${esc(w.img)}" alt="${esc(w.title)}" loading="lazy" referrerpolicy="no-referrer">` : ''}
    <div><h3>${esc(w.title)}</h3><p>${esc(w.text)}</p>
    <a href="${esc(w.url)}" target="_blank" rel="noopener">在維基百科閱讀完整介紹 →</a>
    <div class="muted small">內容來自${w.lang === 'zh' ? '中文' : '日文'}維基百科（CC BY-SA 4.0）</div></div></div>`;
}

async function loadPlayers() {
  if (!state.players) {
    try { state.players = await getJSON(`data/${state.year}/players.json`); } catch { state.players = { batting: [], pitching: [] }; }
  }
  return state.players;
}

function avatar(p, size = 64) {
  const initial = esc((p.fullName || p.name || '?').trim().slice(0, 1));
  return `<span class="avatar" style="width:${size}px;height:${size}px;--tc:${team(p.team).color}">
    <span>${initial}</span>${p.photo ? `<img src="${esc(p.photo)}" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="this.remove()">` : ''}</span>`;
}

/* ------------------------------------------------------------ 球隊 */
async function renderTeams() {
  const code = TEAMS[state.extra]?.lg ? state.extra : (state.filterTeam || 'G');
  const T = TEAMS[code];
  const games = state.sched.games.filter(g => g.away === code || g.home === code);
  const st = computeStandings(state.sched.games);
  const r = (st[T.lg] || []).find(x => x.code === code);
  const vs = {};
  for (const g of games) {
    if (g.stage !== 'regular' || g.status !== 'final') continue;
    const opp = g.away === code ? g.home : g.away;
    const my = g.away === code ? g.awayScore : g.homeScore, op = g.away === code ? g.homeScore : g.awayScore;
    const v = vs[opp] ??= { W: 0, L: 0, T: 0 };
    v[my > op ? 'W' : my < op ? 'L' : 'T']++;
  }
  $('#app').innerHTML = `<div class="team-strip">${Object.keys(TEAMS).filter(c => TEAMS[c].lg).map(c =>
      `<a class="${c === code ? 'on' : ''}" href="#/${state.year}/teams/${c}" title="${esc(team(c).zh)}">${logo(c, 40)}<span>${team(c).s}</span></a>`).join('')}</div>
    <section class="team-banner" style="--tc:${T.color}">
      ${logo(code, 120)}
      <div>
        <div class="muted">${LEAGUES[T.lg]} · ${esc(T.ja)}</div>
        <h1>${esc(T.zh)}</h1>
        <div class="facts left">
          <span>創立 <b>${T.founded}</b></span><span>所在地 <b>${esc(T.city)}</b></span><span>主場 <b>${esc(T.home)}</b></span>
        </div>
        <div class="links">
          <a href="${T.site}" target="_blank" rel="noopener">球團官網</a>
          <a href="https://npb.jp/bis/teams/rst_${code.toLowerCase()}.html" target="_blank" rel="noopener">NPB 官方球員名單</a>
        </div>
      </div>
    </section>
    ${r ? `<div class="hero">
      <div class="hero-card"><div class="label">${state.year} 排名</div><div class="big">第 ${r.rank} 名</div><div class="status">勝差 ${r.GB}</div></div>
      <div class="hero-card"><div class="label">戰績</div><div class="big">${r.W}勝 ${r.L}敗 ${r.T}和</div><div class="status">勝率 ${pct(r.W, r.L)} · ${r.streak}</div></div>
      <div class="hero-card"><div class="label">得失分</div><div class="big">${r.RS} / ${r.RA}</div><div class="status">剩餘 ${r.left} 場</div></div>
    </div>` : ''}
    <h2>球隊故事</h2><div id="team-story" data-code="${code}"><p class="muted">載入維基百科介紹中…</p></div>
    <h2>${state.year} 出賽球員</h2><div id="roster"><p class="muted">載入中…</p></div>
    <h2>對戰成績</h2>
    <div class="table-wrap"><table class="data"><thead><tr><th class="l">對手</th><th>勝</th><th>敗</th><th>和</th><th>勝率</th></tr></thead>
    <tbody>${Object.entries(vs).sort((a, b) => (TEAMS[a[0]].lg === T.lg ? 0 : 1) - (TEAMS[b[0]].lg === T.lg ? 0 : 1)).map(([o, v]) =>
      `<tr><td class="l">${dot(o)} ${teamLink(o)}</td><td>${v.W}</td><td>${v.L}</td><td>${v.T}</td><td>${pct(v.W, v.L)}</td></tr>`).join('')}</tbody></table></div>
    <h2>全部賽程（${games.length} 場）</h2>
    <div class="games">${games.map(g => gameCard(g, { date: true })).join('')}</div>`;
  bindGameClicks();

  const yearAtRender = state.year;
  loadPlayers().then(p => {
    if (state.year !== yearAtRender || state.tab !== 'teams') return;
    const seen = new Map();
    for (const kind of ['pitching', 'batting']) {
      for (const x of p[kind] || []) {
        if (x.team !== code) continue;
        const k = x.key || playerKey(x.id, x.team, x.name);
        const cur = seen.get(k) || { ...x, key: k, roles: [] };
        cur.roles.push(kind === 'pitching' ? `${x.G} 場投球` : `${x.G} 場打擊`);
        seen.set(k, cur);
      }
    }
    const list = [...seen.values()].sort((a, b) => (+a.number || 999) - (+b.number || 999) || a.name.localeCompare(b.name));
    $('#roster').innerHTML = list.length ? `<div class="roster">${list.map(x => `<a class="pcard" href="#/${state.year}/player/${encodeURIComponent(x.key)}">
        ${avatar(x, 72)}<div><div class="pname">${x.number ? `<span class="num">#${esc(x.number)}</span>` : ''}${esc(x.fullName || x.name)}</div>
        <div class="muted small">${esc(x.position || '')} ${x.roles.join(' · ')}</div></div></a>`).join('')}</div>`
      : '<p class="muted">本年度尚無球員出賽資料</p>';
  });
  wiki([['zh', T.wiki[0]], ['ja', T.wiki[1]]]).then(w => {
    const el = $('#team-story');
    if (el?.dataset.code === code) storyCard(el, w, '目前無法載入維基百科介紹。');
  });
}

/* ------------------------------------------------------------ 選手 */
async function renderPlayer() {
  const key = state.extra;
  $('#app').innerHTML = '<p class="empty">載入中…</p>';
  const all = await loadPlayers();
  const bat = (all.batting || []).find(x => (x.key || playerKey(x.id, x.team, x.name)) === key);
  const pit = (all.pitching || []).find(x => (x.key || playerKey(x.id, x.team, x.name)) === key);
  const base = pit || bat || {};
  let log = null, prof = null;
  try { log = await getJSON(`data/${state.year}/players/${encodeURIComponent(key)}.json`); } catch { /* 無逐場紀錄 */ }
  const pid = base.id || log?.id || (/^\d+$/.test(key) ? key : null);
  if (pid) { try { prof = await getJSON(`data/players/${pid}.json`); } catch { /* 無個人資料 */ } }
  const p = { ...base, ...(log ? { name: log.name, team: log.team } : {}), ...(prof || {}) };
  if (!p.name && !p.fullName) {
    $('#app').innerHTML = '<p class="empty">找不到這位選手的資料</p>';
    return;
  }
  p.team ||= base.team;
  const displayName = p.fullName || p.name;
  const fields = Object.entries(prof?.fields || {});
  const gameById = Object.fromEntries(state.sched.games.map(g => [g.id, g]));
  const res = (gid, ha) => {
    const g = gameById[gid];
    if (!g || g.status !== 'final') return '';
    const my = ha === 'A' ? g.awayScore : g.homeScore, op = ha === 'A' ? g.homeScore : g.awayScore;
    return `<span class="res ${my > op ? 'W' : my < op ? 'L' : 'T'}">${my > op ? '勝' : my < op ? '敗' : '和'} ${my}-${op}</span>`;
  };
  const ip = o => `${Math.floor(o / 3)}${o % 3 ? ` ${o % 3}/3` : ''}`;
  const logTable = (rows, cols, labels, fmt) => rows?.length ? `<div class="table-wrap"><table class="data">
      <thead><tr><th class="l">日期</th><th class="l">對手</th><th class="l">結果</th>${labels.map(l => `<th>${l}</th>`).join('')}</tr></thead>
      <tbody>${rows.map(r => `<tr class="${gameById[r[0]]?.hasBox ? 'clickable' : ''}" data-game="${esc(r[0])}">
        <td class="l">${r[1].slice(5).replace('-', '/')}</td><td class="l">${r[3] === 'A' ? '@' : 'vs'} ${dot(r[2])} ${esc(team(r[2]).s)}</td>
        <td class="l">${res(r[0], r[3])}</td>${cols.map((c, i) => `<td>${fmt(c, r[4 + i])}</td>`).join('')}</tr>`).join('')}</tbody></table></div>` : '';

  $('#app').innerHTML = `
    <section class="player-hero" style="--tc:${team(p.team).color}">
      <div class="player-photo">${avatar(p, 160)}</div>
      <div>
        <div class="muted">${logo(p.team, 22)} ${teamLink(p.team)}</div>
        <h1>${p.number ? `<span class="num">#${esc(p.number)}</span> ` : ''}${esc(displayName)}</h1>
        ${p.kana ? `<div class="muted">${esc(p.kana)}</div>` : ''}
        ${p.position ? `<div class="tag">${esc(p.position)}</div>` : ''}
        ${fields.length ? `<dl class="profile">${fields.map(([k, v]) => `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join('')}</dl>` : ''}
        <div class="links">
          ${pid ? `<a href="https://npb.jp/bis/players/${pid}.html" target="_blank" rel="noopener">NPB 官方個人頁</a>` : ''}
          <a href="https://zh.wikipedia.org/w/index.php?search=${encodeURIComponent(displayName.replace(/\s+/g, ''))}" target="_blank" rel="noopener">搜尋維基百科</a>
        </div>
      </div>
    </section>
    ${bat ? `<h2>${state.year} 打擊成績</h2><div class="stat-row">
      ${[['場', bat.G], ['打數', bat.AB], ['安打', bat.H], ['全壘打', bat.HR], ['打點', bat.RBI], ['盜壘', bat.SB], ['打擊率', bat.AVG == null ? '-' : bat.AVG.toFixed(3).replace(/^0/, '')]]
        .map(([l, v]) => `<div class="stat"><div class="label">${l}</div><div class="big">${v}</div></div>`).join('')}</div>` : ''}
    ${pit ? `<h2>${state.year} 投球成績</h2><div class="stat-row">
      ${[['出賽', pit.G], ['勝', pit.W], ['敗', pit.L], ['救援', pit.SV], ['局數', pit.IP], ['三振', pit.SO], ['防禦率', pit.ERA == null ? '-' : pit.ERA.toFixed(2)]]
        .map(([l, v]) => `<div class="stat"><div class="label">${l}</div><div class="big">${v}</div></div>`).join('')}</div>` : ''}
    <h2>選手故事</h2><div id="player-story"><p class="muted">載入維基百科介紹中…</p></div>
    ${log?.pit?.length ? `<h2>逐場投球紀錄</h2>${logTable(log.pit, ['OUTS', 'H', 'R', 'ER', 'BB', 'SO', 'NP', 'DEC'],
      ['局數', '被安打', '失分', '責失', '四壞', '三振', '用球數', '勝敗'], (c, v) => c === 'OUTS' ? ip(v) : c === 'DEC' ? ({ W: '勝', L: '敗', SV: '救援' }[v] || '') : v)}` : ''}
    ${log?.bat?.length ? `<h2>逐場打擊紀錄</h2>${logTable(log.bat, ['AB', 'R', 'H', 'RBI', 'HR', 'BB', 'SO', 'SB'],
      ['打數', '得分', '安打', '打點', '全壘打', '四壞', '三振', '盜壘'], (c, v) => v)}` : ''}`;
  $('#app').querySelectorAll('tr.clickable[data-game]').forEach(el =>
    el.addEventListener('click', () => { location.hash = `#/${state.year}/game/${el.dataset.game}`; }));
  // 只有姓氏時（沒有全名）維基百科多半會對到消歧義頁，因此只用全名查詢
  const wikiName = (p.fullName || '').replace(/\s+/g, '');
  const w = wikiName ? await wiki([['zh', wikiName], ['ja', wikiName], ['zh', `${wikiName} (棒球選手)`], ['ja', `${wikiName} (野球)`]]) : null;
  if (state.tab === 'player' && state.extra === key) {
    storyCard($('#player-story'), w, wikiName ? '維基百科上找不到這位選手的條目。' : '尚未取得選手全名，無法查詢維基百科。');
    if (w?.img && !p.photo) {
      const ph = $('.player-photo .avatar');
      ph?.insertAdjacentHTML('beforeend', `<img src="${esc(w.img)}" alt="" referrerpolicy="no-referrer" onerror="this.remove()">`);
    }
  }
}

/* ------------------------------------------------------------ 單場詳細 */
async function openGame(id) {
  const g = state.sched.games.find(x => x.id === id);
  const dlg = $('#game-dialog');
  $('#dlg-title').textContent = g ? `${g.date}  ${team(g.away).zh} vs ${team(g.home).zh}` : id;
  $('#dlg-body').innerHTML = '<p class="empty">載入中…</p>';
  if (!dlg.open) dlg.showModal();
  let box;
  try {
    box = state.boxCache[id] ??= await getJSON(`data/${state.year}/games/${id}.json`);
  } catch {
    $('#dlg-body').innerHTML = '<p class="empty">此場比賽尚無詳細數據</p>';
    return;
  }
  const info = box.info || {};
  const aw = box.away, hm = box.home;
  const tbl = (t, title, code, pitching) => {
    if (!t || !t.headers) return '';
    const n = t.headers.length;
    const names = pitching ? ['投手', '投手名', '選手', '選手名', 'Player', 'Name', 'PITCHERS', 'Pitcher']
      : ['選手', '選手名', '打者', 'Player', 'Name', 'BATTERS', 'Batter'];
    const ni = t.headers.findIndex(h => names.includes(h));
    const cell = (r, i, ri) => {
      const v = r[i] ?? '';
      if (i !== ni || !v || ['計', '合計', 'チーム計', 'Totals', 'Total'].includes(v)) return esc(v);
      const nm = pitching ? v.replace(/^(?:[○●◯△]\s*|[勝敗SHＳＨ]\s+)|\s*[(（].*$/g, '').trim() : v.replace(/^[()（）]+/, '');
      return playerLink(playerKey(t.pids?.[ri], code, nm), v);
    };
    return `<h3>${logo(code, 20)} ${title}</h3><div class="table-wrap"><table class="data"><thead><tr>${t.headers.map((h, i) =>
      `<th class="${i < 3 ? 'l' : ''}">${esc(h)}</th>`).join('')}</tr></thead>
      <tbody>${t.rows.map((r, ri) => `<tr>${Array.from({ length: Math.max(n, r.length) }, (_, i) =>
        `<td class="${i < 3 ? 'l' : ''}">${cell(r, i, ri)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
  };
  const ls = box.linescore;
  const facts = [
    (info.venue || g?.venue) && `球場 <b>${esc(info.venue || g.venue)}</b>`,
    (info.start || g?.time) && `開始 <b>${esc(info.start || g.time)}</b>`,
    info.duration && `比賽時間 <b>${esc(info.duration)}</b>`,
    info.attendance && `觀眾 <b>${info.attendance.toLocaleString()}</b> 人`,
    info.winP && `勝投 <b>${esc(info.winP)}</b>`, info.loseP && `敗投 <b>${esc(info.loseP)}</b>`,
    info.saveP && `救援 <b>${esc(info.saveP)}</b>`,
  ].filter(Boolean).map(s => `<span>${s}</span>`).join('');
  $('#dlg-body').innerHTML = `
    <div class="scoreboard">
      <div class="sb-team">${logo(aw, 64)}<div>${teamLink(aw)}</div><small>客隊（先攻）</small></div>
      <div class="sb-score">${box.awayScore ?? '-'} : ${box.homeScore ?? '-'}</div>
      <div class="sb-team">${logo(hm, 64)}<div>${teamLink(hm)}</div><small>主隊（後攻）</small></div>
    </div>
    <div class="facts">${facts}</div>
    ${g && g.stage !== 'regular' ? `<p style="text-align:center"><span class="tag post">${esc(g.stageName)}</span></p>` : ''}
    ${ls ? `<div class="table-wrap"><table class="data"><thead><tr>${ls.headers.map((h, i) => `<th class="${i ? '' : 'l'}">${esc(h)}</th>`).join('')}</tr></thead>
      <tbody>${ls.rows.map(r => `<tr>${r.map((c, i) => `<td class="${i ? '' : 'l'}">${esc(c)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>` : ''}
    ${info.homeRuns ? `<p><b>全壘打：</b>${esc(info.homeRuns)}</p>` : ''}
    <div class="grid2"><div>${tbl(box.teams?.[aw]?.batting, `${team(aw).s} 打擊`, aw)}</div><div>${tbl(box.teams?.[hm]?.batting, `${team(hm).s} 打擊`, hm)}</div></div>
    <div class="grid2"><div>${tbl(box.teams?.[aw]?.pitching, `${team(aw).s} 投手`, aw, true)}</div><div>${tbl(box.teams?.[hm]?.pitching, `${team(hm).s} 投手`, hm, true)}</div></div>
    ${info.umpires ? `<p style="color:var(--muted)">裁判：${esc(info.umpires)}</p>` : ''}
    ${box.source ? `<p style="color:var(--muted);font-size:12px">來源：<a href="${esc(box.source)}" target="_blank" rel="noopener">${esc(box.source)}</a></p>` : ''}`;
}

$('#dlg-body').addEventListener('click', e => {
  if (e.target.closest('a.plink, a.tlink')) $('#game-dialog').close();
});

function closeGame() {
  $('#game-dialog').close();
}
$('#game-dialog').addEventListener('close', () => {
  if (parseHash().tab === 'game') history.replaceState(null, '', `#/${state.year}/${state.tab}${state.extra && state.tab !== 'game' ? '/' + encodeURIComponent(state.extra) : ''}`);
});

/* ------------------------------------------------------------ 啟動 */
(async function init() {
  try {
    state.seasons = (await getJSON('data/seasons.json')).seasons || [];
  } catch { state.seasons = []; }
  const sel = $('#season');
  sel.innerHTML = state.seasons.map(s => `<option value="${s.year}">${s.year}${s.complete ? '' : ' ●'}</option>`).join('');
  sel.onchange = () => go(state.tab, +sel.value);
  window.addEventListener('hashchange', route);
  route().catch(e => { $('#app').innerHTML = `<p class="empty">載入失敗：${esc(e.message)}</p>`; });
})();
