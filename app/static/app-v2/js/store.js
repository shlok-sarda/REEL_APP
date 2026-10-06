// App state + the model built from API responses. Screens subscribe to
// events and patch themselves; nothing here touches the DOM.
import * as api from './api.js';
import { cleanCreator, store as ls, words } from './util.js';
import { buildIndex, queryIndex, reasonText } from './searchcore.js';

export const S = {
  loaded: false,
  loadError: null,
  session: null,
  reels: [],
  byId: new Map(),
  collections: [],
  unsorted: [],
  lists: [],
  recipes: [],
  recipesEnabled: false,
  geo: null,
  places: [],
  processing: [],
  failed: [],
  jobs: [],
  diagnostics: [],
  dashboard: {},
  docs: {},
  meta: {},
  index: [],
  extrasLoaded: false,
  flags: {},
  prefs: {
    soundOn: ls.get('soundOn', true),
    city: ls.get('city', ''),
    recent: ls.get('recent', []),
    ticks: ls.get('ticks', {}),
    shop: ls.get('shop', {}),
    listEmoji: ls.get('listEmoji', {}),
    claimSkip: ls.get('claimSkip', {}),
    nameSkip: ls.get('nameSkip', false),
  },
  session_flags: { homeIntroDone: false },
};

export function savePref(key, value) {
  S.prefs[key] = value;
  ls.set(key, value);
}

/* ---------- events ---------- */
const subs = {};
export function on(evt, fn) {
  (subs[evt] = subs[evt] || new Set()).add(fn);
  return () => subs[evt].delete(fn);
}
export function emit(evt, data) {
  (subs[evt] || []).forEach((fn) => { try { fn(data); } catch (e) { console.error(e); } });
}

/* ---------- category emoji: explicit table, then whole-word match ---------- */
const BASE_EMOJI = {
  'Food & Restaurants': '🍜', 'Recipes & Cooking': '🍳', 'Travel & Places': '✈️', 'Gym & Fitness': '💪',
  'Gadgets & Tech': '📱', 'Apps & AI Tools': '🛠️', 'Fashion & Shopping': '🛍️', 'Grooming & Personal Care': '🧴',
  'Movies & Shows': '🎬', 'Money & Career': '💼', 'People & Performance': '🎭', 'Home & Decor': '🛋️',
  'Cars & Rides': '🏎️', Music: '🎵', 'Books & Reading': '📚', 'Pets & Animals': '🐾', 'Art & Design': '🎨',
  'Hobbies & Collecting': '🧩',
};
const WORD_EMOJI = [
  [['recipe', 'recipes', 'cooking', 'cook', 'protein'], '🍳'],
  [['food', 'restaurant', 'restaurants', 'eats', 'cafe', 'cafes', 'dining', 'eat'], '🍜'],
  [['gym', 'fitness', 'exercise', 'training', 'workout', 'arm', 'arms', 'shoulder', 'biceps', 'triceps', 'chest', 'legs'], '💪'],
  [['travel', 'places', 'trip', 'destination', 'flight'], '✈️'],
  [['gadget', 'gadgets', 'tech', 'device'], '📱'],
  [['apps', 'ai', 'software', 'tools', 'productivity', 'coding'], '🛠️'],
  [['fashion', 'shopping', 'style', 'outfit', 'outfits'], '🛍️'],
  [['grooming', 'skin', 'hair', 'haircut', 'beauty'], '🧴'],
  [['movies', 'movie', 'shows', 'film', 'films', 'series'], '🎬'],
  [['money', 'career', 'business', 'finance', 'startup'], '💼'],
  [['nature', 'weather', 'sky', 'clouds', 'sunset'], '🌦️'],
  [['home', 'decor', 'interior'], '🛋️'],
  [['cars', 'car', 'rides', 'bike'], '🏎️'],
  [['music', 'song', 'songs'], '🎵'],
  [['books', 'reading', 'book'], '📚'],
  [['pets', 'animals', 'dog', 'cat'], '🐾'],
  [['art', 'design'], '🎨'],
];
export function emojiFor(...texts) {
  for (const t of texts) if (BASE_EMOJI[t]) return BASE_EMOJI[t];
  const toks = new Set(words(texts.join(' ')));
  for (const [list, e] of WORD_EMOJI) if (list.some((w) => toks.has(w))) return e;
  return '';
}
export function monogram(text) {
  return (String(text || '?').trim().charAt(0) || '?').toUpperCase();
}

