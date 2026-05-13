import argparse
import csv
import hashlib
import json
import math
import re
import sqlite3
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from statistics import mean
from urllib.parse import urlparse

from api_config import get_openai_client


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DB = BASE_DIR / "app.db"
EMBEDDING_MODEL = "text-embedding-3-small"
FALLBACK_EMBEDDING_DIM = 96
AGGREGATION_SIMILARITY_THRESHOLDS = {
    "Travel": 0.73,
    "Products & Apps": 0.77,
    "Food": 0.76,
    "Technology": 0.78,
    "Entertainment": 0.79,
    "Health & Lifestyle": 0.76,
    "Finance & Business": 0.78,
    "Miscellaneous": 0.84,
}
TRAVEL_LOCATION_ALIASES = {
    "north goa": "Goa",
    "south goa": "Goa",
    "goa": "Goa",
    "agonda": "Goa",
    "mandrem": "Goa",
    "banaras": "Varanasi",
    "banarasi": "Varanasi",
    "varanasi": "Varanasi",
    "kashi": "Varanasi",
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


KEYWORD_RULES = {
    "technology": [
        (r"\b(?:chatgpt|seo|search queries|cloud agents?|ai)\b", "AI & Future Tech", "theme", 0.84),
        (r"\b(?:gmail|open rates?|marketing)\b", "Marketing Tactics", "topic_type", 0.8),
    ],
    "entertainment": [
        (r"\bedit\b", "Celebrity Edits", "format_type", 0.76),
        (r"\b(?:film|movie|movies|drama|thriller|adaptation|zee5|detective|tv)\b", "Films & Shows", "topic_type", 0.9),
        (r"\b(?:music|rap|ringtone|song|songs)\b", "Music", "topic_type", 0.82),
    ],
    "travel": [
        (r"\bgoa\b", "Goa", "location", 0.94),
        (r"\bnorth goa\b", "Goa", "location", 0.94),
        (r"\bagonda\b", "Goa", "location", 0.92),
        (r"\bmandrem\b", "Goa", "location", 0.92),
        (r"\bhyderabad\b", "Hyderabad", "location", 0.9),
        (r"\bnainital\b", "Nainital", "location", 0.94),
        (r"\bdehradun\b", "Dehradun", "location", 0.94),
        (r"\b(?:airline|travel hack|travel savings|budget travel|packing)\b", "Travel Tips & Utilities", "topic_type", 0.82),
    ],
    "food": [
        (r"\b(?:lemonade|recipe|drink|frappe|americano|coffee|burger|chocolate)\b", "Food & Drinks", "topic_type", 0.84),
    ],
    "health": [
        (r"\b(?:pose|posing|photo pose|duo photo|trio photo|photo trend)\b", "Photo Ideas", "activity_type", 0.9),
        (r"\bcalisthenics\b", "Calisthenics", "fitness_type", 0.9),
        (r"\b(?:health remedy|life advice)\b", "Advice & Wellness", "topic_type", 0.76),
    ],
    "finance": [
        (r"\b(?:marketing|gmail|open rates?)\b", "Marketing Tactics", "topic_type", 0.84),
        (r"\b(?:growth potential|business)\b", "Business Ideas & Potential", "topic_type", 0.8),
    ],
    "miscellaneous": [
        (r"\b(?:goatedbhai|uncategorized)\b", "Unsorted Finds", "topic_type", 0.55),
    ],
    "products & apps": [
        (r"\b(?:radarbot|essembl|prank app|app that helps|styling assistant)\b", "Apps & Tools", "product_type", 0.9),
        (r"\b(?:powerbeats|earphones|headphones)\b", "Audio Devices", "product_type", 0.88),
        (r"\b(?:onechef|note pro|device|gadget|drone|coffee machine)\b", "Gadgets & Devices", "product_type", 0.84),
        (r"\b(?:perfume|fragrance)\b", "Fragrances", "product_type", 0.88),
        (r"\b(?:name stamp|labeling)\b", "Kids Labeling Products", "product_type", 0.9),
        (r"\bgarment roller\b", "Travel Utility Products", "product_type", 0.84),
    ],
}


PROMOTION_THRESHOLDS = {
    "travel": 3,
    "food": 3,
    "technology": 3,
    "health": 3,
    "finance": 3,
    "entertainment": 3,
    "products & apps": 3,
    "miscellaneous": 3,
}

VERY_HIGH_CONFIDENCE_PROMOTION = 0.91
EARLY_PROMOTION_ANCHOR_TYPES = {
    "location",
    "product_type",
    "activity_type",
    "fitness_type",
}
GENERIC_EARLY_PROMOTION_LABELS = {
    "travel ideas",
    "food & drinks",
    "tech & ai",
    "entertainment picks",
    "business & money",
    "lifestyle & advice",
    "other saved reels",
    "needs better extraction",
    "advice & wellness",
    "useful products",
}


DOMAIN_ALIASES = {
    "technology": "technology",
    "tech & gadgets": "technology",
    "travel": "travel",
    "travel & food": "travel",
    "food & culture": "travel",
    "food": "food",
    "health & lifestyle": "health",
    "fitness": "health",
    "fashion": "health",
    "finance & business": "finance",
    "entertainment": "entertainment",
    "products & apps": "products & apps",
    "miscellaneous": "miscellaneous",
}


VISIBLE_FALLBACK_TITLES = {
    "Travel": "Travel Ideas",
    "Food": "Food & Drinks",
    "Products & Apps": "Useful Products",
    "Technology": "Tech & AI",
    "Entertainment": "Entertainment Picks",
    "Health & Lifestyle": "Lifestyle & Advice",
    "Finance & Business": "Business & Money",
    "Miscellaneous": "Other Saved Reels",
}


MAX_PROMOTED_PER_PRIMARY = 2

FALLBACK_INTENT_RULES = {
    "Travel": [
        (r"\b(?:airline|travel hack|travel savings|packing|budget travel)\b", "Travel Hacks", 0.84),
        (r"\b(?:culture comparison|usa vs japan|comparison)\b", "Culture & Comparison", 0.9),
        (r"\b(?:hyderabad|experience|restaurant|cafe|coffee|burger|chocolate)\b", "Destinations & Experiences", 0.9),
    ],
    "Products & Apps": [
        (r"\b(?:powerbeats|earphones|headphones|audio)\b", "Audio Devices", 0.9),
        (r"\b(?:perfume|fragrance)\b", "Fragrances", 0.9),
        (r"\b(?:garment roller|name stamp|labeling|utility)\b", "Utility Products", 0.88),
    ],
    "Health & Lifestyle": [
        (r"\b(?:duo photo|trio photo|photo pose|posing|photo trend)\b", "Photo Ideas", 0.92),
        (r"\b(?:calisthenics|workout|fitness|strength challenge)\b", "Fitness", 0.9),
        (r"\b(?:private jet|luxury)\b", "Luxury Lifestyle", 0.86),
        (r"\b(?:health remedy|life advice|advice)\b", "Advice & Wellness", 0.82),
    ],
    "Finance & Business": [
        (r"\b(?:marketing|gmail|open rates?)\b", "Marketing Tactics", 0.86),
        (r"\b(?:growth potential|business|market)\b", "Business Ideas & Potential", 0.84),
    ],
    "Entertainment": [
        (r"\b(?:trend|viral|music video)\b", "Trends & Internet Culture", 0.82),
        (r"\b(?:commentary|concert|ringtone|song)\b", "Entertainment Picks", 0.76),
    ],
    "Miscellaneous": [
        (r"\b(?:generic|uncategorized|goatedbhai)\b", "Needs Better Extraction", 0.7),
    ],
    "Food": [
        (r"\b(?:lemonade|recipe|drink|food)\b", "Food & Drinks", 0.84),
    ],
    "Technology": [
        (r"\b(?:ai|chatgpt|cloud agents|seo)\b", "Tech & AI", 0.82),
    ],
}

DISPLAY_COMPACTION_FAMILIES = {
    "Travel": [
        ("Travel Ideas", {"Places & Perspectives", "Travel Ideas", "Travel Hacks", "Culture & Comparison", "Destinations & Experiences"}),
    ],
    "Products & Apps": [
        ("Personal & Utility Products", {"Utility Products", "Useful Products", "Audio Devices", "Fragrances"}),
    ],
    "Health & Lifestyle": [
        ("Lifestyle & Advice", {"Advice & Wellness", "Lifestyle & Advice", "Fitness", "Luxury Lifestyle"}),
    ],
    "Entertainment": [
        ("Entertainment Picks", {"Entertainment Picks", "Trends & Internet Culture"}),
    ],
}


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
    primary: str
    rows: list[ItemRow]
    received_at: str = ""
    anchor_key: str = ""
    anchor_label: str = ""
    anchor_type: str = ""
    anchor_confidence: float = 0.0
    intent_summary: str = ""
    intent_embedding: list[float] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)

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
    def summary_text(self) -> str:
        return " ".join(normalize(row.display_summary) for row in self.rows if normalize(row.display_summary))

    @property
    def combined_text(self) -> str:
        product_bits = []
        for row in self.rows:
            product_bits.extend(
                filter(
                    None,
                    [
                        normalize(row.product_name),
                        normalize(row.product_brand),
                        normalize(row.product_type),
                        normalize(row.folder),
                    ],
                )
            )
        return " | ".join(
            filter(
                None,
                [
                    self.primary,
                    " / ".join(self.secondary_categories),
                    " / ".join(self.item_names),
                    " / ".join(product_bits),
                    self.summary_text,
                ],
            )
        )


