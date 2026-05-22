import os, math, json, logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
import numpy as np
import pandas as pd
import yfinance as yf
import httpx
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from motor.motor_asyncio import AsyncIOMotorClient

app = FastAPI(title="SOPHII.TERMINAL API")
logging.basicConfig(level=logging.INFO)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "sophii_terminal")
EMERGENT_LLM_KEY = os.getenv("EMERGENT_LLM_KEY") or os.getenv("UNIVERSAL_LLM_API_KEY")
client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]
cache = db["api_cache"]

TTL = {"quote":300,"search":300,"sparkline":300,"chart":1800,"summary":3600,"peers":3600,"analyst":3600,"sentiment":3600}


def clean(v: Any):
    if v is None: return None
    if isinstance(v, dict):
        return {k: clean(val) for k,val in v.items() if k != "_id"}
    if isinstance(v, list): return [clean(x) for x in v]
    if isinstance(v, (np.generic,)): return clean(v.item())
    if isinstance(v, (pd.Timestamp, datetime)): return v.isoformat()
    if isinstance(v, float):
        if math.isnan(v) or math.isinf(v): return None
        return float(v)
    if isinstance(v, (int,str,bool)): return v
    return str(v)

async def get_cache(key):
    doc = await cache.find_one({"key": key})
    if not doc: return None, None
    exp = doc.get("expires_at")
    return doc.get("value"), exp

async def set_cache(key, value, ttl):
    await cache.update_one({"key":key},{"$set":{"key":key,"value":clean(value),"expires_at": datetime.now(timezone.utc)+timedelta(seconds=ttl)}},upsert=True)

async def cached(name, ticker, params, builder, fallback=None):
    key = f"{name}:{ticker}:{json.dumps(params, sort_keys=True)}"
    val, exp = await get_cache(key)
    now = datetime.now(timezone.utc)
    if val and exp and exp > now:
        return val
    try:
        out = clean(await builder())
        await set_cache(key, out, TTL[name])
        return out
    except Exception:
        logging.exception("refresh failed")
        if val is not None: return val
        return fallback if fallback is not None else {}


def map_range(r):
    return {"1W":"7d","1M":"1mo","3M":"3mo","1Y":"1y","5Y":"5y"}.get(r, "1mo")

def summary_from_info(t, info):
    p = info.get("currentPrice") or info.get("regularMarketPrice")
    pc = info.get("previousClose")
    c = ((p-pc)/pc*100) if p and pc else None
    return clean({"ticker":t,"name":info.get("longName") or info.get("shortName"),"price":p,"prev_close":pc,"change_pct":c,
    "mkt_cap":info.get("marketCap"),"pe_trailing":info.get("trailingPE"),"pe_forward":info.get("forwardPE"),"eps_trailing":info.get("trailingEps"),"eps_forward":info.get("forwardEps"),
    "revenue":info.get("totalRevenue"),"revenue_growth_yoy":(info.get("revenueGrowth")*100 if info.get("revenueGrowth") is not None else None),"gross_margin":(info.get("grossMargins")*100 if info.get("grossMargins") is not None else None),
    "operating_margin":(info.get("operatingMargins")*100 if info.get("operatingMargins") is not None else None),"profit_margin":(info.get("profitMargins")*100 if info.get("profitMargins") is not None else None),"debt_to_equity":info.get("debtToEquity"),
    "fcf":info.get("freeCashflow"),"week52_low":info.get("fiftyTwoWeekLow"),"week52_high":info.get("fiftyTwoWeekHigh"),"beta":info.get("beta"),"dividend":info.get("dividendRate"),"volume":info.get("volume"),
    "sector":info.get("sector"),"industry":info.get("industry"),"exchange":info.get("exchange"),"summary":info.get("longBusinessSummary")})

@app.get('/api/health')
async def health(): return {"status":"ok"}

@app.get('/api/stock/search')
async def search(q: str = Query("")):
    async def b():
        if not q.strip(): return []
        t = yf.Ticker(q.upper())
        info=t.info or {}
        row={"symbol":q.upper(),"name":info.get("longName") or info.get("shortName") or q.upper(),"exchange":info.get("exchange")}
        return [row]
    return await cached("search", q, {"q":q}, b, [])

@app.get('/api/stock/{t}')
async def stock(t:str):
    async def b(): return summary_from_info(t.upper(), yf.Ticker(t.upper()).info or {})
    data = await cached("summary", t, {}, b, {})
    if not data.get("ticker"): return JSONResponse(status_code=404, content={"error":"Ticker not found"})
    return data

@app.get('/api/stock/{t}/quote')
async def quote(t:str):
    async def b():
        info=yf.Ticker(t.upper()).info or {}
        p=info.get("currentPrice") or info.get("regularMarketPrice")
        pc=info.get("previousClose")
        return {"ticker":t.upper(),"price":p,"change_pct":((p-pc)/pc*100 if p and pc else None),"pe_trailing":info.get("trailingPE")}
    return await cached("quote", t, {}, b, {"ticker":t.upper(),"price":None,"change_pct":None,"pe_trailing":None})

