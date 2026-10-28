import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type { Reading } from './api';

export default function EnergyChart({
  readings,
  timezone,
}: {
  readings: Reading[];
  timezone: string;
}) {
  const data = readings.map((r) => ({
    timestamp: new Date(r.timestamp).getTime(),
    kwh: r.kwh === null ? null : Number(r.kwh),
  }));
  const date = (n: number) =>
    new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short', timeZone: timezone }).format(
      n,
    );
  return (
    <div
      className="energy-chart"
      role="img"
      aria-label="Cumulative kWh register readings over time"
    >
      <ResponsiveContainer width="100%" height={290}>
        <LineChart
          data={data}
          margin={{ top: 20, right: 18, left: 6, bottom: 0 }}
          accessibilityLayer
        >
          <CartesianGrid stroke="#e7ebe5" vertical={false} strokeDasharray="3 4" />
          <XAxis
            dataKey="timestamp"
            type="number"
            domain={['dataMin', 'dataMax']}
            tickFormatter={date}
            tickLine={false}
            axisLine={false}
            tick={{ fill: '#7d887f', fontSize: 11 }}
            minTickGap={48}
          />
          <YAxis
            domain={['auto', 'auto']}
            tickFormatter={(n: number) => n.toLocaleString('en-IN')}
            tickLine={false}
            axisLine={false}
            width={66}
            tick={{ fill: '#7d887f', fontSize: 11 }}
          />
          <Tooltip
            labelFormatter={(value) =>
              new Intl.DateTimeFormat('en-GB', {
                dateStyle: 'medium',
                timeStyle: 'short',
                timeZone: timezone,
              }).format(Number(value))
            }
            formatter={(value) => [
              `${Number(value).toLocaleString('en-IN', { maximumFractionDigits: 3 })} kWh`,
              'Register',
            ]}
            contentStyle={{ borderRadius: 10, border: '1px solid #dfe5dc', fontSize: 12 }}
          />
          <Line
            type="linear"
            dataKey="kwh"
            stroke="#2c765a"
            strokeWidth={2.4}
            dot={false}
            connectNulls={false}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
