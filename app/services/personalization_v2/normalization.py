from __future__ import annotations

import re
from collections import Counter


DOMAIN_ALIASES = {
    "generic": "Generic",
    "products & shopping": "Products & Shopping",
    "product & shopping": "Products & Shopping",
    "food & dining": "Food & Dining",
    "travel": "Travel",
    "travel": "Travel",
    "travel & food": "Travel & Food",
    "food & travel": "Travel & Food",
    "food": "Travel & Food",
    "food & local eats": "Food & Local Eats",
    "food & recipes": "Food & Recipes",
    "technology": "Technology",
    "entertainment": "Entertainment",
    "humor & commentary": "Entertainment",
    "health & lifestyle": "Health & Lifestyle",
    "lifestyle": "Lifestyle",
    "travel destinations": "Travel Destinations",
    "travel accommodations": "Travel Accommodations",
    "local info": "Local Info",
    "fitness & health": "Fitness & Health",
    "fitness": "Fitness & Health",
    "learning & skills": "Learning & Skills",
    "finance & business": "Finance & Business",
    "career & money": "Career & Money",
    "personal growth": "Personal Growth",
    "self improvement": "Personal Growth",
    "startup education": "Career & Money",
    "miscellaneous": "Miscellaneous",
}

CANONICAL_DOMAINS = {
    "Generic",
    "Products & Shopping",
    "Food & Dining",
    "Travel",
    "Travel & Food",
    "Food & Local Eats",
    "Food & Recipes",
    "Travel Destinations",
    "Travel Accommodations",
    "Technology",
    "Entertainment",
    "Health & Lifestyle",
    "Lifestyle",
    "Fitness & Health",
    "Learning & Skills",
    "Finance & Business",
    "Career & Money",
    "Personal Growth",
    "Local Info",
    "Miscellaneous",
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


SUBDOMAIN_ALIASES = {
    "restaurant": "restaurants",
    "restaurants": "restaurants",
    "food place": "restaurants",
    "food places": "restaurants",
    "restaurant place": "restaurants",
    "seafood": "seafood restaurants",
    "seafood restaurant": "seafood restaurants",
    "seafood restaurants": "seafood restaurants",
    "street food": "street food",
    "street food place": "street food",
    "street food places": "street food",
    "cafe": "cafes",
    "cafes": "cafes",
    "café": "cafes",
    "dessert": "dessert spots",
    "desserts": "dessert spots",
    "dessert spot": "dessert spots",
    "dessert spots": "dessert spots",
    "food product": "food products",
    "food products": "food products",
    "local food": "local food",
    "stay": "stay",
    "stays": "stay",
    "accommodation": "stay",
    "accommodations": "stay",
    "hotel": "stay",
    "villa": "stay",
    "resort": "stay",
    "destinations": "destinations",
    "destination": "destinations",
    "travel destination": "destinations",
    "travel inspiration": "destinations",
    "travel planning": "travel planning",
    "itinerary": "travel planning",
    "itineraries": "travel planning",
    "travel itinerary": "travel planning",
    "travel utility": "travel utility",
    "travel app": "travel utility",
    "cultural experience": "cultural experience",
    "recipe": "recipes",
    "recipes": "recipes",
    "protein recipe": "protein recipes",
    "protein recipes": "protein recipes",
    "movie": "films and shows",
    "movies": "films and shows",
    "film": "films and shows",
    "films": "films and shows",
    "show": "films and shows",
    "shows": "films and shows",
    "series": "films and shows",
    "music": "music",
    "song": "music",
    "songs": "music",
    "dance": "internet culture",
    "dance moves": "internet culture",
    "trend": "internet culture",
    "trends": "internet culture",
    "internet culture": "internet culture",
    "humor": "humor",
    "commentary": "commentary",
    "fragrance": "fragrance",
    "fragrances": "fragrance",
    "perfume": "fragrance",
    "perfumes": "fragrance",
    "beauty": "beauty and style",
    "style": "beauty and style",
    "beauty and style": "beauty and style",
    "hair styling": "beauty and style",
    "natural deodorant": "beauty and style",
    "natural deodorant products": "beauty and style",
    "home products": "home products",
    "home upgrades": "home products",
    "men's clothing": "men's clothing brands",
    "men's clothing brands": "men's clothing brands",
    "mens clothing brands": "men's clothing brands",
    "luxury outlet shopping": "luxury outlet shopping",
    "outlet shopping": "luxury outlet shopping",
    "slides and sandals": "slides and sandals",
    "sneaker culture": "sneaker culture",
    "lifestyle ideas": "lifestyle ideas",
    "wellness": "wellness",
    "fitness": "fitness",
    "photo ideas": "photo ideas",
    "app": "app",
    "apps": "app",
    "tool": "app",
    "tools": "app",
    "learning app": "learning app",
    "job search tools": "job search tools",
    "wealth education": "wealth education",
    "money making ideas": "money making ideas",
    "startup advice": "startup advice",
    "motivation": "motivation and mindset",
    "motivation and mindset": "motivation and mindset",
    "advice": "advice",
    "device": "device",
    "devices": "device",
    "gadget": "device",
    "gadgets": "device",
    "audio device": "audio device",
    "audio devices": "audio device",
    "kitchen device": "kitchen device",
    "kitchen devices": "kitchen device",
    "consumer tech": "consumer tech",
    "technology innovation": "innovation",
    "innovation": "innovation",
    "local rentals": "local rentals",
    "marketing": "marketing",
    "business and money": "business and money",
}


CANONICAL_ITEM_TYPES = {"place", "recipe", "app", "product", "media", "idea", "general"}
ITEM_TYPE_ALIASES = {
    "venue": "place",
    "destination": "place",
    "location": "place",
    "dish": "recipe",
    "meal": "recipe",
    "tool": "app",
    "software": "app",
    "website": "app",
    "digital product": "app",
    "gadget": "product",
    "device": "product",
    "movie": "media",
    "show": "media",
    "music": "media",
    "commentary": "media",
    "advice": "idea",
}


CANONICAL_INTENTS = {
    "place_to_visit",
    "recipe_to_make",
    "tool_to_use",
    "product_to_buy",
    "media_to_watch_or_hear",
    "idea_to_try",
    "advice_to_remember",
    "general_reference",
}
INTENT_ALIASES = {
    "visit": "place_to_visit",
    "go": "place_to_visit",
    "travel": "place_to_visit",
    "eat_out": "place_to_visit",
    "make_recipe": "recipe_to_make",
    "cook": "recipe_to_make",
    "use_tool": "tool_to_use",
    "download_tool": "tool_to_use",
    "buy_product": "product_to_buy",
    "shop": "product_to_buy",
    "watch": "media_to_watch_or_hear",
    "listen": "media_to_watch_or_hear",
    "consume_media": "media_to_watch_or_hear",
    "try_idea": "idea_to_try",
    "remember_advice": "advice_to_remember",
    "reference": "general_reference",
}


SUBDOMAIN_RULES = {
    "Food & Local Eats": [
        (r"\b(?:street food)\b", "street food"),
        (r"\b(?:seafood restaurants?|seafood spot)\b", "seafood restaurants"),
        (r"\b(?:biryani|bbq|barbecue|kebab|mandi|chicken fry|cafe|cake|dessert)\b", "local food"),
        (r"\b(?:restaurants?)\b", "restaurants"),
        (r"\b(?:spot|food place|place recommendation|dish recommendation|available from)\b", "restaurants"),
        (r"\b(?:cafes?)\b", "cafes"),
        (r"\b(?:late night non-veg|late night food)\b", "late-night food"),
        (r"\b(?:chocolate)\b", "dessert spots"),
    ],
    "Food & Recipes": [
        (r"\b(?:protein meals?|high protein meals?)\b", "protein recipes"),
        (r"\b(?:desserts?|sweets?|cake|chocolate)\b", "dessert spots"),
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
        (r"\b(?:how-to guide|execution guide)\b", "advice"),
        (r"\b(?:general advice)\b", "general advice"),
    ],
    "Fitness & Health": [
        (r"\b(?:calisthenics training|calisthenics|bar workout)\b", "fitness"),
        (r"\b(?:agility|coordination|hopping drill)\b", "fitness"),
        (r"\b(?:workout accessories)\b", "fitness accessories"),
    ],
    "Learning & Skills": [
        (r"\b(?:app)\b", "app"),
        (r"\b(?:english speaking)\b", "learning app"),
    ],
    "Local Info": [
        (r"\b(?:local rentals)\b", "local rentals"),
    ],
    "Products & Shopping": [
        (r"\b(?:fragrances?|perfumes?|mens fragrances?|party and date night fragrances?|affordable luxury fragrances?)\b", "fragrance"),
        (r"\b(?:job search|productivity apps?|language learning tools?|ai productivity tools?|ai video tools?|ai simulation tools?|ai image tutorials?)\b", "app"),
        (r"\b(?:menswear|mens clothing|clothing brands)\b", "men's clothing brands"),
        (r"\b(?:slides?|sandals?)\b", "slides and sandals"),
        (r"\b(?:hair styling products?|hair styling tools?|beauty tips|deodorants?|alum)\b", "beauty and style"),
        (r"\b(?:night lights?|projectors?|charging gadgets?|chargers?)\b", "device"),
        (r"\b(?:home|lifestyle upgrades?|candles?|toothbrush|bedsheets?|pillow|diffuser|towels?)\b", "home products"),
    ],
    "Generic": [
        (r"\b(?:local food experience|local food discovery|food experience review|street food exploration)\b", "restaurants"),
        (r"\b(?:travel accommodation ideas|local rental discovery|south goa stays)\b", "stay"),
        (r"\b(?:travel itinerary advice)\b", "travel planning"),
        (r"\b(?:travel experience guide|city exploration ideas|island destinations)\b", "destinations"),
        (r"\b(?:social commentary humor|entertainment commentary|social media satire)\b", "commentary"),
        (r"\b(?:series recommendation|entertainment recommendations?|entertainment discovery|film success stories)\b", "films and shows"),
        (r"\b(?:music album review|dance moves tutorial)\b", "music"),
        (r"\b(?:ai education course|ai simulation tools?|ai video tools?|ai productivity tools?|ai image tutorials?)\b", "ai"),
        (r"\b(?:app discussion|language learning tools?)\b", "app"),
        (r"\b(?:beauty tips)\b", "beauty and style"),
        (r"\b(?:startup education|startup workshop|founder workshop)\b", "startup advice"),
        (r"\b(?:motivational perspective|personal perspective|transformation story)\b", "motivation and mindset"),
        (r"\b(?:device repair tips|technology showcase)\b", "consumer tech"),
        (r"\b(?:bangkok shopping deals)\b", "luxury outlet shopping"),
        (r"\b(?:money education advice)\b", "wealth education"),
        (r"\b(?:cooking tutorial)\b", "recipes"),
        (r"\b(?:food products in bali)\b", "local food"),
        (r"\b(?:asmr experience)\b", "commentary"),
    ],
    "Food & Dining": [
        (r"\b(?:restaurants? in banaras|restaurant in goa)\b", "restaurants"),
        (r"\b(?:street food places? in varanasi|street food in banaras)\b", "street food"),
        (r"\b(?:late night non-veg spots? banaras)\b", "late-night food"),
        (r"\b(?:cafes? in goa|cafes? in varanasi)\b", "cafes"),
        (r"\b(?:food products in bali)\b", "local food"),
    ],
    "Travel": [
        (r"\b(?:travel accommodation ideas|south goa stays)\b", "stay"),
        (r"\b(?:travel itinerary advice)\b", "travel planning"),
        (r"\b(?:travel experience guide|city exploration ideas|island destinations)\b", "destinations"),
    ],
    "Travel & Food": [
        (r"\b(?:restaurant|cafe|coffee|seafood|street food|burger|dining|food spot|dish|dishes|local food|biryani|bbq|barbecue|kebab|mandi|chicken fry|cake|dessert)\b", "restaurant"),
        (r"\b(?:recipe|drink|lemonade|americano|frappe|pasta)\b", "recipe"),
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
        (r"\b(?:meme|memes)\b", "humor"),
        (r"\b(?:dance tutorials?|footwork|dance moves?)\b", "music"),
        (r"\b(?:dance challenge|cha cha)\b", "internet culture"),
        (r"\b(?:social media commentary|entertainment trends)\b", "internet culture"),
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
    (r"\b(?:restaurant|food place|place recommendation|dish recommendation|available from|biryani spot)\b", "restaurants"),
    (r"\b(?:movie|film|series|drama|thriller|detective|zee5|adaptation)\b", "films and shows"),
    (r"\b(?:music|rap|song|ringtone)\b", "music"),
    (r"\b(?:dance tutorials?|footwork|dance moves?)\b", "music"),
    (r"\b(?:photo pose|duo photo|trio photo|posing|photo trend)\b", "photo ideas"),
    (r"\b(?:perfume|fragrance)\b", "fragrance"),
    (r"\b(?:hair styling|styling routine|curly hair|hair routine)\b", "beauty and style"),
    (r"\b(?:fashion appearance|appearance tips?|color palette|colors you wear|which colors suit|clothing color)\b", "beauty and style"),
    (r"\b(?:deodorants?|alum)\b", "beauty and style"),
    (r"\b(?:desserts?|sweets?|cake|chocolate)\b", "dessert spots"),
    (r"\b(?:calisthenics|bar workout)\b", "fitness"),
    (r"\b(?:agility|coordination|hopping drill)\b", "fitness"),
    (r"\b(?:ai tutorials?)\b", "ai"),
    (r"\b(?:startup education|startup workshop|founder workshop)\b", "startup advice"),
    (r"\b(?:social commentary humor|social media commentary)\b", "commentary"),
    (r"\b(?:entertainment memes)\b", "humor"),
]


PLACE_LIKE_SUBDOMAINS = {
    "restaurants",
    "restaurant",
    "seafood restaurants",
    "street food",
    "cafes",
    "late-night food",
    "dessert spots",
    "local food",
    "stay",
    "local rentals",
    "destinations",
    "travel planning",
    "cultural experience",
}


FOOD_PLACE_SUBDOMAINS = {
    "restaurants",
    "restaurant",
    "seafood restaurants",
    "street food",
    "cafes",
    "late-night food",
    "dessert spots",
    "local food",
}


PRODUCT_SIGNAL_RULES = [
    (r"\b(?:airpods?|earpods?|ear hooks?|earphones?|earbuds?|headphones?|powerbeats|beats)\b", ["audio device", "device"]),
    (r"\b(?:night light|lamp|light projector|projector light|starry night light)\b", ["device"]),
    (r"\b(?:appliance|kitchen device|cooking device|onechef|chef)\b", ["kitchen device", "device"]),
    (r"\b(?:wireless charger|charger|drone|gadget|device|hologram fan|fan)\b", ["device"]),
    (r"\b(?:perfume|fragrance)\b", ["fragrance"]),
    (r"\b(?:fashion appearance|appearance tips?|color palette|colors you wear|which colors suit|clothing color)\b", ["beauty and style"]),
    (r"\b(?:deodorants?|alum)\b", ["beauty and style"]),
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
    "party and date night fragrances": {
        "subdomains": ["fragrance"],
        "item_type": "product",
        "intent": "product_to_buy",
    },
    "men's fragrances": {
        "subdomains": ["fragrance"],
        "item_type": "product",
        "intent": "product_to_buy",
    },
    "affordable luxury fragrances": {
        "subdomains": ["fragrance"],
        "item_type": "product",
        "intent": "product_to_buy",
    },
    "indian menswear brands": {
        "subdomains": ["men's clothing brands"],
        "item_type": "product",
        "intent": "product_to_buy",
    },
    "slides & sandals": {
        "subdomains": ["slides and sandals"],
        "item_type": "product",
        "intent": "product_to_buy",
    },
    "affordable home & lifestyle upgrades": {
        "subdomains": ["home products"],
        "item_type": "product",
        "intent": "product_to_buy",
    },
    "job search & productivity apps": {
        "subdomains": ["job search tools", "app"],
        "item_type": "app",
        "intent": "tool_to_use",
    },
    "hair styling products & tools": {
        "subdomains": ["beauty and style"],
        "item_type": "product",
        "intent": "product_to_buy",
    },
    "fashion appearance tips": {
        "subdomains": ["beauty and style"],
        "item_type": "idea",
        "intent": "idea_to_try",
    },
    "ai productivity tools": {
        "subdomains": ["ai", "app"],
        "item_type": "app",
        "intent": "tool_to_use",
    },
    "night lights & projectors": {
        "subdomains": ["device"],
        "item_type": "product",
        "intent": "product_to_buy",
    },
    "multi-function charging gadgets": {
        "subdomains": ["device"],
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
    "tech tips": {
        "subdomains": ["consumer tech"],
        "item_type": "idea",
        "intent": "advice_to_remember",
    },
    "ai tutorials": {
        "subdomains": ["ai"],
        "item_type": "app",
        "intent": "tool_to_use",
    },
    "language learning tools": {
        "subdomains": ["learning app"],
        "item_type": "app",
        "intent": "tool_to_use",
    },
    "ai simulation tools": {
        "subdomains": ["ai", "app"],
        "item_type": "app",
        "intent": "tool_to_use",
    },
    "ai video tools": {
        "subdomains": ["ai", "app"],
        "item_type": "app",
        "intent": "tool_to_use",
    },
    "ai image tutorials": {
        "subdomains": ["ai", "app"],
        "item_type": "app",
        "intent": "tool_to_use",
    },
    "ai education course": {
        "subdomains": ["ai", "advice"],
        "item_type": "idea",
        "intent": "advice_to_remember",
    },
    "job search tools": {
        "subdomains": ["job search tools"],
        "item_type": "app",
        "intent": "tool_to_use",
    },
    "startup education": {
        "subdomains": ["startup advice", "advice"],
        "item_type": "idea",
        "intent": "advice_to_remember",
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
    "natural deodorant products": {
        "subdomains": ["beauty and style"],
        "item_type": "product",
        "intent": "product_to_buy",
    },
    "agility & coordination": {
        "subdomains": ["fitness"],
        "item_type": "idea",
        "intent": "idea_to_try",
    },
    "local rentals": {
        "subdomains": ["local rentals"],
        "item_type": "place",
        "intent": "place_to_visit",
    },
    "local rental discovery": {
        "subdomains": ["local rentals"],
        "item_type": "place",
        "intent": "place_to_visit",
    },
    "local food commentary": {
        "subdomains": ["local food"],
        "item_type": "place",
        "intent": "place_to_visit",
    },
    "local food experience": {
        "subdomains": ["restaurants"],
        "item_type": "place",
        "intent": "place_to_visit",
    },
    "local food discovery": {
        "subdomains": ["restaurants"],
        "item_type": "place",
        "intent": "place_to_visit",
    },
    "food experience review": {
        "subdomains": ["restaurants"],
        "item_type": "place",
        "intent": "place_to_visit",
    },
    "street food exploration": {
        "subdomains": ["street food", "restaurants"],
        "item_type": "place",
        "intent": "place_to_visit",
    },
    "restaurant in goa": {
        "subdomains": ["restaurants"],
        "location": "Goa",
        "item_type": "place",
        "intent": "place_to_visit",
    },
    "restaurants in banaras": {
        "subdomains": ["restaurants"],
        "location": "Varanasi",
        "item_type": "place",
        "intent": "place_to_visit",
    },
    "street food places in varanasi": {
        "subdomains": ["street food", "restaurants"],
        "location": "Varanasi",
        "item_type": "place",
        "intent": "place_to_visit",
    },
    "street food in banaras": {
        "subdomains": ["street food", "restaurants"],
        "location": "Varanasi",
        "item_type": "place",
        "intent": "place_to_visit",
    },
    "late night non-veg spots banaras": {
        "subdomains": ["late-night food", "restaurants"],
        "location": "Varanasi",
        "item_type": "place",
        "intent": "place_to_visit",
    },
    "cafes in goa": {
        "subdomains": ["cafes", "restaurants"],
        "location": "Goa",
        "item_type": "place",
        "intent": "place_to_visit",
    },
    "social commentary humor": {
        "subdomains": ["humor", "commentary"],
        "item_type": "media",
        "intent": "media_to_watch_or_hear",
    },
    "commentary": {
        "subdomains": ["commentary"],
        "item_type": "media",
        "intent": "media_to_watch_or_hear",
    },
    "social media commentary": {
        "subdomains": ["commentary", "internet culture"],
        "item_type": "media",
        "intent": "media_to_watch_or_hear",
    },
    "entertainment memes": {
        "subdomains": ["humor", "internet culture"],
        "item_type": "media",
        "intent": "media_to_watch_or_hear",
    },
    "entertainment trends": {
        "subdomains": ["music", "internet culture"],
        "item_type": "media",
        "intent": "media_to_watch_or_hear",
    },
    "dance tutorials": {
        "subdomains": ["music"],
        "item_type": "media",
        "intent": "media_to_watch_or_hear",
    },
    "dance moves tutorial": {
        "subdomains": ["music", "internet culture"],
        "item_type": "media",
        "intent": "media_to_watch_or_hear",
    },
    "dance challenge": {
        "subdomains": ["internet culture", "music"],
        "item_type": "media",
        "intent": "media_to_watch_or_hear",
    },
    "series recommendation": {
        "subdomains": ["films and shows"],
        "item_type": "media",
        "intent": "media_to_watch_or_hear",
    },
    "film success stories": {
        "subdomains": ["films and shows"],
        "item_type": "media",
        "intent": "media_to_watch_or_hear",
    },
    "music album review": {
        "subdomains": ["music"],
        "item_type": "media",
        "intent": "media_to_watch_or_hear",
    },
    "social media satire": {
        "subdomains": ["commentary", "internet culture"],
        "item_type": "media",
        "intent": "media_to_watch_or_hear",
    },
    "personal routine tips": {
        "subdomains": ["beauty and style"],
        "item_type": "idea",
        "intent": "idea_to_try",
    },
    "beauty tips": {
        "subdomains": ["beauty and style"],
        "item_type": "idea",
        "intent": "idea_to_try",
    },
    "how-to guide": {
        "subdomains": ["advice"],
        "item_type": "idea",
        "intent": "advice_to_remember",
    },
    "motivational perspective": {
        "subdomains": ["motivation and mindset"],
        "item_type": "idea",
        "intent": "advice_to_remember",
    },
    "personal perspective": {
        "subdomains": ["advice"],
        "item_type": "idea",
        "intent": "advice_to_remember",
    },
    "transformation story": {
        "subdomains": ["motivation and mindset"],
        "item_type": "idea",
        "intent": "advice_to_remember",
    },
    "calisthenics training": {
        "subdomains": ["fitness"],
        "item_type": "idea",
        "intent": "idea_to_try",
    },
    "back training": {
        "subdomains": ["fitness"],
        "item_type": "idea",
        "intent": "idea_to_try",
    },
    "vegetarian pasta recipes": {
        "subdomains": ["recipes"],
        "item_type": "recipe",
        "intent": "recipe_to_make",
    },
    "travel accommodation ideas": {
        "subdomains": ["stay"],
        "item_type": "place",
        "intent": "place_to_visit",
    },
    "south goa stays": {
        "subdomains": ["stay"],
        "location": "Goa",
        "item_type": "place",
        "intent": "place_to_visit",
    },
    "travel itinerary advice": {
        "subdomains": ["travel planning"],
        "item_type": "place",
        "intent": "place_to_visit",
    },
    "travel experience guide": {
        "subdomains": ["destinations"],
        "item_type": "place",
        "intent": "place_to_visit",
    },
    "city exploration ideas": {
        "subdomains": ["destinations"],
        "item_type": "place",
        "intent": "place_to_visit",
    },
    "bangkok shopping deals": {
        "subdomains": ["luxury outlet shopping"],
        "location": "Bangkok",
        "item_type": "place",
        "intent": "place_to_visit",
    },
    "device repair tips": {
        "subdomains": ["consumer tech"],
        "item_type": "idea",
        "intent": "advice_to_remember",
    },
    "technology showcase": {
        "subdomains": ["device", "consumer tech"],
        "item_type": "product",
        "intent": "product_to_buy",
    },
    "cooking tutorial": {
        "subdomains": ["recipes"],
        "item_type": "recipe",
        "intent": "recipe_to_make",
    },
    "money education advice": {
        "subdomains": ["wealth education"],
        "item_type": "idea",
        "intent": "advice_to_remember",
    },
    "viral desserts & sweets": {
        "subdomains": ["dessert spots", "local food"],
        "item_type": "place",
        "intent": "place_to_visit",
    },
    "chocolate in bali": {
        "subdomains": ["dessert spots", "local food"],
        "location": "Bali",
        "item_type": "place",
        "intent": "place_to_visit",
    },
    "food products in bali": {
        "subdomains": ["food products"],
        "location": "Bali",
        "item_type": "product",
        "intent": "product_to_buy",
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
    (r"\b(?:in\s+goa|in\s+varanasi|in\s+banaras|in\s+bangkok|in\s+meghalaya|in\s+bali|in\s+london)\b.*\b(?:restaurant|cafe|spot|place|biryani|bbq|barbecue|cake|dessert|seafood|food)\b", "place_to_visit"),
    (r"\b(?:restaurant|cafe|spot|place|biryani|bbq|barbecue|cake|dessert|seafood|food)\b.*\b(?:in\s+goa|in\s+varanasi|in\s+banaras|in\s+bangkok|in\s+meghalaya|in\s+bali|in\s+london)\b", "place_to_visit"),
    (r"\b(?:restaurant|cafe|stay|resort|villa|trip|itinerary|travel|spot|food place|place recommendation|available from)\b", "place_to_visit"),
    (r"\b(?:restaurant|cafe|stay|resort|villa|trip|itinerary|travel)\b", "place_to_visit"),
    (r"\b(?:recipe|drink|cook|meal prep|high protein|pasta|wrap|kebab|meal)\b", "recipe_to_make"),
    (r"\b(?:app|tool|assistant|navigation)\b", "tool_to_use"),
    (r"\b(?:chatgpt|gemini|ai tutorial)\b", "tool_to_use"),
    (r"\b(?:perfume|device|gadget|product|unboxing|drone|earphones|earbuds|appliance)\b", "product_to_buy"),
    (r"\b(?:movie|series|show|film|drama|song|music)\b", "media_to_watch_or_hear"),
    (r"\b(?:dance|footwork|meme|commentary|humor)\b", "media_to_watch_or_hear"),
    (r"\b(?:pose|trend|advice|challenge)\b", "idea_to_try"),
]


ITEM_TYPE_RULES = [
    (r"\b(?:in\s+goa|in\s+varanasi|in\s+banaras|in\s+bangkok|in\s+meghalaya|in\s+bali|in\s+london)\b.*\b(?:restaurant|cafe|spot|place|biryani|bbq|barbecue|cake|dessert|seafood|food)\b", "place"),
    (r"\b(?:restaurant|cafe|spot|place|biryani|bbq|barbecue|cake|dessert|seafood|food)\b.*\b(?:in\s+goa|in\s+varanasi|in\s+banaras|in\s+bangkok|in\s+meghalaya|in\s+bali|in\s+london)\b", "place"),
    (r"\b(?:restaurant|cafe|coffee|burger|seafood|food spot|food place|place recommendation|dish recommendation|available from|outlet|bbq|barbecue|biryani|cake|dessert|hotel|resort|villa|stay)\b", "place"),
    (r"\b(?:restaurant|cafe|coffee|burger|seafood|food spot|hotel|resort|villa|stay)\b", "place"),
    (r"\b(?:recipe|drink|meal prep|dish)\b", "recipe"),
    (r"\b(?:app|assistant|navigation|radarbot)\b", "app"),
    (r"\b(?:chatgpt|gemini|ai tutorial)\b", "app"),
    (r"\b(?:device|gadget|drone|earphones|earbuds|perfume|stamp|appliance|powerbeats|onechef)\b", "product"),
    (r"\b(?:movie|series|show|song|music|drama)\b", "media"),
    (r"\b(?:dance|footwork|meme|commentary|humor)\b", "media"),
    (r"\b(?:pose|challenge|advice|trend)\b", "idea"),
]


def normalize(value: str) -> str:
    return " ".join((value or "").strip().split())


def normalize_key(value: str) -> str:
    return normalize(value).lower()


def canonical_domain(primary_category: str) -> str:
    key = normalize_key(primary_category)
    value = DOMAIN_ALIASES.get(key, normalize(primary_category) or "Miscellaneous")
    return value if value in CANONICAL_DOMAINS else "Miscellaneous"


def canonical_location(*texts: str) -> str:
    haystack = " ".join(normalize_key(text) for text in texts)
    for alias, canonical in sorted(LOCATION_ALIASES.items(), key=lambda item: len(item[0]), reverse=True):
        if alias in haystack:
            return canonical
    return ""


def canonical_subdomain_label(value: str) -> str:
    key = normalize_key(value)
    return SUBDOMAIN_ALIASES.get(key, normalize(value))


def canonical_subdomain_list(values: list[str]) -> list[str]:
    seen = []
    for value in values or []:
        label = canonical_subdomain_label(value)
        if label and label not in seen:
            seen.append(label)
    return seen


def canonical_item_type(value: str) -> str:
    key = normalize_key(value)
    resolved = ITEM_TYPE_ALIASES.get(key, normalize(value).lower())
    return resolved if resolved in CANONICAL_ITEM_TYPES else ""


def canonical_intent(value: str) -> str:
    key = normalize_key(value)
    resolved = INTENT_ALIASES.get(key, key)
    return resolved if resolved in CANONICAL_INTENTS else ""


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
    return canonical_subdomain_list(seen)


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
            normalized = canonical_subdomain_label(item)
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
    if subdomain_set & {"men's clothing brands", "sneaker culture", "beauty and style", "slides and sandals", "home products"}:
        return "Lifestyle"
    if subdomain_set & {"audio device", "kitchen device", "device", "consumer tech", "app", "learning app"}:
        return "Technology"
    if subdomain_set & {"beauty and style", "men's clothing brands", "luxury outlet shopping", "sneaker culture", "lifestyle ideas"}:
        return "Lifestyle"
    if subdomain_set & {"food products"}:
        return "Products & Shopping"
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
    if location and item_type == "place" and subdomain_set & {"local food", "dessert spots"}:
        return "Food & Local Eats"
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
