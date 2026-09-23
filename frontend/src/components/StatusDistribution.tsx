import { Card, Skeleton } from 'antd';

import type { RunStats } from '../types';

interface Props {
  stats: RunStats | null;
  loading: boolean;
}

const ROWS: Array<{ key: keyof RunStats; label: string; color: string }> = [
  { key: 'recommend', label: '推荐简历', color: '#16a34a' },
  { key: 'pending', label: '待复核简历', color: '#f59e0b' },
  { key: 'reject', label: '暂不推进', color: '#ef4444' },
];

export default function StatusDistribution({ stats, loading }: Props) {
  const total = stats?.total ?? 0;
  const base = Math.max(total, 1);

  return (
    <Card className="is-card" title="状态分布" variant="borderless">
      {ROWS.map((row) => {
        const count = stats?.[row.key] ?? 0;
        return (
          <div className="is-dist-row" key={row.key}>
            <span className="is-dist-label">{row.label}</span>
            <span className="is-dist-track">
              <span
                className="is-dist-bar"
                style={{
                  width: `${(count / base) * 100}%`,
                  background: row.color,
                }}
              />
            </span>
            <span className="is-dist-count">
              {loading || stats === null ? (
                <Skeleton.Input active size="small" style={{ width: 28 }} />
              ) : (
                count
              )}
            </span>
          </div>
        );
      })}
    </Card>
  );
}
