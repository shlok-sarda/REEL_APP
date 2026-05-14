import argparse
import csv
import hashlib
import json
import math
import re
import sqlite3
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from statistics import mean
from urllib.parse import urlparse

import numpy as np
from sklearn.cluster import DBSCAN

from api_config import get_openai_client

try:
    import hdbscan  # type: ignore
except Exception:  # pragma: no cover - optional dependency on live infra
    hdbscan = None


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DB = BASE_DIR / "app.db"
EMBEDDING_MODEL = "text-embedding-3-small"
FALLBACK_EMBEDDING_DIM = 128

LOCATION_ALIASES = {
    "goa": "Goa",
    "north goa": "Goa",
    "south goa": "Goa",
    "agonda": "Goa",
    "mandrem": "Goa",
    "banaras": "Varanasi",
    "banarasi": "Varanasi",
    "varanasi": "Varanasi",
    "kashi": "Varanasi",
    "hyderabad": "Hyderabad",
    "nainital": "Nainital",
    "dehradun": "Dehradun",
    "london": "London",
    "thailand": "Thailand",
    "india": "India",
    "japan": "Japan",
    "usa": "USA",
}

GENERIC_TOKENS = {
    "best",
    "great",
    "good",
    "saved",
    "reel",
    "reels",
    "ideas",
    "idea",
    "pick",
    "picks",
    "tips",
    "guide",
    "travel",
    "food",
    "dining",
    "place",
    "places",
    "spot",
    "spots",
    "restaurant",
    "restaurants",
    "cafe",
    "cafes",
    "recipe",
    "recipes",
    "item",
    "items",
    "video",
    "videos",
    "things",
    "thing",
}

RECIPE_HINTS = {"recipe", "recipes", "meal", "prep", "ingredients", "cook", "cooking", "dessert", "drink", "lemonade"}
PLACE_HINTS = {"restaurant", "restaurants", "cafe", "cafes", "coffee", "bakery", "street", "food", "resort", "villa", "beach", "itinerary"}
PRODUCT_HINTS = {"app", "tool", "device", "gadget", "earphones", "headphones", "perfume", "fragrance", "stamp", "roller"}
ENTERTAINMENT_HINTS = {"movie", "movies", "film", "series", "show", "shows", "drama", "thriller", "music", "song", "songs"}

INTENT_FAMILIES = {
    "recipe_to_make": "recipe",
    "place_to_visit": "place",
    "tool_to_use": "product",
    "product_to_buy": "product",
    "movie_to_watch": "entertainment",
    "music_to_listen": "entertainment",
    "idea_to_copy": "lifestyle",
    "advice_to_remember": "lifestyle",
    "saved_idea": "general",
}


def normalize(value: str) -> str:
    return " ".join((value or "").strip().split())


def normalize_key(value: str) -> str:
    return normalize(value).lower()


def shortcode_from_url(url: str) -> str:
    parts = [part for part in urlparse(url).path.split("/") if part]
    return parts[-1] if parts else normalize(url).replace("/", "_")


def slugify(value: str) -> str:
    chars = []
    last_dash = False
    for char in normalize_key(value):
        if char.isalnum():
            chars.append(char)
            last_dash = False
        elif not last_dash:
            chars.append("-")
            last_dash = True
    slug = "".join(chars).strip("-")
    return slug or "untitled"


def topic_id(kind: str, name: str, parent_id: str | None = None) -> str:
    base = f"{kind}:{normalize_key(name)}:{parent_id or ''}"
    short = hashlib.sha1(base.encode("utf-8")).hexdigest()[:8]
    return f"{kind}_{slugify(name)}_{short}"


def singularize(word: str) -> str:
    word = word.lower()
    if word.endswith("ies") and len(word) > 4:
        return word[:-3] + "y"
    if word.endswith("ses") and len(word) > 4:
        return word[:-2]
    if word.endswith("s") and not word.endswith("ss") and len(word) > 3:
        return word[:-1]
    return word


def pluralize_phrase(value: str) -> str:
    words = normalize(value).split()
    if not words:
        return value
    words[-1] = _pluralize_word(words[-1])
    return " ".join(words)


def _pluralize_word(word: str) -> str:
    lowered = word.lower()
    if lowered.endswith("y") and len(word) > 2 and lowered[-2] not in "aeiou":
        return word[:-1] + "ies"
    if lowered.endswith(("s", "x", "z", "ch", "sh")):
        return word + "es"
    return word + "s"


def tokenize(text: str) -> list[str]:
    return [singularize(token) for token in re.findall(r"[a-zA-Z0-9]+", normalize_key(text)) if len(token) > 2]


def normalize_vector(vector: list[float]) -> list[float]:
    if not vector:
        return []
    magnitude = math.sqrt(sum(value * value for value in vector))
    if magnitude == 0:
        return vector
    return [value / magnitude for value in vector]


def mean_vector(vectors: list[list[float]]) -> list[float]:
    vectors = [vector for vector in vectors if vector]
    if not vectors:
        return []
    size = len(vectors[0])
    accumulator = [0.0] * size
    for vector in vectors:
        for index, value in enumerate(vector):
            accumulator[index] += value
    count = float(len(vectors))
    return normalize_vector([value / count for value in accumulator])


def cosine_similarity(vector_a: list[float], vector_b: list[float]) -> float:
    if not vector_a or not vector_b or len(vector_a) != len(vector_b):
        return 0.0
    return sum(a * b for a, b in zip(vector_a, vector_b))


