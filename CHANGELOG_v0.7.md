# AETHER v0.7 — Cash, FIFO and Exposure

## Added
- Cash ledger with automatic cash movements for BUY/SELL transactions.
- Manual cash entries for deposits, withdrawals, dividends, interest, fees, tax and adjustments.
- Per-currency running balances and transaction references.
- FIFO open-lot calculation with buy fees included in lot cost.
- FIFO realized P&L estimate, explicitly excluding sell-side fee allocation and tax.
- Portfolio market-value exposure, asset-type grouping, unpriced holdings and top-five concentration.
- Audit events for manual cash entries.

## Limitations
This is an analytical ledger, not a bank/broker reconciliation system. Cash balances start at zero until deposits/other entries are recorded. FX conversion is not performed. FIFO calculations are estimates, not tax advice; sell-side fees are not allocated into the displayed FIFO realized P&L, and corporate actions, tax rules, settlement and derivative margin are not handled. Exposure uses latest imported daily bars and excludes cash, derivatives, accrued income and unpriced positions.