@dataclass
class Cluster:
    primary: str
    key: str
    label: str
    anchor_type: str
    profiles: list[ReelProfile] = field(default_factory=list)

    @property
    def unique_reel_count(self) -> int:
        return len({profile.reel_id for profile in self.profiles})

    @property
    def item_count(self) -> int:
        return sum(len(profile.rows) for profile in self.profiles)

    @property
    def avg_confidence(self) -> float:
        return round(mean(profile.anchor_confidence for profile in self.profiles), 3) if self.profiles else 0.0

    @property
    def recent_30d_count(self) -> int:
        if not self.profiles:
            return 0
        cutoff = datetime.now() - timedelta(days=30)
        count = 0
        for profile in self.profiles:
            if not profile.received_at:
                count += 1
                continue
            try:
                ts = datetime.fromisoformat(profile.received_at.replace("Z", "+00:00"))
            except ValueError:
                count += 1
                continue
            if ts >= cutoff:
                count += 1
        return count

    @property
    def promoted(self) -> bool:
        canonical_primary = DOMAIN_ALIASES.get(normalize_key(self.primary), normalize_key(self.primary))
        threshold = PROMOTION_THRESHOLDS.get(canonical_primary, 3)
        if self.unique_reel_count >= threshold and self.avg_confidence >= 0.72 and self.recent_30d_count >= min(threshold, 2):
            return True
        return (
            self.unique_reel_count >= 1
            and self.anchor_type in EARLY_PROMOTION_ANCHOR_TYPES
            and self.anchor_type != "visible_fallback"
            and normalize_key(self.label) not in GENERIC_EARLY_PROMOTION_LABELS
            and self.avg_confidence >= VERY_HIGH_CONFIDENCE_PROMOTION
        )

    @property
    def memory_embedding(self) -> list[float]:
        vectors = [profile.intent_embedding for profile in self.profiles if profile.intent_embedding]
        return mean_vector(vectors)


