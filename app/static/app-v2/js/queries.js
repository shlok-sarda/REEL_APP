// Search phrases built from this person's own library, so the Ask widget and
// the search suggestions only ever type things that have results here. No AI:
// places, recipes, workouts, shows and what each reel is about, cleaned into
// the way people actually remember a reel ("veg food in bali", "biceps
// workout", "ajmal aristocrat perfume"). No backslashes (port-safe).
import { S, localSearch } from './store.js';
import { words } from './util.js';

const KINDS = [
  [['vegetarian', 'vegan', 'veg'], 'veg food'],
  [['street food'], 'street food'],
  [['cafe', 'coffee'], 'cafes'],
  [['villa', 'rental', 'stay', 'hotel', 'resort', 'airbnb', 'homestay'], 'stays'],
  [['beach'], 'beaches'],
  [['club', 'bar', 'nightlife', 'party'], 'nightlife'],
  [['outlet', 'shopping', 'market', 'mall'], 'shopping'],
  [['restaurant', 'food', 'dish', 'eat', 'dining', 'brunch', 'dessert'], 'food'],
];

// Words that describe the person in the video, not the thing they remember.
const LEAD = new Set(['a', 'an', 'the', 'young', 'old', 'older', 'middle', 'aged', 'middle-aged', 'elderly', 'shirtless', 'smiling', 'happy',
  'asian', 'indian', 'two', 'three', 'several', 'group', 'of', 'man', 'woman', 'men', 'women', 'person', 'people', 'guy', 'guys', 'girl', 'girls',
  'boy', 'boys', 'lady', 'chef', 'couple', 'family', 'members', 'child', 'kid', 'kids', 'creator', 'influencer', 'teenage', 'adults', 'adult',
  'various', 'different', 'unique', 'multiple', 'many', 'some', 'casual', 'stylish', 'hand', 'hands', 'and', 'animated', '3d', 'figure']);
// A remembered phrase ends where the sentence turns to where, how or who.
const STOPAT = new Set(['in', 'at', 'on', 'with', 'by', 'for', 'from', 'during', 'while', 'near', 'against', 'inside', 'outside', 'being', 'over',
  'called', 'through', 'served', 'held', 'into', 'onto', 'across', 'about', 'featuring', 'including', 'like', 'vs', 'under', 'behind', 'beside',
  'around', 'after', 'before', 'along', 'toward', 'towards', 'to', 'its', 'their', 'his', 'her', 'laid', 'directly', 'or', 'as', 'that', 'which']);
// "preparation and presentation of X", "plate of X", "scenic view of X" are about X.
const FRAME = new Set(['preparation', 'presentation', 'review', 'reviews', 'showcase', 'collection', 'view', 'views', 'scenic', 'scenes', 'montage',
  'compilation', 'footage', 'variety', 'selection', 'list', 'ranking', 'tour', 'demonstration', 'unboxing', 'comparison', 'making', 'process',
  'close', 'closeup', 'shots', 'shot', 'clips', 'dishes', 'dish', 'ambiance', 'ambience', 'interior', 'exterior', 'aerial', 'glimpse', 'plate',
  'bowl', 'cup', 'glass', 'box', 'pair', 'set', 'and', 'a', 'an', 'the', 'unique', 'various']);
const VAGUE = new Set(['video', 'reel', 'camera', 'screen', 'scene', 'scenes', 'content', 'moments', 'things', 'items', 'products', 'product',
  'something', 'setting', 'interface', 'process', 'routine', 'tips', 'lifestyle', 'story', 'outdoors', 'front', 'experience', 'experiences',
  'activities', 'spots', 'locations', 'hack', 'setup', 'display', 'room', 'area', 'stuff', 'characters', 'and', 'served']);
