# SPDX-FileCopyrightText: 2026-present ContextFetch
#
# SPDX-License-Identifier: Apache-2.0

import os
from unittest.mock import MagicMock, patch

import pytest
from contextfetch import AuthenticationError
from haystack import Document
from haystack.core.serialization import component_from_dict, component_to_dict
from haystack.utils import Secret

from haystack_integrations.components.websearch.contextfetch import ContextFetchWebSearch

CLIENT = "haystack_integrations.components.websearch.contextfetch.contextfetch_websearch.ContextFetch"
TYPE = "haystack_integrations.components.websearch.contextfetch.contextfetch_websearch.ContextFetchWebSearch"


class TestInitializationAndSerialization:
    def test_init_default(self):
        ws = ContextFetchWebSearch()
        assert ws.api_key == Secret.from_env_var("CONTEXTFETCH_API_KEY", strict=False)
        assert ws.top_k == 10
        assert ws.search_params is None
        assert ws._client is None

    def test_to_dict_from_dict_round_trip(self, monkeypatch):
        monkeypatch.setenv("MY_CONTEXTFETCH_KEY", "env-key")
        ws = ContextFetchWebSearch(
            api_key=Secret.from_env_var("MY_CONTEXTFETCH_KEY"),
            top_k=3,
            search_params={"include_domains": ["docs.python.org"], "text": True},
        )
        data = component_to_dict(ws, "websearch")
        assert data == {
            "type": TYPE,
            "init_parameters": {
                "api_key": {"type": "env_var", "env_vars": ["MY_CONTEXTFETCH_KEY"], "strict": True},
                "top_k": 3,
                "search_params": {"include_domains": ["docs.python.org"], "text": True},
            },
        }

        restored = component_from_dict(ContextFetchWebSearch, data, "websearch")
        assert restored.top_k == 3
        assert restored.search_params == {"include_domains": ["docs.python.org"], "text": True}
        assert restored.api_key.resolve_value() == "env-key"


class TestWarmUp:
    def test_warm_up_resolves_key_once(self):
        with patch(CLIENT) as client_cls:
            ws = ContextFetchWebSearch(api_key=Secret.from_token("test-key"))
            ws.warm_up()
            ws.warm_up()
        client_cls.assert_called_once_with(api_key="test-key")

    def test_no_key_uses_keyless_tier(self, monkeypatch):
        monkeypatch.delenv("CONTEXTFETCH_API_KEY", raising=False)
        with patch(CLIENT) as client_cls:
            ContextFetchWebSearch().warm_up()
        client_cls.assert_called_once_with(api_key=None)

    def test_strict_secret_requires_key(self, monkeypatch):
        monkeypatch.delenv("CONTEXTFETCH_API_KEY", raising=False)
        ws = ContextFetchWebSearch(api_key=Secret.from_env_var("CONTEXTFETCH_API_KEY"))
        with pytest.raises(ValueError, match="CONTEXTFETCH_API_KEY"):
            ws.warm_up()


class TestRun:
    @pytest.fixture
    def mock_client(self):
        client = MagicMock()
        client.search.return_value = {
            "results": [
                {
                    "url": "https://docs.python.org/3/library/asyncio-task.html",
                    "title": "Coroutines and Tasks",
                    "score": 0.9,
                    "prunedContext": "## Task Groups",
                },
                {"url": "https://example.com/b", "title": None, "highlights": ["first", "second"]},
            ]
        }
        return client

    def test_run_defaults(self, mock_client):
        ws = ContextFetchWebSearch(api_key=Secret.from_token("test-key"))
        ws._client = mock_client

        result = ws.run(query="task groups")

        mock_client.search.assert_called_once_with("task groups", num_results=10, pruned_context=True)
        assert result["links"] == ["https://docs.python.org/3/library/asyncio-task.html", "https://example.com/b"]
        assert result["documents"] == [
            Document(
                content="## Task Groups",
                meta={"title": "Coroutines and Tasks", "url": "https://docs.python.org/3/library/asyncio-task.html"},
                score=0.9,
            ),
            Document(content="first\n\nsecond", meta={"title": "", "url": "https://example.com/b"}),
        ]

    def test_run_text_takes_precedence(self, mock_client):
        mock_client.search.return_value = {
            "results": [{"url": "https://a.example", "title": "A", "text": "# Whole page", "prunedContext": "part"}]
        }
        ws = ContextFetchWebSearch(api_key=Secret.from_token("test-key"))
        ws._client = mock_client

        assert ws.run(query="q")["documents"][0].content == "# Whole page"

    def test_run_params_override_init_params(self, mock_client):
        ws = ContextFetchWebSearch(
            api_key=Secret.from_token("test-key"), top_k=5, search_params={"exclude_domains": ["example.com"]}
        )
        ws._client = mock_client

        ws.run(query="q", search_params={"num_results": 2, "highlights": True})

        mock_client.search.assert_called_once_with("q", num_results=2, highlights=True)

    def test_run_raises_api_errors(self, mock_client):
        mock_client.search.side_effect = AuthenticationError("HTTP 401", status=401)
        ws = ContextFetchWebSearch(api_key=Secret.from_token("bad-key"))
        ws._client = mock_client

        with pytest.raises(AuthenticationError):
            ws.run(query="q")

    def test_run_empty_results(self, mock_client):
        mock_client.search.return_value = {"results": []}
        ws = ContextFetchWebSearch(api_key=Secret.from_token("test-key"))
        ws._client = mock_client

        assert ws.run(query="q") == {"documents": [], "links": []}


@pytest.mark.skipif(
    not os.environ.get("CONTEXTFETCH_API_KEY"),
    reason="Export CONTEXTFETCH_API_KEY to run integration tests.",
)
@pytest.mark.integration
class TestIntegration:
    def test_run_integration(self):
        ws = ContextFetchWebSearch(api_key=Secret.from_env_var("CONTEXTFETCH_API_KEY"), top_k=2)
        result = ws.run(query="python asyncio task groups")
        assert len(result["documents"]) > 0
        assert len(result["links"]) > 0
        assert isinstance(result["documents"][0], Document)
        assert any(doc.content for doc in result["documents"])
