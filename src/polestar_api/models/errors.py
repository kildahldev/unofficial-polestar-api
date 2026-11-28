"""Last command error models (chronos ErrorService/GetErrors).

UNVERIFIED: the stream was opened live but no error was ever received, so
the layout below comes from the app's schema, not from observed messages.
Error enum values are unknown; they are kept as raw ints.
"""

from __future__ import annotations

from dataclasses import dataclass

from .common import Timestamp


@dataclass(frozen=True)
class CommandError:
    """A command error reported by the car for one chronos command category."""

    category: str = ""
    error_code: int = 0
    action_code: int | None = None
    error_id: str = ""
    error_time: Timestamp | None = None

    @property
    def error_name(self) -> str:
        """Enum names are not confirmed yet, so always ``unknown_<n>``."""
        return f"unknown_{self.error_code}"
