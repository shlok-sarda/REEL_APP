from __future__ import annotations

import re
from collections import Counter


DOMAIN_ALIASES = {
    "travel": "Travel",
    "travel & food": "Travel & Food",
    "food & dining": "Travel & Food",
    "food": "Travel & Food",
    "food & local eats": "Food & Local Eats",
    "food & recipes": "Food & Recipes",
    "technology": "Technology",
    "entertainment": "Entertainment",
    "health & lifestyle": "Health & Lifestyle",
    "lifestyle": "Lifestyle",
    "travel destinations": "Travel Destinations",
    "travel accommodations": "Travel Accommodations",
    "local info": "Local Info",
    "fitness & health": "Fitness & Health",
    "learning & skills": "Learning & Skills",
    "finance & business": "Finance & Business",
    "career & money": "Career & Money",
    "personal growth": "Personal Growth",
    "miscellaneous": "Miscellaneous",
}


LOCATION_ALIASES = {
    "goa": "Goa",
    "north goa": "Goa",
    "south goa": "Goa",
    "banaras": "Varanasi",
    "banarasi": "Varanasi",
    "varanasi": "Varanasi",
    "kashi": "Varanasi",
    "hyderabad": "Hyderabad",
    "edinburgh": "Edinburgh",
    "nainital": "Nainital",
    "dehradun": "Dehradun",
    "thailand": "Thailand",
    "london": "London",
    "japan": "Japan",
    "usa": "USA",
    "bali": "Bali",
    "bangkok": "Bangkok",
    "candolim": "Goa",
    "noida": "Noida",
    "pokhara": "Pokhara",
    "meghalaya": "Meghalaya",
    "indonesia": "Indonesia",
    "nepal": "Nepal",
}