@app.get('/api/stock/{t}/chart')
async def chart(t:str, range: str = "1M"):
    async def b():
        h=yf.Ticker(t.upper()).history(period=map_range(range), interval="1d")
        if h is None or h.empty: return []
        return [{"t":idx.isoformat(),"c":r.get("Close"),"o":r.get("Open"),"h":r.get("High"),"l":r.get("Low"),"v":r.get("Volume")} for idx,r in h.iterrows()]
    return await cached("chart", t, {"range":range}, b, [])

@app.get('/api/stock/{t}/sparkline')
async def spark(t:str):
    async def b():
        h=yf.Ticker(t.upper()).history(period="2mo", interval="1d").tail(30)
        return [{"t":idx.date().isoformat(),"c":r.get("Close")} for idx,r in h.iterrows()] if h is not None else []
    return await cached("sparkline", t, {}, b, [])

peer_map={"AAPL":["MSFT","GOOGL","AMZN","META","NVDA"],"MSFT":["AAPL","GOOGL","AMZN","ORCL","NVDA"],"NVDA":["AMD","AVGO","TSM","INTC","MSFT"]}
@app.get('/api/stock/{t}/peers')
async def peers(t:str):
    async def b():
        syms=peer_map.get(t.upper(),[])
        out=[]
        for s in syms:
            i=yf.Ticker(s).info or {}
            p=i.get("currentPrice") or i.get("regularMarketPrice")
            pc=i.get("previousClose")
            out.append({"ticker":s,"name":i.get("longName") or s,"price":p,"change_pct":((p-pc)/pc*100 if p and pc else None),"pe_trailing":i.get("trailingPE"),"mkt_cap":i.get("marketCap")})
        return out
    return await cached("peers", t, {}, b, [])

@app.get('/api/stock/{t}/analyst')
async def analyst(t:str):
    async def b():
        i=yf.Ticker(t.upper()).info or {}
        cur=i.get("currentPrice") or i.get("regularMarketPrice")
        tm=i.get("targetMeanPrice")
        rec=i.get("recommendationKey")
        rec = rec.upper() if isinstance(rec,str) else None
        if rec and rec not in ["BUY","HOLD","SELL"]: rec="HOLD"
        return {"recommendation":rec,"num_analysts":i.get("numberOfAnalystOpinions"),"target_low":i.get("targetLowPrice"),"target_mean":tm,"target_high":i.get("targetHighPrice"),"current":cur,"implied_upside_pct":((tm-cur)/cur*100 if tm and cur else None)}
    return await cached("analyst", t, {}, b, {"recommendation":None,"num_analysts":None,"target_low":None,"target_mean":None,"target_high":None,"current":None,"implied_upside_pct":None})

@app.get('/api/stock/{t}/sentiment')
async def sentiment(t:str):
    fallback={"bullish":0,"neutral":100,"bearish":0,"rationale":"No reliable recent news sentiment was available, so this is treated as neutral.","headlines":[]}
    async def b():
        news=(yf.Ticker(t.upper()).news or [])[:5]
        if not news: return fallback
        heads=[{"title":n.get("title"),"url":n.get("link") or n.get("url")} for n in news if n.get("title")]
        if not EMERGENT_LLM_KEY: return {**fallback,"headlines":heads}
        prompt=f"Return JSON with bullish,neutral,bearish integers adding to 100 and one-sentence rationale for headlines: {heads}"
        async with httpx.AsyncClient(timeout=15) as c:
            r=await c.post("https://api.emergent.sh/v1/chat/completions",headers={"Authorization":f"Bearer {EMERGENT_LLM_KEY}"},json={"model":"claude-sonnet-4-5","messages":[{"role":"user","content":prompt}]})
            r.raise_for_status(); txt=r.json()["choices"][0]["message"]["content"]
        data=json.loads(txt)
        total=max(1,int(data.get("bullish",0))+int(data.get("neutral",0))+int(data.get("bearish",0)))
        b_,n_,be=[int(round(int(data.get(k,0))*100/total)) for k in ["bullish","neutral","bearish"]]
        n_ += 100-(b_+n_+be)
        return {"bullish":b_,"neutral":n_,"bearish":be,"rationale":str(data.get("rationale") or fallback["rationale"]).split(".")[0]+".","headlines":heads[:5]}
    return await cached("sentiment", t, {}, b, fallback)

@app.get('/api/watchlist/summary')
async def watchlist_summary(tickers:str=""):
    out=[]
    for t in [x.strip().upper() for x in tickers.split(',') if x.strip()][:30]:
        q=await quote(t)
        sp=await spark(t)
        out.append({**q,"sparkline":sp})
    return out
