/* NPB 日本職棒賽程戰績 — 純前端，讀取 data/ 底下由爬蟲產生的靜態 JSON */
'use strict';

const TEAMS = {
  G: { lg: 'C', zh: '讀賣巨人', s: '巨人', color: '#F97709' },
  T: { lg: 'C', zh: '阪神虎', s: '阪神', color: '#FFE201' },
  DB: { lg: 'C', zh: '橫濱DeNA海灣之星', s: 'DeNA', color: '#0055A5' },
  C: { lg: 'C', zh: '廣島東洋鯉魚', s: '廣島', color: '#E50012' },
  S: { lg: 'C', zh: '東京養樂多燕子', s: '養樂多', color: '#00AB5C' },
  D: { lg: 'C', zh: '中日龍', s: '中日', color: '#002569' },
  H: { lg: 'P', zh: '福岡軟銀鷹', s: '軟銀', color: '#F5C700' },
  F: { lg: 'P', zh: '北海道日本火腿鬥士', s: '火腿', color: '#01609A' },
  M: { lg: 'P', zh: '千葉羅德海洋', s: '羅德', color: '#221815' },
  E: { lg: 'P', zh: '東北樂天金鷲', s: '樂天', color: '#85010F' },
  B: { lg: 'P', zh: '歐力士猛牛', s: '歐力士', color: '#000019' },
  L: { lg: 'P', zh: '埼玉西武獅', s: '西武', color: '#1F366A' },
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
const dot = c => `<span class="dot" style="background:${team(c).color}"></span>`;
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
  return { y: +y || null, tab: tab || 'schedule', extra };
}
function go(tab, year = state.year) { location.hash = `#/${year}/${tab}`; }

