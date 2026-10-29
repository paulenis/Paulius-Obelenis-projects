// Shopping list app. The list lives in this browser (localStorage) so it keeps working
// without a connection; changes are sent to the home computer whenever it is reachable.
'use strict';

const CHAIN_ORDER = ['lidl', 'maxima', 'iki', 'rimi', 'norfa'];
const CHAIN_LABELS = { lidl: 'Lidl', maxima: 'Maxima', iki: 'Iki', rimi: 'Rimi', norfa: 'Norfa' };
const SYNC_EVERY_MS = 8000;
const STORE_KEY = 'list-state-v1';

const $ = (id) => document.getElementById(id);

// --- small helpers ----------------------------------------------------------

function el(tag, attrs, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k === 'class') node.className = v;
    else if (k.startsWith('on')) node.addEventListener(k.slice(2), v);
    else if (v === true) node.setAttribute(k, '');
    else node.setAttribute(k, v);
  }
  for (const c of children.flat()) {
    if (c === null || c === undefined || c === false) continue;
    node.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return node;
}

const eur = (n) => (n === null || n === undefined) ? '' : (Math.round(n * 100 + 1e-9) / 100).toFixed(2).replace('.', ',') + ' €';
const num = (n) => String(Math.round(n * 100) / 100).replace('.', ',');
const shortDate = (iso) => iso ? iso.slice(5) : '';
const todayIso = () => new Date().toISOString().slice(0, 10);
const newId = () => Date.now().toString(36) + Math.random().toString(36).slice(2, 8);

function load(key, fallback) {
  try { return JSON.parse(localStorage.getItem(key)) ?? fallback; } catch (e) { return fallback; }
}
function save(key, value) {
  try { localStorage.setItem(key, typeof value === 'string' ? value : JSON.stringify(value)); } catch (e) {}
}

// --- state ------------------------------------------------------------------

const state = Object.assign({ items: {}, pending: {} }, load(STORE_KEY, {}));
let userName = (() => { try { return localStorage.getItem('user-name') || ''; } catch (e) { return ''; } })();
let lastResults = [];

function persist() { save(STORE_KEY, { items: state.items, pending: state.pending }); }

function change(item, patch) {
  const updated = Object.assign({}, item, patch, { updated_at: Date.now() });
  state.items[updated.id] = updated;
  state.pending[updated.id] = updated;
  persist();
  renderList();
  renderResults();
  scheduleSync(300);
}

// --- theme ------------------------------------------------------------------

function effectiveTheme() {
  const set = document.documentElement.dataset.theme;
  if (set) return set;
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}
$('theme-btn').addEventListener('click', () => {
  const next = effectiveTheme() === 'dark' ? 'light' : 'dark';
  document.documentElement.dataset.theme = next;
  save('theme', next);
});

// --- tabs (phone) -----------------------------------------------------------

function showTab(tab) {
  $('layout').dataset.tab = tab;
  for (const b of document.querySelectorAll('.tab')) b.setAttribute('aria-selected', String(b.dataset.tab === tab));
  if (tab === 'search') $('q').focus();
}
for (const b of document.querySelectorAll('.tab')) b.addEventListener('click', () => showTab(b.dataset.tab));
showTab('list');

// --- sync with the home computer -------------------------------------------

let syncTimer = null;
let syncing = false;

function scheduleSync(delay) {
  clearTimeout(syncTimer);
  syncTimer = setTimeout(sync, delay);
}

async function sync() {
  if (syncing) return scheduleSync(1000);
  syncing = true;
  const sent = Object.values(state.pending);
  try {
    const resp = await fetch('api/list/sync', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ items: sent }),
    });
    if (!resp.ok) throw new Error('HTTP ' + resp.status);
    const data = await resp.json();
    for (const s of sent) {
      if (state.pending[s.id] && state.pending[s.id].updated_at === s.updated_at) delete state.pending[s.id];
    }
    const fresh = {};
    for (const item of data.items) fresh[item.id] = item;
    for (const p of Object.values(state.pending)) fresh[p.id] = p; // local edits made while the request ran
    state.items = fresh;
    persist();
    setSyncState(true);
    renderList();
    renderResults();
  } catch (e) {
    setSyncState(false);
  } finally {
    syncing = false;
    scheduleSync(SYNC_EVERY_MS);
  }
}

