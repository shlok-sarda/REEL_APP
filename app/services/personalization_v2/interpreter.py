from __future__ import annotations

import json

from api_config import get_openai_client
from app.services.personalization_v2.models import ReelItemRecord, StructuredFeature
from app.services.personalization_v2.normalization import (
    canonical_domain,
    canonical_intent,
    canonical_item_type,
    canonical_location,
    canonical_subdomain_list,
    canonical_subdomains,
    FOOD_PLACE_SUBDOMAINS,
    PLACE_LIKE_SUBDOMAINS,
    refine_domain,
    has_physical_product_signal,
    infer_intent,
    infer_item_type,
    infer_vibes,
    merge_subdomains,
    normalize,
    normalize_entities,
    product_signal_subdomains,
    specific_category_hint,
)


INTERPRET_MODEL = "gpt-4.1-mini"


PROMPT_TEMPLATE = """
You are converting an already-extracted saved reel item into structured personalization metadata.

Do not re-extract the item itself.
Do not invent new products or places.
Normalize this reel item into stable concepts for later clustering.

Allowed canonical domains:
- Travel & Food
- Food & Local Eats
- Food & Recipes
- Travel Destinations
- Travel Accommodations
- Technology
- Entertainment
- Health & Lifestyle
- Lifestyle
- Fitness & Health
- Learning & Skills
- Finance & Business
- Career & Money
- Personal Growth
- Local Info
- Miscellaneous

Allowed item_type values:
- place
- recipe
- app
- product
- media
- idea
- general

Allowed intent values:
- place_to_visit
- recipe_to_make
- tool_to_use
- product_to_buy
- media_to_watch_or_hear
- idea_to_try
- advice_to_remember
- general_reference

Preferred subdomain vocabulary:
- restaurants
- seafood restaurants
- street food
- cafes
- late-night food
- dessert spots
- local food
- stay
- destinations
- travel planning
- travel utility
- cultural experience
- recipes
- protein recipes
- app
- learning app
- ai
- device
- audio device
- kitchen device
- consumer tech
- fragrance
- beauty and style
- men's clothing brands
- luxury outlet shopping
- sneaker culture
- lifestyle ideas
- fitness
- wellness
- films and shows
- music
- internet culture
- humor
- commentary
- photo ideas
- job search tools
- wealth education
- money making ideas
- startup advice
- motivation and mindset
- advice
- local rentals
- marketing
- business and money
- innovation

Return JSON only:
{
  "item_type": "",
  "canonical_domain": "",
  "subdomains": [],
  "entities": [],
  "location": "",
  "vibe": [],
  "intent": "",
  "audience_context": "",
  "confidence_scores": {
    "domain": 0.0,
    "subdomains": 0.0,
    "location": 0.0,
    "intent": 0.0
  }
}

Rules:
- Prefer stable concepts over expressive phrases.
- Keep subdomains concise like "restaurant", "seafood", "cafe", "stay", "recipe", "app", "device".
- If location is unclear, return an empty string.
- If uncertain, lower the confidence instead of guessing.
- Prefer transcript and item name over decorative summary wording.
- Resolve synonyms into canonical concepts.
- Examples:
  - Banaras -> Varanasi
  - restaurants / food place / biryani spot -> restaurants
  - app / tool / website -> app
  - movie / series / show -> films and shows
  - perfume / fragrance -> fragrance
- If the reel is about a place to eat in a city, favor:
  - item_type = place
  - intent = place_to_visit
  - location = canonical city name
- If the reel is about a buyable thing, favor:
  - item_type = product or app
  - intent = product_to_buy or tool_to_use
- Do NOT return decorative broad placeholders like "general", "place", "idea" as subdomains.

Input:
{
  "primary_category": "<<PRIMARY>>",
  "specific_category": "<<SPECIFIC>>",
  "item_name": "<<ITEM>>",
  "summary": "<<SUMMARY>>",
  "product_name": "<<PRODUCT_NAME>>",
  "brand": "<<BRAND>>",
  "product_type": "<<PRODUCT_TYPE>>"
}
""".strip()


def build_prompt(item: ReelItemRecord) -> str:
    return (
        PROMPT_TEMPLATE
        .replace("<<PRIMARY>>", item.primary_category)
        .replace("<<SPECIFIC>>", item.specific_category)
        .replace("<<ITEM>>", item.item_name)
        .replace("<<SUMMARY>>", item.summary)
        .replace("<<PRODUCT_NAME>>", item.product_name)
        .replace("<<BRAND>>", item.brand)
        .replace("<<PRODUCT_TYPE>>", item.product_type)
    )


