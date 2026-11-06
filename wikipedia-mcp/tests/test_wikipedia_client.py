import httpx
import pytest
import respx
from wikipedia_client import search_articles


@pytest.mark.asyncio
@respx.mock
async def test_search_articles_returns_summary():
    respx.get("https://en.wikipedia.org/w/rest.php/v1/search/page").mock(
        return_value=httpx.Response(
            200, json={"pages": [{"title": "Ada Lovelace", "excerpt": "Mathematician"}]}
        )
    )
    respx.get("https://en.wikipedia.org/api/rest_v1/page/summary/Ada_Lovelace").mock(
        return_value=httpx.Response(200, json={
            "title": "Ada Lovelace",
            "extract": "Ada Lovelace was an English mathematician.",
            "content_urls": {"desktop": {"page": "https://en.wikipedia.org/wiki/Ada_Lovelace"}},
        })
    )
    result = await search_articles("Ada Lovelace", limit=1)
    assert result[0]["title"] == "Ada Lovelace"
    assert "mathematician" in result[0]["extract"]


@pytest.mark.asyncio
async def test_empty_topic_is_rejected():
    with pytest.raises(ValueError, match="topic must not be empty"):
        await search_articles("   ")
