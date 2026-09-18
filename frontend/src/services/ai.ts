import { request } from './apiClient';

export interface AiRuntime {
  mode: string;
  overall: 'healthy' | 'fallback_active' | 'degraded' | string;
  remote: { status: 'online' | 'offline' | string };
  llm: {
    active: 'remote' | 'gemini' | string;
    model: string;
    remote: 'online' | 'offline' | string;
    fallback: 'ready' | 'unavailable' | string;
  };
  embedding: {
    active: 'remote' | 'local' | string;
    model: string;
    dimensions: number;
    remote: 'online' | 'offline' | string;
    local: 'ready' | 'unavailable' | string;
    compatible: boolean;
  };
  last_health_check: string | null;
  fallback_reason: string | null;
}

export function getAiRuntime(): Promise<AiRuntime> {
  return request<AiRuntime>('/ai/runtime');
}
