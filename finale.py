import os
import cv2
import json
import base64
import argparse
from collections import Counter
from urllib.parse import quote_plus
from data_preprocessing import download_reel, process_reel
import csv
from pathlib import Path
from api_config import get_openai_client

client = get_openai_client()
BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
PRIMARY_MODEL = "gpt-4.1-mini"
SECONDARY_MODEL = "gpt-4.1"


# --------------------------------------------------
# STEP 1: Extract keyframes
# --------------------------------------------------
def extract_scene_keyframes(video_path, output_dir=BASE_DIR / "keyframes", threshold=0.45, min_frame_gap=10, max_frames=8):
    os.makedirs(output_dir, exist_ok=True)

    cap = cv2.VideoCapture(video_path)

    prev_hist = None
    frame_idx = 0
    saved_count = 0
    last_saved_frame = -min_frame_gap
    saved_paths = []

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        hist = cv2.calcHist([hsv], [0, 1], None, [50, 60], [0, 180, 0, 256])
        cv2.normalize(hist, hist)

        should_save = False

        if frame_idx == 0:
            should_save = True
        elif prev_hist is not None:
            similarity = cv2.compareHist(prev_hist, hist, cv2.HISTCMP_CORREL)
            if similarity < threshold and (frame_idx - last_saved_frame) >= min_frame_gap:
                should_save = True

        if should_save:
            save_path = os.path.join(output_dir, f"frame_{saved_count}.jpg")
            cv2.imwrite(save_path, frame)
            saved_paths.append(save_path)

            saved_count += 1
            last_saved_frame = frame_idx

            if saved_count >= max_frames:
                break

        prev_hist = hist
        frame_idx += 1

    cap.release()
    return saved_paths


# --------------------------------------------------
# STEP 2: Extract visual understanding
# --------------------------------------------------
def extract_visual_data(result, video_path):
    visual_data = {}

    if not video_path or not os.path.exists(video_path):
        return visual_data

    keyframes = extract_scene_keyframes(video_path)

    prompt = f"""
You are analyzing Instagram reel keyframes together with textual context.

TEXTUAL CONTEXT:
Caption: {result.get('caption', '')}
Transcript: {result.get('transcript', '')}
Hashtags: {format_hashtags(result.get('hashtags', ''))}

OBJECTIVE:
Understand what the reel is about and extract meaningful visuals.

OUTPUT STRICT JSON:
{{
  "inferred_main_theme": "",
  "relevant_visible_text": [],
  "relevant_visual_entities": [],
  "visual_supporting_points": [],
  "overall_visual_summary": ""
}}"""

    content = [{"type": "text", "text": prompt}]

    for frame_path in keyframes:
        with open(frame_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")

        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{b64}"}
        })

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        response_format={"type": "json_object"},
        messages=[{"role": "user", "content": content}]
    )

    visual_data = json.loads(response.choices[0].message.content)

    # cleanup
    os.remove(video_path)
    for f in keyframes:
        if os.path.exists(f):
            os.remove(f)

    return visual_data


# --------------------------------------------------
# STEP 3: PRIMARY + SECONDARY CLASSIFICATION
# --------------------------------------------------
def normalize_label(value):
    return " ".join((value or "").strip().split())


def format_hashtags(value):
    if isinstance(value, list):
        return ", ".join(str(item).strip() for item in value if str(item).strip())
    return normalize_label(value)


def load_json_content(response):
    try:
        return json.loads(response.choices[0].message.content)
    except Exception:
        return {"error": "Invalid JSON", "raw": response.choices[0].message.content}


