# contextfetch-haystack

[![PyPI - Version](https://img.shields.io/pypi/v/contextfetch-haystack.svg)](https://pypi.org/project/contextfetch-haystack)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/contextfetch-haystack.svg)](https://pypi.org/project/contextfetch-haystack)

[Haystack](https://haystack.deepset.ai/) components for the [ContextFetch API](https://contextfetch.dev/docs/reference):

- `ContextFetchWebSearch`: searches the web and returns the results as Documents, with page content as Markdown.
- `ContextFetchFetcher`: fetches URLs and returns each page as a Markdown Document.

## Installation

```bash
pip install contextfetch-haystack
```

## Usage

```python
from haystack_integrations.components.fetchers.contextfetch import ContextFetchFetcher
from haystack_integrations.components.websearch.contextfetch import ContextFetchWebSearch

websearch = ContextFetchWebSearch(top_k=3)
result = websearch.run(query="What are asyncio task groups?")
for doc in result["documents"]:
    print(doc.meta["title"], doc.meta["url"])

fetcher = ContextFetchFetcher()
pages = fetcher.run(urls=["https://docs.python.org/3/library/asyncio-task.html"])
print(pages["documents"][0].content[:500])
```

Both components read the API key from the `CONTEXTFETCH_API_KEY` environment variable. Without a key, requests use
the keyless tier, which has a small daily allowance per IP. Get a key at
[contextfetch.dev/get-started](https://contextfetch.dev/get-started).

`ContextFetchWebSearch` sends `pruned_context=True` by default, so each Document holds the page pruned to the parts
relevant to the query. Pass `search_params={"text": True}` for whole pages, or `{"highlights": True}` for the
most relevant chunks. Other keys: `include_domains`, `exclude_domains`, `start_published_date`.

## Development

```bash
hatch run test:unit         # unit tests, no network
hatch run test:integration  # live API tests; they run only when CONTEXTFETCH_API_KEY is set
hatch run test:types
hatch run fmt-check
```

## License

`contextfetch-haystack` is distributed under the terms of the [Apache-2.0](https://spdx.org/licenses/Apache-2.0.html)
license.
