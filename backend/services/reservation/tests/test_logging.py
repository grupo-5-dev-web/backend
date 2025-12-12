import json
from uuid import uuid4

from fastapi import status


def _extract_json_logs(caplog):
    entries = []
    for record in caplog.records:
        try:
            entries.append(json.loads(record.message))
        except json.JSONDecodeError:
            continue
    return entries


def test_request_logs_include_context(client, caplog):
    caplog.set_level("INFO")

    tenant_id = str(uuid4())
    headers = {
        "X-Tenant-ID": tenant_id,
        "X-Request-ID": "req-123",
        "X-Trace-ID": "trace-abc",
    }

    response = client.get("/", headers=headers)
    assert response.status_code == status.HTTP_200_OK

    structured_logs = _extract_json_logs(caplog)
    request_logs = [entry for entry in structured_logs if entry.get("event") == "request_completed"]
    assert request_logs, "middleware deve registrar log estruturado da requisição"

    log_entry = request_logs[-1]
    assert log_entry["tenant_id"] == tenant_id
    assert log_entry["request_id"] == "req-123"
    assert log_entry["trace_id"] == "trace-abc"
    assert log_entry["path"] == "/"
    assert log_entry["method"] == "GET"
