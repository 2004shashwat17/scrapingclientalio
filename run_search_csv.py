import argparse
import csv
import json
import sys
import time
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

# Fail with setup instructions rather than a bare ModuleNotFoundError traceback.
try:
    from backend.services.search_service import SearchService
    from backend.storage.csv_store import DATA_DIR, set_active_product
    from backend.utils.settings import PRODUCTS, settings
except ModuleNotFoundError as exc:
    missing = exc.name or "a dependency"
    print(f"\nMissing dependency: {missing}\n")
    print(f"You are running: {sys.executable}\n")
    print("Set up the project environment once, then re-run:\n")
    print("  python3 -m venv .venv")
    print("  .venv/bin/pip install -r requirements.txt")
    print("  .venv/bin/python -m playwright install chromium\n")
    print(f"Then:  .venv/bin/python {Path(__file__).name}\n")
    raise SystemExit(1) from None

# Numbered menu shown at the start of the run.
PRODUCT_MENU = {str(index): key for index, key in enumerate(PRODUCTS, start=1)}
PROGRESS_FILENAME = "search_progress.json"


def prompt_product() -> dict:
    """Ask which product's keyword list to scrape. Returns the selected product dict."""
    print("\nSelect the product to scrape:\n")
    for number, key in PRODUCT_MENU.items():
        product = PRODUCTS[key]
        print(f"  {number}) {product['name']:<10} -> {product['keywords_file']}")

    while True:
        try:
            choice = input("\nEnter 1 or 2: ").strip()
        except KeyboardInterrupt:
            print("\nInput cancelled. Exiting.")
            sys.exit(1)
        if choice in PRODUCT_MENU:
            return PRODUCTS[PRODUCT_MENU[choice]]
        for product in PRODUCTS.values():
            if choice.lower() == product["key"]:
                return product
        print("Please enter 1 or 2.")


def load_keywords(csv_path: Path) -> list[str]:
    if not csv_path.exists():
        raise FileNotFoundError(f"Keyword CSV not found at {csv_path}")

    keywords: list[str] = []
    with csv_path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if "Keyword" in row:
                keyword = row["Keyword"]
            elif "keyword" in row:
                keyword = row["keyword"]
            elif "KeyWord" in row:
                keyword = row["KeyWord"]
            else:
                raise ValueError("CSV file must include a 'Keyword' column")

            if keyword is None:
                continue
            keyword = str(keyword).strip()
            if not keyword or keyword.lower() == "keyword":
                continue
            keywords.append(keyword)
    return keywords


def load_progress(progress_path: Path, csv_path: Path) -> dict:
    if not progress_path.exists():
        return {}

    try:
        with progress_path.open("r", encoding="utf-8") as handle:
            progress = json.load(handle)
    except Exception:
        return {}

    if progress.get("csv_path") != str(csv_path.resolve()):
        return {}

    return progress


def save_progress(progress_path: Path, csv_path: Path, next_index: int, last_keyword: str, total_count: int) -> None:
    progress_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "csv_path": str(csv_path.resolve()),
        "next_index": next_index,
        "last_keyword": last_keyword,
        "total_count": total_count,
        "saved_at": datetime.utcnow().isoformat(),
    }
    with progress_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)


def prompt_count(max_count: int) -> int:
    while True:
        try:
            raw = input(f"How many keywords do you want to process now? (1 - {max_count}): ").strip()
            if not raw:
                print("Please enter a number.")
                continue
            count = int(raw)
            if count < 1 or count > max_count:
                print(f"Enter a number between 1 and {max_count}.")
                continue
            return count
        except ValueError:
            print("Invalid input. Please enter an integer.")
        except KeyboardInterrupt:
            print("\nInput cancelled. Exiting.")
            sys.exit(1)


