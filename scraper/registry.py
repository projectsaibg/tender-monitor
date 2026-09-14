"""Adapter registry and selection.

Maps an adapter name to its class and auto-selects an adapter for a portal.
New portal-specific adapters can be registered here without changing any other
subsystem. The generic adapter is the default; NIC eProcurement portals are
auto-detected from their URL.
"""
from __future__ import annotations

from scraper.generic import GenericPortalAdapter
from scraper.nic_adapter import NicEprocurementAdapter, is_nic_portal

ADAPTERS = {
    "generic": GenericPortalAdapter,
    "nic": NicEprocurementAdapter,
}


def get_adapter_class(name):
    return ADAPTERS.get((name or "generic").lower(), GenericPortalAdapter)


def register_adapter(name, cls):
    ADAPTERS[name.lower()] = cls


def select_adapter(portal):
    """Choose the adapter class for a portal.

    An explicit non-generic ``adapter`` set on the portal wins. Otherwise NIC
    eProcurement portals are auto-detected from their URL and everything else
    uses the generic adapter.
    """
    name = (portal.get("adapter") or "generic").lower()
    if name not in ("generic", "auto", ""):
        return ADAPTERS.get(name, GenericPortalAdapter)
    if is_nic_portal(portal.get("url", "")):
        return NicEprocurementAdapter
    return GenericPortalAdapter
