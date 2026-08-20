SHOW_VERSION = """Hostname: lab-ex4300
Model: ex4300-48p
Junos: 21.4R3-S5.4
System serial number: AB1234
System uptime: 14 days, 2 hours
"""
SHOW_INTERFACES = """Interface               Admin Link Proto    Local                 Remote
ge-0/0/0                up    up
ge-0/0/1                up    down
irb.10                  up    up   inet     10.0.10.2/24
"""
SHOW_DESCRIPTIONS = """Interface       Admin Link Description
ge-0/0/0        up    up   Uplink to core
ge-0/0/1        up    down User access
"""
SHOW_LLDP = """Local Interface    Parent Interface    Chassis Id          Port info           System Name
ge-0/0/0          -                   00:11:22:33:44:55  xe-0/0/0           core-sw
"""
SHOW_HEALTH = """CPU utilization: 18
Memory utilization: 43
"""

