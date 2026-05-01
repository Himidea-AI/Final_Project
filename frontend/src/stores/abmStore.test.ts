import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { useAbmStore, type AbmRequestPayload } from './abmStore';

const MOCK_PAYLOAD: AbmRequestPayload = {
  target_district: '서교동',
  business_type: 'cafe',
  brand_name: 'Test',
  langgraph_result: { foo: 'bar' },
  n_agents: 5000,
  days: 1,
  scenario: {
    weather_override: null,
    date_override: null,
    weekend_force: false,
    rent_shock_pct: 0.0,
  },
};

/** fetch helper — 응답 객체 모킹. */
function mockFetchResponse(body: unknown, init?: { ok?: boolean; status?: number }) {
  return {
    ok: init?.ok ?? true,
    status: init?.status ?? 200,
    json: async () => body,
  } as unknown as Response;
}

describe('abmStore — 초기 상태', () => {
  beforeEach(() => {
    useAbmStore.getState().reset();
  });

  it('초기에는 idle', () => {
    const s = useAbmStore.getState();
    expect(s.status).toBe('idle');
    expect(s.jobId).toBeNull();
    expect(s.result).toBeNull();
    expect(s.error).toBeNull();
    expect(s.params).toBeNull();
  });
});

describe('abmStore — startAbm 비동기 (job_id) 분기', () => {
  beforeEach(() => {
    useAbmStore.getState().reset();
    vi.restoreAllMocks();
  });

  afterEach(() => {
    useAbmStore.getState().reset();
  });

  it('POST 응답에 job_id 가 있으면 jobId 저장 + status=running 유지', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockImplementation((async (url: string) => {
      if (url === '/api/simulate-abm') {
        return mockFetchResponse({ job_id: 'job-123', status: 'running' });
      }
      // status poll → still running (계속 running 으로 남도록)
      if (url.includes('/status')) {
        return mockFetchResponse({ status: 'running', elapsed_seconds: 5 });
      }
      throw new Error(`unexpected url: ${url}`);
    }) as unknown as typeof fetch);

    await useAbmStore.getState().startAbm(MOCK_PAYLOAD);

    const s = useAbmStore.getState();
    expect(s.status).toBe('running');
    expect(s.jobId).toBe('job-123');
    expect(s.params).toEqual(MOCK_PAYLOAD);
    expect(s._pollTimer).not.toBeNull();
    expect(fetchSpy).toHaveBeenCalled();
    // cleanup interval 방지
    useAbmStore.getState().cancelAbm();
  });

  it('async_mode:true 가 POST body 에 포함된다', async () => {
    let capturedBody: string | null = null;
    vi.spyOn(globalThis, 'fetch').mockImplementation((async (url: string, init: RequestInit) => {
      if (url === '/api/simulate-abm') {
        capturedBody = init.body as string;
        return mockFetchResponse({ job_id: 'job-x', status: 'running' });
      }
      return mockFetchResponse({ status: 'running' });
    }) as unknown as typeof fetch);

    await useAbmStore.getState().startAbm(MOCK_PAYLOAD);
    const parsed = JSON.parse(capturedBody!);
    expect(parsed.async_mode).toBe(true);
    expect(parsed.target_district).toBe('서교동');
    useAbmStore.getState().cancelAbm();
  });
});

describe('abmStore — 동기 (캐시 hit) 분기', () => {
  beforeEach(() => {
    useAbmStore.getState().reset();
    vi.restoreAllMocks();
  });

  it('POST 응답에 job_id 없으면 결과 그대로 done', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      mockFetchResponse({
        status: 'ok',
        daily_visits_mean: 100,
      }),
    );

    await useAbmStore.getState().startAbm(MOCK_PAYLOAD);

    const s = useAbmStore.getState();
    expect(s.status).toBe('done');
    expect(s.result).toMatchObject({ status: 'ok', daily_visits_mean: 100 });
    expect(s.jobId).toBeNull();
    expect(s.progress).toBe(100);
  });

  it('status=unavailable 면 error 로 전환', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(mockFetchResponse({ status: 'unavailable' }));

    await useAbmStore.getState().startAbm(MOCK_PAYLOAD);

    const s = useAbmStore.getState();
    expect(s.status).toBe('error');
    expect(s.error).toContain('준비 중');
  });
});

describe('abmStore — cancelAbm', () => {
  beforeEach(() => {
    useAbmStore.getState().reset();
    vi.restoreAllMocks();
  });

  it('running 중 cancelAbm 시 idle 로 복귀', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation((async (url: string) => {
      if (url === '/api/simulate-abm') {
        return mockFetchResponse({ job_id: 'job-cancel', status: 'running' });
      }
      return mockFetchResponse({ status: 'running' });
    }) as unknown as typeof fetch);

    await useAbmStore.getState().startAbm(MOCK_PAYLOAD);
    expect(useAbmStore.getState().status).toBe('running');

    useAbmStore.getState().cancelAbm();
    const s = useAbmStore.getState();
    expect(s.status).toBe('idle');
    expect(s.jobId).toBeNull();
    expect(s._pollTimer).toBeNull();
    expect(s._abortController).toBeNull();
  });
});

describe('abmStore — 에러 응답', () => {
  beforeEach(() => {
    useAbmStore.getState().reset();
    vi.restoreAllMocks();
  });

  it('HTTP 5xx 면 error', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      mockFetchResponse({ message: 'boom' }, { ok: false, status: 500 }),
    );

    await useAbmStore.getState().startAbm(MOCK_PAYLOAD);
    const s = useAbmStore.getState();
    expect(s.status).toBe('error');
    expect(s.error).toContain('boom');
  });

  it('네트워크 throw 면 error 메시지에 reason 포함', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error('offline'));
    await useAbmStore.getState().startAbm(MOCK_PAYLOAD);
    const s = useAbmStore.getState();
    expect(s.status).toBe('error');
    expect(s.error).toMatch(/offline|네트워크/);
  });
});