def build_primary_prompt(result, visual_data):
    return f"""
You are assigning a broad, stable primary category to one saved reel.

Your job:
- Predict the PRIMARY category only.
- This should be a reusable top-level browsing bucket.
- It must be broad enough to contain many related reels.
- It must be stable across similar reels.
- Prefer everyday human-readable names.
- Avoid niche, overly specific, decorative, or marketing-heavy wording.

Important:
- This is the broad parent category, not the detailed subcategory.
- If the reel is about one specific product type, choose the broader parent theme it naturally belongs to.
- The same kind of reel should repeatedly map to the same primary category.
- Use only 1 to 3 words.

TEXTUAL DATA:
Caption: {result.get('caption', '')}
Transcript: {result.get('transcript', '')}
Hashtags: {format_hashtags(result.get('hashtags', ''))}

VISUAL DATA:
Theme: {visual_data.get('inferred_main_theme', '')}
Visible Text: {', '.join(visual_data.get('relevant_visible_text', []))}
Visual Entities: {', '.join(visual_data.get('relevant_visual_entities', []))}
Visual Insights: {', '.join(visual_data.get('visual_supporting_points', []))}

Return ONLY valid minified JSON:
{{
  "primary_category": "",
  "reason": ""
}}
""".strip()


def request_primary_category(result, visual_data, samples=3):
    votes = []

    for _ in range(samples):
        response = client.chat.completions.create(
            model=PRIMARY_MODEL,
            temperature=0.3,
            response_format={"type": "json_object"},
            messages=[{"role": "user", "content": build_primary_prompt(result, visual_data)}],
        )
        payload = load_json_content(response)
        primary = normalize_label(payload.get("primary_category"))
        if primary:
            votes.append(primary)

    if not votes:
        raise ValueError("Primary category prediction failed.")

    counts = Counter(votes)
    winning_primary, winning_votes = max(
        counts.items(),
        key=lambda row: (row[1], len(row[0]), row[0].lower()),
    )
    return {
        "primary_category": winning_primary,
        "votes": winning_votes,
        "candidates": votes,
    }


def build_secondary_prompt(result, visual_data, primary_category):
    return f"""
You are organizing one saved reel inside an already chosen primary category.

PRIMARY CATEGORY:
{primary_category}

You must produce:
1. A SECONDARY category
2. The core items in the reel

SECONDARY CATEGORY RULES:
- This must be more specific than the primary category.
- It should fit naturally under the primary category.
- It should reflect the user's likely browsing intent later.
- Use 2 to 4 words.
- Keep wording clean, stable, and human-readable.
- Do not simply repeat the primary category unless the reel is too broad to narrow further.
- Similar reels should produce the same secondary category whenever possible.

ITEM RULES:
- Extract ONLY the main items that the reel is truly about.
- Do not add background objects or accessories unless they are central.
- Prefer fewer, better items.
- If only one real core item exists, return one item only.
- Use visuals only to refine naming, not to invent extra items.
- If the reel clearly showcases multiple distinct core items, include all of them.
- Do NOT collapse a multi-item reel into one generic category item.
- Do NOT use the secondary category itself as the only item unless the reel is genuinely about one single thing.
- If the reel is a roundup, recommendation list, or product showcase, extract each distinct featured item that a user would want to remember later.
- When the reel says or shows things like "3 gadgets", "top 5 products", "these tools", or multiple named examples, return those separate items.

TEXTUAL DATA:
Caption: {result.get('caption', '')}
Transcript: {result.get('transcript', '')}
Hashtags: {format_hashtags(result.get('hashtags', ''))}

VISUAL DATA:
Theme: {visual_data.get('inferred_main_theme', '')}
Visible Text: {', '.join(visual_data.get('relevant_visible_text', []))}
Visual Entities: {', '.join(visual_data.get('relevant_visual_entities', []))}
Visual Insights: {', '.join(visual_data.get('visual_supporting_points', []))}

Return ONLY valid minified JSON:
{{
  "secondary_category": "",
  "items": [
    {{"name":"", "summary":""}}
  ]
}}
""".strip()


