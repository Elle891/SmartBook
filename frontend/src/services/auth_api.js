/** Auth REST endpoints (Task 31a). */

export function createAuthApi(rpc) {
  return {
    registerEmail(body) {
      return rpc.request("/auth/register/email", { method: "POST", body });
    },
    registerMobile(body) {
      return rpc.request("/auth/register/mobile", { method: "POST", body });
    },
    verifyRegistrationOtp(body) {
      return rpc.request("/auth/register/verify-otp", { method: "POST", body });
    },
    loginEmail(body) {
      return rpc.request("/auth/login/email", { method: "POST", body });
    },
    loginMobile(body) {
      return rpc.request("/auth/login/mobile", { method: "POST", body });
    },
    verifyLoginOtp(body) {
      return rpc.request("/auth/login/verify-otp", { method: "POST", body });
    },
    resetEmail(body) {
      return rpc.request("/auth/password-reset/email", { method: "POST", body });
    },
    resetMobile(body) {
      return rpc.request("/auth/password-reset/mobile", { method: "POST", body });
    },
    verifyResetOtp(body) {
      return rpc.request("/auth/password-reset/verify-otp", { method: "POST", body });
    },
    resendOtp(body) {
      return rpc.request("/auth/otp/resend", { method: "POST", body });
    },
  };
}
