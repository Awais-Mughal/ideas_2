export const na = (v) => (v == null || Number.isNaN(v) ? 'N/A' : v);
export const formatCurrency = (v) => (na(v) === 'N/A' ? 'N/A' : `$${Number(v).toLocaleString(undefined, { maximumFractionDigits: 2 })}`);
export const formatLargeNumber = (v) => {
  if (na(v) === 'N/A') return 'N/A';
  const n = Math.abs(v);
  if (n >= 1e12) return `${(v / 1e12).toFixed(2)}T`;
  if (n >= 1e9) return `${(v / 1e9).toFixed(2)}B`;
  if (n >= 1e6) return `${(v / 1e6).toFixed(2)}M`;
  return `${v}`;
};
export const formatPercent = (v) => (na(v) === 'N/A' ? 'N/A' : `${Number(v).toFixed(2)}%`);
export const formatRatio = (v) => (na(v) === 'N/A' ? 'N/A' : Number(v).toFixed(2));
export const formatDate = (v) => (v ? new Date(v).toLocaleDateString() : 'N/A');
export const formatMetricValue = (k, v) => (k.includes('margin') || k.includes('growth') || k.includes('pct') ? formatPercent(v) : (k.includes('cap') || k === 'revenue' || k === 'fcf' || k === 'volume' ? formatLargeNumber(v) : v));
export const getPositiveNegativeClass = (v) => (v > 0 ? 'text-[#006F4A]' : (v < 0 ? 'text-[#B5577A]' : 'text-[#0A0A0A]'));

export function getHealthBadge(metric, value) {
  if (value == null) return 'NEUTRAL';
  if (metric === 'revenue_growth_yoy') return value > 10 ? 'LOOKS HEALTHY' : value < 0 ? 'POTENTIAL CONCERN' : 'NEUTRAL';
  if (metric === 'gross_margin') return value > 40 ? 'LOOKS HEALTHY' : value < 20 ? 'POTENTIAL CONCERN' : 'NEUTRAL';
  if (metric === 'operating_margin') return value > 20 ? 'LOOKS HEALTHY' : value < 5 ? 'POTENTIAL CONCERN' : 'NEUTRAL';
  if (metric === 'profit_margin') return value > 15 ? 'LOOKS HEALTHY' : value < 0 ? 'POTENTIAL CONCERN' : 'NEUTRAL';
  if (metric === 'debt_to_equity') return value < 1 ? 'LOOKS HEALTHY' : value > 2 ? 'POTENTIAL CONCERN' : 'NEUTRAL';
  if (metric === 'fcf') return value > 0 ? 'LOOKS HEALTHY' : value < 0 ? 'POTENTIAL CONCERN' : 'NEUTRAL';
  if (metric.includes('pe')) return value < 0 || value > 60 ? 'POTENTIAL CONCERN' : 'NEUTRAL';
  return 'NEUTRAL';
}
