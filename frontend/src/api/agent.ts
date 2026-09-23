import type { RunRecord, RunResponse, RunStats } from '../types';
import { client } from './client';

export interface RunAgentPayload {
  input_type: 'text' | 'pdf';
  raw_input: string;
}

export async function runAgent(payload: RunAgentPayload): Promise<RunResponse> {
  const res = await client.post<RunResponse>('/agent/run', payload);
  return res.data;
}

export async function resumeAgent(
  threadId: string,
  humanInput: Record<string, unknown>,
): Promise<RunResponse> {
  const res = await client.post<RunResponse>('/agent/resume', {
    thread_id: threadId,
    human_input: humanInput,
  });
  return res.data;
}

export async function uploadPdf(file: File): Promise<string> {
  const form = new FormData();
  form.append('file', file);
  const res = await client.post<{ file_path: string }>('/agent/upload', form);
  return res.data.file_path;
}

export async function getCandidates(): Promise<RunRecord[]> {
  const res = await client.get<RunRecord[]>('/candidates');
  return res.data;
}

export async function getCandidateRun(threadId: string): Promise<RunRecord> {
  const res = await client.get<RunRecord>(`/candidates/${threadId}`);
  return res.data;
}

export async function deleteCandidateRun(threadId: string): Promise<void> {
  await client.delete(`/candidates/${threadId}`);
}

export async function getStats(): Promise<RunStats> {
  const res = await client.get<RunStats>('/stats');
  return res.data;
}

export async function getPendingReviews(): Promise<RunRecord[]> {
  const res = await client.get<RunRecord[]>('/review/pending');
  return res.data;
}

export async function getRules(): Promise<Record<string, unknown>> {
  const res = await client.get<Record<string, unknown>>('/rules');
  return res.data;
}
