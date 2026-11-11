import { Component, useState, xml } from "@odoo/owl";
import { AuthLayout } from "../components/auth/AuthLayout";
import { ChannelTabs } from "../components/auth/ChannelTabs";
import { OtpStep } from "../components/auth/OtpStep";
import { ErrorBanner } from "../components/ErrorBanner";
import { createAuthApi } from "../services/auth_api";
import { useService } from "../services/registry";
import { formatApiError } from "../utils/errors";
import { formatMobile, isValidEmail, isValidMobile } from "../utils/validation";

const COUNTRY_CODES = ["+86", "+1", "+44", "+61", "+65", "+852"];

export class LoginPage extends Component {
  static components = {
    AuthLayout,
    ChannelTabs,
    OtpStep,
    ErrorBanner,
  };
  static template = xml`
    <AuthLayout subtitle="'Sign in to your account'">
      <ErrorBanner message="state.error" onDismiss.bind="clearError"/>

      <ChannelTabs channel="state.channel" onChange.bind="setChannel"/>

      <t t-if="state.channel === 'email'">
        <form class="sb-auth__form" t-on-submit.prevent="onEmailLogin">
          <div class="sb-field">
            <label for="login-email">Email</label>
            <input
              id="login-email"
              type="email"
              class="sb-input"
              t-att-value="state.email"
              t-on-input="(ev) => this.state.email = ev.target.value"
              autocomplete="username"
            />
            <p t-if="state.fieldErrors.email" class="sb-field__error">
              <t t-esc="state.fieldErrors.email"/>
            </p>
          </div>
          <div class="sb-field">
            <label for="login-password">Password</label>
            <input
              id="login-password"
              type="password"
              class="sb-input"
              t-att-value="state.password"
              t-on-input="(ev) => this.state.password = ev.target.value"
              autocomplete="current-password"
            />
            <p t-if="state.fieldErrors.password" class="sb-field__error">
              <t t-esc="state.fieldErrors.password"/>
            </p>
          </div>
          <p class="sb-auth__links">
            <a href="#/password-reset" class="sb-link">Forgot password?</a>
          </p>
          <div class="sb-auth__actions">
            <button type="submit" class="sb-btn sb-btn--primary sb-btn--block" t-att-disabled="state.loading">
              <t t-if="state.loading">Signing in…</t>
              <t t-else="">Sign in</t>
            </button>
          </div>
        </form>
      </t>

      <t t-elif="state.mobileStep === 'form'">
        <form class="sb-auth__form" t-on-submit.prevent="onSendMobileOtp">
          <div class="sb-field">
            <label for="login-mobile">Mobile number</label>
            <div class="sb-mobile-row">
              <select
                class="sb-input sb-input--code"
                t-on-change="(ev) => this.state.countryCode = ev.target.value"
              >
                <t t-foreach="countryCodes" t-as="code" t-key="code">
                  <option t-att-value="code" t-att-selected="code === state.countryCode">
                    <t t-esc="code"/>
                  </option>
                </t>
              </select>
              <input
                id="login-mobile"
                type="tel"
                class="sb-input"
                placeholder="Phone number"
                t-att-value="state.mobile"
                t-on-input="(ev) => this.state.mobile = ev.target.value"
                autocomplete="tel-national"
              />
            </div>
            <p t-if="state.fieldErrors.mobile" class="sb-field__error">
              <t t-esc="state.fieldErrors.mobile"/>
            </p>
          </div>
          <p class="sb-auth__links">
            <a href="#/password-reset" class="sb-link">Forgot password?</a>
          </p>
          <div class="sb-auth__actions">
            <button type="submit" class="sb-btn sb-btn--primary sb-btn--block" t-att-disabled="state.loading">
              <t t-if="state.loading">Sending OTP…</t>
              <t t-else="">Send OTP</t>
            </button>
          </div>
        </form>
      </t>

      <t t-else="">
        <OtpStep
          inputId="'login-otp'"
          target="mobileTarget"
          error="state.fieldErrors.otp"
          loading="state.loading"
          onVerify.bind="onVerifyMobileOtp"
          onResend.bind="onResendMobileOtp"
          onBack.bind="goBackMobileForm"
        />
      </t>

      <p class="sb-auth__footer">
        New to SmartBook?
        <a href="#/register" class="sb-link">Create an account</a>
      </p>
    </AuthLayout>
  `;

