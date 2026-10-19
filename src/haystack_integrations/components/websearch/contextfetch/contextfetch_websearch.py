# SPDX-FileCopyrightText: 2026-present ContextFetch
#
# SPDX-License-Identifier: Apache-2.0

from typing import Any

from haystack import Document, component
from haystack.utils import Secret

from contextfetch import ContextFetch, SearchResponse

_CONTENT_OPTIONS = {"text", "highlights", "pruned_context"}


@component
class ContextFetchWebSearch:
    """
    A component that uses ContextFetch to search the web and return results as Haystack Documents.

    This component wraps the [ContextFetch Search API](https://contextfetch.dev/docs/reference), which returns
    page content as Markdown with each result. By default each Document holds the page pruned to the parts
    relevant to the query.

    Without an API key, requests use the keyless tier, which has a small daily allowance per IP.
    Get a key at [contextfetch.dev/get-started](https://contextfetch.dev/get-started).

    ### Usage example

    ```python
    from haystack_integrations.components.websearch.contextfetch import ContextFetchWebSearch

    websearch = ContextFetchWebSearch(top_k=5)
    result = websearch.run(query="What are asyncio task groups?")
    documents = result["documents"]
    links = result["links"]
    ```
    """

    def __init__(
        self,
        api_key: Secret = Secret.from_env_var("CONTEXTFETCH_API_KEY", strict=False),
        top_k: int | None = 10,
        search_params: dict[str, Any] | None = None,
    ) -> None:
        """
        Initialize the ContextFetchWebSearch component.

        :param api_key:
            API key for ContextFetch. Defaults to the `CONTEXTFETCH_API_KEY` environment variable. Resolved
            leniently: when no key resolves, requests use the keyless tier. Pass
            `Secret.from_env_var("CONTEXTFETCH_API_KEY")` to require a key.
        :param top_k:
            Maximum number of results to return. Maps to `num_results` in the ContextFetch API.
        :param search_params:
            Additional keyword arguments for `contextfetch.ContextFetch.search`: `include_domains`,
            `exclude_domains`, `start_published_date`, and the content options `text`, `highlights` and
            `pruned_context`. When none of the content options is given, `pruned_context=True` is sent.
            Document content is the page `text` when requested, else `prunedContext`, else the
            `highlights` joined by blank lines.
            See the [ContextFetch API reference](https://contextfetch.dev/docs/reference) for details.
        """
        self.api_key = api_key
        self.top_k = top_k
        self.search_params = search_params
        self._client: ContextFetch | None = None

    def warm_up(self) -> None:
        """
        Initialize the ContextFetch client.

        Called automatically on first use. Can be called explicitly to avoid cold-start latency.
        """
        if self._client is None:
            self._client = ContextFetch(api_key=self.api_key.resolve_value())

    @component.output_types(documents=list[Document], links=list[str])
    def run(self, query: str, search_params: dict[str, Any] | None = None) -> dict[str, Any]:
        """
        Search the web using ContextFetch and return results as Documents.

        :param query: Search query string.
        :param search_params:
            Optional per-run override of search parameters.
            If provided, fully replaces the init-time `search_params`.
        :returns: A dictionary with:
            - `documents`: List of Documents with page content as Markdown and `title` and `url` in `meta`.
            - `links`: List of URLs from the search results.
        :raises contextfetch.ContextFetchError: If the ContextFetch API request fails.
        """
        self.warm_up()
        assert self._client is not None  # noqa: S101

        params = (search_params if search_params is not None else self.search_params or {}).copy()
        if "num_results" not in params and self.top_k is not None:
            params["num_results"] = self.top_k
        if not params.keys() & _CONTENT_OPTIONS:
            params["pruned_context"] = True

        response = self._client.search(query, **params)
        return self._parse_response(response)

    @staticmethod
    def _parse_response(response: SearchResponse) -> dict[str, Any]:
        """
        Convert a ContextFetch search response to Haystack Documents and links.

        :param response: ContextFetch search response dictionary.
        :returns: Dictionary with `documents` and `links` keys.
        """
        documents: list[Document] = []
        links: list[str] = []

        for result in response.get("results", []):
            url = result.get("url", "")
            content = result.get("text") or result.get("prunedContext") or "\n\n".join(result.get("highlights") or [])
            documents.append(
                Document(
                    content=content, meta={"title": result.get("title") or "", "url": url}, score=result.get("score")
                )
            )
            if url:
                links.append(url)

        return {"documents": documents, "links": links}