SUBDOMAIN_RULES = {
    "Food & Local Eats": [
        (r"\b(?:street food)\b", "street food"),
        (r"\b(?:seafood restaurants?|seafood spot)\b", "seafood restaurants"),
        (r"\b(?:restaurants?)\b", "restaurants"),
        (r"\b(?:cafes?)\b", "cafes"),
        (r"\b(?:late night non-veg|late night food)\b", "late-night food"),
        (r"\b(?:chocolate)\b", "dessert spots"),
    ],
    "Food & Recipes": [
        (r"\b(?:protein meals?|high protein meals?)\b", "protein recipes"),
        (r"\b(?:recipe|meals?)\b", "recipes"),
    ],
    "Travel Destinations": [
        (r"\b(?:island destinations?|travel inspiration|destinations?)\b", "destinations"),
        (r"\b(?:travel itinerary ideas?|itinerary)\b", "travel planning"),
    ],
    "Travel Accommodations": [
        (r"\b(?:stays?|accommodations?|hotel|resort|villa)\b", "stay"),
    ],
    "Lifestyle": [
        (r"\b(?:beauty and style|hair styling|styling routine)\b", "beauty and style"),
        (r"\b(?:men's clothing brands|mens clothing brands)\b", "men's clothing brands"),
        (r"\b(?:luxury outlet shopping)\b", "luxury outlet shopping"),
        (r"\b(?:sneaker culture)\b", "sneaker culture"),
        (r"\b(?:lifestyle ideas)\b", "lifestyle ideas"),
    ],
    "Career & Money": [
        (r"\b(?:job search tools)\b", "job search tools"),
        (r"\b(?:wealth education)\b", "wealth education"),
        (r"\b(?:money making ideas)\b", "money making ideas"),
        (r"\b(?:startup advice)\b", "startup advice"),
    ],
    "Personal Growth": [
        (r"\b(?:motivation and mindset)\b", "motivation and mindset"),
        (r"\b(?:general advice)\b", "general advice"),
    ],
    "Learning & Skills": [
        (r"\b(?:app)\b", "app"),
        (r"\b(?:english speaking)\b", "learning app"),
    ],
    "Fitness & Health": [
        (r"\b(?:workout accessories)\b", "fitness accessories"),
    ],
    "Local Info": [
        (r"\b(?:local rentals)\b", "local rentals"),
    ],
    "Travel & Food": [
        (r"\b(?:restaurant|cafe|coffee|seafood|street food|burger|dining|food spot)\b", "restaurant"),
        (r"\b(?:recipe|drink|lemonade|americano|frappe)\b", "recipe"),
        (r"\b(?:budget stay|resort|villa|stay|hotel)\b", "stay"),
        (r"\b(?:trip|itinerary|travel hack|travel savings|packing|gear)\b", "travel planning"),
        (r"\b(?:culture|comparison|experience)\b", "cultural experience"),
        (r"\b(?:app|navigation|radarbot)\b", "travel utility"),
    ],
    "Technology": [
        (r"\b(?:earphones|earbuds|headphones|powerbeats|beats)\b", "audio device"),
        (r"\b(?:appliance|kitchen device|cooking device|onechef)\b", "kitchen device"),
        (r"\b(?:device|gadget|drone|note pro|neo 3)\b", "device"),
        (r"\b(?:innovation)\b", "innovation"),
        (r"\b(?:app|assistant|navigation|radarbot)\b", "app"),
        (r"\b(?:ai|chatgpt|cloud agents|seo)\b", "ai"),
        (r"\b(?:unboxing|consumer tech|smart device)\b", "consumer tech"),
    ],
    "Entertainment": [
        (r"\b(?:movie|film|series|drama|thriller|detective|zee5|adaptation)\b", "films and shows"),
        (r"\b(?:music|rap|song|ringtone)\b", "music"),
        (r"\b(?:humor)\b", "humor"),
        (r"\b(?:commentary)\b", "commentary"),
        (r"\b(?:trend|viral|edit)\b", "internet culture"),
    ],
    "Health & Lifestyle": [
        (r"\b(?:perfume|fragrance)\b", "fragrance"),
        (r"\b(?:photo pose|duo photo|trio photo|posing|photo trend)\b", "photo ideas"),
        (r"\b(?:calisthenics|fitness|workout)\b", "fitness"),
        (r"\b(?:health remedy|advice|wellness)\b", "wellness"),
    ],
    "Finance & Business": [
        (r"\b(?:marketing|gmail|open rates)\b", "marketing"),
        (r"\b(?:business|growth|potential|finance|savings)\b", "business and money"),
    ],
    "Miscellaneous": [
        (r"\b(?:labeling|name stamp)\b", "labeling"),
        (r"\b(?:goatedbhai|uncategorized|generic)\b", "uncertain"),
    ],
}


GLOBAL_SUBDOMAIN_RULES = [
    (r"\b(?:movie|film|series|drama|thriller|detective|zee5|adaptation)\b", "films and shows"),
    (r"\b(?:music|rap|song|ringtone)\b", "music"),
    (r"\b(?:photo pose|duo photo|trio photo|posing|photo trend)\b", "photo ideas"),
    (r"\b(?:perfume|fragrance)\b", "fragrance"),
]


PRODUCT_SIGNAL_RULES = [
    (r"\b(?:airpods?|earpods?|ear hooks?|earphones?|earbuds?|headphones?|powerbeats|beats)\b", ["audio device", "device"]),
    (r"\b(?:night light|lamp|light projector|projector light|starry night light)\b", ["device"]),
    (r"\b(?:appliance|kitchen device|cooking device|onechef|chef)\b", ["kitchen device", "device"]),
    (r"\b(?:wireless charger|charger|drone|gadget|device|hologram fan|fan)\b", ["device"]),
    (r"\b(?:perfume|fragrance)\b", ["fragrance"]),
    (r"\b(?:shirt|pant|pants|clothing|sneaker|sneakers|shoe|shoes|fashion)\b", ["men's clothing brands"]),
]


