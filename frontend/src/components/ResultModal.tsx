import { Modal } from 'antd';

import type { RunView } from '../types';
import ResultCard from './ResultCard';

interface Props {
  open: boolean;
  run: RunView | null;
  onClose: () => void;
}

export default function ResultModal({ open, run, onClose }: Props) {
  return (
    <Modal
      open={open}
      title="筛选结果"
      width={720}
      footer={null}
      onCancel={onClose}
      styles={{ body: { paddingTop: 8 } }}
    >
      {run && <ResultCard run={run} embedded />}
    </Modal>
  );
}
