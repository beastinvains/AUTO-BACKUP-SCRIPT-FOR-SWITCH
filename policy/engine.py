"""
Phase 4 — Deterministic Policy Engine.

Rules are evaluated from structured parameters stored in PolicyRecord.rule_definition.
No LLM, no free-text command generation.  Each rule_type has a well-defined schema
and evaluation function that returns "pass", "fail", or "unknown".

Results MUST be reproducible: identical inputs always produce identical outputs.

Rule types and their rule_definition schemas:

config_pattern:
  {
    "pattern": "<regex or substring>",      # required
    "match_means": "fail" | "pass",         # required — does matching mean FAIL or PASS?
    "case_sensitive": true | false          # optional, default false
  }

telemetry_threshold:
  {
    "metric": "cpu_percent" | "memory_percent" | "temperature_c" | "fan_speed_rpm",
    "operator": "gt" | "lt" | "gte" | "lte",
    "threshold": <number>
  }

service_check:
  {
    "port": <int>,
    "protocol": "tcp" | "udp",
    "expected_state": "absent" | "present"  # "absent" = port must NOT be open
  }

interface_check:
  {
    "check": "no_unused_up",    # all admin-up interfaces must have traffic
    "error_threshold": <int>    # optional: max allowed interface errors
  }
"""
from __future__ import annotations

import logging
import re

log = logging.getLogger(__name__)

# Canonical result values
PASS = "pass"
FAIL = "fail"
UNKNOWN = "unknown"


def evaluate(policy_record, context: dict) -> tuple[str, dict]:
    """
    Evaluate a policy against the provided context.

    context dict keys (all optional — missing keys → UNKNOWN):
        config_text: str                    for config_pattern
        telemetry: dict                     for telemetry_threshold
        services: list[dict]               for service_check
        interfaces: list[dict]             for interface_check

    Returns (result, details) where result ∈ {pass, fail, unknown}.
    details is a human-readable dict explaining the outcome.
    """
    rule_type = policy_record.rule_type
    defn = policy_record.rule_definition or {}

    try:
        if rule_type == "config_pattern":
            return _eval_config_pattern(defn, context)
        if rule_type == "telemetry_threshold":
            return _eval_telemetry_threshold(defn, context)
        if rule_type == "service_check":
            return _eval_service_check(defn, context)
        if rule_type == "interface_check":
            return _eval_interface_check(defn, context)
        return UNKNOWN, {"reason": f"unknown rule_type: {rule_type}"}
    except Exception as exc:
        log.exception("policy evaluation error for policy %s", policy_record.id)
        return UNKNOWN, {"reason": f"evaluation_error: {exc}"}


# ---------------------------------------------------------------------------
# rule_type = config_pattern
# ---------------------------------------------------------------------------

def _eval_config_pattern(defn: dict, context: dict) -> tuple[str, dict]:
    config_text = context.get("config_text")
    if config_text is None:
        return UNKNOWN, {"reason": "no_config_available"}

    pattern = defn.get("pattern", "")
    if not pattern:
        return UNKNOWN, {"reason": "no_pattern_defined"}

    match_means = defn.get("match_means", "fail")
    case_sensitive = defn.get("case_sensitive", False)
    flags = 0 if case_sensitive else re.IGNORECASE

    try:
        matched = bool(re.search(pattern, config_text, flags))
    except re.error as exc:
        return UNKNOWN, {"reason": f"invalid_regex: {exc}"}

    if match_means == "fail":
        result = FAIL if matched else PASS
        details = {
            "pattern": pattern,
            "matched": matched,
            "reason": "pattern found in configuration — policy violation" if matched else "pattern not found — compliant",
        }
    else:  # match_means == "pass"
        result = PASS if matched else FAIL
        details = {
            "pattern": pattern,
            "matched": matched,
            "reason": "required pattern found" if matched else "required pattern missing — policy violation",
        }
    return result, details


# ---------------------------------------------------------------------------
# rule_type = telemetry_threshold
# ---------------------------------------------------------------------------

_OPS = {
    "gt":  lambda v, t: v > t,
    "lt":  lambda v, t: v < t,
    "gte": lambda v, t: v >= t,
    "lte": lambda v, t: v <= t,
}


def _eval_telemetry_threshold(defn: dict, context: dict) -> tuple[str, dict]:
    telemetry = context.get("telemetry")
    if not telemetry:
        return UNKNOWN, {"reason": "no_telemetry_available"}

    metric = defn.get("metric")
    operator = defn.get("operator")
    threshold = defn.get("threshold")

    if not metric or not operator or threshold is None:
        return UNKNOWN, {"reason": "incomplete_rule_definition"}

    op_fn = _OPS.get(operator)
    if op_fn is None:
        return UNKNOWN, {"reason": f"unknown_operator: {operator}"}

    value = telemetry.get(metric)
    if value is None:
        return UNKNOWN, {"reason": f"metric_not_collected: {metric}"}

    violated = op_fn(value, threshold)
    result = FAIL if violated else PASS
    return result, {
        "metric": metric,
        "value": value,
        "operator": operator,
        "threshold": threshold,
        "violated": violated,
        "reason": f"{metric}={value} {operator} {threshold} → {'VIOLATION' if violated else 'OK'}",
    }


# ---------------------------------------------------------------------------
# rule_type = service_check
# ---------------------------------------------------------------------------

def _eval_service_check(defn: dict, context: dict) -> tuple[str, dict]:
    services = context.get("services")
    if services is None:
        return UNKNOWN, {"reason": "no_service_data_available"}

    port = defn.get("port")
    protocol = defn.get("protocol", "tcp")
    expected_state = defn.get("expected_state", "absent")  # "absent" | "present"

    if port is None:
        return UNKNOWN, {"reason": "no_port_defined"}

    found = any(
        s.get("port") == port and s.get("protocol", "tcp") == protocol and s.get("state") == "open"
        for s in services
    )

    if expected_state == "absent":
        result = FAIL if found else PASS
        reason = (
            f"port {port}/{protocol} is open — policy violation"
            if found
            else f"port {port}/{protocol} is not open — compliant"
        )
    else:  # expected_state == "present"
        result = PASS if found else FAIL
        reason = (
            f"port {port}/{protocol} is open — compliant"
            if found
            else f"port {port}/{protocol} is not open — policy violation"
        )

    return result, {"port": port, "protocol": protocol, "found": found, "reason": reason}


# ---------------------------------------------------------------------------
# rule_type = interface_check
# ---------------------------------------------------------------------------

def _eval_interface_check(defn: dict, context: dict) -> tuple[str, dict]:
    interfaces = context.get("interfaces")
    if interfaces is None:
        return UNKNOWN, {"reason": "no_interface_data_available"}

    check = defn.get("check", "no_unused_up")

    if check == "no_unused_up":
        # Flag interfaces that are admin-up but have no addresses and no description
        unused = [
            i.get("name", "unknown")
            for i in interfaces
            if (
                i.get("admin_state", "").lower() == "up"
                and not i.get("addresses")
                and not i.get("description")
            )
        ]
        result = FAIL if unused else PASS
        return result, {
            "check": check,
            "unused_up_interfaces": unused,
            "reason": f"{len(unused)} unused admin-up interface(s)" if unused else "no unused admin-up interfaces",
        }

    return UNKNOWN, {"reason": f"unknown interface check: {check}"}
