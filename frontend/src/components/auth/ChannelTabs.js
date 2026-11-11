import { Component, xml } from "@odoo/owl";

export class ChannelTabs extends Component {
  static template = xml`
    <div class="sb-channel-tabs" role="tablist">
      <button
        type="button"
        role="tab"
        t-att-aria-selected="props.channel === 'email'"
        t-att-class="{ 'sb-channel-tabs__tab--active': props.channel === 'email' }"
        t-on-click="() => props.onChange('email')"
      >Email</button>
      <button
        type="button"
        role="tab"
        t-att-aria-selected="props.channel === 'mobile'"
        t-att-class="{ 'sb-channel-tabs__tab--active': props.channel === 'mobile' }"
        t-on-click="() => props.onChange('mobile')"
      >Mobile</button>
    </div>
  `;
  static props = {
    channel: String,
    onChange: Function,
  };
}