def build_product_prompt(result, visual_data, classification):
    item_preview = json.dumps(classification.get("items", []), ensure_ascii=False)
    return f"""
You are extracting structured product information from one Instagram reel.

Your goal:
- Decide whether this reel contains any real buyable products.
- If yes, extract concrete product records for later marketplace linking.
- Use multimodal fusion, but obey this evidence priority:
  1. Transcript
  2. Visible text
  3. Caption and hashtags
  4. Visual inference from images
- Only rely on lower-priority evidence when higher-priority evidence is missing or incomplete.

Important:
- Do NOT guess product names without evidence.
- Do NOT treat vague themes or categories as products unless a real product is being shown or discussed.
- A product can be a gadget, accessory, beauty item, fashion item, home item, toy, appliance, or other buyable consumer item.
- If the reel is not about buying or showing a product, return contains_products = false.
- If possible, align extracted products with the existing reel items below.
- search_query should be concise and optimized for trusted marketplace search.
- product_name should be the best human-readable product label.
- brand and model can be blank if unknown.

REEL CLASSIFICATION:
Primary Category: {classification.get('primary_category', '')}
Secondary Category: {classification.get('secondary_category', '')}
Extracted Items: {item_preview}

TEXTUAL DATA:
Transcript: {result.get('transcript', '')}
Caption: {result.get('caption', '')}
Hashtags: {format_hashtags(result.get('hashtags', ''))}

VISUAL DATA:
Visible Text: {', '.join(visual_data.get('relevant_visible_text', []))}
Visual Entities: {', '.join(visual_data.get('relevant_visual_entities', []))}
Visual Insights: {', '.join(visual_data.get('visual_supporting_points', []))}
Overall Visual Summary: {visual_data.get('overall_visual_summary', '')}

Return ONLY valid minified JSON:
{{
  "contains_products": true,
  "products": [
    {{
      "item_name": "",
      "product_name": "",
      "brand": "",
      "model": "",
      "product_type": "",
      "search_query": "",
      "confidence": "high",
      "evidence_summary": "",
      "source_priority_used": "transcript"
    }}
  ]
}}
""".strip()


def build_marketplace_links(search_query, primary_category="", secondary_category="", product_type=""):
    query = normalize_label(search_query)
    if not query:
        return {}

    query_lower = query.lower()
    category_text = " ".join(
        filter(
            None,
            [
                normalize_label(primary_category).lower(),
                normalize_label(secondary_category).lower(),
                normalize_label(product_type).lower(),
                query_lower,
            ],
        )
    )

    marketplaces = [("amazon", "https://www.amazon.in/s?k="), ("flipkart", "https://www.flipkart.com/search?q=")]

    if any(token in category_text for token in ["skincare", "serum", "perfume", "fragrance", "beauty", "makeup", "hair"]):
        marketplaces = [("nykaa", "https://www.nykaa.com/search/result/?q=")] + marketplaces
    elif any(token in category_text for token in ["fashion", "shoes", "outfit", "streetwear", "clothing", "watch"]):
        marketplaces = [("amazon", "https://www.amazon.in/s?k="), ("flipkart", "https://www.flipkart.com/search?q=")]
    elif any(token in category_text for token in ["phone", "iphone", "laptop", "mac", "airpods", "audio", "tech", "gadget", "electronics"]):
        marketplaces = [("amazon", "https://www.amazon.in/s?k="), ("flipkart", "https://www.flipkart.com/search?q=")]

    encoded = quote_plus(query)
    links = {name: f"{base}{encoded}" for name, base in marketplaces}
    if links:
        first_name = next(iter(links))
        links["best_buy_link"] = links[first_name]
        links["best_marketplace"] = first_name
    return links


def normalize_products(payload):
    contains_products = bool(payload.get("contains_products"))
    products = payload.get("products", [])
    if not isinstance(products, list):
        products = []

    normalized = []
    for product in products:
        if not isinstance(product, dict):
            continue
        product_name = normalize_label(product.get("product_name"))
        search_query = normalize_label(product.get("search_query")) or product_name
        if not product_name and not search_query:
            continue

        normalized.append(
            {
                "item_name": normalize_label(product.get("item_name")),
                "product_name": product_name or search_query,
                "brand": normalize_label(product.get("brand")),
                "model": normalize_label(product.get("model")),
                "product_type": normalize_label(product.get("product_type")),
                "search_query": search_query,
                "confidence": normalize_label(product.get("confidence")) or "medium",
                "evidence_summary": normalize_label(product.get("evidence_summary")),
                "source_priority_used": normalize_label(product.get("source_priority_used")) or "unknown",
            }
        )

    return contains_products or bool(normalized), normalized