def canonicalize_location(value: str) -> str:
    normalized = normalize_key(value)
    if not normalized:
        return ""
    if normalized in LOCATION_ALIASES:
        return LOCATION_ALIASES[normalized]
    return " ".join(part.capitalize() for part in normalized.split())


def extract_location(text: str) -> str:
    raw_text = normalize(text)
    lowered = normalize_key(raw_text)
    for source, target in sorted(LOCATION_ALIASES.items(), key=lambda item: -len(item[0])):
        if re.search(rf"\b{re.escape(source)}\b", lowered):
            return target

    patterns = [
        r"\b(?:in|at|from|near)\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,2})\b",
        r"\b([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,2})\s+(?:beaches|beach|villas|villa|resorts|resort|restaurants|restaurant|cafes|cafe|itinerary|nightlife)\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, raw_text)
        if match:
            return canonicalize_location(match.group(1))
    return ""


def simplify_specific_category(value: str) -> str:
    value = normalize(value)
    if not value:
        return ""
    lowered = normalize_key(value)
    replacements = [
        ("restaurants in ", ""),
        ("street food in ", ""),
        ("resorts in ", ""),
        ("cafes in ", ""),
        ("coffee shops in ", ""),
        ("budget ", ""),
        ("best ", ""),
    ]
    for source, target in replacements:
        if lowered.startswith(source):
            return value[len(source):].strip().title() if not target else (target + value[len(source):]).strip()
    return value


@dataclass
class ItemRow:
    url: str
    primary: str
    secondary: str
    umbrella: str
    folder: str
    item_name: str
    summary: str
    contains_product: str
    product_name: str
    product_brand: str
    product_model: str
    product_type: str
    product_search_query: str
    best_buy_link: str
    amazon_link: str
    flipkart_link: str
    nykaa_link: str
    media_status: str
    local_video_path: str
    local_video_url: str
    thumbnail_path: str
    thumbnail_url: str

    @property
    def display_name(self) -> str:
        return self.item_name or self.folder or self.secondary or "Saved Reel"

    @property
    def display_summary(self) -> str:
        return self.summary or "No structured summary captured yet."


@dataclass
class ReelProfile:
    reel_id: str
    url: str
    user_id: str
    broad_primary: str
    rows: list[ItemRow]
    received_at: str = ""
    raw_primary: str = ""
    location: str = ""
    save_intent: str = ""
    semantic_tags: list[str] = field(default_factory=list)
    semantic_text: str = ""
    embedding: list[float] = field(default_factory=list)

    @property
    def secondary_categories(self) -> list[str]:
        values = []
        seen = set()
        for row in self.rows:
            key = normalize_key(row.secondary)
            if key and key not in seen:
                seen.add(key)
                values.append(row.secondary)
        return values

    @property
    def item_names(self) -> list[str]:
        values = []
        seen = set()
        for row in self.rows:
            key = normalize_key(row.display_name)
            if key and key not in seen:
                seen.add(key)
                values.append(row.display_name)
        return values

    @property
    def entities(self) -> list[str]:
        values = []
        seen = set()
        for row in self.rows:
            for value in [
                row.display_name,
                row.product_name,
                row.product_brand,
                row.product_model,
                row.product_type,
                row.folder,
            ]:
                key = normalize_key(value)
                if key and key not in seen:
                    seen.add(key)
                    values.append(normalize(value))
        return values

    @property
    def summary_text(self) -> str:
        return " ".join(normalize(row.display_summary) for row in self.rows if normalize(row.display_summary))


@dataclass
class Cluster:
    umbrella: str
    label: str
    profiles: list[ReelProfile]
    cluster_id: str
    coherence: float
    engine: str

    @property
    def unique_reel_count(self) -> int:
        return len({profile.reel_id for profile in self.profiles})

    @property
    def item_count(self) -> int:
        return sum(len(profile.rows) for profile in self.profiles)

    @property
    def recent_30d_count(self) -> int:
        count = 0
        cutoff = datetime.now().timestamp() - (30 * 24 * 60 * 60)
        for profile in self.profiles:
            if not profile.received_at:
                count += 1
                continue
            try:
                ts = datetime.fromisoformat(profile.received_at.replace("Z", "+00:00")).timestamp()
            except ValueError:
                count += 1
                continue
            if ts >= cutoff:
                count += 1
        return count


class EmbeddingBackend:
    def __init__(self):
        self.cache: dict[str, list[float]] = {}
        self.mode = "fallback"
        self.last_error = ""
        self.client = None
        try:
            self.client = get_openai_client()
            self.mode = "openai"
        except Exception as exc:
            self.last_error = normalize(str(exc))

    def embed(self, text: str) -> list[float]:
        normalized = normalize(text)
        if not normalized:
            return []
        if normalized in self.cache:
            return self.cache[normalized]

        if self.client is not None:
            try:
                response = self.client.embeddings.create(
                    model=EMBEDDING_MODEL,
                    input=normalized,
                    timeout=8.0,
                )
                vector = normalize_vector(list(response.data[0].embedding))
                self.cache[normalized] = vector
                return vector
            except Exception as exc:  # pragma: no cover - networked runtime
                self.mode = "fallback"
                self.last_error = normalize(str(exc))

        vector = self._hashed_embedding(normalized)
        self.cache[normalized] = vector
        return vector

    def _hashed_embedding(self, text: str) -> list[float]:
        vector = [0.0] * FALLBACK_EMBEDDING_DIM
        tokens = tokenize(text)
        if not tokens:
            return vector
        for token in tokens:
            digest = hashlib.sha1(token.encode("utf-8")).hexdigest()
            bucket = int(digest[:8], 16) % FALLBACK_EMBEDDING_DIM
            sign = -1.0 if int(digest[8:10], 16) % 2 else 1.0
            vector[bucket] += sign
        return normalize_vector(vector)


def _build_item_rows(raw_rows: list[dict]) -> list[ItemRow]:
    rows = []
    for row in raw_rows:
        rows.append(
            ItemRow(
                url=normalize(row.get("URL")),
                primary=normalize(row.get("Primary Category")),
                secondary=normalize(row.get("Secondary Category")),
                umbrella=normalize(row.get("Umbrella Folder") or row.get("Umbrella Category") or row.get("Primary Category")),
                folder=normalize(row.get("Folder")),
                item_name=normalize(row.get("Item Name")),
                summary=normalize(row.get("Summary")),
                contains_product=normalize(row.get("Contains Product")),
                product_name=normalize(row.get("Product Name")),
                product_brand=normalize(row.get("Product Brand")),
                product_model=normalize(row.get("Product Model")),
                product_type=normalize(row.get("Product Type")),
                product_search_query=normalize(row.get("Product Search Query")),
                best_buy_link=normalize(row.get("Best Buy Link")),
                amazon_link=normalize(row.get("Amazon Link")),
                flipkart_link=normalize(row.get("Flipkart Link")),
                nykaa_link=normalize(row.get("Nykaa Link")),
                media_status=normalize(row.get("Media Status")),
                local_video_path=normalize(row.get("Local Video Path")),
                local_video_url=normalize(row.get("Local Video URL")),
                thumbnail_path=normalize(row.get("Thumbnail Path")),
                thumbnail_url=normalize(row.get("Thumbnail URL")),
            )
        )
    return rows


def load_rows(path: Path) -> tuple[list[ItemRow], dict]:
    if path.suffix.lower() == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        return _build_item_rows(payload.get("rows", [])), payload
    with path.open(newline="", encoding="utf-8") as infile:
        return _build_item_rows(list(csv.DictReader(infile))), {}


def load_reel_metadata(db_path: Path, user_id: str) -> dict[str, dict]:
    if not db_path.exists():
        return {}
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "select id, user_id, url, received_at from reels where user_id = ? order by received_at, id",
        (user_id,),
    ).fetchall()
    conn.close()
    return {normalize(row["url"]): dict(row) for row in rows}


