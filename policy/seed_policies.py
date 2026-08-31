"""
Phase 4 — Default Starter Policies.

Seeds 7 deterministic security policies on first startup.
Each policy is idempotent: if a policy with the same name already
exists it is left unchanged.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import PolicyRecord

log = logging.getLogger(__name__)

SEED_POLICIES = [
    {
        "name": "Telnet Management Disabled",
        "description": "Telnet transmits credentials in cleartext. It must not be enabled as a management service.",
        "category": "access_control",
        "severity": "critical",
        "rule_type": "config_pattern",
        "rule_definition": {
            "pattern": r"set system services telnet",
            "match_means": "fail",
            "case_sensitive": False,
        },
    },
    {
        "name": "SSH Management Enabled",
        "description": "SSH must be enabled for secure management access.",
        "category": "access_control",
        "severity": "high",
        "rule_type": "config_pattern",
        "rule_definition": {
            "pattern": r"set system services ssh",
            "match_means": "pass",
            "case_sensitive": False,
        },
    },
    {
        "name": "FTP Service Disabled",
        "description": "FTP transmits files and credentials in cleartext. It must not be active.",
        "category": "hardening",
        "severity": "high",
        "rule_type": "service_check",
        "rule_definition": {
            "port": 21,
            "protocol": "tcp",
            "expected_state": "absent",
        },
    },
    {
        "name": "Telnet Port Not Reachable",
        "description": "TCP port 23 (Telnet) must not be listening on any managed device.",
        "category": "hardening",
        "severity": "critical",
        "rule_type": "service_check",
        "rule_definition": {
            "port": 23,
            "protocol": "tcp",
            "expected_state": "absent",
        },
    },
    {
        "name": "CPU Utilization Within Threshold",
        "description": "Sustained CPU utilization above 90 % indicates a resource anomaly or attack indicator.",
        "category": "availability",
        "severity": "medium",
        "rule_type": "telemetry_threshold",
        "rule_definition": {
            "metric": "cpu_percent",
            "operator": "gt",
            "threshold": 90,
        },
    },
    {
        "name": "Memory Utilization Within Threshold",
        "description": "Memory utilization above 95 % indicates potential service instability.",
        "category": "availability",
        "severity": "medium",
        "rule_type": "telemetry_threshold",
        "rule_definition": {
            "metric": "memory_percent",
            "operator": "gt",
            "threshold": 95,
        },
    },
    {
        "name": "No Unused Admin-Up Interfaces",
        "description": "Admin-up interfaces with no addresses and no description increase the attack surface.",
        "category": "hardening",
        "severity": "low",
        "rule_type": "interface_check",
        "rule_definition": {
            "check": "no_unused_up",
        },
    },
]


def seed(session_factory) -> int:
    """Insert default policies that don't already exist.  Returns count inserted."""
    now = datetime.now(timezone.utc)
    inserted = 0
    with session_factory() as session:
        existing_names = set(
            session.scalars(select(PolicyRecord.name))
        )
        for spec in SEED_POLICIES:
            if spec["name"] in existing_names:
                continue
            record = PolicyRecord(
                id=str(uuid4()),
                name=spec["name"],
                description=spec["description"],
                category=spec["category"],
                severity=spec["severity"],
                vendor_scope=[],
                device_type_scope=[],
                rule_type=spec["rule_type"],
                rule_definition=spec["rule_definition"],
                enabled=True,
                created_at=now,
                created_by="system",
            )
            session.add(record)
            inserted += 1
        session.commit()
    if inserted:
        log.info("seeded %d default policies", inserted)
    return inserted
