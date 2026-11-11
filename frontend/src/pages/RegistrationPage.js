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

export class RegistrationPage extends Component {
  static components = {
    AuthLayout,
    ChannelTabs,
    PasswordField,
    OtpStep,
    ErrorBanner,
  };
  static template = xml`
    <AuthLayout subtitle="'Create your SmartBook account'">
      <ErrorBanner message="state.error" onDismiss.bind="clearError"/>

      <t t-if="state.step === 'form'">
        <ChannelTabs channel="state.channel" onChange.bind="setChannel"/>

        <form class="sb-auth__form" t-on-submit.prevent="onSendOtp">
          <div class="sb-field">
            <label for="reg-name">Display name</label>
            <input
              id="reg-name"
              type="text"
              class="sb-input"
              t-att-value="state.displayName"
              t-on-input="(ev) => this.state.displayName = ev.target.value"
              autocomplete="name"
            />
            <p t-if="state.fieldErrors.displayName" class="sb-field__error">
              <t t-esc="state.fieldErrors.displayName"/>
            </p>
          </div>

          <t t-if="state.channel === 'email'">
            <div class="sb-field">
              <label for="reg-email">Email</label>
              <input
                id="reg-email"
                type="email"
                class="sb-input"
                t-att-value="state.email"
                t-on-input="(ev) => this.state.email = ev.target.value"
                autocomplete="email"
              />
              <p t-if="state.fieldErrors.email" class="sb-field__error">
                <t t-esc="state.fieldErrors.email"/>
              </p>
            </div>
          </t>
          <t t-else="">
            <div class="sb-field">
              <label for="reg-mobile">Mobile number</label>
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
                  id="reg-mobile"
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
          </t>

          <PasswordField
            id="'reg-password'"
            label="'Password'"
            value="state.password"
            showStrength="true"
            error="state.fieldErrors.password"
            onInput.bind="setPassword"
          />

          <PasswordField
            id="'reg-confirm'"
            label="'Confirm password'"
            value="state.confirmPassword"
            error="state.fieldErrors.confirmPassword"
            onInput.bind="setConfirmPassword"
          />

          <div class="sb-auth__actions">
            <button type="submit" class="sb-btn sb-btn--primary sb-btn--block" t-att-disabled="state.loading">
              <t t-if="state.loading">Sending OTP…</t>
              <t t-else="">Send OTP</t>
            </button>
          </div>
        </form>

        <p class="sb-auth__footer">
          Already have an account?
          <a href="#/login" class="sb-link">Sign in</a>
        </p>
      </t>

      <t t-else="">
        <OtpStep
          inputId="'reg-otp'"
          target="otpTarget"
          error="state.fieldErrors.otp"
          loading="state.loading"
          onVerify.bind="onVerifyOtp"
          onResend.bind="onResendOtp"
          onBack.bind="goBackToForm"
        />
      </t>
    </AuthLayout>
  `;

  setup() {
    this.rpc = useService("rpc");
    this.authApi = createAuthApi(this.rpc);
    this.authStore = this.env.stores.authStore;

    this.state = useState({
      step: "form",
      channel: "email",
      displayName: "",
      email: "",
      countryCode: "+86",
      mobile: "",
      password: "",
      confirmPassword: "",
      sessionId: "",
      userId: "",
      loading: false,
      error: "",
      fieldErrors: {},
      otp: "",
    });
    this.countryCodes = COUNTRY_CODES;
  }

  get otpTarget() {
    return this.state.channel === "email"
      ? this.state.email.trim()
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

  validateForm() {
    const errors = {};
    if (!this.state.displayName.trim()) {
      errors.displayName = "Display name is required.";
    }
    if (this.state.channel === "email") {
      if (!isValidEmail(this.state.email)) {
        errors.email = "Enter a valid email address.";
      }
    } else {
      const mobile = formatMobile(this.state.countryCode, this.state.mobile);
      if (!isValidMobile(mobile)) {
        errors.mobile = "Enter a valid mobile number.";
      }
    }
    if (!isPasswordStrong(this.state.password)) {
      errors.password = "Password does not meet strength requirements.";
    }
    if (!passwordsMatch(this.state.password, this.state.confirmPassword)) {
      errors.confirmPassword = "Passwords do not match.";
    }
    this.state.fieldErrors = errors;
    return Object.keys(errors).length === 0;
  }

  async onSendOtp() {
    if (!this.validateForm()) return;
    this.state.loading = true;
    this.state.error = "";
    try {
      const body = {
        display_name: this.state.displayName.trim(),
        password: this.state.password,
      };
      let result;
      if (this.state.channel === "email") {
        body.email = this.state.email.trim().toLowerCase();
        result = await this.authApi.registerEmail(body);
      } else {
        body.mobile = formatMobile(this.state.countryCode, this.state.mobile);
        result = await this.authApi.registerMobile(body);
      }
      if (!result || !result.session_id) {
        throw new Error("Registration failed: server did not return a session. Check API connectivity.");
      }
      this.state.sessionId = result.session_id;
      this.state.userId = result.user_id;
      this.state.step = "otp";
    } catch (err) {
      this.state.error = formatApiError(err);
    } finally {
      this.state.loading = false;
    }
  }

  goBackToForm() {
    this.state.step = "form";
    this.state.fieldErrors = {};
  }

  async onVerifyOtp(otp) {
    if (!otp || otp.length !== 6) {
      this.state.fieldErrors = { otp: "Enter the 6-digit code." };
      return;
    }
    this.state.loading = true;
    this.state.fieldErrors = {};
    try {
      const target = this.otpTarget;
      const purpose =
        this.state.channel === "email" ? "register_email" : "register_mobile";
      const result = await this.authApi.verifyRegistrationOtp({
        target,
        session_id: this.state.sessionId,
        otp,
        purpose,
      });
      this.authStore.loginFromToken(result.access_token, {
        display_name: this.state.displayName.trim(),
        email: this.state.channel === "email" ? target : null,
        mobile: this.state.channel === "mobile" ? target : null,
      });
      this.authStore.resetInactivityTimer(() => {
        window.location.hash = "#/login";
      });
      window.location.hash = "#/account-sets/create";
    } catch (err) {
      this.state.fieldErrors = { otp: formatApiError(err) };
    } finally {
      this.state.loading = false;
    }
  }

  async onResendOtp() {
    this.state.error = "";
    try {
      const target = this.otpTarget;
      const purpose =
        this.state.channel === "email" ? "register_email" : "register_mobile";
      await this.authApi.resendOtp({
        target,
        purpose,
        session_id: this.state.sessionId,
      });
    } catch (err) {
      this.state.error = formatApiError(err);
    }
  }
}
