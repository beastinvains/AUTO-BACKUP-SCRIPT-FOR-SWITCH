"""Fixture estate for the multi-device mock lab.

``tests/mock_data.py`` describes one device, which is all the Phase 1/Phase 2 tests need.
Topology needs several devices that *talk about each other*, so this module describes a
small estate whose LLDP tables cross-reference by hostname the way real ones do.

The evidence is deliberately uneven, because that is what the topology rules are for.  Read
together, the six personas below produce every outcome ``topology/graph.py`` can reach:

* **corroborated (0.95)** — core-rtr01 ↔ dist-sw01.dc-a.lab and dist-sw01.dc-a.lab ↔
  access-sw01 each report one another, with both interface names;
* **single-sided (0.7)** — core-rtr01 reports edge-fw01 and dist-sw01.dc-b.lab reports
  core-rtr01, but the far end does not report back (LLDP is not enabled on those ports);
* **unresolved / external (0.4)** — ``isp-edge-rtr`` and ``ap-lobby-01`` are real neighbours
  that inventory does not contain, so they become explicit unmanaged nodes;
* **partial interface evidence** — access-sw01 sees access-sw02 on a neighbour that
  advertises no port id, so the link is drawn without a far-end interface name;
* **ambiguous identity, refused** — both sites run a ``dist-sw01``, and access-sw02 reports
  its uplink by the short name only.  Two devices answer to ``dist-sw01``, so the platform
  refuses to pick one and shows an unmanaged node plus a warning instead of guessing.

``insufficient_evidence`` stays at 0 here on purpose: every LLDP row carries at least a
chassis id, so there is no honest way to produce an identity-less observation from device
output.  That counter guards neighbour rows recorded without an identity and is covered by
``tests/test_phase3_topology.py`` instead of being faked here.

Serial numbers are serial numbers, not chassis MACs — so a managed device is correlated by
the hostname it advertises, never by the MAC in the Chassis Id column.  That is the same
situation as a real estate.

Nothing here is a credential: the mock accepts one well-known development login
(``admin``/``admin``) that exists only inside this lab.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from textwrap import dedent

#: Credential profile the platform side should use, resolved by :mod:`credentials` from
#: ``MOCK_LAB_USERNAME`` / ``MOCK_LAB_PASSWORD``.
CREDENTIALS_PROFILE = "mock_lab"
USERNAME = "admin"
PASSWORD = "admin"

#: First TCP port of the estate; each persona takes ``BASE_PORT + port_offset``.
BASE_PORT = 2201

#: Answers netmiko's session setup needs from any Junos device.
BASE_CLI_RESPONSES: dict[str, str] = {
    "set cli screen-width 511": "Screen width set to 511\n",
    "set cli complete-on-space off": "Disabling complete-on-space\n",
    "set cli screen-length 0": "Screen length set to 0\n",
    "cli": "",
    "exit": "",
}

CONFIGURATION_COMMAND = "show configuration | display set"


@dataclass(frozen=True)
class ConfigChange:
    """One configuration edit the lab console can apply, so a diff has something to show."""

    summary: str
    replace: tuple[str, str] | None = None
    add: str | None = None


@dataclass
class LabPersona:
    """One mock device: what it answers, and how its configuration can be changed."""

    hostname: str
    device_type: str
    model: str
    os_version: str
    serial_number: str
    site: str
    chassis_id: str
    port_offset: int
    uptime: str
    cpu_percent: int
    memory_percent: int
    interfaces_terse: str
    interface_descriptions: str
    lldp_neighbors: str
    config_lines: list[str]
    drift_steps: list[ConfigChange] = field(default_factory=list)
    drift_applied: int = 0
    responses: dict[str, str] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        self.responses.update(BASE_CLI_RESPONSES)
        self.responses.update({
            "show version": dedent(f"""\
                Hostname: {self.hostname}
                Model: {self.model}
                Junos: {self.os_version}
                System serial number: {self.serial_number}
                System uptime: {self.uptime}
                """),
            "show interfaces terse": self.interfaces_terse,
            "show interfaces descriptions": self.interface_descriptions,
            "show lldp neighbors": self.lldp_neighbors,
            "show system processes extensive": dedent(f"""\
                CPU utilization: {self.cpu_percent}
                Memory utilization: {self.memory_percent}
                """),
        })
        self._publish_configuration()

    @property
    def short_name(self) -> str:
        """Leftmost DNS label — what a Junos prompt and a short LLDP report would use."""
        return self.hostname.split(".", 1)[0]

    @property
    def prompt(self) -> str:
        return f"admin@{self.short_name}>"

    def port(self, base_port: int = BASE_PORT) -> int:
        return base_port + self.port_offset

    def _publish_configuration(self) -> None:
        self.responses[CONFIGURATION_COMMAND] = "\n".join(self.config_lines) + "\n"

    def apply_drift(self) -> str:
        """Change the running configuration the way an operator would, and report what changed.

        The next backup therefore stores a genuinely new version with a real diff, instead of
        the platform being told a change happened.
        """
        if self.drift_applied < len(self.drift_steps):
            change = self.drift_steps[self.drift_applied]
        else:  # every scripted edit used; keep going with something harmless but real
            revision = self.drift_applied - len(self.drift_steps) + 1
            change = ConfigChange(summary=f"snmp location set to lab rack A{revision}",
                                  add=f'set snmp location "lab rack A{revision}"')
        self.drift_applied += 1
        if change.replace:
            old, new = change.replace
            self.config_lines = [new if line == old else line for line in self.config_lines]
        if change.add:
            self._insert_in_hierarchy(change.add)
        self._publish_configuration()
        return change.summary

    def _insert_in_hierarchy(self, line: str) -> None:
        """Place a new ``set`` line next to its siblings, as ``display set`` would order it."""
        prefix = " ".join(line.split()[:3])
        matches = [index for index, existing in enumerate(self.config_lines) if existing.startswith(prefix)]
        if not matches:
            prefix = " ".join(line.split()[:2])
            matches = [index for index, existing in enumerate(self.config_lines) if existing.startswith(prefix)]
        if matches:
            self.config_lines.insert(matches[-1] + 1, line)
        else:
            self.config_lines.append(line)


def _config(text: str) -> list[str]:
    return [line for line in dedent(text).strip().splitlines() if line.strip()]


def build_estate() -> list[LabPersona]:
    """A fresh estate. Callers mutate personas (drift), so this always returns new objects."""
    return [
        LabPersona(
            hostname="core-rtr01",
            device_type="router",
            model="mx204",
            os_version="21.4R3-S5.4",
            serial_number="JN11CORE0001",
            site="dc-a",
            chassis_id="2c:6b:f5:11:00:01",
            port_offset=0,
            uptime="112 days, 4 hours, 39 minutes",
            cpu_percent=12,
            memory_percent=38,
            interfaces_terse=dedent("""\
                Interface               Admin Link Proto    Local                 Remote
                ge-0/0/0                up    up
                ge-0/0/0.0              up    up   inet     10.10.0.1/30
                ge-0/0/1                up    up
                ge-0/0/1.0              up    up   inet     203.0.113.2/30
                ge-0/0/2                up    up
                ge-0/0/2.0              up    up   inet     10.10.0.5/30
                ge-0/0/3                up    up
                ge-0/0/3.0              up    up   inet     10.10.0.9/30
                ge-0/0/4                up    down
                """),
            interface_descriptions=dedent("""\
                Interface       Admin Link Description
                ge-0/0/0        up    up   Transit to dist-sw01.dc-a
                ge-0/0/1        up    up   ISP handoff - change control required
                ge-0/0/2        up    up   Transit to edge-fw01
                ge-0/0/3        up    up   Transit to dc-b
                ge-0/0/4        up    down Spare
                """),
            # ge-0/0/0 is reported by the far end too (corroborated); ge-0/0/1 points at a
            # neighbour inventory does not contain; ge-0/0/2 is never reported back.
            lldp_neighbors=dedent("""\
                Local Interface    Parent Interface    Chassis Id          Port info          System Name
                ge-0/0/0           -                   2c:6b:f5:22:00:01   xe-0/0/48          dist-sw01.dc-a.lab
                ge-0/0/1           -                   00:1a:2b:3c:4d:5e   Gi0/0/1            isp-edge-rtr
                ge-0/0/2           -                   2c:6b:f5:44:00:01   ge-0/0/0           edge-fw01
                """),
            config_lines=_config("""
                set version 21.4R3-S5.4
                set system host-name core-rtr01
                set system domain-name dc-a.lab
                set system root-authentication encrypted-password "$6$Kd8Lq$coreRedactedRootHashValue."
                set system login user netops uid 2001
                set system login user netops class super-user
                set system login user netops authentication encrypted-password "$6$Rt4Vb$coreRedactedUserHash."
                set system services ssh root-login deny
                set system services ssh protocol-version v2
                set system ntp server 10.0.0.1
                set system ntp server 10.0.0.2
                set interfaces ge-0/0/0 description "Transit to dist-sw01.dc-a"
                set interfaces ge-0/0/0 unit 0 family inet address 10.10.0.1/30
                set interfaces ge-0/0/1 description "ISP handoff - change control required"
                set interfaces ge-0/0/1 unit 0 family inet address 203.0.113.2/30
                set interfaces ge-0/0/2 description "Transit to edge-fw01"
                set interfaces ge-0/0/2 unit 0 family inet address 10.10.0.5/30
                set interfaces ge-0/0/3 description "Transit to dc-b"
                set interfaces ge-0/0/3 unit 0 family inet address 10.10.0.9/30
                set snmp community lab-readonly authorization read-only
                set snmp community lab-readonly clients 10.0.0.0/24
                set routing-options static route 0.0.0.0/0 next-hop 203.0.113.1
                set protocols ospf area 0.0.0.0 interface ge-0/0/0.0
                set protocols ospf area 0.0.0.0 interface ge-0/0/2.0
                set protocols lldp interface all
            """),
            drift_steps=[
                ConfigChange(summary="OSPF enabled on the dc-b transit link",
                             add="set protocols ospf area 0.0.0.0 interface ge-0/0/3.0"),
                ConfigChange(summary="ISP handoff description updated",
                             replace=('set interfaces ge-0/0/1 description "ISP handoff - change control required"',
                                      'set interfaces ge-0/0/1 description "ISP handoff - circuit ID 88213"')),
                ConfigChange(summary="second static route added",
                             add="set routing-options static route 10.30.0.0/16 next-hop 10.10.0.10"),
            ],
        ),
        LabPersona(
            hostname="dist-sw01.dc-a.lab",
            device_type="switch",
            model="ex4650-48y",
            os_version="21.4R3-S4.9",
            serial_number="JN22DISTA001",
            site="dc-a",
            chassis_id="2c:6b:f5:22:00:01",
            port_offset=1,
            uptime="87 days, 19 hours, 2 minutes",
            cpu_percent=22,
            memory_percent=51,
            interfaces_terse=dedent("""\
                Interface               Admin Link Proto    Local                 Remote
                xe-0/0/48               up    up
                ge-0/0/1                up    up
                ge-0/0/2                up    up
                ge-0/0/3                up    down
                irb.10                  up    up   inet     10.20.10.2/24
                irb.20                  up    up   inet     10.20.20.2/24
                """),
            interface_descriptions=dedent("""\
                Interface       Admin Link Description
                xe-0/0/48       up    up   Uplink to core-rtr01
                ge-0/0/1        up    up   Downlink to access-sw01
                ge-0/0/2        up    up   Downlink to access-sw02
                ge-0/0/3        up    down Spare
                """),
            lldp_neighbors=dedent("""\
                Local Interface    Parent Interface    Chassis Id          Port info          System Name
                xe-0/0/48          -                   2c:6b:f5:11:00:01   ge-0/0/0           core-rtr01
                ge-0/0/1           -                   2c:6b:f5:33:00:01   ge-0/0/47          access-sw01
                """),
            config_lines=_config("""
                set version 21.4R3-S4.9
                set system host-name dist-sw01.dc-a.lab
                set system root-authentication encrypted-password "$6$Wp3Nc$distARedactedRootHash."
                set system login user netops uid 2001
                set system login user netops class super-user
                set system login user netops authentication encrypted-password "$6$Zx9Mn$distARedactedUserHash."
                set system services ssh root-login deny
                set system ntp server 10.0.0.1
                set chassis aggregated-devices ethernet device-count 4
                set interfaces xe-0/0/48 description "Uplink to core-rtr01"
                set interfaces xe-0/0/48 unit 0 family inet address 10.10.0.2/30
                set interfaces ge-0/0/1 description "Downlink to access-sw01"
                set interfaces ge-0/0/1 unit 0 family ethernet-switching interface-mode trunk
                set interfaces ge-0/0/1 unit 0 family ethernet-switching vlan members [ USERS VOICE ]
                set interfaces ge-0/0/2 description "Downlink to access-sw02"
                set interfaces ge-0/0/2 unit 0 family ethernet-switching interface-mode trunk
                set interfaces ge-0/0/2 unit 0 family ethernet-switching vlan members [ USERS VOICE ]
                set interfaces irb unit 10 family inet address 10.20.10.2/24
                set interfaces irb unit 20 family inet address 10.20.20.2/24
                set snmp community lab-readonly authorization read-only
                set vlans USERS vlan-id 10
                set vlans USERS l3-interface irb.10
                set vlans VOICE vlan-id 20
                set vlans VOICE l3-interface irb.20
                set protocols lldp interface all
                set protocols rstp interface ge-0/0/1
                set protocols rstp interface ge-0/0/2
            """),
            drift_steps=[
                ConfigChange(summary="GUEST VLAN 30 created",
                             add="set vlans GUEST vlan-id 30"),
                ConfigChange(summary="VOICE VLAN renumbered from 20 to 120",
                             replace=("set vlans VOICE vlan-id 20", "set vlans VOICE vlan-id 120")),
                ConfigChange(summary="spare port ge-0/0/3 described",
                             add='set interfaces ge-0/0/3 description "Reserved for access-sw03"'),
            ],
        ),
        LabPersona(
            hostname="access-sw01",
            device_type="switch",
            model="ex4300-48p",
            os_version="20.4R3-S9.2",
            serial_number="JN33ACC01001",
            site="dc-a",
            chassis_id="2c:6b:f5:33:00:01",
            port_offset=2,
            uptime="61 days, 7 hours, 55 minutes",
            cpu_percent=9,
            memory_percent=34,
            interfaces_terse=dedent("""\
                Interface               Admin Link Proto    Local                 Remote
                ge-0/0/0                up    up
                ge-0/0/1                up    up
                ge-0/0/2                up    down
                ge-0/0/47               up    up
                irb.10                  up    up   inet     10.20.10.11/24
                """),
            interface_descriptions=dedent("""\
                Interface       Admin Link Description
                ge-0/0/0        up    up   Desk 1A
                ge-0/0/1        up    up   Cross-link to access-sw02
                ge-0/0/2        up    down Desk 1C
                ge-0/0/47       up    up   Uplink to dist-sw01.dc-a
                """),
            # The ge-0/0/1 row is the parser's short form: this neighbour advertises no port
            # id, so the platform records the link with only the near-end interface known.
            lldp_neighbors=dedent("""\
                Local Interface    Parent Interface    Chassis Id          Port info          System Name
                ge-0/0/47          -                   2c:6b:f5:22:00:01   ge-0/0/1           dist-sw01.dc-a.lab
                ge-0/0/1           2c:6b:f5:33:00:02   access-sw02
                """),
            config_lines=_config("""
                set version 20.4R3-S9.2
                set system host-name access-sw01
                set system root-authentication encrypted-password "$6$Bg5Tq$acc01RedactedRootHash."
                set system login user netops uid 2001
                set system login user netops class super-user
                set system login user netops authentication encrypted-password "$6$Hj2Ws$acc01RedactedUserHash."
                set system services ssh root-login deny
                set system ntp server 10.0.0.1
                set interfaces ge-0/0/0 description "Desk 1A"
                set interfaces ge-0/0/0 unit 0 family ethernet-switching interface-mode access
                set interfaces ge-0/0/0 unit 0 family ethernet-switching vlan members USERS
                set interfaces ge-0/0/1 description "Cross-link to access-sw02"
                set interfaces ge-0/0/1 unit 0 family ethernet-switching interface-mode trunk
                set interfaces ge-0/0/2 description "Desk 1C"
                set interfaces ge-0/0/2 unit 0 family ethernet-switching interface-mode access
                set interfaces ge-0/0/2 unit 0 family ethernet-switching vlan members USERS
                set interfaces ge-0/0/47 description "Uplink to dist-sw01.dc-a"
                set interfaces ge-0/0/47 unit 0 family ethernet-switching interface-mode trunk
                set interfaces irb unit 10 family inet address 10.20.10.11/24
                set snmp community lab-readonly authorization read-only
                set vlans USERS vlan-id 10
                set vlans VOICE vlan-id 20
                set protocols lldp interface all
                set protocols rstp interface ge-0/0/47
            """),
            drift_steps=[
                ConfigChange(summary="desk 1C moved to the VOICE VLAN",
                             replace=("set interfaces ge-0/0/2 unit 0 family ethernet-switching vlan members USERS",
                                      "set interfaces ge-0/0/2 unit 0 family ethernet-switching vlan members VOICE")),
                ConfigChange(summary="storm control added to the uplink",
                             add="set interfaces ge-0/0/47 unit 0 family ethernet-switching storm-control default"),
            ],
        ),
        LabPersona(
            hostname="access-sw02",
            device_type="switch",
            model="ex2300-48p",
            os_version="20.4R3-S9.2",
            serial_number="JN33ACC02001",
            site="dc-a",
            chassis_id="2c:6b:f5:33:00:02",
            port_offset=3,
            uptime="61 days, 6 hours, 12 minutes",
            cpu_percent=15,
            memory_percent=44,
            interfaces_terse=dedent("""\
                Interface               Admin Link Proto    Local                 Remote
                ge-0/0/0                up    up
                ge-0/0/1                up    up
                ge-0/0/47               up    up
                irb.10                  up    up   inet     10.20.10.12/24
                """),
            interface_descriptions=dedent("""\
                Interface       Admin Link Description
                ge-0/0/0        up    up   Desk 2A
                ge-0/0/1        up    up   Lobby access point
                ge-0/0/47       up    up   Uplink to distribution
                """),
            # The uplink is reported by short name only. Both sites run a "dist-sw01", so the
            # platform cannot tell which one this is and must refuse to draw that link.
            lldp_neighbors=dedent("""\
                Local Interface    Parent Interface    Chassis Id          Port info          System Name
                ge-0/0/47          -                   2c:6b:f5:22:00:01   ge-0/0/2           dist-sw01
                ge-0/0/1           -                   2c:6b:f5:55:00:07   eth0               ap-lobby-01
                """),
            config_lines=_config("""
                set version 20.4R3-S9.2
                set system host-name access-sw02
                set system root-authentication encrypted-password "$6$Nv7Rd$acc02RedactedRootHash."
                set system login user netops uid 2001
                set system login user netops class super-user
                set system login user netops authentication encrypted-password "$6$Qc8Pl$acc02RedactedUserHash."
                set system services ssh root-login deny
                set system ntp server 10.0.0.1
                set interfaces ge-0/0/0 description "Desk 2A"
                set interfaces ge-0/0/0 unit 0 family ethernet-switching interface-mode access
                set interfaces ge-0/0/0 unit 0 family ethernet-switching vlan members USERS
                set interfaces ge-0/0/1 description "Lobby access point"
                set interfaces ge-0/0/1 unit 0 family ethernet-switching interface-mode trunk
                set interfaces ge-0/0/47 description "Uplink to distribution"
                set interfaces ge-0/0/47 unit 0 family ethernet-switching interface-mode trunk
                set interfaces irb unit 10 family inet address 10.20.10.12/24
                set snmp community lab-readonly authorization read-only
                set vlans USERS vlan-id 10
                set vlans VOICE vlan-id 20
                set protocols lldp interface all
            """),
            drift_steps=[
                ConfigChange(summary="PoE limited on the lobby access point port",
                             add="set poe interface ge-0/0/1 maximum-power 15.4"),
                ConfigChange(summary="desk 2A description corrected",
                             replace=('set interfaces ge-0/0/0 description "Desk 2A"',
                                      'set interfaces ge-0/0/0 description "Desk 2A - reception"')),
            ],
        ),
        LabPersona(
            hostname="edge-fw01",
            device_type="firewall",
            model="srx345",
            os_version="21.4R3-S5.4",
            serial_number="JN44EDGEFW01",
            site="dc-a",
            chassis_id="2c:6b:f5:44:00:01",
            port_offset=4,
            uptime="203 days, 11 hours, 8 minutes",
            cpu_percent=31,
            memory_percent=72,
            interfaces_terse=dedent("""\
                Interface               Admin Link Proto    Local                 Remote
                ge-0/0/0                up    up
                ge-0/0/0.0              up    up   inet     10.10.0.6/30
                ge-0/0/1                up    up
                ge-0/0/1.0              up    up   inet     10.40.0.1/24
                ge-0/0/2                up    down
                """),
            interface_descriptions=dedent("""\
                Interface       Admin Link Description
                ge-0/0/0        up    up   Transit to core-rtr01
                ge-0/0/1        up    up   DMZ
                ge-0/0/2        up    down Spare
                """),
            # LLDP is not enabled on this device, so the core's report of it stays one-sided.
            lldp_neighbors=dedent("""\
                LLDP is not enabled
                """),
            config_lines=_config("""
                set version 21.4R3-S5.4
                set system host-name edge-fw01
                set system root-authentication encrypted-password "$6$Ty6Xf$fw01RedactedRootHash."
                set system login user netops uid 2001
                set system login user netops class super-user
                set system login user netops authentication encrypted-password "$6$Ui3Ke$fw01RedactedUserHash."
                set system services ssh root-login deny
                set system ntp server 10.0.0.1
                set interfaces ge-0/0/0 description "Transit to core-rtr01"
                set interfaces ge-0/0/0 unit 0 family inet address 10.10.0.6/30
                set interfaces ge-0/0/1 description "DMZ"
                set interfaces ge-0/0/1 unit 0 family inet address 10.40.0.1/24
                set snmp community lab-readonly authorization read-only
                set security zones security-zone trust interfaces ge-0/0/0.0
                set security zones security-zone dmz interfaces ge-0/0/1.0
                set security policies from-zone trust to-zone dmz policy allow-web match source-address any
                set security policies from-zone trust to-zone dmz policy allow-web match destination-address any
                set security policies from-zone trust to-zone dmz policy allow-web match application junos-https
                set security policies from-zone trust to-zone dmz policy allow-web then permit
                set security nat source rule-set trust-to-dmz from zone trust
                set security nat source rule-set trust-to-dmz to zone dmz
            """),
            drift_steps=[
                ConfigChange(summary="DNS allowed from trust to dmz",
                             add="set security policies from-zone trust to-zone dmz policy allow-dns then permit"),
                ConfigChange(summary="DMZ interface description updated",
                             replace=('set interfaces ge-0/0/1 description "DMZ"',
                                      'set interfaces ge-0/0/1 description "DMZ - web tier"')),
            ],
        ),
        LabPersona(
            hostname="dist-sw01.dc-b.lab",
            device_type="switch",
            model="ex4650-48y",
            os_version="21.4R3-S4.9",
            serial_number="JN22DISTB001",
            site="dc-b",
            chassis_id="2c:6b:f5:22:00:02",
            port_offset=5,
            uptime="45 days, 22 hours, 41 minutes",
            cpu_percent=19,
            memory_percent=47,
            interfaces_terse=dedent("""\
                Interface               Admin Link Proto    Local                 Remote
                xe-0/0/48               up    up
                ge-0/0/1                up    down
                irb.10                  up    up   inet     10.30.10.2/24
                """),
            interface_descriptions=dedent("""\
                Interface       Admin Link Description
                xe-0/0/48       up    up   Transit to core-rtr01
                ge-0/0/1        up    down Reserved
                """),
            # core-rtr01 does not report this link back, so it stays single-sided.
            lldp_neighbors=dedent("""\
                Local Interface    Parent Interface    Chassis Id          Port info          System Name
                xe-0/0/48          -                   2c:6b:f5:11:00:01   ge-0/0/3           core-rtr01
                """),
            config_lines=_config("""
                set version 21.4R3-S4.9
                set system host-name dist-sw01.dc-b.lab
                set system root-authentication encrypted-password "$6$Ml4Qs$distBRedactedRootHash."
                set system login user netops uid 2001
                set system login user netops class super-user
                set system login user netops authentication encrypted-password "$6$Vn7Jd$distBRedactedUserHash."
                set system services ssh root-login deny
                set system ntp server 10.0.0.1
                set interfaces xe-0/0/48 description "Transit to core-rtr01"
                set interfaces xe-0/0/48 unit 0 family inet address 10.10.0.10/30
                set interfaces irb unit 10 family inet address 10.30.10.2/24
                set snmp community lab-readonly authorization read-only
                set vlans USERS vlan-id 10
                set vlans USERS l3-interface irb.10
                set protocols lldp interface all
            """),
            drift_steps=[
                ConfigChange(summary="VOICE VLAN 20 created at dc-b",
                             add="set vlans VOICE vlan-id 20"),
            ],
        ),
    ]


#: A device the lab deliberately does not serve, so the platform's failure paths are visible.
UNREACHABLE_DEVICE = {
    "hostname": "spare-sw09",
    "device_type": "switch",
    "site": "dc-a",
    "port_offset": 90,
}