// -ing words that name a thing or a field, not an action in the video.
const NOT_VERB = new Set(['clothing', 'building', 'evening', 'morning', 'something', 'nothing', 'anything', 'everything', 'ceiling', 'wedding',
  'pudding', 'dumpling', 'stuffing', 'icing', 'frosting', 'topping', 'filling', 'dressing', 'seasoning', 'swimming', 'training', 'painting',
  'housewarming', 'spring', 'string', 'being', 'during', 'engineering', 'marketing', 'gaming', 'camping', 'parking', 'housing', 'catering',
  'branding', 'coding', 'programming', 'trading', 'investing', 'budgeting', 'banking', 'accounting', 'bedding', 'lighting', 'packaging', 'sibling']);
const isVerb = (w) => w.length > 4 && w.endsWith('ing') && !NOT_VERB.has(w);

// Short keys must be whole words ("bar" is not "barbecue"); longer ones may
// sit inside a phrase ("cafes & restaurants").
function has(raw, keys) {
  const text = raw.split('é').join('e');
  const toks = new Set(words(text));
  return keys.some((k) => (k.length > 4 || k.includes(' ') ? text.includes(k) : toks.has(k) || toks.has(k + 's')));
}

function good(ws) {
  if (ws.length < 2 || ws.length > 4 || STOPAT.has(ws[0])) return false;
  if (VAGUE.has(ws[ws.length - 1]) || isVerb(ws[ws.length - 1]) || ws.some((w) => /^[0-9]+$/.test(w))) return false;
  return !ws.every((w) => VAGUE.has(w) || w.length < 3);
}

// The noun phrase at the start of ws, optionally with "in <city>" when the
// reel is tagged with that place.
function core(ws, locs) {
  ws = ws.slice();
  while (ws.length && LEAD.has(ws[0])) ws.shift();
  if (!ws.length || STOPAT.has(ws[0])) return '';
  // "enjoying a vacation" is a clause; "breathing techniques" is a thing.
  const clause = (i) => isVerb(ws[i]) && (i + 1 >= ws.length || LEAD.has(ws[i + 1]) || STOPAT.has(ws[i + 1]));
  if (clause(0)) return '';
  const end = ws.findIndex((w, i) => i > 0 && (STOPAT.has(w) || clause(i)));
  let head = end > 0 ? ws.slice(0, end) : ws;
  let loc = '';
  if (end > 0 && ws[end] === 'in' && ws[end + 1] && locs.includes(ws[end + 1])) loc = ws[end + 1];
  if (head.length > 4) { const a = head.indexOf('and'); head = a >= 2 ? head.slice(0, a) : []; }
  while (head.length && (head[head.length - 1] === 'and' || head[head.length - 1] === 'or')) head.pop();
  if (!good(head)) return '';
  if (loc && head.length <= 3) head = head.concat(['in', loc]);
  return head.join(' ');
}

