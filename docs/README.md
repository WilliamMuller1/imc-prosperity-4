# Documentation

Deep dives behind the [main write-up](../README.md). Each round document contains the full numbers,
the design decisions we made, and what we would do instead where they differ.

| | |
|---|---|
| [01 · The competition](01-the-competition.md) | Format, the `Trader` contract, the constraints that actually bind, the data traps |
| [02 · Round 1: finding fair value](02-round-1-fair-value.md) | Wall mid, an OU anchor, a deterministic drift, and how to rank inventory against spread |
| [03 · Round 3: the voucher surface](03-round-3-voucher-surface.md) | Empirical delta ladders, the intrinsic-value basis, why cross-strike relative value does not clear the spread, and how to use the chain as leverage instead |
| [04 · Round 4: counterparties](04-round-4-counterparties.md) | Execution-edge profiling, and a t-statistic of 26 that turned out to be our own estimator |
| [05 · Round 5: fifty products](05-round-5-fifty-products.md) | The multiple-testing trap, the rounding lattice, an exact identity that was not a trade, the trade we missed next door, and the bet we got away with |

## The short version

If you are about to compete and have ten minutes, read these six paragraphs:

1. **Fair value first, and not the touch mid.** Use the midpoint of the deepest level on each side.
   On Round-1 osmium it cuts the tick-to-tick variance of the estimator by a factor of 2.8, and in
   Round 4 it is the difference between a real signal and a t-statistic of 26 pointing at nothing.

2. **Rank your edges before optimising any of them.** In Round 1 a unit of pepper-root inventory was
   worth 1,000 ticks of drift per day and a market-making round trip was worth 13, so being long comes
   first. But a round trip returns the inventory, so the two add: the real cost of quoting is only the
   drift forgone while flat. Getting the order right is the exercise; treating the smaller term as zero
   costs you the rest of the round.

3. **Measure every effect in ticks and compare it with the spread.** The Round-3 volatility smile is
   real and worth about one tick against spreads of 1–6. That single comparison saved us a day.

4. **Prefer mechanisms to correlations, then price both against the spread.** A rounding lattice, an
   accounting identity, an option's intrinsic value have a *because*, so they survive out of sample.
   That is a separate question from whether they are tradable: the Round-5 pebbles identity is exact
   and costs 23x its own signal to trade, while a drifting -0.92 correlation next door was worth 11x
   its cost. Round 5 also hands you 1,225 pairs, one in five of which passes ADF on noise alone.

5. **Hold out a day, and always run the null.** Fit on two days, test on the third: 97% of our
   in-sample "cointegrated" pairs failed. Simulate independent random walks of the same length and
   see what your screen finds in them: 13.8%.

6. **Optimise for plateaus, not peaks.** If a threshold of 100 works and 95 and 105 do not, the only
   special thing about 100 is noise.
