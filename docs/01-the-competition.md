# The competition, in enough detail to be useful

*What a new participant needs to know before Round 1 opens, and the constraints that shape every
design decision afterwards.*

---

## Format

IMC Prosperity 4 ran over 16 days in April 2026, split into two phases with a four-day intermission:

| | Rounds | Length | Purpose |
|---|---|---|---|
| Tutorial | — | ~3 weeks | Sandbox. One product, no scoring. |
| Phase 1 | 1, 2 | 72 h each | Qualifier. Reach 200,000 XIRECs to advance. |
| Intermission | — | 4 days | Nothing to submit. |
| Phase 2 | 3, 4, 5 | 48 h each | **Leaderboard reset to zero.** This decides the competition. |

The reset matters more than anything else about the schedule. Whatever you do in Rounds 1–2 buys you
only qualification; the final ranking is determined entirely by Rounds 3–5, and Round 5 carries the
largest product universe and therefore the largest dispersion. A team that is 900th after Round 1 and
a team that is 5th are, in Round 3, on the same line.

18,803 teams and 30,703 participants entered, from 1,549 universities across 117 countries. Teams
uploaded 556,223 Python programs over the two weeks.

## The algorithmic challenge

You submit one Python file defining `class Trader` with a single entry point:

```python
def run(self, state: TradingState) -> tuple[dict[Symbol, list[Order]], int, str]:
    ...
```

It is executed against a simulated trading day of 10,000 snapshots (timestamps `0, 100, …, 999_900`).
At each snapshot you receive a `TradingState` containing:

| Field | Contents |
|---|---|
| `order_depths` | Up to three price levels per side, per product. Buy volumes positive, **sell volumes negative**. |
| `market_trades` | Prints since the last call. From Round 4, with counterparty identities. |
| `own_trades` | Your fills since the last call. |
| `position` | Signed position per product. |
| `traderData` | Whatever string you returned last tick. |
| `observations` | Round-specific extras (conversion quotes, tariffs, exogenous indices). |

and you return `(orders, conversions, traderData)`.

### Constraints that actually bind

**The runtime is stateless.** Class attributes and module globals are not guaranteed to survive
between calls. The container can be recycled at any point. All state must round-trip through
`traderData`, capped at 50,000 characters. In practice this means: store *derived summaries*, not
history. An EWMA is one float; a 500-tick rolling window is 500 floats you may not get back.

**Position limits are hard, and the penalty is severe.** If the orders you send for a product in one
tick could, in aggregate, breach the limit, *all* orders for that product in that tick are rejected
outright, not truncated. Every strategy therefore needs a pre-flight accounting step:

```python
max_buy  = limit - position          # total across all buy orders this tick
max_sell = limit + position          # total across all sell orders this tick
```

The subtlety that catches people is *aggregation across strategies*. If two independent sub-strategies
both quote the same voucher, their orders are summed before the check. Any multi-signal design needs
a shared position ledger.

**Orders do not rest.** Everything unfilled is cancelled at the end of the tick. There is no queue
position to protect and no penalty for re-quoting, which makes the design space closer to a
repeated one-shot auction than to a real exchange.

**Execution is instantaneous and priority is yours.** Your orders are processed before the bots' at
the same price. Latency optimisation is pointless; edge sizing and fill probability are everything.

**Only a few libraries.** Standard library plus `numpy`, `pandas`, `statistics`, `math`, `typing`,
`jsonpickle`. No `scipy`, no `sklearn`. Anything that needs fitting has to be fitted offline and
shipped as constants, which is itself a useful discipline: it forces you to state your model
in a handful of numbers you can defend.

**Time budget.** 900 ms hard cap per call, ~100 ms average. Comfortable for anything algebraic;
fatal for anything that loops over history each tick.

## The data you are given

Two semicolon-delimited CSVs per product-day:

```
prices_round_<R>_day_<D>.csv
  day;timestamp;product;bid_price_1..3;bid_volume_1..3;ask_price_1..3;ask_volume_1..3;mid_price;profit_and_loss

trades_round_<R>_day_<D>.csv
  timestamp;buyer;seller;symbol;currency;price;quantity
```

Three practical warnings, all of which cost us time:

1. **`mid_price` is meaningless when a side is empty.** About 8% of Round-1 snapshots are missing a
   quote on one side (4.0% no bid, 3.9% no ask, 0.16% neither); the file still emits a row. Left in, those rows destroy every summary statistic you
   compute. The standard deviation of osmium's mid goes from 4.8 to 404. Filter first.
2. **A day is 1,000,000 timestamps, not 100,000.** Ten thousand snapshots at a step of 100. Getting
   this wrong silently corrupts every time-to-expiry and drift calculation.
3. **The tape is bot-versus-bot.** It records what happened *without you in the book*. It is the right
   input for estimating counterparty behaviour and for modelling passive fills, but it systematically
   omits the flow you would have attracted by quoting differently.

## The manual challenge

A separate puzzle each round, contributing to the same PnL total: an auction, an allocation, a
level-*k* bidding game, an exotic-option pricing exercise, a news-trading round. It is bounded,
self-contained work with no execution risk. Ignoring it, as we largely did, was a poor
trade. See [the manual section of the README](../README.md#the-manual-challenge).

## Why it is hard

- **The data-generating process is unknown and product-specific.** Some products are Ornstein–Uhlenbeck,
  some are deterministic ramps, some are latent random walks observed through a rounding function.
  Standard financial indicators are the wrong tool; the right question is *how would I have generated
  this series?*
- **Three days is not much.** Enough to characterise a mechanism, nowhere near enough to validate a
  weak statistical relationship. The scoring day is always out of sample.
- **The universe grows faster than your time.** Round 5 hands you 50 products and 48 hours. The
  binding constraint is the number of hypotheses you can *reject* reliably, not the number you can
  generate.
- **The leaderboard is a tournament.** Expected PnL and expected rank are different objective
  functions, and the gap between them is where most of the interesting decisions live.