def coerce_list(value) -> list[str]:
    if isinstance(value, list):
        return [normalize(item) for item in value if normalize(item)]
    if isinstance(value, tuple) or isinstance(value, set):
        return [normalize(item) for item in value if normalize(item)]
    if isinstance(value, dict):
        return [normalize(key) for key in value.keys() if normalize(key)]
    normalized = normalize(value)
    return [normalized] if normalized else []


def llm_interpret(item: ReelItemRecord) -> dict:
    client = get_openai_client()
    response = client.chat.completions.create(
        model=INTERPRET_MODEL,
        temperature=0.0,
        response_format={"type": "json_object"},
        messages=[{"role": "user", "content": build_prompt(item)}],
    )
    return json.loads(response.choices[0].message.content)


def heuristic_interpret(item: ReelItemRecord) -> dict:
    hint = specific_category_hint(item.specific_category)
    domain = canonical_domain(item.primary_category)
    product_subdomains = product_signal_subdomains(
        item.product_name,
        item.product_type,
        item.brand,
        item.model,
        item.item_name,
        item.summary,
    )
    physical_product_signal = has_physical_product_signal(
        item.product_name,
        item.product_type,
        item.brand,
        item.model,
        item.item_name,
        item.summary,
    )
    location = normalize(hint.get("location")) or canonical_location(item.specific_category, item.item_name, item.summary)
    subdomains = merge_subdomains(
        canonical_subdomains(domain, item.specific_category, item.item_name, item.summary, item.product_type),
        product_subdomains,
        hint.get("subdomains", []),
    )
    item_type = normalize(hint.get("item_type")) or infer_item_type(item.specific_category, item.item_name, item.summary, item.product_type)
    if physical_product_signal and item_type in {"general", "idea", "place"}:
        item_type = "product"
    if product_subdomains and item_type == "app":
        product_only = [sub for sub in product_subdomains if sub not in {"app", "learning app"}]
        if product_only:
            item_type = "product"
    domain = refine_domain(domain, subdomains, item_type, location)
    vibe = infer_vibes(item.specific_category, item.item_name, item.summary)
    intent = normalize(hint.get("intent")) or infer_intent(item.specific_category, item.item_name, item.summary, item.product_type)
    text_blob = " ".join(
        normalize(part).lower()
        for part in [item.specific_category, item.item_name, item.summary]
        if normalize(part)
    )
    if "fashion appearance tips" in text_blob or any(
        marker in text_blob
        for marker in ["color palette", "clothing color", "which colors suit", "colors you wear", "contrast clothing color"]
    ):
        subdomains = [sub for sub in subdomains if normalize(sub).lower() != "men's clothing brands"]
        subdomains = merge_subdomains(subdomains, ["beauty and style"])
        if item_type in {"product", "general"}:
            item_type = "idea"
        if intent in {"product_to_buy", "general_reference", "advice_to_remember"}:
            intent = "idea_to_try"
        domain = refine_domain(domain, subdomains, item_type, location)
    subdomain_set = {normalize(subdomain).lower() for subdomain in subdomains}
    has_place_like_subdomain = bool(subdomain_set & PLACE_LIKE_SUBDOMAINS)
    has_food_place_subdomain = bool(subdomain_set & FOOD_PLACE_SUBDOMAINS)
    if location and has_place_like_subdomain and item_type in {"general", "idea", "recipe"}:
        item_type = "place"
    if location and has_place_like_subdomain and intent in {"general_reference", "idea_to_try", "recipe_to_make"}:
        intent = "place_to_visit"
    if location and has_food_place_subdomain and item_type != "product":
        item_type = "place"
        if intent in {"general_reference", "idea_to_try", "recipe_to_make"}:
            intent = "place_to_visit"
    if physical_product_signal and intent in {"general_reference", "idea_to_try", "place_to_visit"}:
        intent = "product_to_buy"
    if item_type == "app" and intent in {"general_reference", "advice_to_remember", "idea_to_try"}:
        intent = "tool_to_use"
    if (
        intent == "place_to_visit"
        and location
        and item_type == "idea"
        and any(sub in {"travel planning", "destinations", "cultural experience"} for sub in subdomains)
    ):
        item_type = "place"
    domain = refine_domain(domain, subdomains, item_type, location)
    entities = normalize_entities([item.item_name, item.product_name, item.brand, item.model])
    return {
        "item_type": item_type,
        "canonical_domain": domain,
        "subdomains": subdomains,
        "entities": entities,
        "location": location,
        "vibe": vibe,
        "intent": intent,
        "audience_context": "",
        "confidence_scores": {
            "domain": 0.84 if product_subdomains else 0.78,
            "subdomains": 0.88 if product_subdomains else (0.84 if hint.get("subdomains") else (0.72 if subdomains else 0.45)),
            "location": 0.92 if hint.get("location") else (0.85 if location else 0.35),
            "intent": 0.86 if physical_product_signal and intent == "product_to_buy" else (0.82 if hint.get("intent") else (0.68 if intent != "general_reference" else 0.44)),
        },
    }


