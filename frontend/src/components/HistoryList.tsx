import { DeleteOutlined } from '@ant-design/icons';
import { Button, Empty, Popconfirm, Spin, Tag } from 'antd';

import type { RunRecord } from '../types';

const RATING_COLOR: Record<string, string> = {
  推荐进入笔试: 'green',
  备选: 'blue',
  暂不推进: 'red',
  待人工复核: 'orange',
};

interface Props {
  records: RunRecord[];
  loading: boolean;
  activeThreadId?: string;
  deletable?: boolean;
  onSelect: (record: RunRecord) => void;
  onDelete?: (threadId: string) => void;
}

export default function HistoryList({
  records,
  loading,
  activeThreadId,
  deletable,
  onSelect,
  onDelete,
}: Props) {
  if (loading && records.length === 0) {
    return (
      <div className="is-empty">
        <Spin />
      </div>
    );
  }

  if (records.length === 0) {
    return <Empty description="暂无记录" image={Empty.PRESENTED_IMAGE_SIMPLE} />;
  }

  return (
    <>
      {records.map((record) => (
        <div
          className="is-history-item"
          key={record.thread_id}
          onClick={() => onSelect(record)}
          style={
            record.thread_id === activeThreadId
              ? { borderColor: '#93b4ff', background: '#f4f8ff' }
              : undefined
          }
        >
          <div className="is-history-meta">
            <span style={{ fontWeight: 550 }}>
              {record.candidate_name || record.candidate_id}
            </span>
            <Tag
              color={record.rating ? RATING_COLOR[record.rating] ?? 'default' : 'default'}
            >
              {record.rating ?? '待复核'}
            </Tag>
            {deletable && onDelete && (
              <Popconfirm
                title="确定删除这条记录？"
                description="删除后不可恢复。"
                okText="删除"
                okButtonProps={{ danger: true }}
                cancelText="取消"
                onConfirm={(e) => {
                  e?.stopPropagation();
                  onDelete(record.thread_id);
                }}
              >
                <Button
                  type="text"
                  size="small"
                  danger
                  icon={<DeleteOutlined />}
                  onClick={(e) => e.stopPropagation()}
                />
              </Popconfirm>
            )}
          </div>
          <div className="is-history-sub">
            {record.final_score != null ? `${record.final_score} 分 · ` : ''}
            {record.source_type ?? '-'} · {record.created_at}
          </div>
        </div>
      ))}
    </>
  );
}
