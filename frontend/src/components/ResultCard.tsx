import { Alert, Card, Tag, Typography } from 'antd';

import type { RunFields, RunView } from '../types';

const RATING_COLOR: Record<string, string> = {
  推荐进入笔试: 'green',
  备选: 'blue',
  暂不推进: 'red',
  待人工复核: 'orange',
};

const SCORE_LABELS: Array<[keyof NonNullable<RunView['score']>, string]> = [
  ['degree', '学历'],
  ['school', '院校'],
  ['ai_tool', 'AI 工具'],
  ['stability', '到岗稳定性'],
  ['days_per_week', '每周到岗'],
];

const DEGREE_LABEL: Record<string, string> = {
  phd: '博士',
  master: '硕士',
  bachelor: '本科',
  other: '其他',
};

const AI_TOOL_LABEL: Record<string, string> = {
  project: '项目经历',
  daily_chat: '日常对话',
  none: '无',
  unknown: '未知',
};

/** 每个评分项对应的抽取依据文案，字段缺失时返回 null（不显示） */
function fieldNote(key: string, fields: RunFields | null | undefined): string | null {
  if (!fields) return null;

  switch (key) {
    case 'degree':
      return fields.degree_level ? DEGREE_LABEL[fields.degree_level] ?? fields.degree_level : null;
    case 'school': {
      const schools = [fields.graduate_school, fields.bachelor_school].filter(Boolean);
      return schools.length > 0 ? schools.join(' / ') : null;
    }
    case 'ai_tool':
      return fields.ai_tool_experience
        ? AI_TOOL_LABEL[fields.ai_tool_experience] ?? fields.ai_tool_experience
        : null;
    case 'stability':
      return fields.internship_duration_months == null
        ? null
        : `可实习 ${fields.internship_duration_months} 个月`;
    case 'days_per_week':
      return fields.days_per_week == null ? null : `每周 ${fields.days_per_week} 天`;
    default:
      return null;
  }
}

interface Props {
  run: RunView;
  /** 嵌入弹窗时去掉卡片外壳与标题，只保留内容。 */
  embedded?: boolean;
}

export default function ResultCard({ run, embedded = false }: Props) {
  const { rating, score, hard_filter: hardFilter, explanation } = run;

  return (
    <Card
      className={embedded ? 'is-card-embedded' : 'is-card'}
      variant="borderless"
      title={
        embedded ? undefined : (
          <div className="is-tag-row">
            <span>筛选结果</span>
            {rating && (
              <Tag color={RATING_COLOR[rating] ?? 'default'}>{rating}</Tag>
            )}
            <Tag>{run.candidate_id}</Tag>
            <Tag color="default">thread {run.thread_id.slice(0, 8)}</Tag>
          </div>
        )
      }
    >
      {hardFilter && !hardFilter.passed && (
        <Alert
          type="error"
          showIcon
          message="未通过硬性条件"
          description={hardFilter.reasons.join('；')}
        />
      )}

      {score && (
        <>
          <div className="is-score-grid">
            {SCORE_LABELS.map(([key, label]) => {
              const note = fieldNote(key, run.fields);
              return (
                <div className="is-score-cell" key={key}>
                  <span>{label}</span>
                  <strong>{score[key]}</strong>
                  {note && <em className="is-score-note">{note}</em>}
                </div>
              );
            })}
          </div>

          <div className="is-total">
            <span>
              原始分 {score.raw_score} + 加分 {score.bonus}
            </span>
            <span>
              最终分 <strong>{score.final_score}</strong>
            </span>
          </div>
        </>
      )}

      {explanation && (
        <Typography.Paragraph className="is-explain">
          {explanation}
        </Typography.Paragraph>
      )}
    </Card>
  );
}
