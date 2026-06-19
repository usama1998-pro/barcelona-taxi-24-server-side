from __future__ import annotations

import enum


class InvoiceAddressKind(str, enum.Enum):
    LOCATION = "LOCATION"
    AIRPORT = "AIRPORT"
