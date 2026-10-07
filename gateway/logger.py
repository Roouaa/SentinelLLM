"""Per-request logging for the gateway.

LiteLLM calls into this after every request. We append one JSON object per line
to logs/requests.jsonl.

Deliberately records metadata only — who, which model, how many tokens, what it
cost — and never the prompt or the reply. A gateway log holding the text of
confidential requests would be a second, unclassified copy of the data the
routing rules exist to protect.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from litellm.integrations.custom_logger import CustomLogger

LOG_PATH = Path(__file__).parent.parent / "logs" / "requests.jsonl"


def _write(record):
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_PATH, "a") as stream:
        stream.write(json.dumps(record) + "\n")


def _record(kwargs, response_obj, start_time, end_time, status):
    """Pull the interesting fields out of whatever LiteLLM hands us.

    Everything is fetched defensively: the shape of these objects changes
    between LiteLLM versions, and a logger that crashes takes the request
    with it.
    """
    std = kwargs.get("standard_logging_object") or {}
    metadata = std.get("metadata") or {}
    usage = getattr(response_obj, "usage", None)

    def usage_field(name):
        if usage is None:
            return std.get(name)
        return getattr(usage, name, None)

    duration_ms = None
    if start_time and end_time:
        duration_ms = round((end_time - start_time).total_seconds() * 1000, 1)

    return {
        "time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": status,
        "call_id": std.get("id") or kwargs.get("litellm_call_id"),
        # Which key was used. The alias or a hash — never the key itself.
        "key": metadata.get("user_api_key_alias") or metadata.get("user_api_key_hash"),
        # The public name the caller asked for, and what it really went to.
        "model_group": std.get("model_group") or metadata.get("model_group"),
        "model": std.get("model") or kwargs.get("model"),
        "tokens_in": usage_field("prompt_tokens"),
        "tokens_out": usage_field("completion_tokens"),
        "cost": std.get("response_cost", kwargs.get("response_cost")),
        "duration_ms": duration_ms,
        "error": std.get("error_str") if status == "error" else None,
    }


class RequestLogger(CustomLogger):
    async def async_log_success_event(self, kwargs, response_obj, start_time, end_time):
        try:
            _write(_record(kwargs, response_obj, start_time, end_time, "ok"))
        except Exception as exc:  # never let logging break a request
            print(f"[logger] could not write success record: {exc}")

    async def async_log_failure_event(self, kwargs, response_obj, start_time, end_time):
        try:
            _write(_record(kwargs, response_obj, start_time, end_time, "error"))
        except Exception as exc:
            print(f"[logger] could not write failure record: {exc}")


proxy_handler_instance = RequestLogger()
