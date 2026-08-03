"""Predefined command responses for the mock SSH switch."""

from __future__ import annotations

from textwrap import dedent


COMMAND_OUTPUTS: dict[str, str] = {
    "show version": dedent(
        """\
        Cisco IOS XE Software, Version 17.03.04a
        Cisco IOS Software [Amsterdam], Catalyst L3 Switch Software
        TEST-SWITCH uptime is 3 weeks, 2 days, 4 hours, 18 minutes
        System returned to ROM by power-on
        System image file is "flash:packages.conf"

        cisco C9300-24T (X86) processor with 8388608K/3072K bytes of memory.
        Processor board ID FOC1234A1BC
        24 Gigabit Ethernet interfaces
        4 Ten Gigabit Ethernet interfaces

        Configuration register is 0x102
        """
    ),
    "show inventory": dedent(
        """\
        NAME: "1", DESCR: "Cisco Catalyst 9300-24T"
        PID: C9300-24T         , VID: V01  , SN: FOC1234A1BC

        NAME: "Switch 1 - Power Supply A", DESCR: "Switching Power Supply"
        PID: PWR-C1-350WAC     , VID: V01  , SN: DCA12345678

        NAME: "Switch 1 - FRU1", DESCR: "Network Module"
        PID: C9300-NM-4G       , VID: V01  , SN: FOC1234N1M0
        """
    ),
    "show environment": dedent(
        """\
        Number of Critical alarms: 0
        Number of Major alarms:    0
        Number of Minor alarms:    0

        Switch  1: SYSTEM TEMPERATURE is OK
        Switch  1: FAN 1 is OK
        Switch  1: FAN 2 is OK
        Switch  1: FAN 3 is OK
        Switch  1: POWER SUPPLY 1 is OK
        """
    ),
    "show running-config": dedent(
        """\
        Building configuration...

        Current configuration : 2048 bytes
        !
        version 17.3
        service timestamps debug datetime msec
        service timestamps log datetime msec
        hostname TEST-SWITCH
        !
        no ip domain-lookup
        ip domain name example.local
        username admin privilege 15 secret 9 $9$mock$hash
        !
        interface GigabitEthernet1/0/1
         description Uplink-to-Core
         switchport mode trunk
         spanning-tree portfast trunk
        !
        interface GigabitEthernet1/0/2
         description User-Access-Port
         switchport mode access
         switchport access vlan 20
         spanning-tree portfast
        !
        interface Vlan1
         ip address 192.0.2.10 255.255.255.0
        !
        ip default-gateway 192.0.2.1
        line vty 0 4
         login local
         transport input ssh
        end
        """
    ),
    "show ip interface brief": dedent(
        """\
        Interface              IP-Address      OK? Method Status                Protocol
        GigabitEthernet1/0/1   unassigned      YES unset  up                    up
        GigabitEthernet1/0/2   unassigned      YES unset  up                    up
        GigabitEthernet1/0/3   unassigned      YES unset  administratively down down
        Vlan1                  192.0.2.10      YES manual up                    up
        """
    ),
    "show processes cpu": dedent(
        """\
        CPU utilization for five seconds: 4%/0%; one minute: 3%; five minutes: 2%
         PID Runtime(ms)   Invoked      uSecs   5Sec   1Min   5Min TTY Process
           1           0         1          0  0.00%  0.00%  0.00%   0 Load Meter
          98       45231     82431        548  1.12%  0.76%  0.51%   0 IOSD ipc task
        """
    ),
    "show memory statistics": dedent(
        """\
        Head      Total(b)     Used(b)     Free(b)   Lowest(b)  Largest(b)
        Processor  1934210048   812345678  1121864370  1054321987  1048576000
              I/O   268435456    87654321   180781135   175000000   170000000
        """
    ),
}
