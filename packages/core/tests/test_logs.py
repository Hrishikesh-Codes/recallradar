import json
import logging

from recallradar_core.logs import JsonFormatter


def _record(**extra: object) -> logging.LogRecord:
    record = logging.LogRecord(
        "recallradar.test", logging.INFO, __file__, 1, "hello %s", ("world",), None
    )
    for key, value in extra.items():
        setattr(record, key, value)
    return record


def test_formats_one_json_object_with_the_rendered_message() -> None:
    payload = json.loads(JsonFormatter().format(_record()))
    assert payload["msg"] == "hello world"
    assert payload["level"] == "INFO"
    assert payload["logger"] == "recallradar.test"
    assert payload["ts"].endswith("+00:00")


def test_includes_extra_fields_but_not_logrecord_internals() -> None:
    payload = json.loads(JsonFormatter().format(_record(source="cpsc", inserted=3)))
    assert payload["source"] == "cpsc"
    assert payload["inserted"] == 3
    assert "args" not in payload
    assert "lineno" not in payload
