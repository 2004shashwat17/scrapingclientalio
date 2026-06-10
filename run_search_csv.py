import csv
import json
import sys
from datetime import datetime
from pathlib import Path

from backend.services.search_service import SearchService
from backend.storage.csv_store import DATA_DIR
from backend.utils.settings import settings

CSV_FILENAME = "clientalio_6000_search_keywords.csv"
PROGRESS_FILENAME = "search_progress.json"


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
    csv_path = Path(__file__).resolve().parent / CSV_FILENAME
    progress_path = DATA_DIR / PROGRESS_FILENAME

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

    search_service = SearchService()
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
            next_index = index + 1
            save_progress(progress_path, csv_path, next_index, current_keyword, len(keywords))
    except KeyboardInterrupt:
        resume_index = current_index + 1
        save_progress(progress_path, csv_path, resume_index, current_keyword, len(keywords))
        print(f"\nInterrupted. Progress saved at keyword index {resume_index}. Restart to continue.")
        sys.exit(1)

    if end_index >= len(keywords):
        if progress_path.exists():
            progress_path.unlink(missing_ok=True)
        print("\nAll keywords processed. Progress file removed.")
    else:
        print(f"\nBatch complete. Progress saved. Continue from keyword index {end_index} on next run.")


if __name__ == "__main__":
    main()
