/** Normalize API / fetch errors for display. */

export function formatApiError(err) {
  if (!err) return "Something went wrong.";
  const raw = err.message || String(err);
  try {
    const parsed = JSON.parse(raw);
    if (Array.isArray(parsed)) {
      return parsed.map((item) => item.msg || item.message || JSON.stringify(item)).join("; ");
    }
    if (parsed && typeof parsed.detail === "string") {
      return parsed.detail;
    }
  } catch {
    // not JSON
  }
  if (raw.includes("Account locked")) {
    return raw;
  }
  if (raw.includes("OTP not found or expired")) {
    return "OTP expired or invalid. Request a new code.";
  }
  if (raw.includes("Invalid OTP")) {
    return "Incorrect OTP. Please try again.";
  }
  if (raw.includes("already registered")) {
    return raw;
  }
  if (raw.includes("rate limit")) {
    return "Too many OTP requests. Please wait before trying again.";
  }
  return raw;
}