  setup() {
    this.rpc = useService("rpc");
    this.authApi = createAuthApi(this.rpc);
    this.authStore = this.env.stores.authStore;
    this.countryCodes = COUNTRY_CODES;

    this.state = useState({
      channel: "email",
      email: "",
      password: "",
      countryCode: "+86",
      mobile: "",
      mobileStep: "form",
      sessionId: "",
      loading: false,
      error: "",
      fieldErrors: {},
    });
  }

  get mobileTarget() {
    return formatMobile(this.state.countryCode, this.state.mobile);
  }

  setChannel(channel) {
    this.state.channel = channel;
    this.state.mobileStep = "form";
    this.state.fieldErrors = {};
    this.state.error = "";
  }

  clearError() {
    this.state.error = "";
  }

  async onEmailLogin(ev) {
    // Read from DOM so browser autofill / controlled-input desync still works
    const form = ev && ev.target;
    const emailInput = form && form.querySelector ? form.querySelector("#login-email") : null;
    const passwordInput = form && form.querySelector ? form.querySelector("#login-password") : null;
    const email = (emailInput?.value ?? this.state.email).trim().toLowerCase();
    const password = passwordInput?.value ?? this.state.password;
    this.state.email = email;
    this.state.password = password;

    const errors = {};
    if (!isValidEmail(email)) {
      errors.email = "Enter a valid email address.";
    }
    if (!password) {
      errors.password = "Password is required.";
    }
    this.state.fieldErrors = errors;
    if (Object.keys(errors).length) return;

    this.state.loading = true;
    this.state.error = "";
    try {
      const result = await this.authApi.loginEmail({
        email,
        password,
      });
      this.completeLogin(result.access_token, {
        email,
      });
    } catch (err) {
      this.state.error = formatApiError(err);
    } finally {
      this.state.loading = false;
    }
  }

  async onSendMobileOtp() {
    const mobile = this.mobileTarget;
    if (!isValidMobile(mobile)) {
      this.state.fieldErrors = { mobile: "Enter a valid mobile number." };
      return;
    }
    this.state.loading = true;
    this.state.error = "";
    this.state.fieldErrors = {};
    try {
      const result = await this.authApi.loginMobile({ mobile });
      this.state.sessionId = result.session_id;
      this.state.mobileStep = "otp";
    } catch (err) {
      this.state.error = formatApiError(err);
    } finally {
      this.state.loading = false;
    }
  }

  goBackMobileForm() {
    this.state.mobileStep = "form";
    this.state.fieldErrors = {};
  }

  async onVerifyMobileOtp(otp) {
    if (!otp || otp.length !== 6) {
      this.state.fieldErrors = { otp: "Enter the 6-digit code." };
      return;
    }
    this.state.loading = true;
    this.state.fieldErrors = {};
    try {
      const mobile = this.mobileTarget;
      const result = await this.authApi.verifyLoginOtp({
        mobile,
        session_id: this.state.sessionId,
        otp,
      });
      this.completeLogin(result.access_token, { mobile });
    } catch (err) {
      this.state.fieldErrors = { otp: formatApiError(err) };
    } finally {
      this.state.loading = false;
    }
  }

  async onResendMobileOtp() {
    this.state.error = "";
    try {
      await this.authApi.resendOtp({
        target: this.mobileTarget,
        purpose: "login_mobile",
        session_id: this.state.sessionId,
      });
    } catch (err) {
      this.state.error = formatApiError(err);
    }
  }

  completeLogin(accessToken, userMeta) {
    if (!accessToken || typeof accessToken !== "string") {
      throw new Error("Login failed: no access token returned from server.");
    }
    this.authStore.loginFromToken(accessToken, userMeta);
    this.authStore.resetInactivityTimer(() => {
      window.location.hash = "#/login";
    });
    window.location.hash = "#/";
  }
}