def prompt_resume(progress: dict) -> bool:
    if not progress:
        return False
    last_keyword = progress.get("last_keyword")
    next_index = progress.get("next_index", 0)
    total = progress.get("total_count")
    print("Found existing search progress:")
    print(f"  Last completed keyword index: {next_index - 1}")
    print(f"  Last keyword: {last_keyword}")
    if total is not None:
        print(f"  Total keywords in CSV: {total}")

    while True:
        try:
            answer = input("Resume from the saved progress? [y/N]: ").strip().lower()
        except KeyboardInterrupt:
            print("\nInput cancelled. Exiting.")
            sys.exit(1)
        if answer in {"y", "yes"}:
            return True
        if answer in {"n", "no", ""}:
            return False
        print("Please answer 'y' or 'n'.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Search keywords and optionally push leads to the Lead Capture API.")
    parser.add_argument("product", nargs="?", help="Product key, e.g. clientalio or dropproof")
    parser.add_argument(
        "--push", action="store_true",
        help="Push this keyword's saved leads to the API after the keyword finishes",
    )
    parser.add_argument(
        "--target", choices=("auto", "deployed", "local", "local-https"), default="local-https",
        help="API target used with --push (default: local-https)",
    )
    args = parser.parse_args()

    # Optional product argument skips the prompt, e.g. `python run_search_csv.py dropproof`.
    selected_arg = args.product
    if selected_arg:
        product = next((p for p in PRODUCTS.values() if p["key"] == selected_arg.lower()), None)
        if product is None:
            print(f"Unknown product '{selected_arg}'. Choose one of: {', '.join(PRODUCT_MENU)}")
            sys.exit(1)
    else:
        product = prompt_product()

    # Everything downstream (LeadStore, LeadRepository) writes to the product's CSV.
    set_active_product(product["key"])

    csv_path = BASE_DIR / product["keywords_file"]
    # Per-product progress file so the two keyword lists never resume into each other.
    progress_path = DATA_DIR / f"{product['key']}_{PROGRESS_FILENAME}"

    print(f"\nSelected product: {product['name']}")
    print(f"  Keywords: {csv_path.name}")
    print(f"  Leads:    {product['leads_file']}")

    try:
        keywords = load_keywords(csv_path)
    except FileNotFoundError as exc:
        print(f"Error: {exc}")
        sys.exit(1)

    if not keywords:
        print("No keywords found in the CSV file.")
        sys.exit(1)

    progress = load_progress(progress_path, csv_path)
    if progress and prompt_resume(progress):
        start_index = int(progress.get("next_index", 0))
    else:
        start_index = 0

    remaining = len(keywords) - start_index
    if remaining <= 0:
        print("All keywords are already processed. Remove the progress file to restart.")
        sys.exit(0)

    print(f"Starting from keyword index {start_index} of {len(keywords)}.")
    count = prompt_count(remaining)
    end_index = min(start_index + count, len(keywords))

    pusher = None
    if args.push:
        from push_leads_to_api import LivePusher

        pusher = LivePusher(product["name"], target=args.target)

    keyword_leads = []
    search_service = SearchService(on_saved=keyword_leads.append if pusher else None)
    current_index = start_index
    current_keyword = ""

    try:
        for index in range(start_index, end_index):
            current_index = index
            current_keyword = keywords[index]
            print(f"\n[{index+1}/{len(keywords)}] Searching for: {current_keyword}")
            try:
                results = search_service.search_and_save(
                    query=current_keyword,
                    limit=settings.max_search_results,
                )
                print(f"  Completed. Saved {len(results)} results for keyword: '{current_keyword}'")
            except Exception as exc:
                print(f"  Error on '{current_keyword}': {exc}")
            finally:
                if pusher and keyword_leads:
                    print(f"  Pushing {len(keyword_leads)} saved lead(s) for this keyword...")
                    for lead in keyword_leads:
                        pusher.push(lead)
                    keyword_leads.clear()
            next_index = index + 1
            save_progress(progress_path, csv_path, next_index, current_keyword, len(keywords))
            # Pause between keywords so Google sees a human, not a burst.
            if index + 1 < end_index:
                time.sleep(settings.browser_request_delay * 2)
    except KeyboardInterrupt:
        resume_index = current_index + 1
        save_progress(progress_path, csv_path, resume_index, current_keyword, len(keywords))
        print(f"\nInterrupted. Progress saved at keyword index {resume_index}. Restart to continue.")
        sys.exit(1)
    finally:
        # Always close the browser, even on Ctrl+C, so the profile unlocks.
        search_service.close()

    if end_index >= len(keywords):
        if progress_path.exists():
            progress_path.unlink(missing_ok=True)
        print("\nAll keywords processed. Progress file removed.")
    else:
        print(f"\nBatch complete. Progress saved. Continue from keyword index {end_index} on next run.")


if __name__ == "__main__":
    main()
