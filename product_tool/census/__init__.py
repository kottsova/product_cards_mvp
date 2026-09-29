"""All-brand source census and coverage infrastructure."""

from .catalog import CatalogCensus, CatalogCoverage, load_catalog_coverage
from .fingerprint import PlatformFingerprint, fingerprint_platform
from .models import AccessStatus, LifecycleStatus, SourceRecord
from .probe import AccessProbe, ProbePolicy, ProbeResult
from .registry import SourceCatalog, load_source_catalog

__all__ = [
    "AccessProbe", "AccessStatus", "CatalogCensus", "CatalogCoverage",
    "LifecycleStatus", "PlatformFingerprint", "ProbePolicy", "ProbeResult",
    "SourceCatalog", "SourceRecord", "fingerprint_platform",
    "load_catalog_coverage", "load_source_catalog",
]
