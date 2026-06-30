# Live Cockpit

The Dashboard is where you run and watch your trades. Everything updates live — you don't need to refresh the page.

---

## The engine bar

The strip at the very top of the dashboard tells you what the engine is doing right now and gives you the main controls.

**When the engine is off:**

You'll see "Engine idle" and a **Start Engine** button. There's also a small dot showing whether the live data connection is working.

**When the engine is running:**

You'll see a colored badge showing the mode (blue for Paper, red for Live), the name of the running strategy, and a run number. Two buttons appear:

- **Stop** — Cleanly exits your open position using the strategy's own exit logic, then shuts down. Use this for a planned end to the session.
- **⚡ Kill** — Emergency stop. Immediately closes any open position at the best available price and halts everything. Use this if something is wrong.

---

## Starting the engine

1. Click **Start Engine**.
2. Pick a **strategy** from the dropdown. Strategies are the rules the engine follows to decide when to buy and sell.
3. Pick a **mode**:
   - **Paper** — Simulates trades using real live prices, but no actual orders go to Zerodha. Use this to test a strategy safely.
   - **Live** — Places real orders in your Zerodha account. Only use this after you've confirmed the strategy behaves as expected in Paper mode.
4. Optionally adjust **parameters** (like quantity or period lengths) by editing the JSON box.
5. Click **Start Paper** or **Start Live**.

> **Recommended:** Always run a strategy in Paper mode first for at least a few sessions before switching to Live.

---

## The six tiles

Below the engine bar, six numbers update live while the engine runs:

| Tile | What it shows |
|---|---|
| **Day P&L** | Your total profit or loss for today's session (closed trades + open position) |
| **Unrealized** | The profit or loss on your current open trade right now |
| **LTP** | The last price the market traded at for your instrument |
| **In position** | Yes or No — whether you currently have an open trade |
| **Mode** | Paper or Live |
| **Strategy** | The name of the strategy that's running |

---

## The position card

When you have an open trade, this card shows the details:

- The **instrument** (e.g. NIFTY 24800 CE) and direction (LONG or SHORT)
- A **P&L strip** that turns green when you're up and red when you're down
- Your **entry price**, current **LTP**, and **quantity**
- A **duration clock** counting how long the trade has been open
- A **pos.vars table** showing the strategy's internal state — for example, the trailing high-water mark the strategy is tracking to decide when to exit

When there's no open trade, the card shows "Flat — no open position."

---

## The activity feed

Every significant engine event appears here in real time:

| Event | What happened |
|---|---|
| Engine started | The engine came online |
| Engine stopped | The engine shut down cleanly |
| Kill switch | Emergency stop was triggered |
| Order fill | An entry or exit order was filled by the broker |
| Trade closed | A full round-trip trade finished — the P&L is shown |
| Alert | A risk limit was hit (e.g. daily loss limit or 15:15 forced exit) |

The feed keeps the last 50 events. Click **Clear** to reset it.

---

## Automatic stops

You don't have to be at your screen all day. The engine will stop itself in two situations:

- **15:15 IST** — The engine automatically closes any open position and halts before the market closes. This happens every trading day.
- **Daily loss limit** — If your losses for the session cross a threshold set in your configuration, the engine halts to protect your account.

---

## SAFE mode

SAFE mode is a protective pause. It can happen if the engine restarts unexpectedly (e.g. a server reboot) and detects that your Zerodha account has a position that the engine didn't expect.

While SAFE mode is on, **the engine won't place any new orders**. A red banner appears at the top with three options:

| Option | When to use it |
|---|---|
| **Adopt position** | The position in Zerodha is real and you want the engine to take over managing it. Enter the details (direction, quantity, average price) and confirm. |
| **Square off now** | You want to close the position immediately. The engine will send a market order to flatten it. |
| **Resume** | The position is already flat (either you closed it manually in Zerodha, or there was nothing there). This clears SAFE mode and lets the engine continue. |

---

## The kill switch

The ⚡ Kill button requires a **kill token** — a separate password set when the server was configured. This is intentional: it means even if someone gains access to your dashboard session, they still cannot trigger an emergency stop without the kill token.

When you click Kill:
1. A dialog appears asking for the kill token.
2. Enter the token and click **Kill now**.
3. The engine immediately closes any open position and stops.
