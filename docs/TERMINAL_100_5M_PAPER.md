# Khaledpoly: 100 USDC aggressive 5-minute public-data PAPER study

**Status:** PAPER ONLY. Existing Khaledpoly v0.6.0 release gate and its Java/Python execution components remain unchanged. This standalone research observer **does not call or execute the upstream Node.js trading bot**, and it never places real orders. It tests an enhanced version of the same paired maker-entry economic idea against *public* Polymarket order-book snapshots. No API credentials or wallet keys are required.

## Experiment configuration

| Setting | Value |
| --- | --- |
| Time | 7,200 seconds (2 hours, continuous) |
| Start | $100 virtual USDC |
| Markets | BTC, ETH and SOL Up/Down, 5-minute slots |
| Buy two sides | Maker-proxy bids, max combined price $0.98, min edge $0.015/share |
| Sizing | 18 shares per cycle; roughly 17.64 USDC per pair at combined 0.98 |
| Exposure | One pair at a time, up to 3 paired cycles per 5-minute slot |
| Opportunity ranking | Bid-pair edge, bid/ask spread, smoothed historical per-asset proxy outcome |
| Activity | Reentry up to 2 times per asset per market, entry only in first 115 seconds |
| One-sided control | Timeout 42s after first leg, 14% price drop threshold, close 35s before market end |
| Costs | $0.03 estimated merge cost/pair, 1.5% modeled one-sided exit haircut |
| Maker rebates | Excluded; no estimate is fabricated |
| Proxy fill | Two **subsequent** best-ask price crossings at least half a cent below the posted bid; displayed size requirement at book level |

**Important execution limit:** A displayed best ask below a posted order is *not* evidence that the order would fill at its true queue position, nor is displayed order-book volume equivalent to matched executed volume. Two observations reduce superficial touches but do not prove queue fills. This adapted model also uses best-ask book size filtering, which is only a proxy for depth. A public order-book observer cannot fully account for cancellations, trade priority, transaction costs, chain settlement, latency, actual taker fees, or real maker rebate revenue. If no executable bid is available at exit, the observer assumes a zero-value conservative write-off and separately counts these `unpriced_exits`; this is an estimate, not a genuine sale. The engine assumes instant virtual merge after paired proxy fills (with a fixed fee estimate) and does not execute the full Node bot.

## Full run

GitHub Actions workflow: `.github/workflows/terminal-100-5m-two-hour.yml`.

```bash
python3 research/terminal_100_5m_2h.py --self-test
python3 -u research/terminal_100_5m_2h.py --duration-seconds 7200 --assets btc,eth,sol
```

Output bundle: `paper_runs/terminal_100_5m_2h/{summary.json,state.json,events.jsonl}`. Artifacts retained for 14 days. A failed workflow uploads whatever partial records were captured when possible. Re-run with a **new empty output directory** to avoid silently overwriting or concatenating results. GitHub Actions will start when this workflow is added to `main`; manual re-run is available with `workflow_dispatch`.

## Comparison with prior 70 USDC / BTC 15m study

The previous six-hour study used $70 virtual USDC and a one-sample future-ask-touch proxy. The new two-hour study uses $100, multiple assets, bigger sizing, and a two-snapshot buffered model; *raw count or nominal PnL cannot be compared as a controlled A/B test*. Any headline comparison must normalize by time, capital, model differences and data quality. Stop any promotion toward real-money use until actual queue/settlement and fee evidence is independently validated.