function setSyncState(online) {
  const box = $('sync-state');
  const waiting = Object.keys(state.pending).length;
  box.classList.toggle('offline', !online);
  if (online) {
    box.textContent = 'Sinchronizuota ' + new Date().toLocaleTimeString('lt-LT', { hour: '2-digit', minute: '2-digit' });
  } else {
    box.textContent = waiting
      ? `Be ryšio su kompiuteriu – ${waiting} pakeit. bus išsiųsti vėliau`
      : 'Be ryšio su kompiuteriu – sąrašas veikia, kainų paieška ne';
  }
}

// --- chain status chips ------------------------------------------------------

async function loadStatus() {
  try {
    const data = await (await fetch('api/status')).json();
    const chips = $('chain-chips');
    chips.replaceChildren(...data.chains.map((c) => {
      const date = c.updated_at ? shortDate(c.updated_at.slice(0, 10)) : '—';
      const warn = c.stale || c.last_error;
      const text = c.last_error
        ? `${c.label} – nepavyko, rodoma ${date}`
        : (c.updated_at ? `${c.label} ${date}` : `${c.label} – nėra duomenų`);
      return el('span', { class: 'chip' + (warn ? ' warn' : ''), title: c.last_error || `${c.count} prekių` }, text);
    }));
    setCollecting(data.collecting);
  } catch (e) { /* offline: keep whatever was shown */ }
}

function setCollecting(running) {
  const btn = $('collect-btn');
  btn.disabled = running;
  btn.textContent = running ? 'Renkamos kainos…' : 'Atnaujinti kainas';
  if (running) setTimeout(pollCollect, 3000);
}

async function pollCollect() {
  try {
    const data = await (await fetch('api/collect')).json();
    if (data.running) return setTimeout(pollCollect, 3000);
    setCollecting(false);
    loadStatus();
  } catch (e) { setTimeout(pollCollect, 5000); }
}

$('collect-btn').addEventListener('click', async () => {
  try {
    const data = await (await fetch('api/collect', { method: 'POST' })).json();
    setCollecting(data.running);
  } catch (e) { alert('Nepavyko susisiekti su kompiuteriu.'); }
});

// --- search -----------------------------------------------------------------

let searchTimer = null;
$('q').addEventListener('input', () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(runSearch, 250);
});
$('search-form').addEventListener('submit', (e) => { e.preventDefault(); runSearch(); });

async function runSearch() {
  const q = $('q').value.trim();
  if (!q) { lastResults = []; return renderResults(); }
  try {
    const data = await (await fetch('api/search?q=' + encodeURIComponent(q))).json();
    if ($('q').value.trim() !== q) return; // a newer search is on its way
    lastResults = data.results;
  } catch (e) {
    lastResults = null;
  }
  renderResults();
}

function isLoose(p) {
  // Sold by weight: priced per kg and the name carries no package size ('Mandarinai', 'Plautos morkos, kg').
  return p.unit === 'kg' && p.unit_price && Math.abs(p.price - p.unit_price) < 0.006
    && !/\d\s*(kg|g|l|ml|vnt)\b/i.test(p.name);
}

function activeItems() {
  return Object.values(state.items).filter((i) => !i.deleted);
}

