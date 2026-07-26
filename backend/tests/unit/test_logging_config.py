from pathlib import Path
from types import SimpleNamespace

import app.core.logging_config as logging_config
from app.core.config import config_registry


def test_setup_logging_routes_review_logs_to_dedicated_file(monkeypatch):
    calls: list[dict[str, object]] = []

    def fake_add(*args, **kwargs):
        calls.append({"args": args, "kwargs": kwargs})
        return len(calls)

    monkeypatch.setattr(logging_config.logger, "remove", lambda: None)
    monkeypatch.setattr(logging_config.logger, "add", fake_add)
    monkeypatch.setattr(logging_config.logger, "configure", lambda **kwargs: None)
    monkeypatch.setattr(
        config_registry,
        "get_logging_config",
        lambda: SimpleNamespace(
            level="INFO",
            json=False,
            log_to_file=True,
            diagnose=False,
            file=SimpleNamespace(
                path="logs/synapseflow.log",
                rotation="10 MB",
                retention="7 days",
            ),
        ),
    )

    logging_config.setup_logging()

    assert len(calls) == 5

    normal_sink = calls[0]
    main_file_sink = calls[1]
    review_sink = calls[2]
    document_pipeline_sink = calls[3]
    retrieval_sink = calls[4]

    assert normal_sink["kwargs"]["filter"]({"extra": {}}) is True
    assert normal_sink["kwargs"]["filter"]({"extra": {"kb_review_log": True}}) is False
    assert normal_sink["kwargs"]["filter"]({"extra": {"document_pipeline_log": True}}) is False
    assert normal_sink["kwargs"]["filter"]({"extra": {"kb_retrieval_log": True}}) is False
    assert Path(str(main_file_sink["args"][0])).name == "synapseflow.log"
    assert Path(str(review_sink["args"][0])).name == "kb_chat_review.log"
    assert main_file_sink["kwargs"]["filter"]({"extra": {"document_pipeline_log": True}}) is False
    assert main_file_sink["kwargs"]["filter"]({"extra": {"kb_retrieval_log": True}}) is False
    assert review_sink["kwargs"]["filter"]({"extra": {}}) is False
    assert review_sink["kwargs"]["filter"]({"extra": {"kb_review_log": True}}) is True
    assert Path(str(document_pipeline_sink["args"][0])).name == "document_pipeline.log"
    assert document_pipeline_sink["kwargs"]["filter"]({"extra": {}}) is False
    assert (
        document_pipeline_sink["kwargs"]["filter"]({"extra": {"document_pipeline_log": True}})
        is True
    )
    assert Path(str(retrieval_sink["args"][0])).name == "retrieval.log"
    assert retrieval_sink["kwargs"]["filter"]({"extra": {}}) is False
    assert retrieval_sink["kwargs"]["filter"]({"extra": {"kb_retrieval_log": True}}) is True
