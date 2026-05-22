# SOPHII.TERMINAL Test Checklist

## Accuracy checks (data correctness)
- [ ] `/api/stock/{t}` price roughly matches public quote source for AAPL/MSFT/NVDA.
- [ ] `/api/stock/{t}/chart` returns chronological OHLCV with ISO timestamps.
- [ ] `/api/stock/{t}/analyst` implied upside equals `(target_mean-current)/current*100`.
- [ ] `/api/stock/{t}/sentiment` percentages sum to 100.
- [ ] Missing data fields return `null` not crashes.

## Credibility checks (safe educational behavior)
- [ ] UI copy never instructs to buy/sell/hold/short/trade.
- [ ] Disclaimer is visible: educational only, not financial advice.
- [ ] Sentiment rationale is one sentence and framed as estimate.
- [ ] Chart insight language uses cautious wording ("may suggest", "could indicate").

## Functionality checks (tool behavior)
- [ ] App loads with default ticker AAPL.
- [ ] Search returns selectable results.
- [ ] Chart range tabs load different datasets.
- [ ] Add/remove watchlist works and persists after reload.
- [ ] StreetPulse renders with fallback when sentiment unavailable.
- [ ] Analyst panel renders with null-safe values.
- [ ] Peer table handles empty peer list safely.
- [ ] Error/loading states appear per major section.
