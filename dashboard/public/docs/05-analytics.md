# Analytics

The Analytics page shows how your strategies have performed over time — across all runs, a single run, or filtered by mode.

---

## Filters

At the top right are two dropdowns to focus the analysis:

- **All modes / Paper / Live / Backtest** — show only trades from that mode
- **All runs / Run #N** — zoom into a single engine session

Changing either filter instantly refreshes all three panels below.

---

## Metrics strip

Nine tiles summarising the filtered set of closed trades:

| Tile | What it means |
|---|---|
| **Total P&L** | Net profit or loss across all closed trades in the filter |
| **Win rate** | Percentage of trades that closed with a profit |
| **Avg win** | Average profit of winning trades |
| **Avg loss** | Average loss of losing trades (shown as positive number) |
| **Profit factor** | Gross profit ÷ gross loss. Above 1.0 means the strategy makes more than it loses overall |
| **Trades** | Wins / Losses (total) |
| **Max drawdown** | The largest peak-to-trough fall in cumulative P&L — a measure of the worst losing streak |
| **Largest win** | Single best trade |
| **Largest loss** | Single worst trade |

---

## Equity curve

A cumulative P&L line chart — each point represents one closed trade. The line rises when trades are profitable and falls when they lose. Hover a point to see the individual trade's P&L.

A flat line with no data means there are no closed trades matching the current filter.

---

## Daily P&L

A bar chart showing total profit or loss by calendar day. Green bars are profitable days; red bars are losing days. Use this to spot which days of the week or month tend to perform well or badly.

---

## What "all runs" means

By default, all filters are off and the page shows every closed trade in the database — regardless of which engine session it came from. This gives you a lifetime view of total performance.

Use the **Run #N** selector to isolate a single session if you want to compare a specific paper run against a live run, or see how a strategy performed before you changed its parameters.
