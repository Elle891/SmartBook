import { Component, xml } from "@odoo/owl";
import { checkPasswordStrength, passwordStrengthLabel } from "../../utils/password";

export class PasswordField extends Component {
  static template = xml`
    <div class="sb-field">
      <label t-att-for="props.id"><t t-esc="props.label"/></label>
      <input
        t-att-id="props.id"
        type="password"
        class="sb-input"
        t-att-placeholder="props.placeholder"
        t-att-value="props.value"
        t-on-input="onInput"
        autocomplete="new-password"
      />
      <t t-if="props.showStrength and props.value">
        <div class="sb-password-strength">
          <div class="sb-password-strength__bar">
            <span t-att-class="'sb-password-strength__fill sb-password-strength__fill--' + strength.level"/>
          </div>
          <span class="sb-password-strength__label"><t t-esc="strength.label"/></span>
        </div>
        <ul class="sb-password-rules">
          <li t-att-class="{ 'sb-password-rules__ok': checks.minLength }">At least 8 characters</li>
          <li t-att-class="{ 'sb-password-rules__ok': checks.uppercase }">One uppercase letter</li>
          <li t-att-class="{ 'sb-password-rules__ok': checks.lowercase }">One lowercase letter</li>
          <li t-att-class="{ 'sb-password-rules__ok': checks.digit }">One digit</li>
          <li t-att-class="{ 'sb-password-rules__ok': checks.special }">One special character</li>
        </ul>
      </t>
      <p t-if="props.error" class="sb-field__error"><t t-esc="props.error"/></p>
    </div>
  `;
  static props = {
    id: String,
    label: String,
    value: String,
    placeholder: { type: String, optional: true },
    showStrength: { type: Boolean, optional: true },
    error: { type: String, optional: true },
    onInput: Function,
  };

  get checks() {
    return checkPasswordStrength(this.props.value || "");
  }

  get strength() {
    return passwordStrengthLabel(this.props.value || "");
  }

  onInput(ev) {
    if (this.props.onInput) {
      this.props.onInput(ev.target.value);
    }
  }
}