def infer_broad_primary(item_rows: list[ItemRow]) -> str:
    raw_primary = normalize(item_rows[0].primary)
    text = normalize_key(
        " | ".join(
            filter(
                None,
                [
                    raw_primary,
                    " / ".join(normalize(row.secondary) for row in item_rows if normalize(row.secondary)),
                    " / ".join(normalize(row.display_name) for row in item_rows if normalize(row.display_name)),
                    " / ".join(normalize(row.product_type) for row in item_rows if normalize(row.product_type)),
                    " ".join(normalize(row.display_summary) for row in item_rows if normalize(row.display_summary)),
                ],
            )
        )
    )

    if any(token in text for token in ["movie", "film", "series", "show", "drama", "thriller", "music", "song", "rap"]):
        return "Entertainment"
    if any(token in text for token in ["app", "assistant", "tool", "device", "gadget", "earphones", "headphones", "perfume", "fragrance", "stamp", "roller"]):
        return "Products & Apps"
    if raw_primary == "Travel & Food":
        if any(token in text for token in ["recipe", "meal prep", "ingredients", "lemonade", "drink", "dessert"]):
            return "Food"
        if any(token in text for token in ["restaurant", "cafe", "coffee", "burger", "street food"]):
            return "Food"
        return "Travel"
    if raw_primary:
        return raw_primary
    return "Miscellaneous"


def infer_intent(profile: ReelProfile) -> str:
    text = normalize_key(" | ".join([profile.raw_primary, " / ".join(profile.secondary_categories), " / ".join(profile.entities), profile.summary_text]))
    if any(token in text for token in ["recipe", "meal prep", "ingredients", "cook", "dessert", "drink", "lemonade"]):
        return "recipe_to_make"
    if any(token in text for token in ["restaurant", "cafe", "coffee", "burger", "street food", "resort", "villa", "nightlife", "itinerary", "beach"]):
        return "place_to_visit"
    if any(token in text for token in ["app", "assistant", "tool", "navigation", "styling"]):
        return "tool_to_use"
    if any(token in text for token in ["earphones", "headphones", "perfume", "fragrance", "device", "gadget", "drone"]):
        return "product_to_buy"
    if any(token in text for token in ["movie", "film", "series", "show", "thriller", "drama"]):
        return "movie_to_watch"
    if any(token in text for token in ["music", "song", "ringtone", "rap"]):
        return "music_to_listen"
    if any(token in text for token in ["pose", "photo", "style", "outfit"]):
        return "idea_to_copy"
    if any(token in text for token in ["advice", "remedy", "wellness", "fitness", "calisthenics"]):
        return "advice_to_remember"
    return "saved_idea"