const UNSORTED = new Set(['', 'generic', 'miscellaneous', 'uncertain', 'general', 'personalized', 'unsorted']);
const NOT_A_PLACE = /film|movie|series|season|episode|[0-9]{4}/i;

/* ---------- model ---------- */
function normReel(raw) {
  const base = raw._base || raw.reel_id;
  const d = S.docs[base] || {};
  const m = S.meta[base] || {};
  // Live reels without a thumbnail get the colour placeholder, never a
  // replica fixture path.
  const thumb = raw.thumbnail_url || (api.LIVE ? '' : `fixtures/media/thumbs-sm/${base}.jpg`);
  return {
    id: raw.reel_id,
    base,
    url: raw.url || '',
    name: raw.name || d.main_subject || 'Saved reel',
    summary: raw.summary || '',
    receivedAt: raw.received_at || '',
    thumb,
    full: thumb.replace('/thumbs-sm/', '/thumbs/'),
    video: raw.local_video_url || '',
    color: m.color || '#1c1c20',
    lqip: m.lqip || '',
    duration: m.duration || 0,
    w: m.w || 9, h: m.h || 16,
    creator: cleanCreator(d.creator),
    category: d.primary_category || '',
    sub: d.secondary_category || '',
    locations: d.locations || [],
    items: d.items || [],
    visible: d.visible_text || [],
    visual: d.visual_entities || [],
    subject: d.main_subject || '',
    caption: d.caption || '',
    transcript: d.transcript_excerpt || '',
    collections: [],
    status: 'ready',
  };
}

function rebuild(lib) {
  const reels = lib.recents.map(normReel);
  const byId = new Map(reels.map((r) => [r.id, r]));
  const collections = [];
  lib.personalized.forEach((c) => {
    const key = String(c.parent_title || c.list_title || '').trim().toLowerCase();
    if (UNSORTED.has(key) && UNSORTED.has(String(c.list_title || '').trim().toLowerCase())) return;
    const ids = [];
    c.items.forEach((it) => { if (byId.has(it.reel_id) && !ids.includes(it.reel_id)) ids.push(it.reel_id); });
    if (!ids.length) return;
    const col = { key: c.list_title, title: c.list_title, parent: c.parent_title || '', emoji: emojiFor(c.list_title, c.parent_title), ids };
    ids.forEach((id) => byId.get(id).collections.push(col.key));
    collections.push(col);
  });
  collections.sort((a, b) => b.ids.length - a.ids.length || a.title.localeCompare(b.title));
  // Collections shelves are a gated feature (SHOW_COLLECTIONS in the classic UI).
  if (S.flags && S.flags.showCollections === false) {
    collections.forEach((c) => c.ids.forEach((id) => { const r = byId.get(id); if (r) r.collections = []; }));
    collections.length = 0;
  }
  S.reels = reels;
  S.byId = byId;
  S.collections = collections;
  S.unsorted = collections.length ? reels.filter((r) => !r.collections.length).map((r) => r.id) : [];
  S.index = buildIndex(reels.map((r) => ({
    id: r.id,
    fields: {
      name: r.name, subject: r.subject, items: r.items.map((i) => i.item_name), locations: r.locations,
      category: [r.category, r.sub].concat(r.collections), creator: r.creator, visible: r.visible, visual: r.visual,
      summary: r.summary, caption: r.caption, transcript: r.transcript,
    },
  })));
}

