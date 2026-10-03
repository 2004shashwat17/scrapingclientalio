"""Live check of the search backend (DuckDuckGo first, Google fallback)."""

from backend.crawlers.google_web_search import GoogleWebSearch

QUERIES = ["acme logistics mumbai", "courier companies in Bengaluru India"]

ws = GoogleWebSearch()
try:
    for query in QUERIES:
        results = ws.search(query)
        print(f"\n{query!r} -> {len(results)} results")
        for item in results[:4]:
            print(f"    {item['url'][:70]}")
            print(f"      title: {item['title'][:60]}")
            if item.get("snippet"):
                print(f"      snip:  {item['snippet'][:70]}")
finally:
    if ws._session is not None:
        ws._session.close()