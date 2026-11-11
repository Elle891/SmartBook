const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const MOBILE_RE = /^\+?[1-9]\d{6,14}$|^1[3-9]\d{9}$/;

export function isValidEmail(value) {
  return EMAIL_RE.test(String(value || "").trim());
}

export function isValidMobile(value) {
  return MOBILE_RE.test(String(value || "").trim());
}

export function formatMobile(countryCode, number) {
  const digits = String(number || "").replace(/\D/g, "");
  const code = String(countryCode || "+86").replace(/\s/g, "");
  if (!digits) return "";
  if (digits.startsWith("1") && digits.length === 11 && code === "+86") {
    return digits;
  }
  const normalizedCode = code.startsWith("+") ? code : `+${code}`;
  return `${normalizedCode}${digits}`;
}

export function passwordsMatch(password, confirm) {
  return password === confirm;
}