def extract_product_data(result, visual_data, classification):
    response = client.chat.completions.create(
        model=SECONDARY_MODEL,
        response_format={"type": "json_object"},
        messages=[{"role": "user", "content": build_product_prompt(result, visual_data, classification)}],
        temperature=0,
    )
    payload = load_json_content(response)
    if "error" in payload:
        return {"contains_products": False, "products": []}

    contains_products, products = normalize_products(payload)
    enriched = []
    for product in products:
        links = build_marketplace_links(
            product.get("search_query") or product.get("product_name"),
            classification.get("primary_category", ""),
            classification.get("secondary_category", ""),
            product.get("product_type", ""),
        )
        enriched.append({**product, "links": links})

    return {
        "contains_products": contains_products,
        "products": enriched,
    }


def match_product_to_item(item_name, products):
    normalized_item = normalize_label(item_name).lower()
    if not normalized_item:
        return products[0] if len(products) == 1 else None

    for product in products:
        keys = [
            normalize_label(product.get("item_name")).lower(),
            normalize_label(product.get("product_name")).lower(),
            normalize_label(product.get("search_query")).lower(),
        ]
        if any(key and (normalized_item == key or normalized_item in key or key in normalized_item) for key in keys):
            return product

    return products[0] if len(products) == 1 else None


def classify_reel(result, visual_data):
    primary_result = request_primary_category(result, visual_data)
    primary_category = primary_result["primary_category"]

    prompt = build_secondary_prompt(result, visual_data, primary_category)
    response = client.chat.completions.create(
        model=SECONDARY_MODEL,
        response_format={"type": "json_object"},
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
    )

    payload = load_json_content(response)
    if "error" in payload:
        return payload

    secondary_category = normalize_label(payload.get("secondary_category")) or primary_category
    items = payload.get("items", [])
    if not isinstance(items, list):
        items = []

    return {
        "primary_category": primary_category,
        "secondary_category": secondary_category,
        "list_title": primary_category,
        "folder": secondary_category,
        "primary_candidates": primary_result["candidates"],
        "items": items,
    }


# --------------------------------------------------
# STEP 4: Pretty print
# --------------------------------------------------
def pretty_print(final_output):
    if "error" in final_output:
        print("❌ Error:", final_output["error"])
        print(final_output["raw"])
        return

    print("\n" + "="*60)
    print(f"📂 Primary: {final_output['primary_category']}")
    print(f"🗂️ Secondary: {final_output['secondary_category']}")
    print("="*60)

    for i, item in enumerate(final_output["items"], 1):
        print(f"{i}. {item['name']} — {item['summary']}")

    if final_output.get("contains_products"):
        print("\n🛒 Products:")
        for product in final_output.get("products", []):
            print(f"- {product.get('product_name')} -> {product.get('links', {}).get('best_buy_link', '')}")

    print("="*60 + "\n")


def summarize_error(exc: Exception, limit: int = 180) -> str:
    text = " ".join(str(exc).strip().split())
    return text[:limit] if text else exc.__class__.__name__


# --------------------------------------------------
# MAIN PIPELINE
# --------------------------------------------------
def run_pipeline(url):
    print("🚀 Processing reel...")

    # Step 1: text
    result = process_reel(url)

    # Step 2 + 3: visuals are helpful, but the MVP should still work without them.
    visual_data = {}
    try:
        video_path = download_reel(url)
    except Exception as exc:
        print(f"⚠️ Video download skipped: {summarize_error(exc)}")
        video_path = ""

    if video_path:
        try:
            visual_data = extract_visual_data(result, video_path)
        except Exception as exc:
            print(f"⚠️ Visual extraction skipped: {summarize_error(exc)}")
            try:
                if os.path.exists(video_path):
                    os.remove(video_path)
            except Exception:
                pass

    # Step 4: classification
    final_output = classify_reel(result, visual_data)

    # Step 5: product extraction + buy links
    try:
        product_data = extract_product_data(result, visual_data, final_output)
        final_output["contains_products"] = product_data["contains_products"]
        final_output["products"] = product_data["products"]
    except Exception as exc:
        print(f"⚠️ Product extraction skipped: {summarize_error(exc)}")
        final_output["contains_products"] = False
        final_output["products"] = []

    return final_output

