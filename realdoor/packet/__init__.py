"""Stage 3 — renter-controlled readiness packet (to build).

Compares the confirmed profile and uploaded documents against the gold
checklist, flags missing or expired items, and assembles a packet the renter
can preview, edit, download, and delete. Never auto-sends to any provider.

Planned modules:
    checklist.py  required vs present document types; missing / expired flags
    builder.py    assemble the renter-controlled, downloadable readiness packet
"""