SPECIFIC_CATEGORY_HINTS = {
    "beauty and style": {
        "subdomains": ["beauty and style"],
        "item_type": "idea",
        "intent": "idea_to_try",
    },
    "men's clothing brands": {
        "subdomains": ["men's clothing brands"],
        "item_type": "product",
        "intent": "product_to_buy",
    },
    "sneaker culture": {
        "subdomains": ["sneaker culture"],
        "item_type": "product",
        "intent": "product_to_buy",
    },
    "luxury outlet shopping": {
        "subdomains": ["luxury outlet shopping"],
        "item_type": "place",
        "intent": "place_to_visit",
    },
    "lifestyle ideas": {
        "subdomains": ["lifestyle ideas"],
        "item_type": "idea",
        "intent": "idea_to_try",
    },
    "street food in varanasi": {
        "subdomains": ["street food", "restaurants"],
        "location": "Varanasi",
        "item_type": "place",
        "intent": "place_to_visit",
    },
    "late night non-veg in banaras": {
        "subdomains": ["late-night food", "restaurants"],
        "location": "Varanasi",
        "item_type": "place",
        "intent": "place_to_visit",
    },
    "cafes in varanasi": {
        "subdomains": ["cafes", "restaurants"],
        "location": "Varanasi",
        "item_type": "place",
        "intent": "place_to_visit",
    },
    "restaurants in goa": {
        "subdomains": ["restaurants"],
        "location": "Goa",
        "item_type": "place",
        "intent": "place_to_visit",
    },
    "seafood restaurants in goa": {
        "subdomains": ["seafood restaurants", "restaurants"],
        "location": "Goa",
        "item_type": "place",
        "intent": "place_to_visit",
    },
    "street food in goa": {
        "subdomains": ["street food", "restaurants"],
        "location": "Goa",
        "item_type": "place",
        "intent": "place_to_visit",
    },
    "goa stays & accommodations": {
        "subdomains": ["stay"],
        "location": "Goa",
        "item_type": "place",
        "intent": "place_to_visit",
    },
    "travel inspiration": {
        "subdomains": ["destinations"],
        "item_type": "place",
        "intent": "place_to_visit",
    },
    "travel itinerary ideas": {
        "subdomains": ["travel planning"],
        "item_type": "idea",
        "intent": "place_to_visit",
    },
    "island destinations indonesia": {
        "subdomains": ["destinations"],
        "location": "Indonesia",
        "item_type": "place",
        "intent": "place_to_visit",
    },
    "destinations in nepal": {
        "subdomains": ["destinations"],
        "location": "Nepal",
        "item_type": "place",
        "intent": "place_to_visit",
    },
    "high protein meals": {
        "subdomains": ["protein recipes", "recipes"],
        "item_type": "recipe",
        "intent": "recipe_to_make",
    },
    "entertainment recommendations": {
        "subdomains": ["films and shows"],
        "item_type": "media",
        "intent": "media_to_watch_or_hear",
    },
    "entertainment discovery": {
        "subdomains": ["films and shows"],
        "item_type": "media",
        "intent": "media_to_watch_or_hear",
    },
    "entertainment humor": {
        "subdomains": ["humor"],
        "item_type": "media",
        "intent": "media_to_watch_or_hear",
    },
    "entertainment commentary": {
        "subdomains": ["commentary"],
        "item_type": "media",
        "intent": "media_to_watch_or_hear",
    },
    "movies": {
        "subdomains": ["films and shows"],
        "item_type": "media",
        "intent": "media_to_watch_or_hear",
    },
    "fragrances & perfumes": {
        "subdomains": ["fragrance"],
        "item_type": "product",
        "intent": "product_to_buy",
    },
    "tech gadgets & accessories": {
        "subdomains": ["device"],
        "item_type": "product",
        "intent": "product_to_buy",
    },
    "ai technology": {
        "subdomains": ["ai"],
        "item_type": "app",
        "intent": "tool_to_use",
    },
    "technology innovation": {
        "subdomains": ["innovation"],
        "item_type": "idea",
        "intent": "general_reference",
    },
    "language learning tools": {
        "subdomains": ["learning app"],
        "item_type": "app",
        "intent": "tool_to_use",
    },
    "job search tools": {
        "subdomains": ["job search tools"],
        "item_type": "app",
        "intent": "tool_to_use",
    },
    "wealth education": {
        "subdomains": ["wealth education"],
        "item_type": "idea",
        "intent": "advice_to_remember",
    },
    "money making ideas": {
        "subdomains": ["money making ideas"],
        "item_type": "idea",
        "intent": "advice_to_remember",
    },
    "startup advice": {
        "subdomains": ["startup advice"],
        "item_type": "idea",
        "intent": "advice_to_remember",
    },
    "motivation and mindset": {
        "subdomains": ["motivation and mindset"],
        "item_type": "idea",
        "intent": "advice_to_remember",
    },
    "general advice": {
        "subdomains": ["advice"],
        "item_type": "idea",
        "intent": "advice_to_remember",
    },
    "workout accessories": {
        "subdomains": ["fitness accessories"],
        "item_type": "product",
        "intent": "product_to_buy",
    },
    "local rentals": {
        "subdomains": ["local rentals"],
        "item_type": "place",
        "intent": "place_to_visit",
    },
    "local food commentary": {
        "subdomains": ["local food"],
        "item_type": "place",
        "intent": "place_to_visit",
    },
}


