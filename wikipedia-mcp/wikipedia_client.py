from urllib.parse import quote
import httpx

WIKIPEDIA_API = "https://en.wikipedia.org"
USER_AGENT = "WikipediaMcpSamplingDemo/0.2 (https://github.com/loitrinhxuan-agilityio/ai-tools-training)"


async def search_articles(topic: str, limit: int = 3) -> list[dict[str, str]]:
    """Search Wikipedia and retrieve compact article summaries."""
    if not topic.strip():
        raise ValueError("topic must not be empty")

    timeout = httpx.Timeout(15.0, connect=5.0)
    headers = {"User-Agent": USER_AGENT}

    async with httpx.AsyncClient(timeout=timeout, headers=headers) as client:
        response = await client.get(
            f"{WIKIPEDIA_API}/w/rest.php/v1/search/page",
            params={"q": topic, "limit": max(1, min(limit, 5))},
        )
        response.raise_for_status()
        pages = response.json().get("pages", [])

        articles = []
        for page in pages:
            title = page.get("title")
            if not title:
                continue
            slug = quote(title.replace(" ", "_"), safe="")
            summary_response = await client.get(
                f"{WIKIPEDIA_API}/api/rest_v1/page/summary/{slug}"
            )
            summary_response.raise_for_status()
            summary = summary_response.json()
            articles.append({
                "title": summary.get("title", title),
                "extract": summary.get("extract", page.get("excerpt", "")),
                "url": summary.get("content_urls", {}).get("desktop", {}).get(
                    "page", f"https://en.wikipedia.org/wiki/{slug}"
                ),
            })

    if not articles:
        raise RuntimeError(f"No Wikipedia articles found for: {topic}")
    return articles