function clip(phrase, locations) {
  const locs = (locations || []).map((l) => words(String(l).split('é').join('e'))[0]).filter(Boolean);
  let ws = String(phrase || '').toLowerCase().split('é').join('e').replace(/[^a-z0-9' ]+/g, ' ').split(' ').filter(Boolean);
  const of = ws.indexOf('of');
  if (of > 0 && ws.slice(0, of).every((w) => FRAME.has(w) || LEAD.has(w))) ws = ws.slice(of + 1);
  // The thing after the last action: "man reviewing and unboxing Ajmal
  // Aristocrat perfume" -> "ajmal aristocrat perfume".
  // A gerund right after another one describes the thing ("explaining
  // coding agent skills"), so it does not start a new phrase.
  const verbs = [];
  ws.forEach((w, i) => { if (i < 9 && isVerb(w) && !(i > 0 && isVerb(ws[i - 1]))) verbs.push(i); });
  for (let k = verbs.length - 1; k >= 0; k -= 1) {
    const rest = core(ws.slice(verbs[k] + 1), locs);
    if (rest) return rest;
  }
  if (verbs.length) {
    const before = ws.slice(0, verbs[0]);
    if (before.every((w) => LEAD.has(w) || w.length < 3)) return '';
    ws = before;
  }
  return core(ws, locs);
}

function short(name, max = 4) {
  const ws = words(name).filter((w) => w !== 'recipe' && w !== 'recipes');
  return ws.length && ws.length <= max ? ws.join(' ') : '';
}

function candidates() {
  const out = [];
  const add = (q, group, rid) => { if (q) out.push({ q, group, rid }); };
  // Places: "<kind> in <city>"
  (S.places || []).slice(0, 5).forEach((p) => {
    const text = p.reels.map((rid) => { const r = S.byId.get(rid); return r ? [r.category, r.sub, r.subject, r.name].join(' ') : ''; }).join(' ').toLowerCase();
    const kind = KINDS.find(([keys]) => has(text, keys));
    const city = String(p.place || '').toLowerCase().split(',')[0].trim();
    if (kind && city && city.length < 18) add(`${kind[1]} in ${city}`, 'place', '');
  });
  S.reels.forEach((r) => {
    const group = (r.category || r.sub || 'other').toLowerCase();
    const sub = String(r.sub || '').toLowerCase();
    (r.items || []).forEach((it) => {
      if (it.item_type === 'recipe') { const n = short(it.item_name, 3); if (n) add(n + ' recipe', 'recipe', r.id); }
    });
    // "Biceps Training" -> "biceps workout"
    const train = sub.match(/^([a-z ]+?) (training|workout|workouts|exercises)$/);
    if (train && words(train[1]).length <= 2) add(train[1] + ' workout', 'fitness', r.id);
    // "Horror Mystery Movies" -> "horror movie"
    if (/movie|film/.test(sub) && !/website|success|browsing/.test(sub)) { const w = words(sub)[0]; if (w && !/movie|film|and/.test(w)) add(w + ' movie', 'movie', r.id); }
    if (/series/.test(sub)) add('web series', 'series', r.id);
    add(clip(r.subject, r.locations), group, r.id);
  });
  return out;
}

// A stable shuffle per day, so phrases rotate without jumping on every repaint.
function daySeed() {
  const d = new Date();
  return d.getFullYear() * 400 + d.getMonth() * 32 + d.getDate();
}
function mix(list, seed) {
  const a = list.slice();
  let s = seed % 2147483647 || 7;
  for (let i = a.length - 1; i > 0; i -= 1) { s = (s * 16807) % 2147483647; const j = s % (i + 1); [a[i], a[j]] = [a[j], a[i]]; }
  return a;
}

let cache = { sig: '', list: [] };

export function libraryQueries(n = 7) {
  const sig = `${S.reels.length}:${(S.places || []).length}:${S.reels[0] ? S.reels[0].id : ''}:${daySeed()}`;
  if (cache.sig === sig) return cache.list.slice(0, n);
  const seen = new Set();
  const byGroup = new Map();
  mix(candidates(), daySeed()).forEach((c) => {
    if (seen.has(c.q)) return;
    seen.add(c.q);
    // Only phrases that find their reel (or any reel, for place combos).
    const hits = localSearch(c.q, 6);
    if (!hits.length) return;
    if (c.rid && !hits.some((h) => h.id === c.rid)) return;
    if (!byGroup.has(c.group)) byGroup.set(c.group, []);
    byGroup.get(c.group).push(c.q);
  });
  // Round robin across groups so one big category cannot fill the list;
  // places and recipes lead because they read most like a real question.
  const groups = Array.from(byGroup.keys()).sort((a, b) => rank(a) - rank(b));
  const list = [];
  for (let round = 0; list.length < 12 && round < 4; round += 1) {
    groups.forEach((g) => { const q = byGroup.get(g)[round]; if (q && list.length < 12) list.push(q); });
  }
  cache = { sig, list };
  return list.slice(0, n);
}

function rank(g) {
  if (g === 'place') return 0;
  if (g === 'recipe') return 1;
  if (g === 'fitness') return 2;
  return 3;
}

// Exposed for checking the phrase cleaner against real reel subjects.
export { clip as phraseFrom };