def derive_semantic_tags(profile: ReelProfile) -> list[str]:
    tags = []
    if profile.location:
        tags.append(profile.location)
    tags.append(profile.broad_primary)
    tags.append(profile.save_intent)
    for category in profile.secondary_categories:
        simple = simplify_specific_category(category)
        if simple:
            tags.append(simple)
    for entity in profile.entities[:6]:
        tags.append(entity)
    seen = set()
    values = []
    for tag in tags:
        key = normalize_key(tag)
        if key and key not in seen:
            seen.add(key)
            values.append(normalize(tag))
    return values


def build_semantic_text(profile: ReelProfile) -> str:
    fields = [
        f"primary: {profile.broad_primary}",
        f"source: {profile.raw_primary}",
        f"intent: {profile.save_intent}",
        f"specific: {' | '.join(profile.secondary_categories)}",
        f"entities: {' | '.join(profile.entities[:8])}",
        f"location: {profile.location}" if profile.location else "",
        f"tags: {' | '.join(profile.semantic_tags)}",
        f"summary: {profile.summary_text}",
    ]
    if profile.location:
        fields.append(f"focus: {profile.location} {profile.location} {profile.location}")
    return normalize(" ; ".join(field for field in fields if field))


def build_profiles(rows: list[ItemRow], reel_meta: dict[str, dict], user_id: str, embedding_backend: EmbeddingBackend) -> list[ReelProfile]:
    grouped = defaultdict(list)
    for row in rows:
        if row.url:
            grouped[row.url].append(row)

    profiles = []
    for url, item_rows in grouped.items():
        meta = reel_meta.get(url, {})
        profile = ReelProfile(
            reel_id=normalize(meta.get("id")) or f"reel_{shortcode_from_url(url)}",
            url=url,
            user_id=user_id,
            broad_primary=infer_broad_primary(item_rows),
            rows=item_rows,
            received_at=normalize(meta.get("received_at", "")),
            raw_primary=normalize(item_rows[0].primary),
        )
        profile.location = extract_location(" | ".join([profile.raw_primary, " / ".join(profile.secondary_categories), " / ".join(profile.entities), profile.summary_text]))
        profile.save_intent = infer_intent(profile)
        profile.semantic_tags = derive_semantic_tags(profile)
        profile.semantic_text = build_semantic_text(profile)
        profile.embedding = embedding_backend.embed(profile.semantic_text)
        profiles.append(profile)
    return sorted(profiles, key=lambda profile: (profile.received_at, profile.reel_id, profile.url))


def hybrid_distance(profile_a: ReelProfile, profile_b: ReelProfile) -> float:
    base = 1.0 - cosine_similarity(profile_a.embedding, profile_b.embedding)
    if profile_a.location and profile_a.location == profile_b.location:
        base -= 0.22
    if profile_a.location and profile_b.location and profile_a.location != profile_b.location and profile_a.save_intent == profile_b.save_intent == "place_to_visit":
        base += 0.12
    if profile_a.save_intent == profile_b.save_intent:
        base -= 0.08
    else:
        family_a = INTENT_FAMILIES.get(profile_a.save_intent, "general")
        family_b = INTENT_FAMILIES.get(profile_b.save_intent, "general")
        if family_a != family_b:
            base += 0.18
        elif family_a in {"entertainment", "lifestyle", "product"}:
            base += 0.06
    if profile_a.save_intent == "recipe_to_make" and profile_b.save_intent == "place_to_visit":
        base += 0.18
    if profile_a.save_intent == "place_to_visit" and profile_b.save_intent == "recipe_to_make":
        base += 0.18
    if profile_a.broad_primary == profile_b.broad_primary:
        base -= 0.03
    elif not (profile_a.location and profile_a.location == profile_b.location):
        base += 0.08
    entities_a = {normalize_key(entity) for entity in profile_a.entities}
    entities_b = {normalize_key(entity) for entity in profile_b.entities}
    shared_entities = entities_a & entities_b
    if shared_entities:
        base -= min(0.12, 0.04 * len(shared_entities))
    return float(max(0.0, min(1.0, base)))


def build_distance_matrix(profiles: list[ReelProfile]) -> np.ndarray:
    count = len(profiles)
    matrix = np.zeros((count, count), dtype=float)
    for i in range(count):
        for j in range(i + 1, count):
            distance = hybrid_distance(profiles[i], profiles[j])
            matrix[i, j] = distance
            matrix[j, i] = distance
    return matrix


def choose_cluster_params(count: int) -> tuple[int, int]:
    if count <= 8:
        return 2, 1
    if count <= 18:
        return 2, 2
    if count <= 45:
        return 3, 2
    return max(3, round(count * 0.08)), 2


def cluster_profiles(profiles: list[ReelProfile]) -> tuple[list[int], list[float], str]:
    if not profiles:
        return [], [], "none"
    if len(profiles) == 1:
        return [-1], [0.0], "single"

    distance_matrix = build_distance_matrix(profiles)
    min_cluster_size, min_samples = choose_cluster_params(len(profiles))

    if hdbscan is not None:
        clusterer = hdbscan.HDBSCAN(
            metric="precomputed",
            min_cluster_size=min_cluster_size,
            min_samples=min_samples,
            cluster_selection_method="eom",
        )
        labels = clusterer.fit_predict(distance_matrix)
        probabilities = getattr(clusterer, "probabilities_", np.ones(len(profiles)))
        return labels.tolist(), [float(value) for value in probabilities], "hdbscan"

    fallback_eps = 0.34 if len(profiles) <= 12 else 0.30
    clusterer = DBSCAN(metric="precomputed", eps=fallback_eps, min_samples=min_cluster_size)
    labels = clusterer.fit_predict(distance_matrix)
    probabilities = [1.0 if label >= 0 else 0.0 for label in labels]
    return labels.tolist(), probabilities, "dbscan_fallback"