function buildJobs(jobs) {
  S.jobs = jobs;
  // Only each reel's latest job counts, and only for reels not already in the
  // library: a reel that failed once and then succeeded on retry is fine, and
  // re-processing a reel you already have is not a "new reel".
  const latest = new Map();
  (jobs || []).forEach((j) => {
    if (!j || !j.reel_id) return;
    const cur = latest.get(j.reel_id);
    if (!cur || Number(j.id) > Number(cur.id)) latest.set(j.reel_id, j);
  });
  const fresh = Array.from(latest.values()).filter((j) => !S.byId.has(j.reel_id));
  const active = new Set(['queued', 'running', 'pending']);
  S.processing = fresh.filter((j) => active.has(String(j.status).toLowerCase())).map((j) => ({
    jobId: j.id, rid: j.reel_id, status: String(j.status).toLowerCase() === 'running' ? 'running' : 'queued', step: j.step || (String(j.status).toLowerCase() === 'running' ? 1 : 0), url: j.reel_url, shortcode: j.reel_shortcode,
  }));
  S.failed = fresh.filter((j) => String(j.status).toLowerCase() === 'failed').map((j) => ({ jobId: j.id, rid: j.reel_id, why: friendlyError(j.error_message), url: j.reel_url, shortcode: j.reel_shortcode }));
}

// Raw pipeline errors are for Technical details; cards get plain words.
function friendlyError(msg) {
  const m = String(msg || '').toLowerCase();
  if (!m) return 'Something went wrong while processing.';
  if (m.includes('download') || m.includes('instagram') || m.includes('403') || m.includes('404')) return 'Instagram did not let us download this video.';
  if (m.includes('quota') || m.includes('rate') || m.includes('429')) return 'We were busy. It will work on a retry.';
  if (m.includes('timeout') || m.includes('timed out')) return 'It took too long. A retry usually works.';
  return 'Something went wrong while processing.';
}

export function listFromApi(f, detail) {
  return {
    id: f.id,
    name: f.name,
    description: f.description,
    query: f.query || '',
    createdAt: f.created_at,
    members: detail ? detail.members.map((m) => m.reel_id).filter((id) => S.byId.has(id)) : [],
    suggestions: detail ? detail.suggestions.map((m) => m.reel_id).filter((id) => S.byId.has(id)) : [],
    emoji: S.prefs.listEmoji[f.id] || emojiFor(f.name, f.description) || '',
  };
}

function buildPlaces(pins) {
  const groups = new Map();
  pins.forEach((p) => {
    if (NOT_A_PLACE.test(p.place || '') || /movie/i.test(p.category || '')) return;
    if (!S.byId.has(p.reel_id)) return;
    const g = groups.get(p.place) || { place: p.place, lat: p.lat, lng: p.lng, reels: [], named: [] };
    if (!g.reels.includes(p.reel_id)) g.reels.push(p.reel_id);
    groups.set(p.place, g);
  });
  groups.forEach((g) => {
    g.reels.forEach((rid) => {
      const r = S.byId.get(rid);
      (r.items || []).forEach((it) => {
        if (it.item_type === 'place' && it.item_name && !g.named.some((n) => n.name === it.item_name)) {
          g.named.push({ name: it.item_name, summary: it.summary, rid });
        }
      });
    });
  });
  S.places = Array.from(groups.values()).sort((a, b) => b.reels.length - a.reels.length);
}

/* ---------- loading ---------- */
export async function loadAll() {
  S.loadError = null;
  try {
    const [lib, docs, meta, session, jobs, dashboard] = await Promise.all([
      api.getLibrary(), api.getDocuments(), api.getMediaMeta(), api.getSession(), api.getJobs(), api.getDashboard(),
    ]);
    S.docs = {};
    docs.documents.forEach((d) => { S.docs[d.reel_id] = d; });
    S.meta = meta;
    S.session = session;
    S.dashboard = dashboard;
    S.flags = api.flags();
    S.recipesEnabled = S.flags.showRecipes;
    rebuild(lib);
    buildJobs(jobs);
    S.loaded = true;
    emit('loaded');
    loadExtras();
  } catch (e) {
    S.loadError = e;
    emit('loadError', e);
  }
}

