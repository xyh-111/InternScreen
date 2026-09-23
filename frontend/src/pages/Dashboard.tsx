import { HistoryOutlined } from '@ant-design/icons';
import { App, Button } from 'antd';
import { useCallback, useEffect, useMemo, useState } from 'react';

import {
  deleteCandidateRun,
  getCandidateRun,
  getCandidates,
  getStats,
  resumeAgent,
  runAgent,
  type RunAgentPayload,
} from '../api/agent';
import CandidateInput from '../components/CandidateInput';
import HistoryModal from '../components/HistoryModal';
import ResultModal from '../components/ResultModal';
import ReviewModal from '../components/ReviewModal';
import StatsCards from '../components/StatsCards';
import StatusDistribution from '../components/StatusDistribution';
import type { InterruptPayload, RunRecord, RunStats, RunView } from '../types';

/** 列表弹窗的数据范围：'all' 为头部「历史记录」按钮，其余对应四张统计卡 */
type ListKey = 'all' | keyof RunStats;

/** 与后端 rules.yaml 的 labels 一致：推荐简历 = 推荐进入笔试 + 备选 */
const RECOMMEND_RATINGS = ['推荐进入笔试', '备选'];
const REJECT_RATING = '暂不推进';

const LIST_TITLES: Record<ListKey, string> = {
  all: '运行历史',
  total: '全部简历',
  recommend: '推荐简历',
  pending: '待复核简历',
  reject: '暂不推进',
};

export default function Dashboard() {
  const { message } = App.useApp();
  const [stats, setStats] = useState<RunStats | null>(null);
  const [statsLoading, setStatsLoading] = useState(false);
  const [history, setHistory] = useState<RunRecord[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [listKey, setListKey] = useState<ListKey | null>(null);
  const [running, setRunning] = useState(false);
  const [resuming, setResuming] = useState(false);
  const [result, setResult] = useState<RunView | null>(null);
  const [resultOpen, setResultOpen] = useState(false);
  const [review, setReview] = useState<{
    threadId: string;
    payload: InterruptPayload;
  } | null>(null);
  const [inputResetKey, setInputResetKey] = useState(0);

  const refreshStats = useCallback(async () => {
    setStatsLoading(true);
    try {
      setStats(await getStats());
    } catch {
      message.error('加载统计失败，请确认后端已启动');
    } finally {
      setStatsLoading(false);
    }
  }, []);

  const refreshHistory = useCallback(async () => {
    setHistoryLoading(true);
    try {
      setHistory(await getCandidates());
    } catch {
      message.error('加载历史记录失败，请确认后端已启动');
    } finally {
      setHistoryLoading(false);
    }
  }, []);

  const visibleRecords = useMemo(() => {
    switch (listKey) {
      case 'recommend':
        return history.filter(
          (record) => record.rating != null && RECOMMEND_RATINGS.includes(record.rating),
        );
      case 'pending':
        return history.filter((record) => record.status === 'WAITING_REVIEW');
      case 'reject':
        return history.filter((record) => record.rating === REJECT_RATING);
      default:
        return history;
    }
  }, [history, listKey]);

  useEffect(() => {
    void refreshStats();
    void refreshHistory();
  }, [refreshStats, refreshHistory]);

  const handleRun = async (payload: RunAgentPayload) => {
    setRunning(true);
    setResult(null);
    setResultOpen(false);
    setReview(null);
    try {
      const data = await runAgent(payload);
      if (data.status === 'WAITING_REVIEW' && data.interrupt_payload) {
        setReview({ threadId: data.thread_id, payload: data.interrupt_payload });
        message.warning('该候选人需要人工复核');
      } else {
        setResult(data);
        setResultOpen(true);
        message.success(`筛选完成：${data.rating}`);
      }
      void refreshStats();
      void refreshHistory();
      // 清空输入框（只在请求成功到达后端后清，避免网络失败时用户丢输入）
      setInputResetKey((k) => k + 1);
    } catch (error) {
      message.error(
        error instanceof Error ? `运行失败：${error.message}` : '运行失败',
      );
    } finally {
      setRunning(false);
    }
  };

  const handleResume = async (humanInput: Record<string, unknown>) => {
    if (!review) return;
    setResuming(true);
    try {
      const data = await resumeAgent(review.threadId, humanInput);
      setReview(null);
      if (data.status === 'WAITING_REVIEW' && data.interrupt_payload) {
        setReview({ threadId: data.thread_id, payload: data.interrupt_payload });
        message.warning('仍需人工复核');
      } else {
        setResult(data);
        setResultOpen(true);
        message.success(`复核完成：${data.rating}`);
      }
      void refreshStats();
      void refreshHistory();
      setInputResetKey((k) => k + 1);
    } catch {
      message.error('恢复执行失败');
    } finally {
      setResuming(false);
    }
  };

  const handleSelectHistory = async (record: RunRecord) => {
    try {
      const detail = await getCandidateRun(record.thread_id);
      if (detail.status === 'WAITING_REVIEW' && detail.payload) {
        setReview({ threadId: detail.thread_id, payload: detail.payload });
      } else {
        setResult(detail);
        setResultOpen(true);
      }
    } catch {
      message.error('加载记录详情失败');
    }
  };

  const handleDeleteHistory = async (threadId: string) => {
    try {
      await deleteCandidateRun(threadId);
      message.success('已删除');
      if (result?.thread_id === threadId) {
        setResult(null);
        setResultOpen(false);
      }
      if (review?.threadId === threadId) {
        setReview(null);
      }
      void refreshStats();
      void refreshHistory();
    } catch {
      message.error('删除失败');
    }
  };

  return (
    <div className="is-shell">
      <header className="is-header">
        <div className="is-header-row">
          <div>
            <h1>AI 实习生筛选系统</h1>
            <p>
              LangGraph Agent · parse → extract → validate → screen / review →
              explain
            </p>
          </div>
          <Button
            icon={<HistoryOutlined />}
            onClick={() => setListKey('all')}
          >
            历史记录
          </Button>
        </div>
      </header>

      <div className="is-stack">
        <StatsCards
          stats={stats}
          loading={statsLoading}
          onSelect={(key) => setListKey(key)}
        />
        <StatusDistribution stats={stats} loading={statsLoading} />
        <CandidateInput
          key={inputResetKey}
          loading={running}
          onRun={handleRun}
        />
      </div>

      <ResultModal
        open={resultOpen}
        run={result}
        onClose={() => setResultOpen(false)}
      />

      <HistoryModal
        open={listKey !== null}
        title={listKey ? LIST_TITLES[listKey] : undefined}
        records={visibleRecords}
        loading={historyLoading}
        activeThreadId={result?.thread_id}
        deletable={listKey === 'all'}
        onSelect={handleSelectHistory}
        onDelete={handleDeleteHistory}
        onCancel={() => setListKey(null)}
      />

      <ReviewModal
        open={review !== null}
        threadId={review?.threadId ?? ''}
        payload={review?.payload ?? null}
        loading={resuming}
        onSubmit={handleResume}
        onCancel={() => setReview(null)}
      />
    </div>
  );
}