def dominant_location(profiles: list[ReelProfile]) -> tuple[str, int]:
    counts = Counter(profile.location for profile in profiles if profile.location)
    if not counts:
        return "", 0
    return counts.most_common(1)[0]


def dominant_primary(profiles: list[ReelProfile]) -> tuple[str, int]:
    counts = Counter(profile.broad_primary for profile in profiles if profile.broad_primary)
    if not counts:
        return "Miscellaneous", 0
    return counts.most_common(1)[0]


def cluster_token_candidates(profiles: list[ReelProfile]) -> Counter:
    counter = Counter()
    for profile in profiles:
        for text in profile.secondary_categories + profile.entities:
            for token in tokenize(text):
                if token in GENERIC_TOKENS:
                    continue
                if token in {normalize_key(profile.location)}:
                    continue
                counter[token] += 1
    return counter


def resolve_cluster_umbrella(profiles: list[ReelProfile], label: str) -> str:
    location, location_count = dominant_location(profiles)
    unique_primaries = {profile.broad_primary for profile in profiles}
    if location and location_count >= 2 and len(unique_primaries) >= 2:
        return "Places"
    if any(profile.save_intent == "recipe_to_make" for profile in profiles):
        return "Recipes"
    if any(profile.save_intent == "place_to_visit" for profile in profiles) and location:
        return "Places"
    dominant, _ = dominant_primary(profiles)
    if dominant == "Food":
        return "Food"
    if dominant == "Health & Lifestyle":
        return "Lifestyle"
    if dominant == "Finance & Business":
        return "Business & Money"
    return dominant


