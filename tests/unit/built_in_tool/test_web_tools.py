import pytest

from bbagent.built_in_tool import web
from bbagent.built_in_tool.policy import Policy


@pytest.mark.asyncio
async def test_fetch_url_extracts_readable_html(monkeypatch):
    async def fake_get_text(*args, **kwargs):
        return web.WebResponse(
            text="""
                <html>
                  <head><title>Example</title><style>.x{display:none}</style></head>
                  <body><script>secret()</script><h1>Hello</h1><p>World</p></body>
                </html>
            """,
            url="https://example.com/page",
            status_code=200,
            content_type="text/html; charset=utf-8",
        )

    monkeypatch.setattr(web, "_get_text", fake_get_text)

    result = await web.create_fetch_url_tool(Policy()).async_invoke(
        {"url": "https://example.com/page"}
    )

    assert "Hello" in result
    assert "World" in result
    assert "secret()" not in result
    assert "[URL: https://example.com/page | Status: 200" in result


@pytest.mark.asyncio
async def test_fetch_url_blocks_hosts_outside_policy():
    tool = web.create_fetch_url_tool(Policy(web_allowed_domains=["example.com"]))

    result = await tool.async_invoke({"url": "https://not-example.test/page"})

    assert result == "Error: URL host is not allowed by policy: not-example.test"


@pytest.mark.asyncio
async def test_web_search_parses_results_and_decodes_redirects(monkeypatch):
    async def fake_get_text(*args, **kwargs):
        return web.WebResponse(
            text="""
                <html><body>
                  <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fa">
                    Example Result
                  </a>
                  <a class="result__snippet">A useful snippet.</a>
                  <a class="result__a" href="https://docs.example.com/b">Docs Result</a>
                </body></html>
            """,
            url="https://html.duckduckgo.com/html/?q=example",
            status_code=200,
            content_type="text/html",
        )

    monkeypatch.setattr(web, "_get_text", fake_get_text)

    result = await web.create_web_search_tool(Policy()).async_invoke(
        {"query": "example", "max_results": 2}
    )

    assert 'Search results for "example":' in result
    assert "1. Example Result" in result
    assert "URL: https://example.com/a" in result
    assert "Snippet: A useful snippet." in result
    assert "2. Docs Result" in result


@pytest.mark.asyncio
async def test_web_search_respects_allowed_domains(monkeypatch):
    async def fake_get_text(*args, **kwargs):
        return web.WebResponse(
            text="""
                <a class="result__a" href="https://blocked.test/a">Blocked</a>
                <a class="result__a" href="https://example.com/b">Allowed</a>
            """,
            url="https://html.duckduckgo.com/html/?q=example",
            status_code=200,
            content_type="text/html",
        )

    monkeypatch.setattr(web, "_get_text", fake_get_text)

    result = await web.create_web_search_tool(
        Policy(web_allowed_domains=["example.com"])
    ).async_invoke({"query": "example", "max_results": 5})

    assert "Blocked" not in result
    assert "Allowed" in result
    assert "https://example.com/b" in result
