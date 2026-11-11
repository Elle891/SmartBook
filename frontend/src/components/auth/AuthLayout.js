import { Component, xml } from "@odoo/owl";

export class AuthLayout extends Component {
  static template = xml`
    <div class="sb-auth">
      <div class="sb-auth__card sb-auth__card--wide">
        <header class="sb-auth__header">
          <h1>SmartBook</h1>
          <p t-if="props.subtitle"><t t-esc="props.subtitle"/></p>
        </header>
        <t t-slot="default"/>
      </div>
    </div>
  `;
  static props = {
    subtitle: { type: String, optional: true },
  };
}