function addProduct(p) {
  ensureName();
  const key = p.chain + ':' + p.source_id;
  const loose = isLoose(p);
  const existing = activeItems().find((i) => i.product_key === key && !i.done);
  if (existing) return change(existing, { qty: existing.qty + (existing.loose ? 0.5 : 1) });
  change({
    id: newId(), name: p.name, chain: p.chain, product_key: key, price: p.price,
    unit_price: p.unit_price, unit: p.unit, card: p.card, valid_to: p.valid_to,
    loose: loose ? 1 : 0, qty: 1, done: 0, deleted: 0, added_by: userName || null,
  }, {});
}

function addFreeText(text) {
  ensureName();
  change({ id: newId(), name: text, chain: null, product_key: null, price: null, qty: 1,
           loose: 0, done: 0, deleted: 0, added_by: userName || null }, {});
  $('q').value = '';
  lastResults = [];
  renderResults();
}

function renderResults() {
  const box = $('results');
  const q = $('q').value.trim();
  if (!q) {
    box.replaceChildren(el('div', { class: 'hint' }, 'Įrašykite, ko ieškote, pvz. „morkos“ ar „pienas 2,5“.'));
    return;
  }
  if (lastResults === null) {
    box.replaceChildren(
      el('div', { class: 'hint' }, 'Kainų paieška veikia tik prisijungus prie namų kompiuterio.'),
      el('button', { type: 'button', class: 'btn primary free-add', onclick: () => addFreeText(q) }, `Įdėti „${q}“ be kainos`));
    return;
  }
  const inList = new Set(activeItems().filter((i) => !i.done).map((i) => i.product_key));
  // Highlight the cheapest per unit among results sharing the most common unit.
  const counts = {};
  for (const r of lastResults) if (r.unit_price) counts[r.unit] = (counts[r.unit] || 0) + 1;
  const mainUnit = Object.keys(counts).sort((a, b) => counts[b] - counts[a])[0];
  const best = Math.min(...lastResults.filter((r) => r.unit === mainUnit && r.unit_price).map((r) => r.unit_price));

  const rows = lastResults.map((r) => {
    const isBest = r.unit === mainUnit && r.unit_price === best;
    const added = inList.has(r.chain + ':' + r.source_id);
    const meta = [];
    if (r.promo) meta.push(r.promo);
    if (r.valid_from && r.valid_from > todayIso()) meta.push('nuo ' + shortDate(r.valid_from));
    if (r.valid_to) meta.push('iki ' + shortDate(r.valid_to));
    return el('div', { class: 'result' + (isBest ? ' best' : '') },
      el('div', { class: 'info' },
        el('div', { class: 'chain' }, CHAIN_LABELS[r.chain] || r.chain, isBest ? el('span', { class: 'best-label' }, ' · pigiausia') : null),
        el('div', { class: 'name' }, r.name),
        el('div', { class: 'meta' }, meta.join(' · '), r.card ? el('span', { class: 'card' }, (meta.length ? ' · ' : '') + 'su kortele ' + r.card) : null)),
      el('div', { class: 'prices' },
        el('div', { class: 'price' }, eur(r.price)),
        r.old_price ? el('div', { class: 'old' }, eur(r.old_price)) : null,
        r.unit_price ? el('div', { class: 'unit' }, `${eur(r.unit_price)}/${r.unit}`) : null),
      el('button', { type: 'button', class: 'btn small' + (added ? '' : ' primary'), onclick: () => addProduct(r),
                     'aria-label': (added ? 'Įdėti dar vieną: ' : 'Pridėti: ') + r.name }, added ? '+1' : '+ Pridėti'));
  });
  const free = el('button', { type: 'button', class: 'btn ghost free-add', onclick: () => addFreeText(q) }, `Įdėti „${q}“ be konkrečios prekės`);
  box.replaceChildren(...(rows.length ? rows : [el('div', { class: 'hint' }, 'Akcijose nieko nerasta. Pabandykite trumpesnį žodį, pvz. „sūr“.')]), free);
}

// --- list -------------------------------------------------------------------

function lineTotal(i) { return i.price ? i.price * i.qty : 0; }

