import React, { useEffect, useMemo, useState } from 'react';
import * as Pop from '@radix-ui/react-popover';
import { AreaChart, Area, ResponsiveContainer, Tooltip } from 'recharts';
import { Info, TriangleAlert, ExternalLink, Loader2 } from 'lucide-react';
import { computeInsights } from './lib/insights';
import { Toaster, toast } from 'sonner';
import api from './lib/api';
import { formatCurrency, formatLargeNumber, formatPercent, getPositiveNegativeClass, getHealthBadge } from './lib/format';

const TAPE = ['AAPL','MSFT','NVDA','AMZN','GOOGL','META','TSLA','AVGO','JPM','V','MA','NFLX','AMD','COST','ORCL'];

function SectionState({ type, msg }) {
  if (type === 'loading') return <div data-testid='loading-state' className='border p-3 flex gap-2 items-center'><Loader2 size={14} className='animate-spin'/>Loading…</div>;
  if (type === 'error') return <div data-testid='error-state' className='border p-3'>Unable to load this section. {msg || ''}</div>;
  return null;
}

export default function App() {
  const [ticker, setTicker] = useState('AAPL');
  const [sum, setSum] = useState(null);
  const [chart, setChart] = useState([]);
  const [range, setRange] = useState('1M');
  const [q, setQ] = useState('');
  const [res, setRes] = useState([]);
  const [watch, setWatch] = useState(JSON.parse(localStorage.getItem('sophii_watchlist_v1') || '[]'));
  const [sent, setSent] = useState(null);
  const [analyst, setAnalyst] = useState(null);
  const [peers, setPeers] = useState([]);
  const [status, setStatus] = useState('loading');
  const insights = computeInsights(chart);

  useEffect(() => localStorage.setItem('sophii_watchlist_v1', JSON.stringify(watch)), [watch]);

  useEffect(() => {
    (async () => {
      setStatus('loading');
      try {
        const [s, c, se, a, p] = await Promise.all([api.stock(ticker), api.chart(ticker, range), api.sentiment(ticker), api.analyst(ticker), api.peers(ticker)]);
        setSum(s); setChart(c); setSent(se); setAnalyst(a); setPeers(p);
        setStatus('ready');
      } catch {
        setStatus('error');
      }
    })();
  }, [ticker, range]);

  useEffect(() => {
    const t = setTimeout(async () => {
      try { setRes(q ? await api.search(q) : []); } catch { setRes([]); }
    }, 250);
    return () => clearTimeout(t);
  }, [q]);

  const watchHas = watch.includes(ticker);
  const tapeData = useMemo(() => TAPE.map((t) => ({ ticker: t })), []);

  return <div data-testid='app-root' className='p-4'>
    <Toaster />
    <div data-testid='market-tape' className='bg-black text-white p-2 overflow-x-auto whitespace-nowrap'>
      <span className='bg-[#0000FE] px-2 mr-3'>LIVE TAPE</span>{tapeData.map((t) => <Tape key={t.ticker} t={t.ticker} />)}
    </div>

    <div className='grid grid-cols-12 gap-4 mt-4'>
      <main className='col-span-12 lg:col-span-9 space-y-4'>
        <header className='border p-3'>
          <div className='flex items-center justify-between'><div className='flex gap-2 items-center'><div className='bg-[#0000FE] text-white px-2'>S</div><strong>SOPHII.TERMINAL</strong></div><div className='mono text-xs'>SESSION LIVE</div></div>
          <input data-testid='header-search' className='border w-full p-2 mt-2' value={q} onChange={(e) => setQ(e.target.value)} placeholder='Search ticker or company' />
          {res.map((r) => <button data-testid='search-result' key={r.symbol} onClick={() => { setTicker(r.symbol); setQ(''); setRes([]); }} className='block w-full text-left border p-2 hover:bg-[#0000FE] hover:text-white'>{r.symbol} {r.name}</button>)}
        </header>

        {status !== 'ready' ? <SectionState type={status} /> : <>
          <section data-testid='stock-header' className='border p-4'><div className='mono text-5xl'>{formatCurrency(sum?.price)}</div><div className={getPositiveNegativeClass(sum?.change_pct)}>{formatPercent(sum?.change_pct)}</div><div className='grid grid-cols-2 md:grid-cols-3 gap-2 text-sm mt-2'><div>Market cap {formatLargeNumber(sum?.mkt_cap)}</div><div>Volume {formatLargeNumber(sum?.volume)}</div><div>Prev close {formatCurrency(sum?.prev_close)}</div></div><button data-testid={watchHas ? 'remove-watchlist-button' : 'add-watchlist-button'} onClick={() => { if (watchHas) { setWatch(watch.filter((x) => x !== ticker)); toast('Removed from watchlist'); } else { setWatch([...watch, ticker]); toast('Added to watchlist'); } }} className='bg-[#D1D1FF] text-[#0000FE] px-3 py-2 mt-3'>{watchHas ? 'Remove' : 'Add'} Watchlist</button></section>
          <section data-testid='price-chart' className='border p-4'><div>{['1W','1M','3M','1Y','5Y'].map((r) => <button data-testid='chart-range-tab' key={r} onClick={() => setRange(r)} className={`border px-2 py-1 mr-2 ${range === r ? 'bg-[#0000FE] text-white' : ''}`}>{r}</button>)}</div><div style={{ height: 300 }}>{chart?.length ? <ResponsiveContainer><AreaChart data={chart}><Tooltip /><Area type='monotone' dataKey='c' stroke='#0000FE' fillOpacity={0.12} fill='#0000FE' /></AreaChart></ResponsiveContainer> : <div className='p-3'>No chart data available.</div>}</div></section>
          <section data-testid='chart-insights' className='border p-3'><h3>Chart Patterns · Beginner Read</h3>{insights.length?insights.map((it)=><Insight key={it.key} title={it.label} text={it.text} signal={it.signal}/>):<div>No insight data available.</div>}</section>
          <section data-testid='buy-verdict' className='border p-3'><h3>Beginner’s Verdict <span className='text-xs bg-[#D1D1FF] px-2'>Educational · not advice</span></h3><div>Mixed profile of signals. Educational only.</div></section>
          <section data-testid='metrics-grid' className='grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-2'>{['pe_trailing','pe_forward','revenue','debt_to_equity'].map((k) => <Pop.Root key={k}><Pop.Trigger data-testid='metric-tile' className='border p-2 text-left'><div className='uppercase text-xs'>{k} <Info size={12} /></div><div className='mono'>{String(sum?.[k] ?? 'N/A')}</div><div className='text-xs'>{getHealthBadge(k, sum?.[k])}</div></Pop.Trigger><Pop.Portal><Pop.Content data-testid='metric-popover' className='border-2 border-black bg-white p-3'>WHAT IT IS · HOW TO READ IT · FOR THIS STOCK</Pop.Content></Pop.Portal></Pop.Root>)}</section>
          <section data-testid='peer-table' className='border p-3 overflow-auto'><table className='w-full text-sm'><tbody>{peers.map((p) => <tr key={p.ticker} className={p.ticker === ticker ? 'bg-[#0000FE] text-white' : ''}><td>{p.ticker}</td><td>{p.name}</td><td className='mono'>{formatCurrency(p.price)}</td></tr>)}</tbody></table></section>
          <section className='border p-3'><h3>About</h3><p>{sum?.summary || 'N/A'}</p></section>
        </>}
        <section data-testid='disclaimer' className='bg-[#D1D1FF] p-3 border'><TriangleAlert size={14} /> Not Financial Advice — educational tool, data may be delayed, AI sentiment is an estimate, do your own research, consult a licensed advisor, past performance does not guarantee future results.</section>
      </main>
      <aside className='col-span-12 lg:col-span-3 lg:sticky lg:top-4 lg:z-30 space-y-4'>
        <section data-testid='watchlist' className='border p-3'>{watch.length === 0 ? 'No stocks saved yet. Search a ticker and add it to your watchlist.' : watch.map((w) => <div key={w} className='flex justify-between border-b py-1'><button onClick={() => setTicker(w)}>{w}</button><button data-testid='remove-watchlist-button' onClick={() => setWatch(watch.filter((x) => x !== w))}>x</button></div>)}</section>
        <section data-testid='street-pulse' className='border p-3'><div>{sent ? `${sent.bullish}/${sent.neutral}/${sent.bearish}` : 'N/A'}</div><div>{sent?.rationale}</div>{sent?.headlines?.slice(0,5).map((h) => <a key={h.url || h.title} href={h.url} className='flex gap-1'>{h.title}<ExternalLink size={12} /></a>)}</section>
        <section data-testid='analyst-ratings' className='border p-3'><div>{analyst?.recommendation || 'N/A'}</div><div>{formatPercent(analyst?.implied_upside_pct)}</div></section>
      </aside>
    </div>
    <footer className='mt-6 border-t pt-3 text-sm'>Educational only · Not financial advice</footer>
  </div>;
}

function Tape({ t }) { const [d, setD] = useState(null); useEffect(() => { api.quote(t).then(setD).catch(() => setD({ ticker: t, price: null, change_pct: null })); }, [t]); return <span className='mr-3 mono'>{t} {d ? formatCurrency(d.price) : '...'} <span className={getPositiveNegativeClass(d?.change_pct)}>{d ? formatPercent(d.change_pct) : ''}</span></span>; }
function Insight({ title, text, signal }) { return <Pop.Root><Pop.Trigger data-testid='chart-insight-row' className='border p-2 w-full text-left'><div className='flex justify-between'><span>{title}</span><span>{signal}</span></div><div>{text}</div></Pop.Trigger><Pop.Portal><Pop.Content data-testid='chart-insight-popover' className='border-2 border-black bg-white p-3'><div>WHAT IT IS</div><div>HOW TRADERS READ IT</div><div>FOR THIS STOCK</div></Pop.Content></Pop.Portal></Pop.Root>; }
