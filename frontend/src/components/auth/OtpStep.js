import { Component, onWillUnmount, useState, xml } from "@odoo/owl";

const OTP_TTL_SEC = 10 * 60;
const RESEND_COOLDOWN_SEC = 60;

export class OtpStep extends Component {
  static template = xml`
    <div class="sb-otp-step">
      <p class="sb-otp-step__hint">
        Enter the 6-digit code sent to <strong><t t-esc="props.target"/></strong>.
      </p>
      <div class="sb-field">
        <label t-att-for="props.inputId">Verification code</label>
        <input
          t-att-id="props.inputId"
          type="text"
          class="sb-input sb-input--otp"
          maxlength="6"
          inputmode="numeric"
          pattern="[0-9]*"
          autocomplete="one-time-code"
          t-att-value="state.otp"
          t-on-input="onOtpInput"
        />
        <p t-if="props.error" class="sb-field__error"><t t-esc="props.error"/></p>
      </div>
      <p class="sb-otp-step__timer">
        Code expires in <strong><t t-esc="formatTime(state.remainingSec)"/></strong>
      </p>
      <p class="sb-otp-step__resend">
        <button
          type="button"
          class="sb-link-btn"
          t-att-disabled="state.resendCooldown > 0 or props.loading"
          t-on-click="onResend"
        >
          <t t-if="state.resendCooldown > 0">Resend OTP (<t t-esc="state.resendCooldown"/>s)</t>
          <t t-else="">Resend OTP</t>
        </button>
      </p>
      <div class="sb-auth__actions">
        <button type="button" class="sb-btn sb-btn--ghost" t-on-click="props.onBack" t-att-disabled="props.loading">
          Back
        </button>
        <button type="button" class="sb-btn sb-btn--primary" t-on-click="onVerifyClick" t-att-disabled="props.loading or state.otp.length !== 6">
          <t t-if="props.loading">Verifying…</t>
          <t t-else="">Verify</t>
        </button>
      </div>
    </div>
  `;
  static props = {
    inputId: String,
    target: String,
    error: { type: String, optional: true },
    loading: { type: Boolean, optional: true },
    onVerify: Function,
    onResend: Function,
    onBack: Function,
    onChange: { type: Function, optional: true },
  };

  setup() {
    this.state = useState({
      otp: "",
      remainingSec: OTP_TTL_SEC,
      resendCooldown: 0,
    });
    this._tick = setInterval(() => this.tick(), 1000);
    onWillUnmount(() => clearInterval(this._tick));
  }

  tick() {
    if (this.state.remainingSec > 0) {
      this.state.remainingSec -= 1;
    }
    if (this.state.resendCooldown > 0) {
      this.state.resendCooldown -= 1;
    }
  }

  onOtpInput(ev) {
    this.state.otp = ev.target.value.replace(/\D/g, "").slice(0, 6);
    ev.target.value = this.state.otp;
    if (this.props.onChange) {
      this.props.onChange(this.state.otp);
    }
  }

  onVerifyClick() {
    if (this.props.onVerify) {
      this.props.onVerify(this.state.otp);
    }
  }

  async onResend() {
    if (this.state.resendCooldown > 0 || this.props.loading) return;
    await this.props.onResend();
    this.state.remainingSec = OTP_TTL_SEC;
    this.state.resendCooldown = RESEND_COOLDOWN_SEC;
    this.state.otp = "";
  }

  formatTime(totalSec) {
    const m = Math.floor(totalSec / 60);
    const s = totalSec % 60;
    return `${m}:${String(s).padStart(2, "0")}`;
  }

  resetTimer() {
    this.state.remainingSec = OTP_TTL_SEC;
    this.state.resendCooldown = RESEND_COOLDOWN_SEC;
  }
}
