export interface ScoreDetail {
  degree: number;
  school: number;
  ai_tool: number;
  stability: number;
  days_per_week: number;
  raw_score: number;
  bonus: number;
  final_score: number;
}

export interface HardFilter {
  passed: boolean;
  reasons: string[];
}

/** LLM 抽取出的候选人字段（用于在评分卡上展示打分依据） */
export interface RunFields {
  name?: string | null;
  in_school?: boolean | null;
  education_end?: string | null;
  degree_level?: 'phd' | 'master' | 'bachelor' | 'other' | null;
  major?: string | null;
  bachelor_school?: string | null;
  bachelor_school_tier?: string | null;
  graduate_school?: string | null;
  graduate_school_tier?: string | null;
  ai_tool_experience?: 'project' | 'daily_chat' | 'none' | 'unknown' | null;
  ai_tool_evidence?: string | null;
  internship_duration_months?: number | null;
  days_per_week?: number | null;
  chengdu_onsite?: boolean | null;
}

export interface TraceStep {
  node: string;
  [key: string]: unknown;
}

export interface InterruptPayload {
  candidate_id: string;
  reasons: string[];
  fields: Record<string, unknown>;
  field_confidence: number;
  suggestion: string;
}

export interface RunView {
  thread_id: string;
  candidate_id?: string | null;
  status: string;
  rating?: string | null;
  score?: ScoreDetail | null;
  hard_filter?: HardFilter | null;
  explanation?: string | null;
  fields?: RunFields | null;
  trace: TraceStep[];
}

export interface RunResponse extends RunView {
  interrupt_payload?: InterruptPayload;
}

export interface RunRecord extends RunView {
  candidate_name?: string | null;
  source_type?: string | null;
  raw_input?: string | null;
  final_score?: number | null;
  payload?: InterruptPayload | null;
  created_at: string;
  updated_at: string;
}

export interface RunStats {
  total: number;
  recommend: number;
  pending: number;
  reject: number;
}

export type InputMode = 'text' | 'pdf';
