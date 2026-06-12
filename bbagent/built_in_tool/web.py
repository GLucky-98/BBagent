"""
Web tools - Search the web and fetch readable URL content.
"""

from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import parse_qs, unquote, urlparse

import httpx

from ..core.tool import Tool
from .policy import Policy

SEARCH_ENDPOINT = "https://html.duckduckgo.com/html/"


@dataclass
class WebResponse:
    text: str
    url: str
    status_code: int
    content_type: str
    truncated: bool = False


def _resolve_policy(policy_or_config: Policy | dict | None) -> Policy:
    if isinstance(policy_or_config, Policy):
        return policy_or_config
    if isinstance(policy_or_config, dict) and policy_or_config.get("policy"):
        return Policy(**policy_or_config["policy"])
    return Policy()


def _validate_http_url(url: str) -> tuple[bool, str]:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False, "URL must use http or https"
    if not parsed.netloc:
        return False, "URL host is required"
    return True, ""


def _host_allowed(url: str, allowed_domains: list[str] | None) -> bool:
    if not allowed_domains:
        return True

    host = (urlparse(url).hostname or "").lower().rstrip(".")
    for domain in allowed_domains:
        allowed = domain.lower().strip().lstrip(".").rstrip(".")
        if host == allowed or host.endswith(f".{allowed}"):
            return True
    return False


async def _get_text(
    url: str,
    *,
    params: dict[str, str] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 10.0,
    max_bytes: int = 200_000,
) -> WebResponse:
    chunks: list[bytes] = []
    total = 0
    truncated = False

    async with (
        httpx.AsyncClient(follow_redirects=True, timeout=timeout) as client,
        client.stream("GET", url, params=params, headers=headers) as response,
    ):
        response.raise_for_status()
        async for chunk in response.aiter_bytes():
            if total + len(chunk) > max_bytes:
                keep = max(0, max_bytes - total)
                if keep:
                    chunks.append(chunk[:keep])
                truncated = True
                break
            chunks.append(chunk)
            total += len(chunk)

        raw = b"".join(chunks)
        encoding = response.encoding or "utf-8"
        return WebResponse(
            text=raw.decode(encoding, errors="replace"),
            url=str(response.url),
            status_code=response.status_code,
            content_type=response.headers.get("content-type", ""),
            truncated=truncated,
        )