async function route() {
  const h = parseHash();
  const year = h.y && state.seasons.some(s => s.year === h.y) ? h.y : state.seasons[0]?.year;
  if (!year) return renderNoData();
  if (year !== state.year) await loadSeason(year);
  state.tab = h.tab === 'game' ? state.tab : h.tab;
  $('#season').value = year;
  document.querySelectorAll('#tabs a').forEach(a => {
    a.classList.toggle('active', a.dataset.tab === state.tab);
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
    players: renderPlayers, teams: renderTeams }[state.tab] || renderSchedule;
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
    <div class="team away ${cls(aw, hw)}">${dot(g.away)}<span class="nm">${esc(team(g.away).s)}</span></div>
    <div class="mid">${mid}</div>
    <div class="team home ${cls(hw, aw)}"><span class="nm">${esc(team(g.home).s)}</span>${dot(g.home)}</div>
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
  if (!state.players) {
    try { state.players = await getJSON(`data/${state.year}/players.json`); }
    catch { $('#app').innerHTML = '<p class="empty">本年度尚無個人成績資料</p>'; return; }
  }
  const p = state.players;
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
  const fmt = (r, k) => k === 'team' ? `${dot(r.team)} ${esc(team(r.team).s)}`
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

/* ------------------------------------------------------------ 球隊 */
function renderTeams() {
  const code = parseHash().extra || state.filterTeam || 'G';
  const games = state.sched.games.filter(g => g.away === code || g.home === code);
  const st = computeStandings(state.sched.games);
  const r = (st[TEAMS[code]?.lg] || []).find(x => x.code === code);
  const vs = {};
  for (const g of games) {
    if (g.stage !== 'regular' || g.status !== 'final') continue;
    const opp = g.away === code ? g.home : g.away;
    const my = g.away === code ? g.awayScore : g.homeScore, op = g.away === code ? g.homeScore : g.awayScore;
    const v = vs[opp] ??= { W: 0, L: 0, T: 0 };
    v[my > op ? 'W' : my < op ? 'L' : 'T']++;
  }
  $('#app').innerHTML = `<div class="toolbar">${Object.keys(TEAMS).filter(c => TEAMS[c].lg).map(c =>
      `<a class="chip ${c === code ? 'on' : ''}" href="#/${state.year}/teams/${c}" style="text-decoration:none">${dot(c)} ${team(c).s}</a>`).join('')}</div>
    <h2>${dot(code)} ${esc(team(code).zh)} <span class="tag ${(TEAMS[code]?.lg || '').toLowerCase()}">${LEAGUES[TEAMS[code]?.lg] || ''}</span></h2>
    ${r ? `<div class="hero">
      <div class="hero-card"><div class="label">排名</div><div class="big">第 ${r.rank} 名</div><div class="status">勝差 ${r.GB}</div></div>
      <div class="hero-card"><div class="label">戰績</div><div class="big">${r.W}勝 ${r.L}敗 ${r.T}和</div><div class="status">勝率 ${pct(r.W, r.L)} · ${r.streak}</div></div>
      <div class="hero-card"><div class="label">得失分</div><div class="big">${r.RS} / ${r.RA}</div><div class="status">剩餘 ${r.left} 場</div></div>
    </div>` : ''}
    <h3>對戰成績</h3>
    <div class="table-wrap"><table class="data"><thead><tr><th class="l">對手</th><th>勝</th><th>敗</th><th>和</th><th>勝率</th></tr></thead>
    <tbody>${Object.entries(vs).sort((a, b) => (TEAMS[a[0]].lg === TEAMS[code].lg ? 0 : 1) - (TEAMS[b[0]].lg === TEAMS[code].lg ? 0 : 1)).map(([o, v]) =>
      `<tr><td class="l">${dot(o)} ${esc(team(o).zh)}</td><td>${v.W}</td><td>${v.L}</td><td>${v.T}</td><td>${pct(v.W, v.L)}</td></tr>`).join('')}</tbody></table></div>
    <h3>全部賽程（${games.length} 場）</h3>
    <div class="games">${games.map(g => gameCard(g, { date: true })).join('')}</div>`;
  bindGameClicks();
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
  const tbl = (t, title) => {
    if (!t || !t.headers) return '';
    const n = t.headers.length;
    return `<h3>${title}</h3><div class="table-wrap"><table class="data"><thead><tr>${t.headers.map((h, i) =>
      `<th class="${i < 3 ? 'l' : ''}">${esc(h)}</th>`).join('')}</tr></thead>
      <tbody>${t.rows.map(r => `<tr>${Array.from({ length: Math.max(n, r.length) }, (_, i) =>
        `<td class="${i < 3 ? 'l' : ''}">${esc(r[i] ?? '')}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
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
      <div class="sb-team">${dot(aw)} ${esc(team(aw).zh)}<small>客隊（先攻）</small></div>
      <div class="sb-score">${box.awayScore ?? '-'} : ${box.homeScore ?? '-'}</div>
      <div class="sb-team">${esc(team(hm).zh)} ${dot(hm)}<small>主隊（後攻）</small></div>
    </div>
    <div class="facts">${facts}</div>
    ${g && g.stage !== 'regular' ? `<p style="text-align:center"><span class="tag post">${esc(g.stageName)}</span></p>` : ''}
    ${ls ? `<div class="table-wrap"><table class="data"><thead><tr>${ls.headers.map((h, i) => `<th class="${i ? '' : 'l'}">${esc(h)}</th>`).join('')}</tr></thead>
      <tbody>${ls.rows.map(r => `<tr>${r.map((c, i) => `<td class="${i ? '' : 'l'}">${esc(c)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>` : ''}
    ${info.homeRuns ? `<p><b>全壘打：</b>${esc(info.homeRuns)}</p>` : ''}
    <div class="grid2"><div>${tbl(box.teams?.[aw]?.batting, `${team(aw).s} 打擊`)}</div><div>${tbl(box.teams?.[hm]?.batting, `${team(hm).s} 打擊`)}</div></div>
    <div class="grid2"><div>${tbl(box.teams?.[aw]?.pitching, `${team(aw).s} 投手`)}</div><div>${tbl(box.teams?.[hm]?.pitching, `${team(hm).s} 投手`)}</div></div>
    ${info.umpires ? `<p style="color:var(--muted)">裁判：${esc(info.umpires)}</p>` : ''}
    ${box.source ? `<p style="color:var(--muted);font-size:12px">來源：<a href="${esc(box.source)}" target="_blank" rel="noopener">${esc(box.source)}</a></p>` : ''}`;
}

function closeGame() {
  $('#game-dialog').close();
}
$('#game-dialog').addEventListener('close', () => {
  if (parseHash().tab === 'game') history.replaceState(null, '', `#/${state.year}/${state.tab}`);
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
