"""
strategies/base.py
==================
Abstract interface for edge-hunting strategies.

Every strategy that enters the edge-hunting pipeline implements ``EdgeStrategy``.
The pipeline calls ``fit`` on the in-sample slice, then walks the out-of-sample
slice bar-by-bar calling ``signal``.  The strategy returns a ``Signal`` (target
exposure + stop price); the pipeline handles simulation, fees, and reporting.

Design contract
---------------
* ``fit`` sees ONLY the in-sample slice (no future bars).
* ``signal`` is called with the FULL feature frame + close series but must use
  only data at or before ``bar_idx``.  The look-ahead test gate enforces this.
* Strategies are stateless across windows: ``fit`` resets all learned state.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class Signal:
    """A single-bar trading decision.

    Attributes
    ----------
    target_exposure : float
        Fraction of equity to hold in the asset (0 = cash, 1 = full,
        >1 = leveraged long, <0 = short).
    stop_price : float
        Price below which the position is flattened.  ``0.0`` disables.
    meta : dict | None
        Optional metadata (regime label, confidence, etc.) recorded in the
        regime history for post-hoc analysis.
    """

    target_exposure: float
    stop_price: float = 0.0
    meta: dict | None = None


class EdgeStrategy(ABC):
    """Abstract base class for all edge-hunting strategies."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique strategy identifier (used as output directory name)."""

    @abstractmethod
    def fit(
        self,
        train_features: pd.DataFrame,
        train_close: pd.Series,
        config: dict,
    ) -> None:
        """Train on the in-sample slice.

        Parameters
        ----------
        train_features : pd.DataFrame
            Standardized feature frame for the training window.
        train_close : pd.Series
            Close prices for the training window.
        config : dict
            The full experiment config (entry_rules, exit_rules, etc.).
        """

    @abstractmethod
    def signal(
        self,
        bar_idx: int,
        features: pd.DataFrame,
        close: pd.Series,
    ) -> Signal:
        """Return the trading signal for bar ``bar_idx``.

        Called bar-by-bar on the out-of-sample slice.  Must use only data
        at or before ``bar_idx`` (the look-ahead gate enforces this).

        Parameters
        ----------
        bar_idx : int
            Positional index into ``features`` / ``close``.
        features : pd.DataFrame
            Full standardized feature frame (train + test).
        close : pd.Series
            Full close price series (train + test).

        Returns
        -------
        Signal
            Target exposure + stop price for this bar.
        """