from datetime import UTC, datetime

import pandas as pd
import pytest

from paper_trading.alpaca_config import AlpacaConfigError, AlpacaPaperConfig
from paper_trading.alpaca_market_data import (
    fetch_alpaca_daily_bars,
    write_market_data_csv,
)


def valid_config(**overrides):
    values = {
        "api_key": "paper_key",
        "secret_key": "paper_secret",
        "base_url": "https://paper-api.alpaca.markets",
        "paper_only": True,
        "confirm_live": False,
    }
    values.update(overrides)
    return AlpacaPaperConfig(**values)


class FakeBars:
    def __init__(self, df):
        self.df = df


class FakeClient:
    def __init__(self, bars):
        self.bars = bars
        self.get_bars_calls = []
        self.order_calls = []

    def get_bars(self, *args, **kwargs):
        self.get_bars_calls.append((args, kwargs))
        return self.bars

    def submit_order(self, **kwargs):
        self.order_calls.append(kwargs)
        raise AssertionError("submit_order must not be called")


def test_fetch_bars_from_dataframe_response():
    raw = pd.DataFrame(
        {
            "close": [65.0, 66.0, 67.0],
        },
        index=pd.to_datetime(
            [
                "2026-07-01T20:00:00Z",
                "2026-07-02T20:00:00Z",
                "2026-07-06T20:00:00Z",
            ]
        ),
    )

    client = FakeClient(FakeBars(raw))

    bars = fetch_alpaca_daily_bars(
        config=valid_config(),
        symbol="EEM",
        limit=3,
        client_factory=lambda **kwargs: client,
    )

    assert len(bars) == 3
    assert list(bars.columns) == ["Date", "Close"]
    assert bars["Close"].iloc[-1] == 67.0
    assert client.get_bars_calls
    assert client.order_calls == []


def test_fetch_bars_rejects_live_endpoint_before_client_creation():
    called = False

    def factory(**kwargs):
        nonlocal called
        called = True
        return FakeClient(FakeBars(pd.DataFrame()))

    with pytest.raises(AlpacaConfigError):
        fetch_alpaca_daily_bars(
            config=valid_config(base_url="https://api.alpaca.markets"),
            client_factory=factory,
        )

    assert called is False


def test_fetch_bars_rejects_non_positive_limit():
    with pytest.raises(ValueError):
        fetch_alpaca_daily_bars(
            config=valid_config(),
            limit=0,
            client_factory=lambda **kwargs: FakeClient(FakeBars(pd.DataFrame())),
        )


def test_fetch_bars_from_iterable_bar_objects():
    class Bar:
        def __init__(self, t, c):
            self.t = t
            self.c = c

    client = FakeClient(
        [
            Bar(datetime(2026, 7, 1, 20, 0, tzinfo=UTC), 65.0),
            Bar(datetime(2026, 7, 2, 20, 0, tzinfo=UTC), 66.0),
        ]
    )

    bars = fetch_alpaca_daily_bars(
        config=valid_config(),
        symbol="EEM",
        limit=2,
        client_factory=lambda **kwargs: client,
    )

    assert len(bars) == 2
    assert bars["Close"].iloc[-1] == 66.0
    assert client.order_calls == []


def test_write_market_data_csv_creates_csv_and_json_without_secrets(tmp_path):
    bars = pd.DataFrame(
        {
            "Date": pd.to_datetime(["2026-07-01T20:00:00Z", "2026-07-02T20:00:00Z"]),
            "Close": [65.0, 66.0],
        }
    )

    csv_path, result = write_market_data_csv(
        bars=bars,
        symbol="EEM",
        output_dir=tmp_path,
    )

    assert csv_path.exists()
    assert result.symbol == "EEM"
    assert result.bars_count == 2
    assert result.latest_close == 66.0
    assert result.read_only is True
    assert result.order_submission_enabled is False
    assert result.live_trading_enabled is False
    assert result.broker_order_call_performed is False

    text = csv_path.read_text(encoding="utf-8")
    assert "paper_key" not in text
    assert "paper_secret" not in text



def test_fetch_bars_from_multiindex_column_response():
    raw = pd.DataFrame(
        {
            ("EEM", "close"): [65.0, 66.0],
            ("EEM", "volume"): [100, 200],
        },
        index=pd.to_datetime(
            [
                "2026-07-01T20:00:00Z",
                "2026-07-02T20:00:00Z",
            ]
        ),
    )

    client = FakeClient(FakeBars(raw))

    bars = fetch_alpaca_daily_bars(
        config=valid_config(),
        symbol="EEM",
        limit=2,
        client_factory=lambda **kwargs: client,
    )

    assert len(bars) == 2
    assert list(bars.columns) == ["Date", "Close"]
    assert bars["Close"].iloc[-1] == 66.0
    assert client.order_calls == []



def test_fetch_bars_passes_explicit_start_and_end():
    raw = pd.DataFrame(
        {"close": [65.0, 66.0]},
        index=pd.to_datetime(["2026-07-01T20:00:00Z", "2026-07-02T20:00:00Z"]),
    )

    client = FakeClient(FakeBars(raw))

    fetch_alpaca_daily_bars(
        config=valid_config(),
        symbol="EEM",
        limit=2,
        client_factory=lambda **kwargs: client,
    )

    args, kwargs = client.get_bars_calls[0]

    assert args[0] == "EEM"
    assert "start" in kwargs
    assert "end" in kwargs
    assert kwargs["limit"] == 2
    assert kwargs["adjustment"] == "all"
