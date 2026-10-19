# SPDX-FileCopyrightText: 2026-present ContextFetch
#
# SPDX-License-Identifier: Apache-2.0

import logging
import os
from unittest.mock import MagicMock, patch

import pytest
from haystack import Document
from haystack.core.serialization import component_from_dict, component_to_dict
from haystack.utils import Secret

from haystack_integrations.components.fetchers.contextfetch import ContextFetchFetcher

CLIENT = "haystack_integrations.components.fetchers.contextfetch.contextfetch_fetcher.ContextFetch"
URL = "https://docs.python.org/3/library/asyncio-task.html"


def test_to_dict_from_dict_round_trip(monkeypatch):
    monkeypatch.setenv("MY_CONTEXTFETCH_KEY", "env-key")
    fetcher = ContextFetchFetcher(api_key=Secret.from_env_var("MY_CONTEXTFETCH_KEY"))
    data = component_to_dict(fetcher, "fetcher")
    assert data["init_parameters"] == {
        "api_key": {"type": "env_var", "env_vars": ["MY_CONTEXTFETCH_KEY"], "strict": True}
    }
    restored = component_from_dict(ContextFetchFetcher, data, "fetcher")
    assert restored.api_key.resolve_value() == "env-key"


def test_warm_up_resolves_key_once():
    with patch(CLIENT) as client_cls:
        fetcher = ContextFetchFetcher(api_key=Secret.from_token("test-key"))
        fetcher.warm_up()
        fetcher.warm_up()
    client_cls.assert_called_once_with(api_key="test-key")


def test_run_returns_loaded_pages_and_warns_on_failures(caplog):
    client = MagicMock()
    client.contents.return_value = {
        "results": [{"url": URL, "title": "Coroutines and Tasks", "text": "# Coroutines and Tasks"}],
        "statuses": [
            {"id": URL, "status": "success"},
            {"id": "https://broken.example", "status": "error", "error": {"tag": "CRAWL_NOT_FOUND", "message": "404"}},
        ],
    }
    fetcher = ContextFetchFetcher(api_key=Secret.from_token("test-key"))
    fetcher._client = client

    with caplog.at_level(logging.WARNING):
        result = fetcher.run(urls=[URL, "https://broken.example"])

    client.contents.assert_called_once_with([URL, "https://broken.example"])
    assert result["documents"] == [
        Document(content="# Coroutines and Tasks", meta={"title": "Coroutines and Tasks", "url": URL})
    ]
    assert "https://broken.example" in caplog.text


def test_run_with_no_urls_skips_the_request():
    client = MagicMock()
    fetcher = ContextFetchFetcher(api_key=Secret.from_token("test-key"))
    fetcher._client = client

    assert fetcher.run(urls=[]) == {"documents": []}
    client.contents.assert_not_called()


@pytest.mark.skipif(
    not os.environ.get("CONTEXTFETCH_API_KEY"),
    reason="Export CONTEXTFETCH_API_KEY to run integration tests.",
)
@pytest.mark.integration
def test_run_integration():
    fetcher = ContextFetchFetcher(api_key=Secret.from_env_var("CONTEXTFETCH_API_KEY"))
    result = fetcher.run(urls=[URL])
    assert len(result["documents"]) == 1
    assert result["documents"][0].content