def generate_cluster_title(profiles: list[ReelProfile]) -> str:
    location, location_count = dominant_location(profiles)
    intents = Counter(profile.save_intent for profile in profiles)
    top_intent = intents.most_common(1)[0][0] if intents else "saved_idea"
    tokens = cluster_token_candidates(profiles)

    if location and location_count >= max(2, math.ceil(len(profiles) * 0.4)):
        if top_intent == "place_to_visit":
            street_terms = sum(1 for profile in profiles if re.search(r"\bstreet food|stall|dish|van|thali\b", normalize_key(profile.semantic_text)))
            restaurant_terms = sum(1 for profile in profiles if re.search(r"\brestaurant|cafe|coffee|burger|bakery|spot|non-veg\b", normalize_key(profile.semantic_text)))
            if street_terms >= max(2, len(profiles) // 2 + 1):
                return f"Street Food in {location}"
            if restaurant_terms >= max(2, len(profiles) // 2 + 1):
                return f"Restaurants in {location}"
        return location

    if top_intent == "recipe_to_make":
        if tokens["chocolate"] and (tokens["dessert"] or tokens["brownie"] or tokens["mousse"]):
            return "Chocolate Desserts"
        if tokens["protein"]:
            return "Protein Recipes"
        if tokens["dessert"]:
            return "Desserts"
        if tokens["drink"] or tokens["lemonade"] or tokens["frappe"]:
            return "Drinks"
        return "Recipes"

    if top_intent == "tool_to_use":
        if tokens["navigation"]:
            return "Navigation Apps"
        if tokens["productivity"]:
            return "Productivity Apps"
        return "Apps & Tools"

    if top_intent == "product_to_buy":
        for candidate in ["keyboard", "earphone", "headphone", "fragrance", "perfume", "device", "gadget", "drone"]:
            if tokens[candidate]:
                return pluralize_phrase(candidate.title())
        return "Products to Buy"

    if top_intent == "movie_to_watch":
        if tokens["detective"]:
            return "Detective Movies & Series"
        return "Films & Shows"

    if top_intent == "music_to_listen":
        return "Music"

    if top_intent == "idea_to_copy":
        if tokens["photo"] or tokens["pose"]:
            return "Photo Ideas"
        return "Ideas to Copy"

    if top_intent == "advice_to_remember":
        if tokens["fitness"] or tokens["calisthenic"]:
            return "Fitness & Wellness"
        return "Advice & Wellness"

    for candidate, _count in tokens.most_common(4):
        if candidate in GENERIC_TOKENS:
            continue
        return candidate.title()
    dominant, _ = dominant_primary(profiles)
    return dominant or "Saved Finds"


def derive_noise_label(profile: ReelProfile) -> tuple[str, str]:
    text = normalize_key(profile.semantic_text)
    location = profile.location

    if profile.save_intent == "place_to_visit":
        if profile.broad_primary == "Food":
            if location and re.search(r"\bstreet food|stall|dish|van|thali\b", text):
                return "Food", f"Street Food in {location}"
            if location and re.search(r"\brestaurant|restaurants|cafe|cafes|coffee|burger|bakery|spot|non-veg\b", text):
                return "Food", f"Restaurants in {location}"
            if location:
                return "Food", f"{location} Food Spots"
        if location:
            return "Places", location
        return "Travel", "Travel Finds"

    if profile.save_intent == "recipe_to_make":
        if "chocolate" in text and any(token in text for token in ["dessert", "brownie", "mousse", "tiramisu"]):
            return "Recipes", "Chocolate Desserts"
        if "protein" in text:
            return "Recipes", "Protein Recipes"
        if any(token in text for token in ["dessert", "sweet", "brownie", "cheesecake", "donut", "mousse"]):
            return "Recipes", "Desserts"
        if any(token in text for token in ["drink", "lemonade", "frappe", "americano"]):
            return "Recipes", "Drinks"
        return "Recipes", "Recipes"

    if profile.save_intent == "tool_to_use":
        if "navigation" in text or "radarbot" in text:
            return "Products & Apps", "Navigation Apps"
        if "styling" in text or "essembl" in text:
            return "Products & Apps", "Style Apps"
        if "productivity" in text:
            return "Products & Apps", "Productivity Apps"
        return "Products & Apps", "Apps & Tools"

    if profile.save_intent == "product_to_buy":
        if any(token in text for token in ["earphone", "earphones", "headphone", "headphones", "powerbeats", "audio"]):
            return "Products & Apps", "Audio Devices"
        if any(token in text for token in ["perfume", "fragrance"]):
            return "Products & Apps", "Fragrances"
        if any(token in text for token in ["stamp", "labeling", "roller"]):
            return "Products & Apps", "Utility Products"
        if any(token in text for token in ["device", "gadget", "drone", "note pro", "onechef"]):
            return "Products & Apps", "Gadgets & Devices"
        return "Products & Apps", "Products to Try"

    if profile.save_intent == "movie_to_watch":
        if "detective" in text:
            return "Entertainment", "Detective Movies & Series"
        return "Entertainment", "Films & Shows"

    if profile.save_intent == "music_to_listen":
        return "Entertainment", "Music"

    if profile.save_intent == "idea_to_copy":
        if "photo" in text or "pose" in text:
            return "Lifestyle", "Photo Ideas"
        return "Lifestyle", "Style & Social Ideas"

    if profile.save_intent == "advice_to_remember":
        if "calisthenic" in text or "fitness" in text or "workout" in text:
            return "Lifestyle", "Fitness & Wellness"
        return "Lifestyle", "Advice & Wellness"

    if profile.broad_primary == "Finance & Business":
        if "marketing" in text or "gmail" in text:
            return "Business & Money", "Marketing Ideas"
        return "Business & Money", "Business Ideas"
    if profile.broad_primary == "Products & Apps":
        return "Products & Apps", "Useful Tech Products"
    if profile.broad_primary == "Miscellaneous":
        return "Miscellaneous", "Unsorted Finds"
    if profile.broad_primary == "Entertainment":
        return "Entertainment", "Entertainment Picks"
    if profile.broad_primary == "Travel":
        return "Travel", "Travel Perspectives"
    dominant = profile.broad_primary or "Other"
    return dominant, dominant


def build_density_clusters(profiles: list[ReelProfile]) -> tuple[list[Cluster], list[ReelProfile], list[dict], str]:
    labels, probabilities, engine = cluster_profiles(profiles)
    grouped = defaultdict(list)
    debug_logs = []

    for index, profile in enumerate(profiles):
        label = labels[index] if index < len(labels) else -1
        grouped[label].append(profile)
        debug_logs.append(
            {
                "reel_id": profile.reel_id,
                "url": profile.url,
                "broad_primary": profile.broad_primary,
                "location": profile.location,
                "save_intent": profile.save_intent,
                "semantic_text": profile.semantic_text,
                "cluster_label": int(label),
                "cluster_probability": round(probabilities[index], 4) if index < len(probabilities) else 0.0,
                "clustering_engine": engine,
            }
        )

    semantic_clusters = []
    noise_profiles = []
    for label, members in grouped.items():
        if label < 0:
            noise_profiles.extend(members)
            continue
        label_text = generate_cluster_title(members)
        umbrella = resolve_cluster_umbrella(members, label_text)
        member_vectors = [profile.embedding for profile in members if profile.embedding]
        pairwise_scores = []
        for i in range(len(member_vectors)):
            for j in range(i + 1, len(member_vectors)):
                pairwise_scores.append(cosine_similarity(member_vectors[i], member_vectors[j]))
        coherence = round(mean(pairwise_scores), 4) if pairwise_scores else 1.0
        semantic_clusters.append(
            Cluster(
                umbrella=umbrella,
                label=label_text,
                profiles=members,
                cluster_id=f"cluster_{label}",
                coherence=coherence,
                engine=engine,
            )
        )

    return semantic_clusters, noise_profiles, debug_logs, engine


def build_noise_clusters(profiles: list[ReelProfile]) -> list[Cluster]:
    grouped = defaultdict(list)
    for profile in profiles:
        umbrella, label = derive_noise_label(profile)
        grouped[(umbrella, label)].append(profile)

    clusters = []
    for (umbrella, label), members in grouped.items():
        clusters.append(
            Cluster(
                umbrella=umbrella,
                label=label,
                profiles=members,
                cluster_id=f"noise_{slugify(umbrella)}_{slugify(label)}",
                coherence=0.0,
                engine="noise",
            )
        )
    return sorted(clusters, key=lambda cluster: (cluster.umbrella.lower(), -cluster.unique_reel_count, cluster.label.lower()))


def merge_duplicate_labels(clusters: list[Cluster]) -> list[Cluster]:
    grouped = defaultdict(list)
    for cluster in clusters:
        grouped[(cluster.umbrella, normalize_key(cluster.label))].append(cluster)

    merged = []
    for (umbrella, _key), members in grouped.items():
        if len(members) == 1:
            merged.append(members[0])
            continue
        profiles = []
        for cluster in members:
            profiles.extend(cluster.profiles)
        merged.append(
            Cluster(
                umbrella=umbrella,
                label=members[0].label,
                profiles=profiles,
                cluster_id=members[0].cluster_id,
                coherence=max(cluster.coherence for cluster in members),
                engine=members[0].engine,
            )
        )
    return sorted(merged, key=lambda cluster: (cluster.umbrella.lower(), -cluster.unique_reel_count, cluster.label.lower()))


def cluster_items(cluster: Cluster) -> list[dict]:
    items = []
    seen = set()
    for profile in cluster.profiles:
        for row in profile.rows:
            key = (profile.url, normalize_key(row.display_name), normalize_key(row.display_summary))
            if key in seen:
                continue
            seen.add(key)
            items.append(
                {
                    "reel_id": profile.reel_id,
                    "name": row.display_name,
                    "summary": row.display_summary,
                    "url": profile.url,
                    "contains_product": row.contains_product,
                    "product_name": row.product_name,
                    "product_brand": row.product_brand,
                    "product_model": row.product_model,
                    "product_type": row.product_type,
                    "product_search_query": row.product_search_query,
                    "best_buy_link": row.best_buy_link,
                    "amazon_link": row.amazon_link,
                    "flipkart_link": row.flipkart_link,
                    "nykaa_link": row.nykaa_link,
                    "media_status": row.media_status,
                    "local_video_path": row.local_video_path,
                    "local_video_url": row.local_video_url,
                    "thumbnail_path": row.thumbnail_path,
                    "thumbnail_url": row.thumbnail_url,
                }
            )
    return sorted(items, key=lambda item: (item["name"].lower(), item["summary"].lower(), item["url"]))


def build_graph_and_view(clusters: list[Cluster], source_name: str, user_id: str, row_count: int) -> tuple[dict, dict]:
    umbrella_nodes = {}
    topic_nodes = []
    reels = {}
    sections = []

    grouped_visible = defaultdict(list)
    for cluster in clusters:
        grouped_visible[cluster.umbrella].append(cluster)

    for umbrella, umbrella_clusters in sorted(grouped_visible.items(), key=lambda item: item[0].lower()):
        umbrella_id = topic_id("umbrella", umbrella)
        umbrella_nodes[umbrella] = {
            "id": umbrella_id,
            "name": umbrella,
            "kind": "umbrella",
            "parent_id": None,
            "aliases": [],
            "stats": {"unique_reel_count": 0, "topic_count": 0, "item_count": 0},
        }
        display_groups = []
        unique_reels = set()
        total_items = 0

        for cluster in sorted(umbrella_clusters, key=lambda c: (-c.unique_reel_count, c.label.lower())):
            group_items = cluster_items(cluster)
            group_topic_id = topic_id("topic", cluster.label, umbrella_id)
            cluster_reel_ids = []
            cluster_sample_items = []

            for profile in cluster.profiles:
                unique_reels.add(profile.reel_id)
                reel = reels.setdefault(
                    profile.reel_id,
                    {
                        "id": profile.reel_id,
                        "url": profile.url,
                        "shortcode": shortcode_from_url(profile.url),
                        "topic_ids": [],
                        "umbrella_ids": [],
                        "items": [],
                    },
                )
                if group_topic_id not in reel["topic_ids"]:
                    reel["topic_ids"].append(group_topic_id)
                if umbrella_id not in reel["umbrella_ids"]:
                    reel["umbrella_ids"].append(umbrella_id)
                cluster_reel_ids.append(profile.reel_id)

                existing_item_keys = {
                    (normalize_key(item.get("name")), normalize_key(item.get("summary")))
                    for item in reel["items"]
                }
                for row in profile.rows:
                    item_payload = {
                        "name": row.display_name,
                        "summary": row.display_summary,
                        "url": profile.url,
                        "contains_product": row.contains_product,
                        "product_name": row.product_name,
                        "product_brand": row.product_brand,
                        "product_model": row.product_model,
                        "product_type": row.product_type,
                        "product_search_query": row.product_search_query,
                        "best_buy_link": row.best_buy_link,
                        "amazon_link": row.amazon_link,
                        "flipkart_link": row.flipkart_link,
                        "nykaa_link": row.nykaa_link,
                        "media_status": row.media_status,
                        "local_video_path": row.local_video_path,
                        "local_video_url": row.local_video_url,
                        "thumbnail_path": row.thumbnail_path,
                        "thumbnail_url": row.thumbnail_url,
                    }
                    item_key = (normalize_key(item_payload["name"]), normalize_key(item_payload["summary"]))
                    if item_key in existing_item_keys:
                        continue
                    existing_item_keys.add(item_key)
                    reel["items"].append(item_payload)

            for item in group_items[:5]:
                cluster_sample_items.append({"name": item["name"], "summary": item["summary"]})

            topic_node = {
                "id": group_topic_id,
                "name": cluster.label,
                "kind": "topic",
                "parent_id": umbrella_id,
                "aliases": [cluster.label],
                "stats": {
                    "unique_reel_count": len(set(cluster_reel_ids)),
                    "item_count": len(group_items),
                },
                "sample_items": cluster_sample_items,
                "sample_reels": sorted(set(cluster_reel_ids))[:8],
            }
            topic_nodes.append(topic_node)
            total_items += len(group_items)

            display_groups.append(
                {
                    "name": cluster.label,
                    "reason": cluster.engine,
                    "stats": {
                        "unique_reel_count": topic_node["stats"]["unique_reel_count"],
                        "item_count": topic_node["stats"]["item_count"],
                        "topic_count": 1,
                    },
                    "topics": [
                        {
                            "id": group_topic_id,
                            "name": cluster.label,
                            "stats": topic_node["stats"],
                            "sample_items": cluster_sample_items,
                        }
                    ],
                }
            )

        umbrella_nodes[umbrella]["stats"] = {
            "unique_reel_count": len(unique_reels),
            "topic_count": len(umbrella_clusters),
            "item_count": total_items,
        }
        sections.append(
            {
                "umbrella_id": umbrella_id,
                "umbrella_name": umbrella,
                "personalization_mode": "expanded",
                "recommended_depth": "show_subtopics" if len(umbrella_clusters) > 1 else "umbrella_only",
                "stats": {
                    "unique_reel_count": len(unique_reels),
                    "item_count": total_items,
                    "topic_count": len(umbrella_clusters),
                },
                "display_groups": display_groups,
            }
        )

    graph = {
        "version": 2,
        "generated_on": datetime.now().date().isoformat(),
        "source": {"name": source_name, "row_count": row_count},
        "user_profile": {
            "user_id": user_id,
            "recommended_depth_by_umbrella": {
                section["umbrella_id"]: section["recommended_depth"] for section in sections
            },
            "interest_scores": {"umbrella": {}, "topic": {}},
        },
        "topics": sorted(list(umbrella_nodes.values()) + topic_nodes, key=lambda node: (node["kind"], node["name"].lower())),
        "reels": sorted(reels.values(), key=lambda reel: reel["shortcode"]),
    }
    for umbrella in umbrella_nodes.values():
        graph["user_profile"]["interest_scores"]["umbrella"][umbrella["id"]] = {
            "name": umbrella["name"],
            "score": round(umbrella["stats"]["unique_reel_count"] * 1.8 + umbrella["stats"]["topic_count"] * 1.2 + umbrella["stats"]["item_count"] * 0.35, 2),
            "unique_reel_count": umbrella["stats"]["unique_reel_count"],
            "topic_count": umbrella["stats"]["topic_count"],
            "item_count": umbrella["stats"]["item_count"],
        }
    for topic in topic_nodes:
        graph["user_profile"]["interest_scores"]["topic"][topic["id"]] = {
            "name": topic["name"],
            "score": round(topic["stats"]["unique_reel_count"] * 1.8 + topic["stats"]["item_count"] * 0.35, 2),
            "unique_reel_count": topic["stats"]["unique_reel_count"],
            "item_count": topic["stats"]["item_count"],
        }

    view = {
        "version": 2,
        "generated_from": graph["source"],
        "user_id": user_id,
        "sections": sorted(sections, key=lambda section: section["umbrella_name"].lower()),
    }
    return graph, view


def write_debug_logs(output_path: Path, logs: list[dict]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as outfile:
        for log in logs:
            outfile.write(json.dumps(log, ensure_ascii=True) + "\n")


def build_outputs(input_path: Path, user_id: str, db_path: Path | None = None) -> tuple[dict, dict, list[Cluster], list[dict], str]:
    rows, payload = load_rows(input_path)
    resolved_user_id = user_id or normalize(payload.get("user_id")) or "default"
    embedding_backend = EmbeddingBackend()
    reel_meta = load_reel_metadata(db_path or DEFAULT_DB, resolved_user_id)
    profiles = build_profiles(rows, reel_meta, resolved_user_id, embedding_backend)
    semantic_clusters, noise_profiles, debug_logs, engine = build_density_clusters(profiles)
    noise_clusters = build_noise_clusters(noise_profiles)
    visible_clusters = merge_duplicate_labels(semantic_clusters + noise_clusters)
    graph, view = build_graph_and_view(
        visible_clusters,
        source_name=input_path.name,
        user_id=resolved_user_id,
        row_count=len(rows),
    )
    return graph, view, visible_clusters, debug_logs, engine


def main():
    parser = argparse.ArgumentParser(description="Semantic personalization engine for saved reels.")
    parser.add_argument("--input", required=True, type=Path, help="Accumulated CSV or JSON.")
    parser.add_argument("--graph-output", required=True, type=Path, help="Output topic graph JSON.")
    parser.add_argument("--view-output", required=True, type=Path, help="Output personalized view JSON.")
    parser.add_argument("--debug-log-output", type=Path, default=None, help="Optional clustering debug log output (JSONL).")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="Optional SQLite DB for reel metadata.")
    parser.add_argument("--user-id", default="", help="User id override.")
    args = parser.parse_args()

    graph, view, visible_clusters, debug_logs, engine = build_outputs(args.input, args.user_id, args.db)
    args.graph_output.write_text(json.dumps(graph, indent=2), encoding="utf-8")
    args.view_output.write_text(json.dumps(view, indent=2), encoding="utf-8")
    debug_path = args.debug_log_output or args.view_output.with_name("semantic_personalization_debug.jsonl")
    write_debug_logs(debug_path, debug_logs)

    print(f"Visible lists: {len(visible_clusters)}")
    print(f"Items: {sum(cluster.item_count for cluster in visible_clusters)}")
    print(f"Clustering engine: {engine}")
    print(f"Debug log: {debug_path}")
    for cluster in sorted(visible_clusters, key=lambda item: (item.umbrella.lower(), -item.unique_reel_count, item.label.lower())):
        print(f"- {cluster.umbrella} -> {cluster.label} ({cluster.unique_reel_count} reels)")


if __name__ == "__main__":
    main()
