import os
import math
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Awaitable

import numpy as np
import pandas as pd
import yfinance as yf
import httpx
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from motor.motor_asyncio import AsyncIOMotorClient

app = FastAPI(title='SOPHII.TERMINAL API')
logging.basicConfig(level=logging.INFO)

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

MONGO_URL = os.getenv('MONGO_URL', 'mongodb://localhost:27017')
DB_NAME = os.getenv('DB_NAME', 'sophii_terminal')
EMERGENT_LLM_KEY = os.getenv('EMERGENT_LLM_KEY') or os.getenv('UNIVERSAL_LLM_API_KEY')

client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]
cache = db['api_cache']

TTL = {'quote': 300, 'search': 300, 'sparkline': 300, 'chart': 1800, 'summary': 3600, 'peers': 3600, 'analyst': 3600, 'sentiment': 3600}


def clean(v: Any) -> Any:
    if v is None:
        return None
    if isinstance(v, dict):
        return {k: clean(val) for k, val in v.items() if k != '_id'}
    if isinstance(v, list):
        return [clean(x) for x in v]
    if isinstance(v, np.generic):
        return clean(v.item())
    if isinstance(v, (pd.Timestamp, datetime)):
        return v.isoformat()
    if isinstance(v, float):
        return None if (math.isnan(v) or math.isinf(v)) else float(v)
    if isinstance(v, (int, str, bool)):
        return v
    return str(v)


async def get_cache(key: str):
    doc = await cache.find_one({'key': key})
    if not doc:
        return None, None
    return doc.get('value'), doc.get('expires_at')


async def set_cache(key: str, value: Any, ttl: int):
    await cache.update_one(
        {'key': key},
        {'$set': {'key': key, 'value': clean(value), 'expires_at': datetime.now(timezone.utc) + timedelta(seconds=ttl)}},
        upsert=True,
    )


async def cached(name: str, ticker: str, params: dict, builder: Callable[[], Awaitable[Any]], fallback: Any = None):
    key = f'{name}:{ticker}:{json.dumps(params, sort_keys=True)}'
    val, exp = await get_cache(key)
    now = datetime.now(timezone.utc)
    if val is not None and exp and exp > now:
        return val
    try:
        out = clean(await builder())
        await set_cache(key, out, TTL[name])
        return out
    except Exception:
        logging.exception('Refresh failed for %s', key)
        if val is not None:
            return val
        return fallback


def map_range(r: str) -> str:
    return {'1W': '7d', '1M': '1mo', '3M': '3mo', '1Y': '1y', '5Y': '5y'}.get(r, '1mo')


def safe_ticker(t: str) -> str:
    v = (t or '').strip().upper()
    if not v or len(v) > 12 or not all(ch.isalnum() or ch in '.-' for ch in v):
        raise ValueError('Invalid ticker format')
    return v


@app.get('/api/health')
async def health():
    return {'status': 'ok'}


@app.get('/api/stock/search')
async def search(q: str = Query('')):
    async def build():
        query = (q or '').strip().upper()
        if not query:
            return []
        candidates = [query]
        common = ['AAPL', 'MSFT', 'NVDA', 'AMZN', 'GOOGL', 'META', 'TSLA', 'AVGO', 'JPM', 'V', 'MA', 'NFLX', 'AMD', 'COST', 'ORCL']
        candidates.extend([s for s in common if query in s][:6])
        seen = set()
        results = []
        for c in candidates:
            if c in seen:
                continue
            seen.add(c)
            info = yf.Ticker(c).info or {}
            name = info.get('longName') or info.get('shortName')
            if name and (query in c or query.lower() in name.lower()):
                results.append({'symbol': c, 'name': name, 'exchange': info.get('exchange')})
            if len(results) >= 8:
                break
        return results

    return await cached('search', q, {'q': q}, build, [])


@app.get('/api/stock/{t}')
async def stock(t: str):
    try:
        ticker = safe_ticker(t)
    except ValueError:
        return JSONResponse(status_code=400, content={'error': 'Invalid ticker'})

    async def build():
        info = yf.Ticker(ticker).info or {}
        p = info.get('currentPrice') or info.get('regularMarketPrice')
        pc = info.get('previousClose')
        c = ((p - pc) / pc * 100) if p and pc else None
        return {
            'ticker': ticker, 'name': info.get('longName') or info.get('shortName'), 'price': p, 'prev_close': pc, 'change_pct': c,
            'mkt_cap': info.get('marketCap'), 'pe_trailing': info.get('trailingPE'), 'pe_forward': info.get('forwardPE'), 'eps_trailing': info.get('trailingEps'), 'eps_forward': info.get('forwardEps'),
            'revenue': info.get('totalRevenue'), 'revenue_growth_yoy': (info.get('revenueGrowth') * 100 if info.get('revenueGrowth') is not None else None),
            'gross_margin': (info.get('grossMargins') * 100 if info.get('grossMargins') is not None else None), 'operating_margin': (info.get('operatingMargins') * 100 if info.get('operatingMargins') is not None else None),
            'profit_margin': (info.get('profitMargins') * 100 if info.get('profitMargins') is not None else None), 'debt_to_equity': info.get('debtToEquity'), 'fcf': info.get('freeCashflow'),
            'week52_low': info.get('fiftyTwoWeekLow'), 'week52_high': info.get('fiftyTwoWeekHigh'), 'beta': info.get('beta'), 'dividend': info.get('dividendRate'), 'volume': info.get('volume'),
            'sector': info.get('sector'), 'industry': info.get('industry'), 'exchange': info.get('exchange'), 'summary': info.get('longBusinessSummary'),
        }

    data = await cached('summary', ticker, {}, build, {})
    return data if data.get('ticker') else JSONResponse(status_code=404, content={'error': 'Ticker not found'})

