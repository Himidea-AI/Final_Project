---
name: spotter-async-cleanup
description: Enforces try-finally cleanup pattern for async resources in SPOTTER — Redis clients, httpx AsyncClient, database connections, and frontend polling intervals. Use when modifying LangGraph nodes (market_analyst, legal, population, synthesis), any function creating aioredis clients, any React hook using setInterval, or any code that catches exceptions around resource usage. Triggers when Claude sees redis.from_url(), aioredis.Redis(), AsyncClient(), setInterval() in React, or an except block after resource creation without a finally clause.
---

# SPOTTER Async Resource Cleanup

Prevent connection leaks and polling overload. Codifies two recent fixes: the Redis `aclose()` leak in 3 LangGraph nodes, and the `useManagerList` polling that was hammering RDS at 80 requests per minute.

## Backend: Async Resource Pattern

### Canonical pattern (from 예진's synthesis node)

```python
async def node_function(state):
    redis_client = None
    try:
        redis_client = await aioredis.from_url(REDIS_URL)
        cached = await redis_client.get(key)
        # ... business logic ...
        return result
    except Exception as e:
        logger.warning(f"Cache lookup failed: {e}")
        return fallback_result
    finally:
        if redis_client is not None:
            await redis_client.aclose()
```

### Apply this pattern to every async resource in:
- `market_analyst` node
- `legal` node
- `population` node
- `synthesis` node (already correct — use as reference)
- Any future LangGraph node that touches Redis / httpx / DB connections

### Never do this

```python
# BAD — connection leaks on exception
try:
    redis_client = await aioredis.from_url(REDIS_URL)
    cached = await redis_client.get(key)
    await redis_client.aclose()  # skipped if exception thrown above
except Exception:
    return fallback  # redis_client is still open
```

```python
# BAD — no cleanup at all
redis_client = await aioredis.from_url(REDIS_URL)
return await redis_client.get(key)  # leaked on every call
```

## Frontend: Polling Pattern

### Canonical pattern (ManagerListProvider)

Any polling must satisfy all three:
1. **Global via Context** — one `setInterval` per app, not per component
2. **Page Visibility gated** — pause when tab is hidden
3. **Reasonable frequency** — 5 minutes minimum for non-urgent data; never 30 seconds

```typescript
useEffect(() => {
  let intervalId: number | null = null;

  const start = () => {
    if (intervalId !== null) return;
    fetchData();
    intervalId = window.setInterval(fetchData, 5 * 60 * 1000); // 5 min
  };

  const stop = () => {
    if (intervalId !== null) {
      clearInterval(intervalId);
      intervalId = null;
    }
  };

  const handleVisibility = () => {
    if (document.hidden) stop();
    else start();
  };

  document.addEventListener('visibilitychange', handleVisibility);
  if (!document.hidden) start();

  return () => {
    stop();
    document.removeEventListener('visibilitychange', handleVisibility);
  };
}, []);
```

### Never do this

- `setInterval` inside an individual component's `useEffect` when the same data is fetched by multiple components → lift to a Provider
- Polling intervals under 1 minute unless genuinely real-time (유동인구 data is NOT real-time — it updates infrequently upstream)
- Forgetting `clearInterval` in the cleanup function
- Polling that continues while the tab is hidden (wastes RDS quota)

## Red Flags — Stop and Verify

- `aioredis.from_url(...)` without a matching `aclose()` in a `finally` block
- An `except Exception` block in an async function that used a resource above — where is the finally?
- `setInterval` in a React component that could be mounted in multiple places simultaneously (e.g., navbar bell + dashboard both polling = 2× load per tab)
- Polling frequency faster than the upstream data actually updates
- Any `useEffect` with `setInterval` but no `clearInterval` in cleanup
- A new polling hook being added when a Context Provider already exists for similar data

## Historical Context

- **RDS overload**: `useManagerList` polled every 30s per-component per-tab with no visibility gating. At 10 팀장 × 2 tabs = 80 req/min. Fixed to 4 req/min via `ManagerListProvider` + Page Visibility API.
- **Redis leaks**: market_analyst / legal / population had the cache-miss exception path skip `aclose()`. 예진's synthesis node had the correct pattern — replicated to the other three.