VIBE_RULES = [
    (r"\bluxury|signature|premium\b", "luxury"),
    (r"\bbudget|affordable|savings\b", "budget"),
    (r"\bhidden|less known\b", "hidden"),
    (r"\bsunset|beach\b", "scenic"),
    (r"\bsmart|useful|life hack\b", "utility"),
]


INTENT_RULES = [
    (r"\b(?:restaurant|cafe|stay|resort|villa|trip|itinerary|travel)\b", "place_to_visit"),
    (r"\b(?:recipe|drink|make|cook|meal prep)\b", "recipe_to_make"),
    (r"\b(?:app|tool|assistant|navigation)\b", "tool_to_use"),
    (r"\b(?:perfume|device|gadget|product|unboxing|drone|earphones|earbuds|appliance)\b", "product_to_buy"),
    (r"\b(?:movie|series|show|film|drama|song|music)\b", "media_to_watch_or_hear"),
    (r"\b(?:pose|trend|advice|challenge)\b", "idea_to_try"),
]


ITEM_TYPE_RULES = [
    (r"\b(?:restaurant|cafe|coffee|burger|seafood|food spot|hotel|resort|villa|stay)\b", "place"),
    (r"\b(?:recipe|drink|meal prep|dish)\b", "recipe"),
    (r"\b(?:app|assistant|navigation|radarbot)\b", "app"),
    (r"\b(?:device|gadget|drone|earphones|earbuds|perfume|stamp|appliance|powerbeats|onechef)\b", "product"),
    (r"\b(?:movie|series|show|song|music|drama)\b", "media"),
    (r"\b(?:pose|challenge|advice|trend)\b", "idea"),
]


def normalize(value: str) -> str:
    return " ".join((value or "").strip().split())


def normalize_key(value: str) -> str:
    return normalize(value).lower()


def canonical_domain(primary_category: str) -> str:
    key = normalize_key(primary_category)
    return DOMAIN_ALIASES.get(key, normalize(primary_category) or "Miscellaneous")


def canonical_location(*texts: str) -> str:
    haystack = " ".join(normalize_key(text) for text in texts)
    for alias, canonical in sorted(LOCATION_ALIASES.items(), key=lambda item: len(item[0]), reverse=True):
        if alias in haystack:
            return canonical
    return ""


def canonical_subdomains(domain: str, *texts: str) -> list[str]:
    haystack = " ".join(normalize_key(text) for text in texts)
    matches = []
    for pattern, label in SUBDOMAIN_RULES.get(domain, []):
        if re.search(pattern, haystack):
            matches.append(label)
    for pattern, label in GLOBAL_SUBDOMAIN_RULES:
        if re.search(pattern, haystack):
            matches.append(label)
    seen = []
    for label in matches:
        if label not in seen:
            seen.append(label)
    return seen


