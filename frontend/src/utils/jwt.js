/** Decode JWT payload without verification (UI metadata only). */

export function decodeJwtPayload(token) {
  if (!token) return {};
  const parts = token.split(".");
  if (parts.length < 2) return {};
  try {
    const json = atob(parts[1].replace(/-/g, "+").replace(/_/g, "/"));
    return JSON.parse(json);
  } catch {
    return {};
  }
}
