import type { ExecutionAction, ExecutionPayload } from '../types/market';
import { request } from './http';

const ACTION_PATH_MAP: Record<ExecutionAction, string[]> = {
  preview: ['/api/execution/preview'],
  open: ['/api/execution/open'],
  close: ['/api/execution/close'],
  hedge: ['/api/execution/hedge'],
  'emergency-close': ['/api/execution/emergency-close'],
};

export async function executeAction(action: ExecutionAction, payload: ExecutionPayload): Promise<unknown> {
  const paths = ACTION_PATH_MAP[action];
  let lastError: unknown;

  for (const path of paths) {
    try {
      return await request<unknown>(path, 'POST', payload);
    } catch (error) {
      lastError = error;
    }
  }

  throw lastError instanceof Error ? lastError : new Error('执行动作失败');
}
