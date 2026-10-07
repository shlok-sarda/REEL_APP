// Data layer, live build. Same exports as the replica's fixture api.js, each
// one a thin wrapper over a real endpoint. Port note: no backslashes.
import { NL } from './util.js';

const CFG = window.__CN__ || { userId: '', build: 'dev', flags: {} };
const UID = encodeURIComponent(CFG.userId || '');

export const LIVE = true;
export const net = { profile: 'live', fail: 'off' };
export function config() { return { build: CFG.build, userId: CFG.userId }; }
export function flags() {
  const f = CFG.flags || {};
  return { showRecipes: !!f.showRecipes, showCollections: f.showCollections !== false, showReport: !!f.showReport };
}

export class ApiError extends Error {
  constructor(status, detail) { super(detail); this.status = status; this.detail = detail; }
}

async function call(method, path, body, opts = {}) {
  let res;
  try {
    res = await fetch(path, {
      method,
      credentials: 'same-origin',
      headers: body ? { 'Content-Type': 'application/json' } : undefined,
      body: body ? JSON.stringify(body) : undefined,
      signal: opts.signal,
    });
  } catch (e) {
    if (e && e.name === 'AbortError') throw e;
    throw new ApiError(0, 'offline');
  }
  if (!res.ok) {
    let detail = '';
    try { const j = await res.json(); detail = typeof j.detail === 'string' ? j.detail : ''; } catch (e) { /* not json */ }
    // The classic UI's demo guard answers 403 with a message; the new UI
    // reads any such refusal on the read-only demo as "demo".
    throw new ApiError(res.status, detail || `Request failed (${res.status})`);
  }
  if (opts.raw) return res;
  const text = await res.text();
  return text ? JSON.parse(text) : {};
}
const get = (p, o) => call('GET', p, null, o);
const post = (p, b, o) => call('POST', p, b || {}, o);

// Replica-only hooks, kept so main.js runs unchanged.
export async function loadFixtures() {}
export function setScenario() {}
export async function restoreReel() {}

/* ---------- reads ---------- */
export async function getLibrary() {
  const lib = await get(`/library?user_id=${UID}`);
  const personalized = Array.isArray(lib.personalized) && lib.personalized.length ? lib.personalized : (lib.standard || []);
  return { user_id: lib.user_id, standard: [], personalized, recents: Array.isArray(lib.recents) ? lib.recents : [] };
}
export async function getDocuments() { return get(`/deep-search/cards?user_id=${UID}`); }
export async function getMediaMeta() { return {}; }
export async function getSession() { return get('/auth/session'); }
export async function getFolders() { return get(`/folders?user_id=${UID}`); }
export async function getFolder(id) { return get(`/folders/${encodeURIComponent(id)}?user_id=${UID}`); }
export async function getFoldersForReel(rid) { return get(`/folders/for-reel?reel_id=${encodeURIComponent(rid)}&user_id=${UID}`); }
export async function getJobs() { const j = await get(`/jobs?user_id=${UID}&limit=50`); return Array.isArray(j) ? j : (j.jobs || []); }
export async function getDashboard() { return get(`/dashboard?user_id=${UID}`); }
export async function getDiagnostics() { const d = await get(`/diagnostics/reels?user_id=${UID}&limit=12`); return Array.isArray(d) ? d : []; }
export async function getMapData() { return get(`/api/map-data?user_id=${UID}`); }
// extract=false: cached cards only (background loads must never spend
// OpenAI credit). Opening the Recipes screen passes true, like the classic hub.
export async function getRecipes(opts = {}) {
  if (!flags().showRecipes) throw new ApiError(404, 'Recipes is not enabled for this account');
  return get(`/api/recipes?user_id=${UID}&extract=${opts.extract ? 1 : 0}`);
}
export async function getReelRecipe(rid) { return get(`/api/reel-recipe?reel_id=${encodeURIComponent(rid)}&user_id=${UID}`); }
export async function getAdminUsers() { return get('/admin/users'); }
export async function deepSearch(q, opts = {}) {
  const query = String(q || '').trim();
  if (!query) return { query, results: [] };
  const res = await get(`/deep-search?q=${encodeURIComponent(query)}&user_id=${UID}&limit=30`, { signal: opts.signal });
  const results = Array.isArray(res.results) ? res.results : (res.result && Array.isArray(res.result.hits) ? res.result.hits : []);
  return { query, backend: res.backend, results };
}

/* ---------- writes ---------- */
export async function suggestFolder({ query, reel_ids }) { return post('/folders/suggest', { user_id: CFG.userId, query, reel_ids }); }
export async function createFolder({ name, description, query, reel_ids }) { return post('/folders', { user_id: CFG.userId, name, description, query, reel_ids }); }
export async function updateFolder(id, { name, description }) { return call('PATCH', `/folders/${encodeURIComponent(id)}`, { user_id: CFG.userId, name, description }); }
export async function decide(id, rid, action, reason) { return post(`/folders/${encodeURIComponent(id)}/${action}`, { user_id: CFG.userId, reel_id: rid, reason: reason || '' }); }
export async function undoDecide(id, rid) { return post(`/folders/${encodeURIComponent(id)}/undo`, { user_id: CFG.userId, reel_id: rid }); }
export async function rescanFolder(id) { return post(`/folders/${encodeURIComponent(id)}/rescan`, { user_id: CFG.userId }); }
export async function addReelToFolder(id, rid) { return post(`/folders/${encodeURIComponent(id)}/add-reel`, { user_id: CFG.userId, reel_id: rid }); }
export async function deleteFolder(id) { return call('DELETE', `/folders/${encodeURIComponent(id)}?user_id=${UID}`); }
export async function deleteReel(rid) { return call('DELETE', `/reels/${encodeURIComponent(rid)}`); }
export async function retryFailed(rids) {
  if (rids && rids.length) {
    await Promise.all(rids.map((rid) => post(`/reels/${encodeURIComponent(rid)}/retry`)));
    return { requeued_count: rids.length, error_count: 0 };
  }
  return post(`/reels/retry-unsorted?user_id=${UID}`);
}
export async function saveProfileName(name) { return post('/auth/profile-name', { name }); }
export async function connectInstagram() { return post('/auth/instagram/connect'); }
export async function checkInstagram() { return getSession(); }
export async function extractRecipe(rid) { return post('/api/reel-recipe/extract', { user_id: CFG.userId, reel_id: rid }); }
export async function logout() { return post('/auth/logout'); }

/* ---------- search report: server-sent events read off a POST ---------- */
export async function searchReportStream({ query, include, exclude, signal, onEvent }) {
  const res = await call('POST', '/api/search-report/stream', { user_id: CFG.userId, query, include: include || [], exclude: exclude || [] }, { raw: true, signal });
  const END = NL + NL;
  const frames = (text) => text.split(END).map((f) => f.trim()).filter((f) => f.indexOf('data:') === 0)
    .map((f) => { try { return JSON.parse(f.slice(5)); } catch (e) { return null; } }).filter(Boolean);
  if (res.body && res.body.getReader) {
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buf = '';
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      const cut = buf.lastIndexOf(END);
      if (cut < 0) continue;
      frames(buf.slice(0, cut)).forEach(onEvent);
      buf = buf.slice(cut + END.length);
    }
    if (buf.trim()) frames(buf).forEach(onEvent);
  } else {
    frames(await res.text()).forEach(onEvent);
  }
}