def process_csv(input_csv, output_csv):
    input_csv = Path(input_csv)
    output_csv = Path(output_csv)
    results = []

    with open(input_csv, "r") as infile:
        reader = csv.reader(infile)

        for row in reader:
            url = row[0].strip()

            if not url:
                continue

            print(f"\n🔄 Processing: {url}")

            try:
                output = run_pipeline(url)

                if "error" in output:
                    results.append(
                        [
                            url,
                            "Failed Reels",
                            "Processing Failures",
                            "failed",
                            "Processing Failed",
                            normalize_label(output.get("error")) or "Model returned invalid output.",
                            "no",
                            "",
                            "",
                            "",
                            "",
                            "",
                            "",
                            "",
                            "",
                            "",
                        ]
                    )
                    continue

                primary = output.get("primary_category", "")
                secondary = output.get("secondary_category", "") or primary
                folder = output.get("folder", "") or secondary or primary
                products = output.get("products", [])

                for item in output.get("items", []):
                    name = item.get("name", "")
                    summary = item.get("summary", "")
                    product = match_product_to_item(name, products)
                    links = (product or {}).get("links", {})
                    results.append(
                        [
                            url,
                            primary,
                            secondary,
                            folder,
                            name,
                            summary,
                            "yes" if output.get("contains_products") else "no",
                            (product or {}).get("product_name", ""),
                            (product or {}).get("brand", ""),
                            (product or {}).get("model", ""),
                            (product or {}).get("product_type", ""),
                            (product or {}).get("search_query", ""),
                            links.get("best_buy_link", ""),
                            links.get("amazon", ""),
                            links.get("flipkart", ""),
                            links.get("nykaa", ""),
                        ]
                    )

                if not output.get("items"):
                    product = products[0] if products else {}
                    links = product.get("links", {})
                    results.append(
                        [
                            url,
                            primary,
                            secondary,
                            folder,
                            "",
                            "",
                            "yes" if output.get("contains_products") else "no",
                            product.get("product_name", ""),
                            product.get("brand", ""),
                            product.get("model", ""),
                            product.get("product_type", ""),
                            product.get("search_query", ""),
                            links.get("best_buy_link", ""),
                            links.get("amazon", ""),
                            links.get("flipkart", ""),
                            links.get("nykaa", ""),
                        ]
                    )

            except Exception as e:
                print(f"❌ Failed: {url} | {e}")
                results.append(
                    [
                        url,
                        "Failed Reels",
                        "Processing Failures",
                        "failed",
                        "Processing Failed",
                        f"Processing error: {summarize_error(e)}",
                        "no",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                    ]
                )

    # Write output CSV
    with open(output_csv, "w", newline="") as outfile:
        writer = csv.writer(outfile)

        # Header
        writer.writerow(
            [
                "URL",
                "Primary Category",
                "Secondary Category",
                "Folder",
                "Item Name",
                "Summary",
                "Contains Product",
                "Product Name",
                "Product Brand",
                "Product Model",
                "Product Type",
                "Product Search Query",
                "Best Buy Link",
                "Amazon Link",
                "Flipkart Link",
                "Nykaa Link",
            ]
        )

        # Data
        writer.writerows(results)

    print(f"\n✅ Done! Output saved to: {output_csv}")
# --------------------------------------------------
# RUN



if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process Instagram reel URLs into foldered CSV output.")
    parser.add_argument(
        "--input",
        default=str(BASE_DIR / "tech - Sheet1.csv"),
        help="Input CSV containing reel URLs, one per row.",
    )
    parser.add_argument(
        "--output",
        default=str(BASE_DIR / "final_output_TECH.csv"),
        help="Output CSV path.",
    )
    args = parser.parse_args()

    process_csv(args.input, args.output)
    
    
