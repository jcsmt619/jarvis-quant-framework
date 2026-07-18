"""UI-01 local read-only service package.

This package is intentionally optional. Importing it must not initialize
providers, brokers, credential stores, order routing, or execution modules.
"""

from ui_service.service import LocalReadOnlyService, ServiceConfig

__all__ = ["LocalReadOnlyService", "ServiceConfig"]
