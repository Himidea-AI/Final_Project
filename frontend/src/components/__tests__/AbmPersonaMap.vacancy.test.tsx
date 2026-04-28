import { render, waitFor } from '@testing-library/react';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import AbmPersonaMap from '../AbmPersonaMap';

// 카카오맵 SDK 가 없는 jsdom 환경에서도 렌더 가능하도록 (KAKAO_KEY_MISSING 분기로
// 실제 SDK 호출을 우회). 본 테스트는 mode prop 분기와 fetch 분기만 검증.

function getCalledUrls(spy: ReturnType<typeof vi.spyOn>): string[] {
  return spy.mock.calls.map((c: unknown[]) => String(c[0]));
}

describe('AbmPersonaMap — mode prop', () => {
  let fetchSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    fetchSpy = vi.spyOn(globalThis, 'fetch').mockImplementation((url: any) => {
      const u = typeof url === 'string' ? url : (url as Request).url;
      if (u.includes('/vacancy-evaluation/')) {
        if (u.endsWith('/trajectory')) {
          return Promise.resolve(
            new Response(JSON.stringify({ trajectory: [], n_agents: 0 }), { status: 200 }),
          );
        }
        if (u.endsWith('/visits')) {
          return Promise.resolve(
            new Response(JSON.stringify({ visits_events: [] }), { status: 200 }),
          );
        }
        if (u.endsWith('/stores')) {
          return Promise.resolve(
            new Response(JSON.stringify({ stores: [], vacancy_spot: {} }), { status: 200 }),
          );
        }
        if (u.endsWith('/chats')) {
          return Promise.resolve(new Response(JSON.stringify({ chats: [] }), { status: 200 }));
        }
      }
      // 기존 general 모드 fetch (회귀 X 보장)
      if (u.includes('/api/mapo/spots-all')) {
        return Promise.resolve(new Response(JSON.stringify({ spots: [] }), { status: 200 }));
      }
      if (u.includes('/api/mapo/spots/')) {
        return Promise.resolve(new Response(JSON.stringify({ spots: [] }), { status: 200 }));
      }
      return Promise.resolve(new Response('{}', { status: 200 }));
    });
  });

  afterEach(() => {
    fetchSpy.mockRestore();
  });

  it('default mode (general) — 기존 fetch 가 /api/mapo/spots* 를 호출 (회귀 X)', async () => {
    const onRunSimulation = vi.fn();
    render(
      <AbmPersonaMap
        abmResult={null}
        abmLoading={false}
        abmError={null}
        onRunSimulation={onRunSimulation}
        targetDistrict="서교동"
      />,
    );
    await waitFor(() => {
      const calls = getCalledUrls(fetchSpy);
      expect(calls.some((u: string) => u.includes('/api/mapo/spots-all'))).toBe(true);
    });
    const calls = getCalledUrls(fetchSpy);
    expect(calls.some((u: string) => u.includes('/vacancy-evaluation/'))).toBe(false);
  });

  it('mode="vacancy" with vacancyJobId — 4 endpoint 동시 fetch', async () => {
    const onRunSimulation = vi.fn();
    render(
      <AbmPersonaMap
        abmResult={null}
        abmLoading={false}
        abmError={null}
        onRunSimulation={onRunSimulation}
        mode="vacancy"
        vacancyJobId="test-uuid-1234"
        vacancySpot={{ dong: '서교동', lat: 37.5544, lng: 126.922 }}
      />,
    );
    await waitFor(() => {
      const calls = getCalledUrls(fetchSpy);
      expect(
        calls.some((u: string) => u.includes('/vacancy-evaluation/test-uuid-1234/trajectory')),
      ).toBe(true);
      expect(
        calls.some((u: string) => u.includes('/vacancy-evaluation/test-uuid-1234/visits')),
      ).toBe(true);
      expect(
        calls.some((u: string) => u.includes('/vacancy-evaluation/test-uuid-1234/stores')),
      ).toBe(true);
      expect(
        calls.some((u: string) => u.includes('/vacancy-evaluation/test-uuid-1234/chats')),
      ).toBe(true);
    });
    const calls = getCalledUrls(fetchSpy);
    expect(calls.some((u: string) => u.includes('/api/mapo/spots-all'))).toBe(false);
  });

  it('mode="vacancy" without vacancyJobId — fetch 호출 없음', async () => {
    const onRunSimulation = vi.fn();
    render(
      <AbmPersonaMap
        abmResult={null}
        abmLoading={false}
        abmError={null}
        onRunSimulation={onRunSimulation}
        mode="vacancy"
      />,
    );
    await new Promise((resolve) => setTimeout(resolve, 50));
    const calls = getCalledUrls(fetchSpy);
    expect(calls.some((u: string) => u.includes('/vacancy-evaluation/'))).toBe(false);
    expect(calls.some((u: string) => u.includes('/api/mapo/spots-all'))).toBe(false);
  });
});
