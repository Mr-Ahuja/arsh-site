# Orders

The Orders page shows every trade the engine has ever placed — across all sessions, modes, and strategies. Use it to review your history, spot patterns, and export data for your own analysis.

---

## The filter bar

At the top of the page are filters that narrow down the trades shown. All filters work together — you can combine as many as you like.

| Filter | What it does |
|---|---|
| **Date from / to** | Show only trades that opened on or between these dates |
| **Mode** | Filter by Paper, Live, or Backtest trades |
| **Status** | Closed (finished trades), Open (still running), or Cancelled |
| **Exit reason** | How the trade ended — see the Exit reason glossary below |
| **Symbol** | Type any part of the symbol name to filter (e.g. "NIFTY" or "SBIN") |

Changing any filter immediately refreshes the table.

---

## The summary bar

Just below the filters, a one-line summary shows totals for whatever the current filter shows:

- **N trades** — how many match
- **W wins / L losses** — how many closed trades made or lost money
- **Win rate %** — percentage of closed trades that were profitable
- **Total P&L** — net profit or loss across all matching closed trades

---

## The trade table

Each row is one complete trade. Columns left to right:

| Column | What it means |
|---|---|
| **#** | Internal trade ID |
| **Date (IST)** | When the trade opened |
| **Symbol** | The instrument traded (e.g. NSE:SBIN) |
| **Side** | LONG (bought) or SHORT (sold) |
| **Qty** | Number of shares |
| **Mode** | Paper, Live, or Backtest |
| **Strategy** | Which strategy was running |
| **Entry** | Price at which the trade opened |
| **Exit** | Price at which the trade closed (blank if still open) |
| **P&L** | Profit (green) or loss (red) in rupees |
| **Duration** | How long the trade was open |
| **Exit reason** | Why the trade closed — see glossary below |
| **Status** | Open, Closed, or Cancelled |

---

## Exit reason glossary

| Reason | What happened |
|---|---|
| **Strategy** | The strategy's own exit logic decided to close the trade (e.g. trailing stop hit) |
| **Force exit** | The engine's 15:15 IST forced square-off closed the trade automatically |
| **Daily loss** | The daily loss limit was hit — engine closed the trade and stopped for the day |
| **Kill switch** | You (or someone with the kill token) triggered the emergency stop |
| **Error** | An unexpected error caused the engine to close the position defensively |
| **Manual** | The position was closed manually (e.g. via SAFE mode reconciliation) |

---

## Exporting to CSV

Click **Export CSV** (top right of the filter bar) to download all matching trades as a spreadsheet. The exported file respects the current filters — so if you're viewing only Paper trades from last week, the export contains exactly those rows.

The CSV includes all columns: ID, symbol, side, quantity, mode, strategy, entry/exit prices and timestamps, P&L, duration, exit reason, and run ID.

---

## Pagination

If more than 50 trades match, use the page controls at the bottom of the table to navigate. The summary bar always shows totals across **all** matching trades, not just the current page.
