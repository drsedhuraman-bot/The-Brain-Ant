import httpx

_DUCKDUCKGO_URL = "https://api.duckduckgo.com/"


async def web_search(query: str, num_results: int = 5) -> str:
    """Perform a web search using DuckDuckGo Instant Answer API."""
    params = {"q": query, "format": "json", "no_html": "1", "skip_disambig": "1"}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(_DUCKDUCKGO_URL, params=params)
            resp.raise_for_status()
            data = resp.json()

        results: list[str] = []

        if data.get("Abstract"):
            results.append(f"Summary: {data['Abstract']}\nSource: {data.get('AbstractURL', '')}")

        for topic in data.get("RelatedTopics", [])[:num_results]:
            if isinstance(topic, dict) and topic.get("Text"):
                url = topic.get("FirstURL", "")
                results.append(f"- {topic['Text']}\n  URL: {url}")

        if not results:
            return f"No results found for: {query}"

        return "\n\n".join(results)

    except Exception as exc:
        return f"Search error for '{query}': {exc}"
