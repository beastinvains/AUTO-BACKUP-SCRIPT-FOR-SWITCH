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
}