def interpret_item(item: ReelItemRecord, use_llm: bool = True) -> StructuredFeature:
    heuristic = heuristic_interpret(item)
    interpretation_source = "heuristic"
    llm_error = ""

    if use_llm:
        try:
            llm_payload = llm_interpret(item)
            interpretation_source = "llm+heuristic"
        except Exception as exc:
            llm_payload = {}
            llm_error = str(exc)
    else:
        llm_payload = {}

    llm_domain = canonical_domain(normalize(llm_payload.get("canonical_domain")) or "")
    domain = llm_domain if llm_domain and llm_domain != "Miscellaneous" else heuristic["canonical_domain"]
    domain = canonical_domain(domain or item.primary_category)
    llm_subdomains = canonical_subdomain_list(coerce_list(llm_payload.get("subdomains", [])))
    subdomains = merge_subdomains(
        llm_subdomains,
        heuristic["subdomains"],
    )
    llm_location = normalize(llm_payload.get("location"))
    location = canonical_location(llm_location, item.specific_category, item.item_name, item.summary) or heuristic["location"]
    vibe = merge_subdomains(
        heuristic["vibe"],
        coerce_list(llm_payload.get("vibe", [])),
    )
    intent = canonical_intent(llm_payload.get("intent")) or heuristic["intent"]
    item_type = canonical_item_type(llm_payload.get("item_type")) or heuristic["item_type"]
    entities = normalize_entities(
        heuristic["entities"] +
        coerce_list(llm_payload.get("entities", []))
    )
    confidence_scores = {
        **heuristic["confidence_scores"],
        **{
            key: float(value)
            for key, value in (llm_payload.get("confidence_scores") or {}).items()
            if isinstance(value, (int, float))
        },
    }
    llm_confidence = llm_payload.get("confidence_scores") or {}
    if llm_subdomains and float(llm_confidence.get("subdomains", 0.0) or 0.0) >= 0.55:
        subdomains = merge_subdomains(llm_subdomains, heuristic["subdomains"])
    if llm_location and float(llm_confidence.get("location", 0.0) or 0.0) >= 0.55:
        location = canonical_location(llm_location, item.specific_category, item.item_name, item.summary) or location
    if llm_domain != "Miscellaneous" and float(llm_confidence.get("domain", 0.0) or 0.0) >= 0.55:
        domain = llm_domain
    if canonical_item_type(llm_payload.get("item_type")) and float(llm_confidence.get("subdomains", 0.0) or 0.0) >= 0.5:
        item_type = canonical_item_type(llm_payload.get("item_type")) or item_type
    if canonical_intent(llm_payload.get("intent")) and float(llm_confidence.get("intent", 0.0) or 0.0) >= 0.5:
        intent = canonical_intent(llm_payload.get("intent")) or intent
    domain = refine_domain(domain, subdomains, item_type, location)

    return StructuredFeature(
        reel_item_id=item.reel_item_id,
        reel_id=item.reel_id,
        user_id=item.user_id,
        primary_category=item.primary_category,
        specific_category=item.specific_category,
        item_name=item.item_name,
        summary=item.summary,
        item_type=item_type or heuristic["item_type"],
        canonical_domain=domain,
        subdomains=subdomains,
        entities=entities,
        location=location,
        vibe=vibe,
        intent=intent,
        audience_context=normalize(llm_payload.get("audience_context")),
        confidence_scores=confidence_scores,
        interpretation_status="ready",
        interpretation_source=interpretation_source,
        metadata={
            "heuristic": heuristic,
            "llm_payload": llm_payload,
            "llm_error": llm_error,
        },
    )
