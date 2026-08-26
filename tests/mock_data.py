"""Predefined command responses for the mock SSH switch.

The project Phase 1 flow is Junos-oriented, so the mock device must answer the
read-only discovery commands used by the Juniper adapter and keep future
extensions easy to add without rewriting the server logic.
"""

from __future__ import annotations

from textwrap import dedent


COMMAND_OUTPUTS: dict[str, str] = {
    "show version": dedent(
        """\
        Hostname: lab-ex4300
        Model: ex4300-48p
        Junos: 21.4R3-S5.4
        System serial number: AB1234
        System uptime: 14 days, 2 hours
        """
    ),
    "show version | no-more": dedent(
        """\
        Hostname: lab-ex4300
        Model: ex4300-48p
        Junos: 21.4R3-S5.4
        System serial number: AB1234
        System uptime: 14 days, 2 hours
        """
    ),
    "show interfaces terse": dedent(
        """\
        Interface               Admin Link Proto    Local                 Remote
        ge-0/0/0                up    up
        ge-0/0/1                up    down
        irb.10                  up    up   inet     10.0.10.2/24
        """
    ),
    "show interfaces terse | no-more": dedent(
        """\
        Interface               Admin Link Proto    Local                 Remote
        ge-0/0/0                up    up
        ge-0/0/1                up    down
        irb.10                  up    up   inet     10.0.10.2/24
        """
    ),
    "show interfaces descriptions": dedent(
        """\
        Interface       Admin Link Description
        ge-0/0/0        up    up   Uplink to core
        ge-0/0/1        up    down User access
        """
    ),
    "show interfaces descriptions | no-more": dedent(
        """\
        Interface       Admin Link Description
        ge-0/0/0        up    up   Uplink to core
        ge-0/0/1        up    down User access
        """
    ),
    "show lldp neighbors": dedent(
        """\
        Local Interface    Parent Interface    Chassis Id          Port info           System Name
        ge-0/0/0          -                   00:11:22:33:44:55  xe-0/0/0           core-sw
        """
    ),
    "show lldp neighbors | no-more": dedent(
        """\
        Local Interface    Parent Interface    Chassis Id          Port info           System Name
        ge-0/0/0          -                   00:11:22:33:44:55  xe-0/0/0           core-sw
        """
    ),
    "show system processes extensive": dedent(
        """\
        CPU utilization: 18
        Memory utilization: 43
        """
    ),
    "show system processes extensive | no-more": dedent(
        """\
        CPU utilization: 18
        Memory utilization: 43
        """
    ),
    # Phase 2 configuration backup fixture. The Juniper adapter collects the
    # canonical snapshot with "show configuration | display set | no-more"; the
    # mock's _normalize_command strips "| no-more" for lookup. Secret-bearing
    # lines (encrypted-password, snmp community) exercise redaction on store.
    "show configuration | display set": dedent(
        """\
        set version 21.4R3-S5.4
        set system host-name lab-ex4300
        set system root-authentication encrypted-password "$6$mR7Hk$3Xa1lLredactedHashValue."
        set system login user backup uid 2001
        set system login user backup class read-only
        set system login user backup authentication encrypted-password "$6$Yb2Qz$anotherRedactedHash."
        set system services ssh root-login deny
        set system services ssh protocol-version v2
        set system ntp server 10.0.0.1
        set chassis aggregated-devices ethernet device-count 4
        set interfaces ge-0/0/0 unit 0 family ethernet-switching interface-mode access
        set interfaces ge-0/0/0 unit 0 family ethernet-switching vlan members HR
        set interfaces ge-0/0/1 unit 0 family ethernet-switching interface-mode access
        set interfaces ge-0/0/1 unit 0 family ethernet-switching vlan members ENG
        set interfaces irb unit 10 family inet address 10.0.10.2/24
        set snmp community public authorization read-only
        set snmp community public clients 10.0.0.0/24
        set vlans ENG vlan-id 30
        set vlans HR vlan-id 40
        set vlans HR l3-interface irb.10
        set protocols lldp interface all
        set protocols rstp interface ge-0/0/0
        """
    ),
    "set cli screen-width 511": "Screen width set to 511\n",
    "set cli complete-on-space off": "Disabling complete-on-space\n",
    "set cli screen-length 0": "Screen length set to 0\n",
    "cli": "Switch#\n",
    "exit": "exit\nSwitch#\n",
}
