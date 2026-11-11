import { Component, useState, xml } from "@odoo/owl";
import { AuthLayout } from "../components/auth/AuthLayout";
import { ChannelTabs } from "../components/auth/ChannelTabs";
import { OtpStep } from "../components/auth/OtpStep";
import { PasswordField } from "../components/auth/PasswordField";
import { ErrorBanner } from "../components/ErrorBanner";
import { createAuthApi } from "../services/auth_api";
import { useService } from "../services/registry";
import { formatApiError } from "../utils/errors";
import {
  formatMobile,
  isValidEmail,
  isValidMobile,
  passwordsMatch,
} from "../utils/validation";
import { isPasswordStrong } from "../utils/password";

const COUNTRY_CODES = ["+86", "+1", "+44", "+61", "+65", "+852"];

export class PasswordResetPage extends Component {
  static components = {
    AuthLayout,
    ChannelTabs,
    PasswordField,
    OtpStep,
    ErrorBanner,
  };
  static template = xml`
    <AuthLayout subtitle="'Reset your password'">
      <ErrorBanner message="state.error" onDismiss.bind="clearError"/>
      <div t-if="state.success" class="sb-banner sb-banner--success" role="status">
        <span><t t-esc="state.success"/></span>
      </div>

      <t t-if="state.step === 'request'">
        <ChannelTabs channel="state.channel" onChange.bind="setChannel"/>
        <form class="sb-auth__form" t-on-submit.prevent="onRequestOtp">
          <t t-if="state.channel === 'email'">
            <div class="sb-field">
              <label for="reset-email">Registered email</label>
              <input
                id="reset-email"
                type="email"
                class="sb-input"
                t-att-value="state.email"
                t-on-input="(ev) => this.state.email = ev.target.value"
                autocomplete="email"
              />
              <p t-if="state.fieldErrors.target" class="sb-field__error">
                <t t-esc="state.fieldErrors.target"/>
              </p>
            </div>
          </t>
          <t t-else="">
            <div class="sb-field">
              <label for="reset-mobile">Registered mobile</label>
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
                  id="reset-mobile"
                  type="tel"
                  class="sb-input"
                  placeholder="Phone number"
                  t-att-value="state.mobile"
                  t-on-input="(ev) => this.state.mobile = ev.target.value"
                  autocomplete="tel-national"
                />
              </div>
              <p t-if="state.fieldErrors.target" class="sb-field__error">
                <t t-esc="state.fieldErrors.target"/>
              </p>
            </div>
          </t>
          <div class="sb-auth__actions">
            <button type="submit" class="sb-btn sb-btn--primary sb-btn--block" t-att-disabled="state.loading">
              <t t-if="state.loading">Sending OTP…</t>
              <t t-else="">Send OTP</t>
            </button>
          </div>
        </form>
      </t>

      <t t-elif="state.step === 'otp'">
        <OtpStep
          inputId="'reset-otp'"
          target="resetTarget"
          error="state.fieldErrors.otp"
          loading="state.loading"
          onVerify.bind="onOtpContinue"
          onResend.bind="onResendOtp"
          onBack.bind="goToRequest"
        />
      </t>

      <t t-else="">
        <form class="sb-auth__form" t-on-submit.prevent="onResetPassword">
          <PasswordField
            id="'reset-password'"
            label="'New password'"
            value="state.password"
            showStrength="true"
            error="state.fieldErrors.password"
            onInput.bind="setPassword"
          />
          <PasswordField
            id="'reset-confirm'"
            label="'Confirm new password'"
            value="state.confirmPassword"
            error="state.fieldErrors.confirmPassword"
            onInput.bind="setConfirmPassword"
          />
          <div class="sb-auth__actions">
            <button type="button" class="sb-btn sb-btn--ghost" t-on-click="goToOtp">Back</button>
            <button type="submit" class="sb-btn sb-btn--primary" t-att-disabled="state.loading">
              <t t-if="state.loading">Saving…</t>
              <t t-else="">Reset password</t>
            </button>
          </div>
        </form>
      </t>

      <p class="sb-auth__footer">
        <a href="#/login" class="sb-link">Back to sign in</a>
      </p>
    </AuthLayout>
  `;

