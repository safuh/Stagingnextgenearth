import assert from "node:assert/strict";
import test from "node:test";

import { apiGetRevalidated } from "../lib/api.ts";

test("public GET sends If-None-Match and reuses its representation on 304", async () => {
  const originalFetch = globalThis.fetch;
  const requests: RequestInit[] = [];
  let call = 0;
  globalThis.fetch = async (_input, init) => {
    requests.push(init ?? {});
    call += 1;
    if (call === 1) {
      return new Response(JSON.stringify({ release_count: 2 }), {
        status: 200,
        headers: { "Content-Type": "application/json", ETag: '"climate-v1"' },
      });
    }
    return new Response(null, { status: 304, headers: { ETag: '"climate-v1"' } });
  };

  try {
    const path = "/public/organizations/demo/climate/overview";
    const first = await apiGetRevalidated<{ release_count: number }>(path);
    const second = await apiGetRevalidated<{ release_count: number }>(path);

    assert.deepEqual(first, { release_count: 2 });
    assert.deepEqual(second, first);
    assert.equal(new Headers(requests[1].headers).get("If-None-Match"), '"climate-v1"');
    assert.equal(requests[1].cache, "no-store");
  } finally {
    globalThis.fetch = originalFetch;
  }
});
