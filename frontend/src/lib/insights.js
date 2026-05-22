export function linearRegressionSlope(values) {
  if (!values || values.length < 2) return null;
  const n = values.length;
  const xs = [...Array(n)].map((_, i) => i + 1);
  const sumX = xs.reduce((a, b) => a + b, 0);
  const sumY = values.reduce((a, b) => a + b, 0);
  const sumXY = xs.reduce((a, x, i) => a + x * values[i], 0);
  const sumXX = xs.reduce((a, x) => a + x * x, 0);
  const denom = n * sumXX - sumX * sumX;
  if (!denom) return null;
  return (n * sumXY - sumX * sumY) / denom;
}

export function movingAverage(values, period) {
  if (!values || values.length < period) return null;
  const slice = values.slice(values.length - period);
  return slice.reduce((a, b) => a + b, 0) / period;
}

export function stdDevDailyReturns(values) {
  if (!values || values.length < 3) return null;
  const returns = [];
  for (let i = 1; i < values.length; i += 1) {
    if (values[i - 1] > 0) returns.push((values[i] - values[i - 1]) / values[i - 1]);
  }
  if (!returns.length) return null;
  const mean = returns.reduce((a, b) => a + b, 0) / returns.length;
  const variance = returns.reduce((a, r) => a + (r - mean) ** 2, 0) / returns.length;
  return Math.sqrt(variance) * 100;
}

export function computeInsights(points) {
  const closes = (points || []).map((p) => p.c).filter((v) => typeof v === 'number');
  if (closes.length < 5) return [];
  const slope = linearRegressionSlope(closes);
  const ma20 = movingAverage(closes, 20);
  const ma50 = movingAverage(closes, 50);
  const last = closes[closes.length - 1];
  const mid = Math.floor(closes.length / 2);
  const firstHalf = closes.slice(0, mid);
  const secondHalf = closes.slice(mid);
  const firstHigh = Math.max(...firstHalf), secondHigh = Math.max(...secondHalf);
  const firstLow = Math.min(...firstHalf), secondLow = Math.min(...secondHalf);
  const high = Math.max(...closes), low = Math.min(...closes);
  const rangePos = high === low ? null : ((last - low) / (high - low)) * 100;
  const vol = stdDevDailyReturns(closes);
  const prior = closes.slice(0, -1);
  const priorHigh = prior.length ? Math.max(...prior) : null;
  const priorLow = prior.length ? Math.min(...prior) : null;

  return [
    {
      key: 'trend', label: 'Trend',
      signal: slope == null ? 'INFO' : slope > 0 ? 'BULLISH' : slope < 0 ? 'BEARISH' : 'NEUTRAL',
      text: slope == null ? 'Not enough data for trend slope.' : `Slope is ${slope.toFixed(4)}, which may suggest ${slope > 0 ? 'upward' : 'downward'} drift.`
    },
    {
      key: 'ma', label: 'Moving Averages',
      signal: ma20 == null || ma50 == null ? 'INFO' : (ma20 > ma50 && last > ma20 ? 'BULLISH' : ma20 < ma50 && last < ma20 ? 'BEARISH' : 'NEUTRAL'),
      text: ma20 == null || ma50 == null ? 'Need more data for MA20/MA50.' : `MA20 ${ma20.toFixed(2)} vs MA50 ${ma50.toFixed(2)}; this is often read as momentum context.`
    },
    {
      key: 'highlow', label: 'High/Low Structure',
      signal: secondHigh > firstHigh && secondLow > firstLow ? 'BULLISH' : secondHigh < firstHigh && secondLow < firstLow ? 'BEARISH' : 'NEUTRAL',
      text: `First-half high/low ${firstHigh.toFixed(2)}/${firstLow.toFixed(2)} vs second-half ${secondHigh.toFixed(2)}/${secondLow.toFixed(2)}.`
    },
    {
      key: 'range', label: 'Range Position', signal: 'INFO',
      text: rangePos == null ? 'Range position unavailable.' : `Latest close is at ${rangePos.toFixed(1)}% of this period range.`
    },
    {
      key: 'vol', label: 'Volatility', signal: 'INFO',
      text: vol == null ? 'Volatility unavailable.' : `Std. dev. of daily returns is ${vol.toFixed(2)}%, which could indicate typical movement size.`
    },
    {
      key: 'breakout', label: 'Breakout Check',
      signal: priorHigh == null ? 'INFO' : last > priorHigh ? 'BULLISH' : last < priorLow ? 'BEARISH' : 'NEUTRAL',
      text: priorHigh == null ? 'Breakout check unavailable.' : last > priorHigh ? `Latest close is above prior high (${priorHigh.toFixed(2)}).` : last < priorLow ? `Latest close is below prior low (${priorLow.toFixed(2)}).` : 'Latest close remains inside prior range.'
    }
  ];
}