  setup() {
    this.rpc = useService("rpc");
    this.authApi = createAuthApi(this.rpc);
    this.countryCodes = COUNTRY_CODES;

    this.state = useState({
      step: "request",
      channel: "email",
      email: "",
      countryCode: "+86",
      mobile: "",
      sessionId: "",
      pendingOtp: "",
      password: "",
      confirmPassword: "",
      loading: false,
      error: "",
      success: "",
      fieldErrors: {},
    });
  }

  get resetTarget() {
    return this.state.channel === "email"
      ? this.state.email.trim().toLowerCase()
      : formatMobile(this.state.countryCode, this.state.mobile);
  }

  setChannel(channel) {
    this.state.channel = channel;
    this.state.fieldErrors = {};
    this.state.error = "";
  }

  setPassword(value) {
    this.state.password = value;
  }

  setConfirmPassword(value) {
    this.state.confirmPassword = value;
  }

  clearError() {
    this.state.error = "";
  }

  goToRequest() {
    this.state.step = "request";
    this.state.fieldErrors = {};
  }

  goToOtp() {
    this.state.step = "otp";
  }

  async onRequestOtp() {
    const target = this.resetTarget;
    if (this.state.channel === "email" && !isValidEmail(target)) {
      this.state.fieldErrors = { target: "Enter a valid email address." };
      return;
    }
    if (this.state.channel === "mobile" && !isValidMobile(target)) {
      this.state.fieldErrors = { target: "Enter a valid mobile number." };
      return;
    }

    this.state.loading = true;
    this.state.error = "";
    try {
      const result =
        this.state.channel === "email"
          ? await this.authApi.resetEmail({ email: target })
          : await this.authApi.resetMobile({ mobile: target });
      this.state.sessionId = result.session_id;
      this.state.step = "otp";
    } catch (err) {
      this.state.error = formatApiError(err);
    } finally {
      this.state.loading = false;
    }
  }

  onOtpContinue(otp) {
    if (!otp || otp.length !== 6) {
      this.state.fieldErrors = { otp: "Enter the 6-digit code." };
      return;
    }
    this.state.pendingOtp = otp;
    this.state.fieldErrors = {};
    this.state.step = "password";
  }

  async onResendOtp() {
    this.state.error = "";
    try {
      const purpose = this.state.channel === "email" ? "reset_email" : "reset_mobile";
      await this.authApi.resendOtp({
        target: this.resetTarget,
        purpose,
        session_id: this.state.sessionId,
      });
    } catch (err) {
      this.state.error = formatApiError(err);
    }
  }

  async onResetPassword() {
    const errors = {};
    if (!isPasswordStrong(this.state.password)) {
      errors.password = "Password does not meet strength requirements.";
    }
    if (!passwordsMatch(this.state.password, this.state.confirmPassword)) {
      errors.confirmPassword = "Passwords do not match.";
    }
    this.state.fieldErrors = errors;
    if (Object.keys(errors).length) return;

    this.state.loading = true;
    this.state.error = "";
    try {
      const purpose = this.state.channel === "email" ? "reset_email" : "reset_mobile";
      await this.authApi.verifyResetOtp({
        target: this.resetTarget,
        session_id: this.state.sessionId,
        otp: this.state.pendingOtp,
        new_password: this.state.password,
        purpose,
      });
      this.state.success = "Password reset successful. Redirecting to sign in…";
      setTimeout(() => {
        window.location.hash = "#/login";
      }, 1500);
    } catch (err) {
      this.state.error = formatApiError(err);
      if (String(err.message || "").includes("OTP")) {
        this.state.step = "otp";
        this.state.pendingOtp = "";
      }
    } finally {
      this.state.loading = false;
    }
  }
}
