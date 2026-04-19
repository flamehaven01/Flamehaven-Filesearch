import sys
from types import SimpleNamespace

import pytest

import flamehaven_filesearch.metrics as metrics_module
import flamehaven_filesearch._search_cloud as _search_cloud_module
from flamehaven_filesearch import core as core_module
from flamehaven_filesearch.api import main as api_main
from flamehaven_filesearch.metrics import (
    MetricsCollector,
    RequestMetricsContext,
    get_metrics_content_type,
    get_metrics_text,
)


def test_metrics_collector_records_and_exports():
    MetricsCollector.record_request("GET", "/health", 200, 0.01)
    MetricsCollector.record_file_upload("default", 128, 0.02, True)
    MetricsCollector.record_search("default", 0.03, 2, True)
    MetricsCollector.record_cache_hit("search")
    MetricsCollector.record_cache_miss("search")
    MetricsCollector.update_cache_size("search", 1)
    MetricsCollector.record_rate_limit_exceeded("/api/search")
    MetricsCollector.record_error("ValidationError", "/api/search")
    MetricsCollector.update_stores_count(2)

    metrics_blob = get_metrics_text().decode("utf-8")
    assert "http_requests_total" in metrics_blob
    assert get_metrics_content_type().startswith("text/plain")


def test_request_metrics_context_records_success_and_error():
    with RequestMetricsContext("GET", "/health"):
        pass

    class DummyHTTPError(Exception):
        def __init__(self, status_code):
            super().__init__("failure")
            self.status_code = status_code

    with pytest.raises(DummyHTTPError):
        with RequestMetricsContext("POST", "/api/upload"):
            raise DummyHTTPError(429)


def test_update_system_metrics_handles_failures(monkeypatch, caplog):
    def boom(*args, **kwargs):
        raise RuntimeError("psutil missing")

    monkeypatch.setattr(metrics_module.psutil, "cpu_percent", boom)
    monkeypatch.setattr(metrics_module.psutil, "virtual_memory", boom)
    monkeypatch.setattr(metrics_module.psutil, "disk_usage", boom)

    with caplog.at_level("WARNING"):
        MetricsCollector.update_system_metrics()

    assert "Failed to update system metrics" in caplog.text


def test_flamehaven_remote_client_flow(monkeypatch, tmp_path):
    class FakeUploadOperation:
        def __init__(self):
            self.done = True

    class FakeStores:
        def __init__(self):
            self.deleted = []

        def create(self):
            return SimpleNamespace(name="stores/alpha")

        def upload_to_file_search_store(self, file_search_store_name, file):
            self.last_upload = (file_search_store_name, file)
            return FakeUploadOperation()

        def delete(self, name):
            self.deleted.append(name)

    class FakeModels:
        def generate_content(self, model, contents, config):
            chunk = SimpleNamespace(
                retrieved_context=SimpleNamespace(title="Doc One", uri="mem://doc")
            )
            metadata = SimpleNamespace(grounding_chunks=[chunk])
            candidate = SimpleNamespace(grounding_metadata=metadata)
            return SimpleNamespace(text="Remote answer", candidates=[candidate])

    class FakeClient:
        def __init__(self, api_key):
            self.api_key = api_key
            self.file_search_stores = FakeStores()
            self.operations = SimpleNamespace(get=lambda op: op)
            self.models = FakeModels()

    fake_types = SimpleNamespace(
        GenerateContentConfig=lambda *args, **kwargs: SimpleNamespace(),
        Tool=lambda file_search=None: SimpleNamespace(file_search=file_search),
        FileSearch=lambda file_search_store_names=None: SimpleNamespace(
            file_search_store_names=file_search_store_names
        ),
    )

    monkeypatch.setattr(
        core_module, "google_genai", SimpleNamespace(Client=FakeClient), raising=False
    )
    monkeypatch.setattr(core_module, "google_genai_types", fake_types, raising=False)
    monkeypatch.setattr(
        _search_cloud_module, "_google_genai_types", fake_types, raising=False
    )

    searcher = core_module.FlamehavenFileSearch(api_key="remote", allow_offline=False)
    assert searcher._use_native_client is True

    store_id = searcher.create_store("alpha")
    sample_file = tmp_path / "doc.txt"
    sample_file.write_text("important text about systems", encoding="utf-8")
    upload_result = searcher.upload_file(str(sample_file), store_name="alpha")
    assert upload_result["status"] == "success"
    assert store_id == searcher.stores["alpha"]

    search_result = searcher.search("systems", store_name="alpha")
    assert search_result["status"] == "success"
    assert search_result["sources"][0]["title"] == "Doc One"

    delete_result = searcher.delete_store("alpha")
    assert delete_result["status"] == "success"


def test_cli_help_output(monkeypatch, capsys):
    monkeypatch.setenv("GEMINI_API_KEY", "dummy-key")
    monkeypatch.setattr(sys, "argv", ["flamehaven-api", "--help"])
    api_main()
    output = capsys.readouterr().out
    assert "Usage: flamehaven-api" in output


def test_cli_requires_api_key(monkeypatch, capsys):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setattr(sys, "argv", ["flamehaven-api"])
    with pytest.raises(SystemExit) as excinfo:
        api_main()
    assert excinfo.value.code == 1
    output = capsys.readouterr().out
    assert "Error: GEMINI_API_KEY or GOOGLE_API_KEY must be set" in output


def test_cli_invokes_uvicorn(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "dummy-key")
    monkeypatch.setattr(sys, "argv", ["flamehaven-api"])
    called = {}

    def fake_run(app_path, host, port, workers, reload):
        called["app"] = app_path
        called["host"] = host
        called["port"] = port
        called["workers"] = workers
        called["reload"] = reload

    fake_module = SimpleNamespace(run=fake_run)
    monkeypatch.setitem(sys.modules, "uvicorn", fake_module)

    api_main()

    assert called["app"] == "flamehaven_filesearch.api:app"
    assert called["host"] == "0.0.0.0"
    assert called["port"] == 8000
