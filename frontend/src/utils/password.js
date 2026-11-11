/** Client-side password policy (mirrors backend auth.registration). */

export function checkPasswordStrength(password) {
  return {
    minLength: password.length >= 8,
    uppercase: /[A-Z]/.test(password),
    lowercase: /[a-z]/.test(password),
    digit: /\d/.test(password),
    special: /[^A-Za-z0-9]/.test(password),
  };
}

export function isPasswordStrong(password) {
  const checks = checkPasswordStrength(password);
  return Object.values(checks).every(Boolean);
}

export function passwordStrengthScore(password) {
  const checks = checkPasswordStrength(password);
  return Object.values(checks).filter(Boolean).length;
}

export function passwordStrengthLabel(password) {
  const score = passwordStrengthScore(password);
  if (!password) return { label: "", level: 0 };
  if (score <= 2) return { label: "Weak", level: 1 };
  if (score <= 4) return { label: "Fair", level: 2 };
  return { label: "Strong", level: 3 };
}
