import {
  ClockCircleOutlined,
  CloseCircleOutlined,
  FileTextOutlined,
  LikeOutlined,
} from '@ant-design/icons';
import { Skeleton } from 'antd';

import type { RunStats } from '../types';

interface Props {
  stats: RunStats | null;
  loading: boolean;
  onSelect: (key: keyof RunStats) => void;
}

const CARDS: Array<{
  key: keyof RunStats;
  label: string;
  sub: string;
  color: string;
  icon: React.ReactNode;
}> = [
  {
    key: 'total',
    label: '总简历数',
    sub: '累计接收',
    color: '#2563eb',
    icon: <FileTextOutlined />,
  },
  {
    key: 'recommend',
    label: '推荐简历',
    sub: '推荐 + 备选',
    color: '#16a34a',
    icon: <LikeOutlined />,
  },
  {
    key: 'pending',
    label: '待复核简历',
    sub: '需人工确认',
    color: '#f59e0b',
    icon: <ClockCircleOutlined />,
  },
  {
    key: 'reject',
    label: '暂不推进',
    sub: '未通过筛选',
    color: '#ef4444',
    icon: <CloseCircleOutlined />,
  },
];

export default function StatsCards({ stats, loading, onSelect }: Props) {
  return (
    <div className="is-stat-grid">
      {CARDS.map((card) => (
        <div
          className="is-stat-card"
          key={card.key}
          onClick={() => onSelect(card.key)}
        >
          <div className="is-stat-head">
            <span>{card.label}</span>
            <span className="is-stat-icon" style={{ color: card.color }}>
              {card.icon}
            </span>
          </div>
          {loading || stats === null ? (
            <Skeleton.Input active size="small" style={{ width: 64 }} />
          ) : (
            <div className="is-stat-value" style={{ color: card.color }}>
              {stats[card.key]}
            </div>
          )}
          <div className="is-stat-sub">{card.sub}</div>
        </div>
      ))}
    </div>
  );
}