function itemTag(i) {
  if (i.valid_to && i.valid_to < todayIso()) return ['warn', `Akcija baigėsi ${shortDate(i.valid_to)} – patikrinkite kainą`];
  const parts = [];
  if (i.price && !i.loose) parts.push(eur(i.price) + ' / vnt.');
  if (i.unit_price) parts.push(`${eur(i.unit_price)}/${i.unit}`);
  if (i.card) parts.push('su kortele ' + i.card);
  return [i.card ? 'card' : '', parts.join(' · ')];
}

function renderList() {
  const items = activeItems();
  const groups = {};
  for (const i of items) (groups[i.chain || 'kita'] ||= []).push(i);
  const order = [...CHAIN_ORDER, 'kita'].filter((c) => groups[c]);

  const nodes = order.map((chain) => {
    const list = groups[chain].sort((a, b) => (a.done - b.done) || a.name.localeCompare(b.name, 'lt'));
    const sum = list.reduce((s, i) => s + lineTotal(i), 0);
    return el('section', { class: 'group' },
      el('div', { class: 'group-head' }, el('span', {}, CHAIN_LABELS[chain] || 'Kita'), el('span', {}, sum ? eur(sum) : '')),
      list.map(renderItem));
  });
  $('list').replaceChildren(...(nodes.length ? nodes : [el('div', { class: 'hint' }, 'Sąrašas tuščias. Spauskite „Pridėti prekę“.')]));

  const left = items.filter((i) => !i.done);
  $('list-count').textContent = items.length ? `liko ${left.length} iš ${items.length}` : '';
  $('left-total').textContent = eur(left.reduce((s, i) => s + lineTotal(i), 0));
  $('tab-list').textContent = `Sąrašas · ${left.length}`;
}

function renderItem(i) {
  const [tagClass, tagText] = itemTag(i);
  const step = i.loose ? 0.5 : 1;
  const qtyText = num(i.qty) + (i.loose ? ' kg' : ' vnt.');
  return el('div', { class: 'item' + (i.done ? ' done' : '') },
    el('label', {},
      el('input', { type: 'checkbox', checked: !!i.done, onchange: () => change(i, { done: i.done ? 0 : 1 }) }),
      el('span', { class: 'texts' },
        el('span', { class: 'name' }, i.name),
        tagText ? el('span', { class: 'tag ' + tagClass }, tagText) : null,
        i.added_by ? el('span', { class: 'by' }, 'Pridėjo: ' + i.added_by) : null)),
    el('div', { class: 'side' },
      el('span', { class: 'line-price' }, i.price ? eur(lineTotal(i)) : ''),
      el('div', { class: 'stepper' },
        el('button', { type: 'button', 'aria-label': 'Mažiau: ' + i.name,
                       onclick: () => i.qty - step < step ? change(i, { deleted: 1 }) : change(i, { qty: i.qty - step }) }, '−'),
        el('span', {}, qtyText),
        el('button', { type: 'button', 'aria-label': 'Daugiau: ' + i.name, onclick: () => change(i, { qty: i.qty + step }) }, '+')),
      el('button', { type: 'button', class: 'remove', onclick: () => change(i, { deleted: 1 }) }, 'Išimti')));
}

$('clear-done').addEventListener('click', () => {
  for (const i of activeItems().filter((x) => x.done)) change(i, { deleted: 1 });
});

// --- who is adding ----------------------------------------------------------

function ensureName() {
  if (!userName) $('name-dialog').showModal();
}
$('name-form').addEventListener('submit', () => {
  userName = $('name-input').value.trim();
  save('user-name', userName);
  // Items added before the name was given get it now.
  for (const i of activeItems().filter((x) => !x.added_by)) change(i, { added_by: userName });
});

// --- start ------------------------------------------------------------------

renderList();
renderResults();
loadStatus();
sync();
setInterval(loadStatus, 60000);
if (!userName) $('name-dialog').showModal();
