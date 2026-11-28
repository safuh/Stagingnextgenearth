import assert from "node:assert/strict";
import test from "node:test";

import { ApiRequestError, apiGet } from "../lib/api.ts";

test("API client preserves numeric Retry-After metadata", async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => new Response(
    JSON.stringify({ detail: "CHIRPS provider cooldown is active." }),
    {
      status: 503,
      headers: {
        "Content-Type": "application/json",
        "Retry-After": "10800",
      },
    },
  );

  try {
    await assert.rejects(
      apiGet("/organizations/org-1/climate-ingestion"),
      (error: unknown) => {
        assert.ok(error instanceof ApiRequestError);
        assert.equal(error.status, 503);
        assert.equal(error.message, "CHIRPS provider cooldown is active.");
        assert.equal(error.retryAfterSeconds, 10800);
        return true;
      },
    );
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("API client accepts HTTP-date Retry-After values", async () => {
  const originalFetch = globalThis.fetch;
  const retryAt = new Date(Date.now() + 4_000).toUTCString();
  globalThis.fetch = async () => new Response(
    JSON.stringify({ detail: "Temporarily unavailable." }),
    {
      status: 503,
      headers: {
        "Content-Type": "application/json",
        "Retry-After": retryAt,
      },
    },
  );

  try {
    await assert.rejects(
      apiGet("/organizations/org-1/climate-ingestion"),
      (error: unknown) => {
        assert.ok(error instanceof ApiRequestError);
        assert.equal(error.status, 503);
        assert.ok(error.retryAfterSeconds !== undefined);
        assert.ok(error.retryAfterSeconds >= 0 && error.retryAfterSeconds <= 4);
        return true;
      },
    );
  } finally {
    globalThis.fetch = originalFetch;
  }
});
