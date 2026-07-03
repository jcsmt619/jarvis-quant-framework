# Futures Scalper

A standalone intraday futures trading system. It detects the current volatility
regime with a Hidden Markov Model, runs a scalping playbook that fits that
regime, sizes everything in contracts, and enforces prop-firm rules so a funded
account stays inside its daily loss limit and trailing drawdown. It ships with a
simulation broker so the whole thing runs with no account, and plugs into IBKR,
TradeStation, or a prop-firm gateway like Topstep when you are ready for live.

Be clear about the scope. This is regime-aware intraday trading on short
timeframes. It is not tick-by-tick HFT, and it does not pretend to be. The HMM
reads how violent the tape is right now and decides which setups are allowed and
how big. The setup decides long or short.

## What makes it futures-specific

To start, the broker is not Alpaca. Futures need IBKR, TradeStation, or a prop
gateway, so the system talks to a small broker interface and the simulator is the
default. Sizing is in contracts, worked out from how many ticks sit between entry
and stop and what each tick is worth. The risk layer carries prop-firm rules as
first-class circuit breakers, including a trailing drawdown that locks the
account and writes a lock file you have to delete by hand. And the loop is
session-aware, so it knows Globex hours and the daily maintenance break instead
of a 9:30 to 4:00 stock day.

## Quick start

```bash
pip install -r requirements.txt

# Train the regime model on the bundled synthetic data
python main.py train-only

# Walk-forward backtest with contract P&L and prop-firm rules
python main.py backtest

# Backtest plus the big three checks (walk-forward, Monte Carlo, sensitivity)
python main.py validate

# Watch the whole pipeline run on the simulator, no account needed
python main.py live --demo --fast
```

The defaults use a synthetic regime-switching data source so everything runs out
of the box. Synthetic data has no real edge, so a losing backtest there is
expected. It is for checking the machinery, not the strategy. Point the data
source at a real intraday file or a broker feed before you read anything into the
numbers.

## Switching brokers

Set `broker.type` in `config/settings.yaml` to `sim`, `ibkr`, or `tradestation`.

- `sim` runs locally and needs nothing else.
- `ibkr` needs `pip install ib_insync` and Trader Workstation or the IB Gateway
  running. Port 7497 is paper, 7496 is live.
- `tradestation` needs `pip install requests` and OAuth credentials in `.env`.
  The same adapter fronts Topstep/ProjectX: point `base_url` at the gateway.

Credentials always live in `.env`, never in the config. Copy `.env.example` to
`.env` and fill in what you use.

## Mobile alerts

Message @BotFather on Telegram to create a bot, put the token and your chat id in
`.env` as `TELEGRAM_TOKEN` and `TELEGRAM_CHAT_ID`, and you get a ping on entries,
fills, and circuit breakers. With no token it just logs and does nothing else.

## How it fits together

```
bars -> features -> HMM (filtered, no look-ahead) -> volatility regime
                                                          |
                                          scalp playbook for that regime
                                                          |
                                  risk manager: contract sizing + prop-firm veto
                                                          |
                                          broker (sim / IBKR / TradeStation)
```

The regime is computed with the forward algorithm, so the regime printed at a bar
never changes when later bars arrive. There is a test that fails if that ever
stops being true.

## Prop-firm rules

Set these to your account's real numbers in `config/settings.yaml` under
`risk.prop_firm`. The defaults are placeholders.

- `daily_loss_limit` halts trading for the session.
- `trailing_max_drawdown` trails the high-water mark, and a breach locks the
  account and writes `trading_halted.lock`. Delete the file to resume.
- `daily_loss_reduce_at` halves size as you approach the daily limit.

## The big three (validation)

`python main.py validate` runs the three checks that decide whether a result is
real. Walk-forward trades only out-of-sample data. Monte Carlo reshuffles the
trade sequence to a distribution of outcomes and a probability of breaching the
trailing limit. Sensitivity perturbs the key parameters to confirm the result is
stable rather than a sharp peak you happened to land on.

## Tests

```bash
python -m pytest tests/ -q
```

## Configuration

Everything is in `config/settings.yaml`, grouped and commented: broker, universe,
data source, instrument overrides, HMM, strategy, risk and prop-firm, backtest,
sessions, and monitoring.

## Disclaimer

This is educational software. Futures trading involves substantial risk of loss
and is not suitable for everyone. Nothing here is financial advice and there is
no guarantee of profit. Backtested and simulated results do not represent real
trading and have their own biases. Run it on the simulator, then on a small or
funded evaluation account, and understand every part before risking real money.
You are responsible for your own trades.
