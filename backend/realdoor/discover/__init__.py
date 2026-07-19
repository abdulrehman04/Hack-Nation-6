"""Stretch phase: transparent property discovery from public HUD LIHTC data.

Read-only browsing of the frozen Boston-metro LIHTC subset. It never ranks,
recommends, predicts acceptance, or claims availability — the dataset carries
no availability or rent data. Filtering is the renter's job and happens in the
UI, so the full published set is always visible.
"""

from .properties import AVAILABILITY_NOTICE, DATA_NOTICE, load_properties

__all__ = ["load_properties", "AVAILABILITY_NOTICE", "DATA_NOTICE"]
