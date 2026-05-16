from __future__ import annotations

import json

from api_config import get_openai_client
from app.services.personalization_v2.models import ReelItemRecord, StructuredFeature
from app.services.personalization_v2.normalization import (
    canonical_domain,
    canonical_location,
    canonical_subdomains,
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

    if use_llm:
        try:
            llm_payload = llm_interpret(item)
            interpretation_source = "llm+heuristic"
        except Exception:
            llm_payload = {}
    else:
        llm_payload = {}

    domain = normalize(llm_payload.get("canonical_domain")) or heuristic["canonical_domain"]
    domain = canonical_domain(domain or item.primary_category)
    subdomains = merge_subdomains(
        heuristic["subdomains"],
        coerce_list(llm_payload.get("subdomains", [])),
    )
    location = normalize(llm_payload.get("location")) or heuristic["location"]
    location = canonical_location(location, item.specific_category, item.item_name, item.summary) or location
    vibe = merge_subdomains(
        heuristic["vibe"],
        coerce_list(llm_payload.get("vibe", [])),
    )
    intent = normalize(llm_payload.get("intent")) or heuristic["intent"]
    item_type = normalize(llm_payload.get("item_type")) or heuristic["item_type"]
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
        },
    )
