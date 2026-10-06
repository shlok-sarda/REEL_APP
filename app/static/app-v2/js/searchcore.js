// Weighted lexical search over a personal library. Used twice: for instant
// results while typing, and by the simulated server for queries that have no
// captured fixture. No backslashes (port-safe).
import { words } from './util.js';

const STOP = new Set(['the', 'a', 'an', 'in', 'of', 'for', 'that', 'this', 'my', 'with', 'and', 'to', 'on', 'i', 'me',
  'thing', 'one', 'video', 'reel', 'reels', 'saved', 'some', 'show', 'find', 'about', 'at', 'from', 'it', 'is']);

const SYN = {
  gym: ['exercise', 'workout', 'training', 'fitness'], workout: ['exercise', 'gym', 'training'], exercise: ['workout', 'training'],
  food: ['restaurant', 'cafe', 'eat', 'dish', 'recipe'], veg: ['vegetarian', 'vegan'], vegetarian: ['veg', 'vegan'],
  recipe: ['cooking', 'cook', 'dish', 'recipes'], recipes: ['recipe', 'cooking'], cook: ['recipe', 'cooking'],
  movie: ['film', 'movies'], film: ['movie'], cafe: ['restaurant', 'coffee', 'eatery'], restaurant: ['cafe', 'eatery', 'restaurants'],
  arm: ['bicep', 'biceps', 'tricep', 'triceps'], arms: ['bicep', 'tricep'], shoulder: ['delt', 'shoulders', 'lateral'],
  chest: ['pec', 'crossover'], abs: ['core', 'crunch', 'abdominal'], app: ['tool', 'software', 'repository'],
  nature: ['sky', 'cloud', 'tree', 'sunset'], storm: ['lightning', 'thunderstorm', 'clouds'], sunset: ['sky', 'dusk'],
  outfit: ['fashion', 'style', 'jacket'], hair: ['haircut'], travel: ['trip', 'flight', 'airport'], place: ['restaurant', 'cafe', 'destination'],
  places: ['restaurant', 'cafe'], eat: ['restaurant', 'food', 'cafe'],
};

const CONCRETE = ['visible', 'items', 'locations'];

const FIELDS = [
  ['name', 6, 'In title'], ['locations', 5, 'Place'], ['items', 4.5, 'Mentions'], ['subject', 4, 'About'],
  ['category', 3, 'Shelf'], ['visible', 2.6, 'On screen'], ['creator', 2.5, 'Creator'], ['visual', 1.6, 'Seen'],
  ['summary', 1.6, 'About'], ['caption', 1, 'Caption'], ['transcript', 0.8, 'Said'],
];

// entries: [{ id, fields: { name, subject, items[], locations[], category, creator, visible[], visual[], summary, caption, transcript } }]
export function buildIndex(entries) {
  return entries.map((e) => {
    const f = e.fields;
    const prepared = {};
    FIELDS.forEach(([key]) => {
      const v = f[key];
      const list = Array.isArray(v) ? v : (v ? [v] : []);
      prepared[key] = list.map((text) => ({ text: String(text), toks: words(text) }));
    });
    return { id: e.id, prepared };
  });
}

function tokenMatch(fieldTok, q, isLast) {
  if (fieldTok === q) return 1;
  if (q.length >= 3 && fieldTok.startsWith(q)) return 0.92;
  if (isLast && q.length >= 2 && fieldTok.startsWith(q)) return 0.85;
  if (q.length >= 5 && fieldTok.length >= 5 && (fieldTok.startsWith(q.slice(0, -1)) || q.startsWith(fieldTok))) return 0.7;
  return 0;
}

