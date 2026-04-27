import json
from pathlib import Path

from debug_single_reel import build_debug_report, pretty_print_report


# Paste the reel URL here, then press Run in VS Code.
REEL_URL = "https://www.instagram.com/reel/DXUlpUKujdj/"

# Set this to True if you want a JSON debug file saved beside this script.
SAVE_JSON_REPORT = True


def main():
    if not REEL_URL or "instagram.com" not in REEL_URL:
        raise ValueError("Paste a valid Instagram reel/post URL into REEL_URL first.")

    report = build_debug_report(REEL_URL)
    pretty_print_report(report)

    if SAVE_JSON_REPORT:
        output_path = Path(__file__).resolve().parent / "single_reel_debug_report.json"
        output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"\nSaved JSON report: {output_path}")


if __name__ == "__main__":
    main()