export async function loadExtras() {
  const tasks = [
    api.getFolders().then(async (res) => {
      const details = await Promise.all(res.folders.map((f) => api.getFolder(f.id).catch(() => null)));
      S.lists = res.folders.map((f, i) => listFromApi(f, details[i]));
    }).catch(() => { S.lists = S.lists || []; }),
    api.getMapData().then((res) => buildPlaces(res.pins)).catch(() => {}),
    api.getRecipes().then((res) => {
      S.recipesEnabled = true;
      S.recipes = res.recipes.filter((r) => S.byId.has(r.reel_id));
      S.geo = { apps: res.apps, cities: res.cities, default_apps: res.default_apps };
    }).catch(() => { S.recipesEnabled = false; S.recipes = []; }),
    api.getDiagnostics().then((d) => { S.diagnostics = d; }).catch(() => {}),
  ];
  await Promise.all(tasks);
  S.extrasLoaded = true;
  emit('extras');
}

export async function refreshLists() {
  const res = await api.getFolders();
  const details = await Promise.all(res.folders.map((f) => api.getFolder(f.id).catch(() => null)));
  S.lists = res.folders.map((f, i) => listFromApi(f, details[i]));
  emit('lists');
}

export async function refreshRecipes(opts = {}) {
  try {
    const res = await api.getRecipes(opts);
    S.recipes = res.recipes.filter((r) => S.byId.has(r.reel_id));
    emit('recipes');
  } catch (e) { /* recipes disabled */ }
}

// Background refresh. Diffs ids so screens can patch only what changed.
export async function refresh() {
  const before = new Set(S.reels.map((r) => r.id));
  const [lib, jobs, dashboard] = await Promise.all([api.getLibrary(), api.getJobs(), api.getDashboard()]);
  rebuild(lib);
  buildJobs(jobs);
  S.dashboard = dashboard;
  const landed = S.reels.filter((r) => !before.has(r.id)).map((r) => r.id);
  if (landed.length) {
    try { await Promise.all([api.getMapData().then((res) => buildPlaces(res.pins)), refreshListsQuiet()]); } catch (e) { /* keep old */ }
  }
  emit('library', { landed });
  return landed;
}

async function refreshListsQuiet() {
  const res = await api.getFolders();
  const details = await Promise.all(res.folders.map((f) => api.getFolder(f.id).catch(() => null)));
  S.lists = res.folders.map((f, i) => listFromApi(f, details[i]));
}

/* ---------- selectors ---------- */
export const reel = (id) => S.byId.get(id);
export const reelsFor = (ids) => ids.map((id) => S.byId.get(id)).filter(Boolean);
export const listById = (id) => S.lists.find((l) => l.id === id);
export const collectionByKey = (k) => S.collections.find((c) => c.key === k);
export const recipeFor = (rid) => S.recipes.find((r) => r.reel_id === rid);

export function localSearch(q, limit = 30) {
  return queryIndex(S.index, q, limit).map((h) => ({ id: h.id, score: h.score, evidence: reasonText(h.reason) }));
}

export function cityApps() {
  if (!S.geo) return [];
  return (S.prefs.city && S.geo.cities[S.prefs.city]) || S.geo.default_apps || [];
}
export const appLabel = (a) => (S.geo && S.geo.apps[a] && S.geo.apps[a].label) || a;
export const appColor = (a) => (S.geo && S.geo.apps[a] && S.geo.apps[a].color) || '#888';

export function displayName() {
  const u = S.session && S.session.user;
  if (!u) return '';
  return u.preferred_name || u.display_name || '';
}

export function isGuest() { return !!(S.session && S.session.guest); }

export function resetState() {
  Object.assign(S, {
    loaded: false, loadError: null, session: null, reels: [], byId: new Map(), collections: [], unsorted: [], lists: [],
    recipes: [], recipesEnabled: false, geo: null, places: [], processing: [], failed: [], jobs: [], diagnostics: [],
    dashboard: {}, index: [], extrasLoaded: false,
  });
  S.session_flags.homeIntroDone = false;
}