export function queryIndex(index, rawQuery, limit = 40) {
  const all = words(rawQuery);
  const qs = all.filter((t) => !STOP.has(t));
  const tokens = qs.length ? qs : all;
  if (!tokens.length) return [];
  const out = [];
  index.forEach((doc) => {
    let total = 0;
    let best = null;
    let bestOther = null;
    let concrete = null;
    let missed = 0;
    const nameText = ((doc.prepared.name[0] || {}).text || '').trim().toLowerCase();
    tokens.forEach((q, qi) => {
      const isLast = qi === tokens.length - 1;
      const variants = [[q, 1]].concat((SYN[q] || []).map((s) => [s, 0.6]));
      let tokBest = 0;
      let tokReason = null;
      let otherBest = 0;
      let otherReason = null;
      FIELDS.forEach(([key, weight, label]) => {
        doc.prepared[key].forEach((entry) => {
          variants.forEach(([v, vw]) => {
            let m = 0;
            for (let i = 0; i < entry.toks.length; i += 1) {
              const s = tokenMatch(entry.toks[i], v, isLast && vw === 1);
              if (s > m) m = s;
              if (m === 1) break;
            }
            const score = m * weight * vw;
            if (score > tokBest) { tokBest = score; tokReason = { label, text: entry.text, key }; }
            if (key !== 'name' && score > otherBest && entry.text.trim().toLowerCase() !== nameText) { otherBest = score; otherReason = { label, text: entry.text, key }; }
            if (m >= 0.85 && vw === 1 && ['visible', 'items', 'locations'].includes(key) && entry.text.trim().toLowerCase() !== nameText && (!concrete || CONCRETE.indexOf(key) < CONCRETE.indexOf(concrete.key))) concrete = { label, text: entry.text, key };
          });
        });
      });
      if (tokBest === 0) missed += 1;
      total += tokBest;
      if (tokReason && (!best || tokBest > best.score)) best = { ...tokReason, score: tokBest };
      if (otherReason && (!bestOther || otherBest > bestOther.score)) bestOther = { ...otherReason, score: otherBest };
    });
    // The title is already on screen, so explain the match with anything
    // else, preferring concrete evidence (on-screen text, named things,
    // places) over the model's prose description.
    if (missed === 0 && total > 0) out.push({ id: doc.id, score: total, reason: concrete || bestOther || best });
  });
  out.sort((a, b) => b.score - a.score);
  return out.slice(0, limit);
}

// Turn a reason into the short evidence chip text shown under a result.
export function reasonText(reason) {
  if (!reason) return null;
  let text = String(reason.text || '').trim();
  if (text.length > 64) text = text.slice(0, 62).replace(/[ ,;.]+[^ ]*$/, '') + '...';
  return { label: reason.label, text };
}

// The server sends match_reasons as a list, or as a stringified Python list.
export function parseServerReasons(raw) {
  if (Array.isArray(raw)) return raw.map(String);
  let s = String(raw || '').trim();
  if (!s) return [];
  if (s.startsWith('[')) s = s.slice(1);
  if (s.endsWith(']')) s = s.slice(0, -1);
  return s.split(/', '|", "|', "|", '/).map((p) => p.replace(/^['"]+|['"]+$/g, '').trim()).filter(Boolean);
}

// Server reasons list everything known about a reel, not only what matched.
// Show one that actually contains a query word (or synonym); otherwise the
// plain "About" line. Never surface unrelated on-screen text.
export function evidenceFromServer(raw, query) {
  const reasons = parseServerReasons(raw);
  const qs = words(query).filter((t) => !STOP.has(t));
  const want = new Set(qs.concat(qs.flatMap((q) => SYN[q] || [])));
  const hits = (r) => words(r.slice(r.indexOf(':') + 1)).some((w) => Array.from(want).some((q) => w === q || (q.length >= 3 && w.startsWith(q))));
  const order = ['On-screen text:', 'Seen:', 'Visual clue:', 'About:'];
  let pick = null;
  for (const pre of order) { pick = reasons.find((r) => r.startsWith(pre) && hits(r)); if (pick) break; }
  if (!pick) pick = reasons.find((r) => r.startsWith('About:')) || null;
  if (!pick) return null;
  const idx = pick.indexOf(':');
  const head = idx > 0 ? pick.slice(0, idx) : 'About';
  const body = idx > 0 ? pick.slice(idx + 1).trim() : pick;
  const label = head === 'On-screen text' ? 'On screen' : head === 'Visual clue' ? 'Seen' : head;
  const parts = body.split(', ');
  const best = parts.find((p) => hits(':' + p)) || parts[0];
  return reasonText({ label, text: best });
}
