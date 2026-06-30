# Go-Live Checklist

Work through this list before switching from Paper to Live mode for the first time.

---

## 1. Settings & connectivity

- [ ] API key and secret saved in Settings → Zerodha API
- [ ] Redirect URL and Postback URL pasted into your Kite developer console app
- [ ] Kite login successful (green badge in the top bar)
- [ ] Telegram alerts configured and test message received (optional but recommended)

---

## 2. Strategy validation in Paper mode

- [ ] Run the strategy in **Paper mode** for at least 1 full trading session (preferably 3–5)
- [ ] Review the Orders page — do the entry/exit reasons make sense?
- [ ] Check Analytics — is the profit factor > 1? Is the max drawdown acceptable?
- [ ] Confirm the strategy exits before 15:15 IST on its own (or that the forced exit fires correctly)
- [ ] Confirm the kill switch works: click ⚡ Kill, enter kill token, verify the engine stops and position flattens

---

## 3. Risk configuration

Before going live, review these values in your `.env` file:

| Setting | What it controls | Recommended start |
|---|---|---|
| `MAX_DAILY_LOSS` | Engine halts if day loss exceeds this | ₹2,000–₹5,000 |
| `FORCE_SQUAREOFF_TIME` | Time to force-exit all positions | `15:15` |
| `KILL_TOKEN` | Password for the kill switch | Long random string |

Start with a conservative daily loss limit. You can widen it once you have live data.

---

## 4. First live session

- [ ] Start with **minimum quantity** (qty=1 or the smallest your strategy allows)
- [ ] Watch the cockpit for the first 30 minutes live
- [ ] Confirm the first entry/exit order appears in Zerodha's order book
- [ ] Check P&L matches between the dashboard and Zerodha
- [ ] Let the engine run to 15:15 or stop it manually with the Stop button — not Kill

---

## 5. Daily routine (once live)

Each trading day:

1. Log in to Kite from the top bar before 9:15 IST
2. Start the engine at or just before market open
3. Monitor the cockpit periodically — you don't need to watch it all day
4. The engine stops itself at 15:15 IST automatically
5. Review the Orders page after market close

---

## 6. Backups

The trading database is at `/opt/trade-engine/app/data/trade.db` on the server. Back it up regularly:

```bash
# Run manually or via cron
/opt/trade-engine/app/deploy/backup.sh
```

The backup script keeps the 30 most recent copies. Add it to crontab to run daily:

```
0 16 * * 1-5  /opt/trade-engine/app/deploy/backup.sh >> /var/log/trade-backup.log 2>&1
```

(Runs at 16:00 IST on weekdays, after the market closes and all trades are settled.)

---

## 7. Monitoring

- The systemd service (`trade-engine`) auto-restarts the API if it crashes
- Telegram alerts fire for: engine stops, kill switch, daily loss halt, trade closes
- Check `journalctl -u trade-engine -n 50` on the server for raw logs if something looks wrong

---

## 8. When NOT to trade live

Stop the engine and stay in Paper if any of the following happen:

- Zerodha has a system outage (check their status page)
- Your internet connection or VPS is unstable
- You've changed the strategy code and haven't re-validated in Paper
- It's a holiday or a day with unusual market conditions (budget day, election results)
