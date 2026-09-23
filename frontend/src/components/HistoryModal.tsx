import { Modal } from 'antd';

import type { RunRecord } from '../types';
import HistoryList from './HistoryList';

interface Props {
  open: boolean;
  title?: string;
  records: RunRecord[];
  loading: boolean;
  activeThreadId?: string;
  deletable?: boolean;
  onSelect: (record: RunRecord) => void;
  onDelete?: (threadId: string) => void;
  onCancel: () => void;
}

export default function HistoryModal({
  open,
  title = '运行历史',
  records,
  loading,
  activeThreadId,
  deletable,
  onSelect,
  onDelete,
  onCancel,
}: Props) {
  return (
    <Modal
      open={open}
      title={title}
      width={560}
      footer={null}
      onCancel={onCancel}
      styles={{ body: { maxHeight: '60vh', overflowY: 'auto' } }}
    >
      <HistoryList
        records={records}
        loading={loading}
        activeThreadId={activeThreadId}
        deletable={deletable}
        onSelect={onSelect}
        onDelete={onDelete}
      />
    </Modal>
  );
}
