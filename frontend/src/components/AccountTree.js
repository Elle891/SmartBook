import { Component, xml } from "@odoo/owl";

export class AccountTree extends Component {
  static components = {};
  static template = xml`
    <ul class="sb-account-tree" t-att-class="props.className">
      <li t-foreach="props.nodes" t-as="node" t-key="node.code" class="sb-account-tree__node">
        <div class="sb-account-tree__row" t-att-style="'padding-left:' + ((node.depth || 0) * 16) + 'px'">
          <span class="sb-account-tree__code"><t t-esc="node.code"/></span>
          <span class="sb-account-tree__name"><t t-esc="node.name"/></span>
          <span class="sb-account-tree__type"><t t-esc="node.account_type"/></span>
          <span t-if="node.aux_dimensions and node.aux_dimensions.length" class="sb-tag">
            <t t-esc="node.aux_dimensions.join(', ')"/>
          </span>
          <span class="sb-account-tree__actions">
            <button t-if="props.onSelect" type="button" class="sb-link-btn" t-on-click="() => props.onSelect(node)">
              Select
            </button>
            <button t-if="props.onEdit" type="button" class="sb-link-btn" t-on-click="() => props.onEdit(node)">
              Edit
            </button>
            <button t-if="props.onDelete and node.is_leaf" type="button" class="sb-link-btn sb-link-btn--danger" t-on-click="() => props.onDelete(node)">
              Delete
            </button>
          </span>
        </div>
        <AccountTree t-if="node.children and node.children.length"
          nodes="childNodes(node)"
          onSelect="props.onSelect"
          onEdit="props.onEdit"
          onDelete="props.onDelete"
        />
      </li>
    </ul>
  `;
  static props = {
    nodes: { type: Array },
    className: { type: String, optional: true },
    onSelect: { type: Function, optional: true },
    onEdit: { type: Function, optional: true },
    onDelete: { type: Function, optional: true },
  };

  setup() {
    this.constructor.components.AccountTree = this.constructor;
  }

  childNodes(node) {
    return (node.children || []).map((c) => ({ ...c, depth: (node.depth || 0) + 1 }));
  }
}