class _ReadableHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs):
        if tag in {"script", "style", "noscript", "svg"}:
            self._skip_depth += 1
        if tag in {"br", "p", "div", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6"}:
            self._parts.append("\n")

    def handle_endtag(self, tag: str):
        if tag in {"script", "style", "noscript", "svg"} and self._skip_depth:
            self._skip_depth -= 1
        if tag in {"p", "div", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6"}:
            self._parts.append("\n")

    def handle_data(self, data: str):
        if self._skip_depth:
            return
        text = " ".join(data.split())
        if text:
            self._parts.append(text)

    def text(self) -> str:
        lines = []
        current: list[str] = []
        for part in self._parts:
            if part == "\n":
                line = " ".join(current).strip()
                if line:
                    lines.append(line)
                current = []
            else:
                current.append(part)
        line = " ".join(current).strip()
        if line:
            lines.append(line)
        return "\n".join(lines)


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str = ""


def _decode_duckduckgo_url(href: str) -> str:
    if href.startswith("//"):
        href = f"https:{href}"
    parsed = urlparse(href)
    params = parse_qs(parsed.query)
    uddg = params.get("uddg")
    if uddg:
        return unquote(uddg[0])
    return href


class _DuckDuckGoHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.results: list[SearchResult] = []
        self._current_title: list[str] = []
        self._current_href = ""
        self._in_title = False
        self._in_snippet = False
        self._snippet_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs):
        attr_map = dict(attrs)
        classes = set((attr_map.get("class") or "").split())
        if tag == "a" and "result__a" in classes:
            self._in_title = True
            self._current_title = []
            self._current_href = attr_map.get("href") or ""
        elif "result__snippet" in classes:
            self._in_snippet = True
            self._snippet_parts = []

    def handle_endtag(self, tag: str):
        if tag == "a" and self._in_title:
            title = " ".join(" ".join(self._current_title).split())
            if title and self._current_href:
                self.results.append(
                    SearchResult(title=title, url=_decode_duckduckgo_url(self._current_href))
                )
            self._in_title = False
        elif self._in_snippet and tag in {"a", "div", "td"}:
            snippet = " ".join(" ".join(self._snippet_parts).split())
            if snippet and self.results and not self.results[-1].snippet:
                self.results[-1].snippet = snippet
            self._in_snippet = False

    def handle_data(self, data: str):
        if self._in_title:
            self._current_title.append(data)
        elif self._in_snippet:
            self._snippet_parts.append(data)


def _extract_readable_text(html: str) -> str:
    parser = _ReadableHTMLParser()
    parser.feed(html)
    return parser.text()


def _format_fetch_result(
    response: WebResponse,
    content: str,
    *,
    max_chars: int,
) -> str:
    output_truncated = False
    if len(content) > max_chars:
        content = content[:max_chars]
        output_truncated = True

    markers = []
    if response.truncated:
        markers.append("response")
    if output_truncated:
        markers.append("output")
    truncated = f" | Truncated: {', '.join(markers)}" if markers else ""

    return (
        f"{content}\n\n"
        f"[URL: {response.url} | Status: {response.status_code} | "
        f"Content-Type: {response.content_type or 'unknown'} | Returned: {len(content)} chars{truncated}]"
    )


def create_fetch_url_tool(policy_or_config: Policy | dict | None = None) -> Tool:
    policy = _resolve_policy(policy_or_config)

    async def fetch_url_func(url: str, max_chars: int | None = None) -> str:
        """Fetch a URL and return readable text content."""
        url = (url or "").strip()
        ok, error = _validate_http_url(url)
        if not ok:
            return f"Error: {error}"
        if not _host_allowed(url, policy.web_allowed_domains):
            return f"Error: URL host is not allowed by policy: {urlparse(url).hostname}"

        try:
            response = await _get_text(
                url,
                headers={"User-Agent": policy.web_user_agent},
                timeout=policy.web_timeout,
                max_bytes=policy.web_max_response_size,
            )
        except httpx.HTTPStatusError as e:
            return f"Error fetching URL: HTTP {e.response.status_code}"
        except Exception as e:
            return f"Error fetching URL: {e!s}"

        content_type = response.content_type.lower()
        content = _extract_readable_text(response.text) if "html" in content_type else response.text

        content = content.strip()
        if not content:
            content = "(empty response)"

        limit = max_chars or policy.web_max_output_size
        limit = max(1, min(limit, policy.web_max_output_size))
        return _format_fetch_result(response, content, max_chars=limit)

    input_schema = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "HTTP or HTTPS URL to fetch",
            },
            "max_chars": {
                "type": "number",
                "description": "Maximum characters to return, capped by tool policy",
            },
        },
        "required": ["url"],
    }

    return Tool(
        fetch_url_func,
        name="fetch_url",
        description="Fetch a web URL and return readable text content.",
        input_schema=input_schema,
        source="built_in",
    )


def create_web_search_tool(policy_or_config: Policy | dict | None = None) -> Tool:
    policy = _resolve_policy(policy_or_config)

    async def web_search_func(query: str, max_results: int | None = None) -> str:
        """Search the web and return result titles, URLs, and snippets."""
        query = (query or "").strip()
        if not query:
            return "Error: query is required"

        limit = max_results or policy.web_search_max_results
        limit = max(1, min(limit, 20))

        try:
            response = await _get_text(
                SEARCH_ENDPOINT,
                params={"q": query},
                headers={
                    "User-Agent": policy.web_user_agent,
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                timeout=policy.web_timeout,
                max_bytes=policy.web_max_response_size,
            )
        except httpx.HTTPStatusError as e:
            return f"Error searching web: HTTP {e.response.status_code}"
        except Exception as e:
            return f"Error searching web: {e!s}"

        parser = _DuckDuckGoHTMLParser()
        parser.feed(response.text)

        results = []
        seen_urls = set()
        for item in parser.results:
            if not _validate_http_url(item.url)[0]:
                continue
            if not _host_allowed(item.url, policy.web_allowed_domains):
                continue
            if item.url in seen_urls:
                continue
            seen_urls.add(item.url)
            results.append(item)
            if len(results) >= limit:
                break

        if not results:
            return f'No search results found for "{query}".'

        lines = [f'Search results for "{query}":']
        for idx, item in enumerate(results, start=1):
            lines.append(f"{idx}. {item.title}")
            lines.append(f"   URL: {item.url}")
            if item.snippet:
                lines.append(f"   Snippet: {item.snippet}")
        lines.append(f"\n[Search: duckduckgo_html | Returned: {len(results)} results]")
        return "\n".join(lines)

    input_schema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query",
            },
            "max_results": {
                "type": "number",
                "description": "Maximum number of results to return, capped at 20",
            },
        },
        "required": ["query"],
    }

    return Tool(
        web_search_func,
        name="web_search",
        description="Search the web and return result titles, URLs, and snippets.",
        input_schema=input_schema,
        source="built_in",
    )
