# Reference implementations

These are **teaching versions**, not our competition submissions. Each file isolates one idea from
the write-up, keeps its parameters at the top as module-level constants, and stays short enough to
read in one sitting. They are `Trader`-compatible: drop one into the Prosperity IDE (where the real
`datamodel` exists) and it will run.

Deliberately removed relative to what we submitted: the multi-strategy arbitration layer, shared-leg
position accounting across overlapping pairs, the `traderData` compression scheme, and the parameter
sets that came out of our own search.

| File | Idea | Round | Discussed in |
|---|---|---|---|
| [`anchored_market_maker.py`](anchored_market_maker.py) | Take through a fixed fair value, quote the rest, skew on inventory | 1 | [docs/02](../docs/02-round-1-fair-value.md) |
| [`deterministic_drift.py`](deterministic_drift.py) | Recover an exact fair-value function; let the position limit, not the spread, drive the design | 1 | [docs/02](../docs/02-round-1-fair-value.md) |
| [`synthetic_forward_mm.py`](synthetic_forward_mm.py) | A deep-ITM option is a synthetic forward: quote around a fair value you *derive* | 3–4 | [docs/03](../docs/03-round-3-voucher-surface.md) |
| [`voucher_delta_expression.py`](voucher_delta_expression.py) | Express a mean-reversion view on the underlying through the option chain, sized by delta | 3–4 | [docs/03](../docs/03-round-3-voucher-surface.md) |
| [`lattice_reversal.py`](lattice_reversal.py) | Fade a rounding-lattice crossing; armed generically on every product | 5 | [docs/05](../docs/05-round-5-fifty-products.md) |