def build_cluster(
    primary: str,
    label: str,
    anchor_type: str,
    profiles: list[ReelProfile],
    key: str | None = None,
) -> Cluster:
    return Cluster(
        primary=primary,
        key=key or normalize_key(label),
        label=label,
        anchor_type=anchor_type,
        profiles=sorted(profiles, key=lambda profile: (profile.received_at, profile.reel_id)),
    )


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
        cached = self.cache.get(normalized)
        if cached is not None:
            return cached

        vector: list[float]
        if self.client is not None:
            try:
                response = self.client.embeddings.create(
                    model=EMBEDDING_MODEL,
                    input=normalized,
                    timeout=4.0,
                )
                vector = list(response.data[0].embedding)
            except Exception as exc:
                self.mode = "fallback"
                self.last_error = normalize(str(exc))
                vector = self._hashed_embedding(normalized)
        else:
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
    if normalized in TRAVEL_LOCATION_ALIASES:
        return TRAVEL_LOCATION_ALIASES[normalized]
    return " ".join(part.capitalize() for part in normalized.split())


def extract_location_entity(text: str) -> str:
    raw_text = normalize(text)
    lowered = normalize_key(raw_text)
    for source, target in sorted(TRAVEL_LOCATION_ALIASES.items(), key=lambda item: -len(item[0])):
        if re.search(rf"\b{re.escape(source)}\b", lowered):
            return target

    patterns = [
        r"\b(?:in|at|from|near)\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,2})\b",
        r"\b([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,2})\s+(?:beaches|beach|villas|villa|resorts|resort|restaurants|restaurant|cafes|cafe|itinerary)\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, raw_text)
        if match:
            return canonicalize_location(match.group(1))
    return ""


def derive_memory_label(profile: ReelProfile) -> str:
    text = profile.combined_text
    if profile.primary == "Travel":
        location = extract_location_entity(text)
        if location:
            return location
    return profile.anchor_label or profile.primary


def build_intent_summary(profile: ReelProfile) -> str:
    text = normalize_key(profile.combined_text)
    location = extract_location_entity(profile.combined_text)

    if profile.primary == "Travel":
        if re.search(r"\b(?:airline|travel hack|travel savings|packing|budget travel)\b", text):
            return f"{location} travel hacks" if location else "travel hacks and planning"
        if location:
            return f"{location} trip planning"
        if re.search(r"\b(?:restaurant|cafe|coffee|burger|beach|villa|resort|stay|itinerary)\b", text):
            return "trip planning and places to visit"
        return "travel planning and local discovery"

    if profile.primary == "Food":
        if re.search(r"\b(?:recipe|meal prep|how to make|ingredients|lemonade|drink)\b", text):
            return "recipes and drinks to make"
        if location:
            return f"{location} food places to try"
        return "food and drink places to try"

    if profile.primary == "Products & Apps":
        if re.search(r"\b(?:app|assistant|tool|navigation|productivity|styling)\b", text):
            return "useful apps and tools"
        if re.search(r"\b(?:earphones|headphones|audio|powerbeats)\b", text):
            return "audio gear to buy"
        if re.search(r"\b(?:perfume|fragrance)\b", text):
            return "personal care products to buy"
        return "useful products and gadgets"

    if profile.primary == "Technology":
        if re.search(r"\b(?:chatgpt|ai|cloud agent|seo)\b", text):
            return "ai and future tech ideas"
        return "technology ideas and tools"

    if profile.primary == "Entertainment":
        if re.search(r"\b(?:movie|film|series|show|thriller|drama|detective)\b", text):
            return "films and shows to watch"
        if re.search(r"\b(?:music|song|rap|ringtone)\b", text):
            return "music to listen to"
        return "entertainment ideas to explore"

    if profile.primary == "Health & Lifestyle":
        if re.search(r"\b(?:duo photo|trio photo|pose|photo trend)\b", text):
            return "photo ideas to copy"
        if re.search(r"\b(?:calisthenics|workout|fitness|strength challenge)\b", text):
            return "fitness routines to try"
        return "lifestyle advice and wellness"

    if profile.primary == "Finance & Business":
        if re.search(r"\b(?:marketing|open rates|gmail)\b", text):
            return "marketing ideas to use"
        return "business and money ideas"

    return "saved ideas to explore"


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


def infer_primary_domain(item_rows: list[ItemRow]) -> str:
    raw_primary = normalize(item_rows[0].primary)
    secondary_text = " / ".join(normalize(row.secondary) for row in item_rows if normalize(row.secondary))
    item_text = " / ".join(normalize(row.display_name) for row in item_rows if normalize(row.display_name))
    product_text = " / ".join(
        filter(
            None,
            [
                normalize(row.product_name)
                for row in item_rows
                if normalize(row.product_name)
            ]
            + [
                normalize(row.product_brand)
                for row in item_rows
                if normalize(row.product_brand)
            ]
            + [
                normalize(row.product_type)
                for row in item_rows
                if normalize(row.product_type)
            ]
            + [
                normalize(row.folder)
                for row in item_rows
                if normalize(row.folder)
            ],
        )
    )
    summary_text = " ".join(normalize(row.display_summary) for row in item_rows if normalize(row.display_summary))
    text = normalize_key(" | ".join(filter(None, [secondary_text, item_text, product_text, summary_text])))

    if re.search(r"\b(?:movie|movies|film|drama|thriller|adaptation|zee5|detective|tv|series)\b", text):
        return "Entertainment"
    if re.search(r"\b(?:duo photo|trio photo|photo pose|posing|photo trend)\b", text):
        return "Health & Lifestyle"
    if re.search(r"\b(?:app|assistant app|navigation app|styling app|radarbot|essembl|powerbeats|earphones|device|gadget|drone|note pro|stamp|labeling|perfume|fragrance|garment roller)\b", text):
        return "Products & Apps"
    if raw_primary == "Travel & Food":
        if re.search(r"\b(?:goa|north goa|agonda|mandrem|hyderabad|resort|hotel|airline|packing|culture comparison|budget travel|travel hack)\b", text):
            return "Travel"
        if re.search(r"\b(?:lemonade|recipe|burger|coffee|chocolate|frappe|americano|restaurant|cafe|drink)\b", text):
            return "Food"
        return "Travel"
    if raw_primary == "Finance & Business":
        return "Finance & Business"
    if raw_primary == "Health & Lifestyle":
        return "Health & Lifestyle"
    if raw_primary == "Technology":
        return "Technology"
    if raw_primary == "Entertainment":
        return "Entertainment"
    if raw_primary == "Miscellaneous":
        if re.search(r"\b(?:stamp|labeling)\b", text):
            return "Products & Apps"
        return "Miscellaneous"
    return raw_primary or "Miscellaneous"


def build_profiles(rows: list[ItemRow], reel_meta: dict[str, dict], user_id: str) -> list[ReelProfile]:
    grouped = defaultdict(list)
    for row in rows:
        if not row.url:
            continue
        grouped[row.url].append(row)

    profiles = []
    for url, item_rows in grouped.items():
        meta = reel_meta.get(url, {})
        reel_id = normalize(meta.get("id")) or f"reel_{shortcode_from_url(url)}"
        primary = infer_primary_domain(item_rows)
        profiles.append(
            ReelProfile(
                reel_id=reel_id,
                url=url,
                user_id=user_id,
                primary=primary,
                rows=item_rows,
                received_at=normalize(meta.get("received_at", "")),
            )
        )
    return profiles


def tokenize(text: str) -> list[str]:
    return [singularize(token) for token in re.findall(r"[a-zA-Z0-9]+", normalize_key(text)) if len(token) > 2]


def infer_anchor(profile: ReelProfile) -> None:
    primary_key = DOMAIN_ALIASES.get(normalize_key(profile.primary), normalize_key(profile.primary))
    text = profile.combined_text
    lowered = normalize_key(text)
    secondary_counter = Counter(normalize(row.secondary) for row in profile.rows if normalize(row.secondary))
    dominant_secondary = secondary_counter.most_common(1)[0][0] if secondary_counter else profile.primary

    for pattern, label, anchor_type, confidence in KEYWORD_RULES.get(primary_key, []):
        if re.search(pattern, lowered):
            profile.anchor_key = normalize_key(label)
            profile.anchor_label = label
            profile.anchor_type = anchor_type
            profile.anchor_confidence = confidence
            profile.evidence = [pattern, dominant_secondary]
            return

    if dominant_secondary and dominant_secondary != profile.primary:
        profile.anchor_key = normalize_key(dominant_secondary)
        profile.anchor_label = dominant_secondary
        profile.anchor_type = "secondary_category"
        profile.anchor_confidence = 0.6
        profile.evidence = [dominant_secondary]
        return

    tokens = tokenize(profile.combined_text)
    common = [token for token in tokens if token not in {"reel", "concept", "idea", "thing", "video", "saved"}]
    if common:
        label = " ".join(word.capitalize() for word in common[:3])
        profile.anchor_key = normalize_key(label)
        profile.anchor_label = label
        profile.anchor_type = "derived_keywords"
        profile.anchor_confidence = 0.5
        profile.evidence = common[:5]
        return

    profile.anchor_key = normalize_key(profile.primary)
    profile.anchor_label = profile.primary
    profile.anchor_type = "primary_fallback"
    profile.anchor_confidence = 0.48
    profile.evidence = [profile.primary]


def find_best_semantic_cluster(profile: ReelProfile, clusters: list[Cluster]) -> tuple[Cluster | None, float]:
    threshold = AGGREGATION_SIMILARITY_THRESHOLDS.get(profile.primary, 0.8)
    best_cluster = None
    best_score = 0.0
    for cluster in clusters:
        similarity = cosine_similarity(profile.intent_embedding, cluster.memory_embedding)
        if similarity > best_score:
            best_score = similarity
            best_cluster = cluster
    if best_cluster and best_score >= threshold:
        return best_cluster, round(best_score, 4)
    return None, round(best_score, 4)


def cluster_profiles(profiles: list[ReelProfile], embedding_backend: EmbeddingBackend) -> tuple[list[Cluster], list[dict]]:
    clusters_by_primary = defaultdict(list)
    debug_logs = []

    ordered_profiles = sorted(profiles, key=lambda profile: (profile.received_at, profile.reel_id, profile.url))
    for profile in ordered_profiles:
        infer_anchor(profile)
        profile.intent_summary = build_intent_summary(profile)
        profile.intent_embedding = embedding_backend.embed(profile.intent_summary)
        memory_label = derive_memory_label(profile)

        primary_clusters = clusters_by_primary[profile.primary]
        matched_cluster = None
        similarity = 0.0
        strategy = "new_memory"

        exact_anchor_match = None
        if profile.anchor_key and profile.anchor_confidence >= 0.9:
            for cluster in primary_clusters:
                if cluster.key == profile.anchor_key:
                    exact_anchor_match = cluster
                    break

        if exact_anchor_match is not None:
            matched_cluster = exact_anchor_match
            similarity = 1.0
            strategy = "exact_anchor"
        elif primary_clusters:
            matched_cluster, similarity = find_best_semantic_cluster(profile, primary_clusters)
            if matched_cluster is not None:
                strategy = "semantic_memory"

        if matched_cluster is not None:
            matched_cluster.profiles.append(profile)
            created = False
            matched_memory_key = matched_cluster.label
        else:
            new_cluster = build_cluster(
                profile.primary,
                memory_label,
                profile.anchor_type,
                [profile],
                key=normalize_key(memory_label),
            )
            primary_clusters.append(new_cluster)
            created = True
            matched_memory_key = new_cluster.label

        debug_logs.append(
            {
                "reel_id": profile.reel_id,
                "url": profile.url,
                "primary": profile.primary,
                "intent_summary": profile.intent_summary,
                "matched_memory_key": matched_memory_key,
                "similarity_score": round(similarity, 4),
                "created_new_memory": created,
                "strategy": strategy,
                "anchor_label": profile.anchor_label,
                "anchor_type": profile.anchor_type,
                "embedding_backend": embedding_backend.mode,
                "embedding_error": embedding_backend.last_error,
            }
        )

    clusters = []
    for primary in sorted(clusters_by_primary):
        clusters.extend(clusters_by_primary[primary])

    return sorted(
        clusters,
        key=lambda cluster: (
            cluster.primary.lower(),
            -cluster.unique_reel_count,
            -cluster.avg_confidence,
            cluster.label.lower(),
        ),
    ), debug_logs


def infer_fallback_intent(profile: ReelProfile, primary: str) -> tuple[str, float]:
    text = normalize_key(profile.combined_text)
    for pattern, label, confidence in FALLBACK_INTENT_RULES.get(primary, []):
        if re.search(pattern, text):
            return label, confidence
    return VISIBLE_FALLBACK_TITLES.get(primary, f"{primary} Picks"), 0.5


def should_surface_fallback_intent(primary: str, label: str, members: list[ReelProfile], confidence: float) -> bool:
    default_label = VISIBLE_FALLBACK_TITLES.get(primary, f"{primary} Picks")
    if label == default_label:
        return False
    if len(members) >= 2:
        return True
    return confidence >= 0.88 and primary in {"Travel", "Products & Apps", "Health & Lifestyle"}


def build_fallback_clusters(primary: str, weak_clusters: list[Cluster]) -> list[Cluster]:
    intent_profiles = defaultdict(list)
    intent_confidences = defaultdict(list)

    for cluster in weak_clusters:
        for profile in cluster.profiles:
            label, confidence = infer_fallback_intent(profile, primary)
            intent_profiles[label].append(profile)
            intent_confidences[label].append(confidence)

    surfaced_clusters = []
    catch_all_profiles = []
    catch_all_label = VISIBLE_FALLBACK_TITLES.get(primary, f"{primary} Picks")

    for label, profiles in sorted(intent_profiles.items(), key=lambda item: (item[0] != catch_all_label, -len(item[1]), item[0].lower())):
        avg_confidence = mean(intent_confidences[label]) if intent_confidences[label] else 0.0
        if should_surface_fallback_intent(primary, label, profiles, avg_confidence):
            surfaced_clusters.append(build_cluster(primary, label, "intent_fallback", profiles))
        else:
            catch_all_profiles.extend(profiles)

    if primary == "Travel":
        travel_mix_labels = {"Culture & Comparison", "Destinations & Experiences"}
        merged_profiles = []
        kept_clusters = []
        for cluster in surfaced_clusters:
            if cluster.label in travel_mix_labels:
                merged_profiles.extend(cluster.profiles)
            else:
                kept_clusters.append(cluster)
        if merged_profiles:
            kept_clusters.append(build_cluster(primary, "Places & Perspectives", "intent_fallback", merged_profiles))
        surfaced_clusters = kept_clusters

    elif primary == "Health & Lifestyle":
        keep_labels = {"Photo Ideas", "Advice & Wellness"}
        kept_clusters = []
        merged_profiles = []
        for cluster in surfaced_clusters:
            if cluster.label in keep_labels:
                kept_clusters.append(cluster)
            else:
                merged_profiles.extend(cluster.profiles)
        if merged_profiles:
            catch_all_profiles.extend(merged_profiles)
        surfaced_clusters = kept_clusters

    elif primary == "Products & Apps":
        keep_labels = {"Utility Products"}
        kept_clusters = []
        merged_profiles = []
        for cluster in surfaced_clusters:
            if cluster.label in keep_labels:
                kept_clusters.append(cluster)
            else:
                merged_profiles.extend(cluster.profiles)
        if merged_profiles:
            catch_all_profiles.extend(merged_profiles)
        surfaced_clusters = kept_clusters

    fallback_clusters = list(surfaced_clusters)
    if catch_all_profiles:
        fallback_clusters.append(build_cluster(primary, catch_all_label, "visible_fallback", catch_all_profiles))

    return sorted(
        fallback_clusters,
        key=lambda cluster: (
            1 if cluster.anchor_type == "visible_fallback" else 0,
            -cluster.unique_reel_count,
            cluster.label.lower(),
        ),
    )


def build_visible_clusters(clusters: list[Cluster]) -> list[Cluster]:
    grouped = defaultdict(list)
    for cluster in clusters:
        grouped[cluster.primary].append(cluster)

    visible = []
    for primary, primary_clusters in sorted(grouped.items(), key=lambda item: item[0].lower()):
        promoted_clusters = [cluster for cluster in primary_clusters if cluster.promoted]
        promoted_clusters.sort(key=lambda cluster: (-cluster.unique_reel_count, -cluster.avg_confidence, cluster.label.lower()))
        visible_promoted = promoted_clusters[:MAX_PROMOTED_PER_PRIMARY]
        overflow_promoted = promoted_clusters[MAX_PROMOTED_PER_PRIMARY:]
        weak_clusters = [cluster for cluster in primary_clusters if not cluster.promoted] + overflow_promoted

        visible.extend(visible_promoted)

        if weak_clusters:
            visible.extend(build_fallback_clusters(primary, weak_clusters))

    return visible


def compact_visible_clusters(clusters: list[Cluster]) -> list[Cluster]:
    grouped = defaultdict(list)
    for cluster in clusters:
        grouped[cluster.primary].append(cluster)

    compacted = []
    for primary, primary_clusters in sorted(grouped.items(), key=lambda item: item[0].lower()):
        remaining = list(primary_clusters)
        families = DISPLAY_COMPACTION_FAMILIES.get(primary, [])

        for compact_label, member_labels in families:
            matched = [
                cluster
                for cluster in remaining
                if cluster.anchor_type in {"intent_fallback", "visible_fallback", "display_compaction"}
                and cluster.label in member_labels
            ]
            if len(matched) <= 1:
                continue

            merged_profiles = []
            matched_ids = {id(cluster) for cluster in matched}
            for cluster in matched:
                merged_profiles.extend(cluster.profiles)
            remaining = [cluster for cluster in remaining if id(cluster) not in matched_ids]
            remaining.append(build_cluster(primary, compact_label, "display_compaction", merged_profiles))

        compacted.extend(
            sorted(
                remaining,
                key=lambda cluster: (
                    cluster.primary.lower(),
                    0 if cluster.promoted else 1,
                    -cluster.unique_reel_count,
                    cluster.label.lower(),
                ),
            )
        )

    return compacted


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
    return items


def build_graph_and_view(visible_clusters: list[Cluster], source_name: str, user_id: str, row_count: int) -> tuple[dict, dict]:
    umbrella_nodes = {}
    topic_nodes = []
    topic_lookup = {}
    reels = {}
    sections = []

    grouped_visible = defaultdict(list)
    for cluster in visible_clusters:
        grouped_visible[cluster.primary].append(cluster)

    for primary, clusters in sorted(grouped_visible.items(), key=lambda item: item[0].lower()):
        umbrella_id = topic_id("umbrella", primary)
        umbrella_nodes[primary] = {
            "id": umbrella_id,
            "name": primary,
            "kind": "umbrella",
            "parent_id": None,
            "aliases": [],
            "stats": {"unique_reel_count": 0, "topic_count": 0, "item_count": 0},
        }
        display_groups = []
        unique_reels = set()
        total_items = 0

        for cluster in clusters:
            group_items = cluster_items(cluster)
            group_topic_id = topic_id("topic", cluster.label, umbrella_id)
            topic_lookup[(primary, cluster.label)] = group_topic_id
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
                    "reason": cluster.anchor_type,
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

        umbrella_nodes[primary]["stats"] = {
            "unique_reel_count": len(unique_reels),
            "topic_count": len(clusters),
            "item_count": total_items,
        }
        sections.append(
            {
                "umbrella_id": umbrella_id,
                "umbrella_name": primary,
                "personalization_mode": "expanded" if any(cluster.promoted and cluster.anchor_type != "visible_fallback" for cluster in clusters) else "collapsed",
                "recommended_depth": "show_subtopics" if len(clusters) > 1 else "umbrella_only",
                "stats": {
                    "unique_reel_count": len(unique_reels),
                    "item_count": total_items,
                    "topic_count": len(clusters),
                },
                "display_groups": display_groups,
            }
        )

    user_profile = {
        "user_id": user_id,
        "recommended_depth_by_umbrella": {
            section["umbrella_id"]: section["recommended_depth"] for section in sections
        },
        "interest_scores": {"umbrella": {}, "topic": {}},
    }
    for umbrella in umbrella_nodes.values():
        user_profile["interest_scores"]["umbrella"][umbrella["id"]] = {
            "name": umbrella["name"],
            "score": round(umbrella["stats"]["unique_reel_count"] * 1.8 + umbrella["stats"]["topic_count"] * 1.2 + umbrella["stats"]["item_count"] * 0.35, 2),
            "unique_reel_count": umbrella["stats"]["unique_reel_count"],
            "topic_count": umbrella["stats"]["topic_count"],
            "item_count": umbrella["stats"]["item_count"],
        }
    for topic in topic_nodes:
        user_profile["interest_scores"]["topic"][topic["id"]] = {
            "name": topic["name"],
            "score": round(topic["stats"]["unique_reel_count"] * 1.8 + topic["stats"]["item_count"] * 0.35, 2),
            "unique_reel_count": topic["stats"]["unique_reel_count"],
            "item_count": topic["stats"]["item_count"],
        }

    graph = {
        "version": 1,
        "generated_on": datetime.now().date().isoformat(),
        "source": {"name": source_name, "row_count": row_count},
        "user_profile": user_profile,
        "topics": sorted(
            list(umbrella_nodes.values()) + topic_nodes,
            key=lambda node: (node["kind"], node["name"].lower()),
        ),
        "reels": sorted(reels.values(), key=lambda reel: reel["shortcode"]),
    }
    view = {
        "version": 1,
        "generated_from": graph["source"],
        "user_id": user_id,
        "sections": sorted(sections, key=lambda section: section["umbrella_name"].lower()),
    }
    return graph, view


def build_outputs(input_path: Path, user_id: str, db_path: Path | None = None) -> tuple[dict, dict, list[Cluster], list[Cluster], list[dict]]:
    rows, payload = load_rows(input_path)
    user_id = user_id or normalize(payload.get("user_id")) or "default"
    reel_meta = load_reel_metadata(db_path or DEFAULT_DB, user_id)
    profiles = build_profiles(rows, reel_meta, user_id)
    embedding_backend = EmbeddingBackend()
    leaf_clusters, debug_logs = cluster_profiles(profiles, embedding_backend)
    visible_clusters = compact_visible_clusters(build_visible_clusters(leaf_clusters))
    graph, view = build_graph_and_view(
        visible_clusters,
        source_name=input_path.name,
        user_id=user_id,
        row_count=len(rows),
    )
    return graph, view, leaf_clusters, visible_clusters, debug_logs


def write_debug_logs(output_path: Path, logs: list[dict]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as outfile:
        for log in logs:
            outfile.write(json.dumps(log, ensure_ascii=True) + "\n")


def main():
    parser = argparse.ArgumentParser(description="Build the ambitious personalized reel organization view.")
    parser.add_argument("--input", required=True, type=Path, help="Accumulated CSV or JSON.")
    parser.add_argument("--graph-output", required=True, type=Path, help="Output topic graph JSON.")
    parser.add_argument("--view-output", required=True, type=Path, help="Output personalized view JSON.")
    parser.add_argument("--debug-log-output", type=Path, default=None, help="Optional aggregation debug log output (JSONL).")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="Optional SQLite DB for reel metadata.")
    parser.add_argument("--user-id", default="", help="User id override.")
    args = parser.parse_args()

    graph, view, leaf_clusters, visible_clusters, debug_logs = build_outputs(args.input, args.user_id, args.db)
    args.graph_output.write_text(json.dumps(graph, indent=2), encoding="utf-8")
    args.view_output.write_text(json.dumps(view, indent=2), encoding="utf-8")
    debug_log_output = args.debug_log_output or args.view_output.with_name("aggregation_debug.jsonl")
    write_debug_logs(debug_log_output, debug_logs)

    promoted = [cluster for cluster in leaf_clusters if cluster.promoted]
    print(f"Leaf clusters: {len(leaf_clusters)}")
    print(f"Visible lists: {len(visible_clusters)}")
    print(f"Promoted lists: {len(promoted)}")
    print(f"Aggregation debug log: {debug_log_output}")
    for cluster in promoted:
        print(f"- {cluster.primary} -> {cluster.label} ({cluster.unique_reel_count} reels)")


if __name__ == "__main__":
    main()