def infer_vibes(*texts: str) -> list[str]:
    haystack = " ".join(normalize_key(text) for text in texts)
    vibes = []
    for pattern, label in VIBE_RULES:
        if re.search(pattern, haystack) and label not in vibes:
            vibes.append(label)
    return vibes


def infer_intent(*texts: str) -> str:
    haystack = " ".join(normalize_key(text) for text in texts)
    for pattern, label in INTENT_RULES:
        if re.search(pattern, haystack):
            return label
    return "general_reference"


def infer_item_type(*texts: str) -> str:
    haystack = " ".join(normalize_key(text) for text in texts)
    for pattern, label in ITEM_TYPE_RULES:
        if re.search(pattern, haystack):
            return label
    return "general"


def product_signal_subdomains(*texts: str) -> list[str]:
    haystack = " ".join(normalize_key(text) for text in texts)
    matches = []
    for pattern, labels in PRODUCT_SIGNAL_RULES:
        if re.search(pattern, haystack):
            for label in labels:
                if label not in matches:
                    matches.append(label)
    return matches


def has_physical_product_signal(*texts: str) -> bool:
    return bool(product_signal_subdomains(*texts))


def merge_subdomains(*collections: list[str]) -> list[str]:
    merged = []
    for collection in collections:
        for item in collection or []:
            normalized = normalize(item)
            if normalized and normalized not in merged:
                merged.append(normalized)
    return merged


def normalize_entities(values: list[str]) -> list[str]:
    counter = Counter()
    for value in values or []:
        normalized = normalize(value)
        if normalized:
            counter[normalized] += 1
    return [item for item, _ in counter.most_common(10)]


def specific_category_hint(specific_category: str) -> dict:
    key = normalize_key(specific_category)
    return {**SPECIFIC_CATEGORY_HINTS.get(key, {})}


def refine_domain(domain: str, subdomains: list[str], item_type: str, location: str) -> str:
    subdomain_set = {normalize_key(item) for item in subdomains}
    if subdomain_set & {"fragrance"}:
        return "Health & Lifestyle"
    if subdomain_set & {"men's clothing brands", "sneaker culture", "beauty and style"}:
        return "Lifestyle"
    if subdomain_set & {"audio device", "kitchen device", "device", "consumer tech", "app", "learning app"}:
        return "Technology"
    if subdomain_set & {"beauty and style", "men's clothing brands", "luxury outlet shopping", "sneaker culture", "lifestyle ideas"}:
        return "Lifestyle"
    if subdomain_set & {"street food", "restaurants", "seafood restaurants", "cafes", "late-night food", "dessert spots", "local food"}:
        return "Food & Local Eats"
    if subdomain_set & {"protein recipes", "recipes"}:
        return "Food & Recipes"
    if subdomain_set & {"destinations"}:
        return "Travel Destinations"
    if subdomain_set & {"job search tools", "wealth education", "money making ideas", "startup advice"}:
        return "Career & Money"
    if subdomain_set & {"motivation and mindset", "advice"}:
        return "Personal Growth"
    if subdomain_set & {"fitness accessories"}:
        return "Fitness & Health"
    if subdomain_set & {"local rentals"}:
        return "Local Info"
    if subdomain_set & {"photo ideas", "fragrance", "fitness", "wellness"}:
        return "Health & Lifestyle"
    if subdomain_set & {"travel planning", "cultural experience"} and location and item_type == "place":
        return "Travel Destinations"
    if subdomain_set & {"restaurant", "recipe", "stay", "travel planning", "cultural experience", "travel utility"}:
        return "Travel & Food"
    if location and domain == "Travel":
        return "Travel & Food"
    if subdomain_set & {"films and shows", "music", "internet culture", "humor", "commentary"}:
        return "Entertainment"
    if subdomain_set & {"ai", "app", "device", "consumer tech", "audio device", "kitchen device", "innovation", "learning app"}:
        return "Technology"
    if subdomain_set & {"marketing", "business and money"}:
        return "Finance & Business"
    if item_type == "media":
        return "Entertainment"
    if item_type in {"app", "product"} and domain == "Technology":
        return "Technology"
    return domain
