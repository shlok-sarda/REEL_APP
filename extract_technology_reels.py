import csv
import json
from pathlib import Path
from urllib.parse import urlparse

import joblib


BASE_DIR = Path(__file__).resolve().parent
CACHE_JSON = BASE_DIR / "cache.json"
CATALOG_CSV = BASE_DIR / "saved_reels_accumulated.csv"
CLASSIFIER_PATH = BASE_DIR / "reel_classifier.pkl"
VECTORIZER_PATH = BASE_DIR / "tfidf_vectorizer.pkl"
ALL_PREDICTIONS_CSV = BASE_DIR / "saved_reels_model_predictions.csv"
TECH_URLS_CSV = BASE_DIR / "technology_reel_urls.csv"
TECH_LABEL = "Technology & Gadgets"


def normalize(value):
    return " ".join((value or "").strip().split())


def shortcode_from_url(url):
    parsed = urlparse(normalize(url))
    parts = [part for part in parsed.path.split("/") if part]
    return parts[-1] if parts else normalize(url).rstrip("/")


def load_unique_urls(catalog_csv):
    urls = []
    seen = set()
    with open(catalog_csv, newline="", encoding="utf-8") as infile:
        reader = csv.DictReader(infile)
        for row in reader:
            url = normalize(row.get("URL"))
            if url and url not in seen:
                seen.add(url)
                urls.append(url)
    return urls


def build_combined_text(cache_entry):
    transcript = cache_entry.get("transcript") or ""
    caption = cache_entry.get("caption") or ""
    hashtags = cache_entry.get("hashtags") or ""
    creator = cache_entry.get("creator") or ""
    return " ".join([transcript * 2, caption, hashtags, creator]).strip()


def predict_reels():
    cache = json.loads(CACHE_JSON.read_text(encoding="utf-8"))
    urls = load_unique_urls(CATALOG_CSV)
    vectorizer = joblib.load(VECTORIZER_PATH)
    classifier = joblib.load(CLASSIFIER_PATH)

    rows = []
    for url in urls:
        shortcode = shortcode_from_url(url)
        cache_entry = cache.get(shortcode, {}) if isinstance(cache.get(shortcode), dict) else {}
        combined_text = build_combined_text(cache_entry)

        if not combined_text:
            rows.append(
                {
                    "URL": url,
                    "Shortcode": shortcode,
                    "Predicted Label": "NO_TEXT",
                    "Confidence": "0.0000",
                    "Is Technology": "False",
                    "Caption": "",
                    "Transcript Preview": "",
                }
            )
            continue

        features = vectorizer.transform([combined_text])
        predicted_label = classifier.predict(features)[0]
        probabilities = classifier.predict_proba(features)[0]
        confidence = float(probabilities.max())

        rows.append(
            {
                "URL": url,
                "Shortcode": shortcode,
                "Predicted Label": predicted_label,
                "Confidence": f"{confidence:.4f}",
                "Is Technology": str(predicted_label == TECH_LABEL),
                "Caption": cache_entry.get("caption", ""),
                "Transcript Preview": (cache_entry.get("transcript", "") or "")[:300],
            }
        )

    return rows


def write_csv(path, rows, fieldnames):
    with open(path, "w", newline="", encoding="utf-8") as outfile:
        writer = csv.DictWriter(outfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main():
    rows = predict_reels()
    prediction_fields = [
        "URL",
        "Shortcode",
        "Predicted Label",
        "Confidence",
        "Is Technology",
        "Caption",
        "Transcript Preview",
    ]
    write_csv(ALL_PREDICTIONS_CSV, rows, prediction_fields)

    tech_rows = [
        {
            "URL": row["URL"],
            "Shortcode": row["Shortcode"],
            "Predicted Label": row["Predicted Label"],
            "Confidence": row["Confidence"],
        }
        for row in rows
        if row["Predicted Label"] == TECH_LABEL
    ]
    write_csv(TECH_URLS_CSV, tech_rows, ["URL", "Shortcode", "Predicted Label", "Confidence"])

    print(f"Saved all predictions: {ALL_PREDICTIONS_CSV}")
    print(f"Saved technology URLs: {TECH_URLS_CSV}")
    print(f"Total reels classified: {len(rows)}")
    print(f"Technology reels found: {len(tech_rows)}")


if __name__ == "__main__":
    main()