@app.get('/api/stock/{t}/quote')
async def quote(t: str):
    try:
        ticker = safe_ticker(t)
    except ValueError:
        return {'ticker': (t or '').upper(), 'price': None, 'change_pct': None, 'pe_trailing': None}

    async def build():
        info = yf.Ticker(ticker).info or {}
        p = info.get('currentPrice') or info.get('regularMarketPrice')
        pc = info.get('previousClose')
        return {'ticker': ticker, 'price': p, 'change_pct': ((p - pc) / pc * 100 if p and pc else None), 'pe_trailing': info.get('trailingPE')}

    return await cached('quote', ticker, {}, build, {'ticker': ticker, 'price': None, 'change_pct': None, 'pe_trailing': None})


@app.get('/api/stock/{t}/chart')
async def chart(t: str, range: str = '1M'):
    ticker = safe_ticker(t)

    async def build():
        h = yf.Ticker(ticker).history(period=map_range(range), interval='1d')
        if h is None or h.empty:
            return []
        return [{'t': idx.isoformat(), 'c': r.get('Close'), 'o': r.get('Open'), 'h': r.get('High'), 'l': r.get('Low'), 'v': r.get('Volume')} for idx, r in h.iterrows()]

    return await cached('chart', ticker, {'range': range}, build, [])


@app.get('/api/stock/{t}/sparkline')
async def spark(t: str):
    ticker = safe_ticker(t)

    async def build():
        h = yf.Ticker(ticker).history(period='2mo', interval='1d').tail(30)
        return [{'t': idx.date().isoformat(), 'c': r.get('Close')} for idx, r in h.iterrows()] if h is not None else []

    return await cached('sparkline', ticker, {}, build, [])


@app.get('/api/stock/{t}/peers')
async def peers(t: str):
    ticker = safe_ticker(t)
    peer_map = {'AAPL': ['MSFT', 'GOOGL', 'AMZN', 'META', 'NVDA'], 'MSFT': ['AAPL', 'GOOGL', 'AMZN', 'ORCL', 'NVDA'], 'NVDA': ['AMD', 'AVGO', 'TSM', 'INTC', 'MSFT']}

    async def build():
        out = []
        for s in peer_map.get(ticker, []):
            i = yf.Ticker(s).info or {}
            p = i.get('currentPrice') or i.get('regularMarketPrice')
            pc = i.get('previousClose')
            out.append({'ticker': s, 'name': i.get('longName') or s, 'price': p, 'change_pct': ((p - pc) / pc * 100 if p and pc else None), 'pe_trailing': i.get('trailingPE'), 'mkt_cap': i.get('marketCap')})
        return out

    return await cached('peers', ticker, {}, build, [])

@app.get('/api/stock/{t}/analyst')
async def analyst(t: str):
    ticker = safe_ticker(t)

    async def build():
        i = yf.Ticker(ticker).info or {}
        cur = i.get('currentPrice') or i.get('regularMarketPrice')
        tm = i.get('targetMeanPrice')
        rec = i.get('recommendationKey')
        rec = rec.upper() if isinstance(rec, str) else None
        if rec and rec not in ['BUY', 'HOLD', 'SELL']:
            rec = 'HOLD'
        return {'recommendation': rec, 'num_analysts': i.get('numberOfAnalystOpinions'), 'target_low': i.get('targetLowPrice'), 'target_mean': tm, 'target_high': i.get('targetHighPrice'), 'current': cur, 'implied_upside_pct': ((tm - cur) / cur * 100 if tm and cur else None)}

    return await cached('analyst', ticker, {}, build, {'recommendation': None, 'num_analysts': None, 'target_low': None, 'target_mean': None, 'target_high': None, 'current': None, 'implied_upside_pct': None})


@app.get('/api/stock/{t}/sentiment')
async def sentiment(t: str):
    ticker = safe_ticker(t)
    fallback = {'bullish': 0, 'neutral': 100, 'bearish': 0, 'rationale': 'No reliable recent news sentiment was available, so this is treated as neutral.', 'headlines': []}

    async def build():
        news = (yf.Ticker(ticker).news or [])[:5]
        if not news:
            return fallback
        heads = [{'title': n.get('title'), 'url': n.get('link') or n.get('url')} for n in news if n.get('title')]
        if not EMERGENT_LLM_KEY:
            return {**fallback, 'headlines': heads}
        prompt = f"Return compact JSON with bullish/neutral/bearish integers summing to 100 and one-sentence beginner rationale for: {heads}"
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.post('https://api.emergent.sh/v1/chat/completions', headers={'Authorization': f'Bearer {EMERGENT_LLM_KEY}'}, json={'model': 'claude-sonnet-4-5', 'messages': [{'role': 'user', 'content': prompt}]})
            r.raise_for_status()
            txt = r.json()['choices'][0]['message']['content']
        data = json.loads(txt)
        total = max(1, int(data.get('bullish', 0)) + int(data.get('neutral', 0)) + int(data.get('bearish', 0)))
        b, n, br = [int(round(int(data.get(k, 0)) * 100 / total)) for k in ['bullish', 'neutral', 'bearish']]
        n += 100 - (b + n + br)
        return {'bullish': b, 'neutral': n, 'bearish': br, 'rationale': str(data.get('rationale') or fallback['rationale']).split('.')[0] + '.', 'headlines': heads[:5]}

    return await cached('sentiment', ticker, {}, build, fallback)


@app.get('/api/watchlist/summary')
async def watchlist_summary(tickers: str = ''):
    symbols = [x.strip().upper() for x in tickers.split(',') if x.strip()][:30]
    out = []
    for t in symbols:
        q = await quote(t)
        sp = await spark(t)
        out.append({**q, 'sparkline': sp})
    return clean(out)
