# SPDX-FileCopyrightText: 2026-present ContextFetch
#
# SPDX-License-Identifier: Apache-2.0

from typing import Any

from haystack import Document, component, logging
from haystack.utils import Secret

from contextfetch import ContextFetch

logger = logging.getLogger(__name__)


@component
class ContextFetchFetcher:
    """
    A component that uses ContextFetch to fetch web pages as Markdown and return them as Haystack Documents.

    This component wraps the [ContextFetch Contents API](https://contextfetch.dev/docs/reference). URLs that fail
    to load are skipped with a warning and are not billed.

    Without an API key, requests use the keyless tier, which has a small daily allowance per IP.
    Get a key at [contextfetch.dev/get-started](https://contextfetch.dev/get-started).

    ### Usage example

    ```python
    from haystack_integrations.components.fetchers.contextfetch import ContextFetchFetcher

    fetcher = ContextFetchFetcher()
    result = fetcher.run(urls=["https://docs.python.org/3/library/asyncio-task.html"])
    documents = result["documents"]
    ```
    """

    def __init__(self, api_key: Secret = Secret.from_env_var("CONTEXTFETCH_API_KEY", strict=False)) -> None:
        """
        Initialize the ContextFetchFetcher component.

        :param api_key:
            API key for ContextFetch. Defaults to the `CONTEXTFETCH_API_KEY` environment variable. Resolved
            leniently: when no key resolves, requests use the keyless tier. Pass
            `Secret.from_env_var("CONTEXTFETCH_API_KEY")` to require a key.
        """
        self.api_key = api_key
        self._client: ContextFetch | None = None

    def warm_up(self) -> None:
        """
        Initialize the ContextFetch client.

        Called automatically on first use. Can be called explicitly to avoid cold-start latency.
        """
        if self._client is None:
            self._client = ContextFetch(api_key=self.api_key.resolve_value())

    @component.output_types(documents=list[Document])
    def run(self, urls: list[str]) -> dict[str, Any]:
        """
        Fetch the given URLs as Markdown using ContextFetch.

        :param urls: URLs to fetch. See the API reference for the maximum per request.
        :returns: A dictionary with:
            - `documents`: One Document per page that loaded, with the page as Markdown and `title` and `url` in
              `meta`.
        :raises contextfetch.ContextFetchError: If the ContextFetch API request fails.
        """
        self.warm_up()
        assert self._client is not None  # noqa: S101

        if not urls:
            return {"documents": []}

        response = self._client.contents(urls)
        for status in response.get("statuses", []):
            if status.get("status") == "error":
                logger.warning(
                    "ContextFetch could not fetch {url}: {error}",
                    url=status.get("id"),
                    error=(status.get("error") or {}).get("message"),
                )

        documents = [
            Document(
                content=result.get("text", ""), meta={"title": result.get("title") or "", "url": result.get("url", "")}
            )
            for result in response.get("results", [])
        ]
        return {"documents": documents}
