/** Identify anonymous public climate GETs whose validators may cross the BFF. */
export function isPublicClimateRead(method: string, path: string): boolean {
  if (method !== "GET" && method !== "HEAD") return false;
  return /^public\/organizations\/[^/]+\/climate\/(?:overview|sources|insights|releases(?:\/[^/]+(?:\/series)?)?)$/.test(path);
}
