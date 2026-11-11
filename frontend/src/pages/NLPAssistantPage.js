import { Component, useState, xml } from "@odoo/owl";
import { AppShell } from "../components/AppShell";
import { createNlpApi } from "../services/module_apis";
import { useService, useStore } from "../services/registry";
import { formatApiError } from "../utils/errors";
import { accountSetId } from "../utils/ledger_page";

const ACTION_INTENTS = new Set([
  "create_voucher",
  "submit_payment",
  "run_reconciliation",
  "generate_report",
  "close_period",
]);

export class NLPAssistantPage extends Component {
  static components = { AppShell };
  static template = xml`
    <AppShell title="'Assistant'" loading="state.loading" error="state.error">
      <section class="sb-page">
        <p t-if="isFallback()" class="sb-muted">
          Fallback mode active — DeepSeek model unavailable; using rule-based responses.
        </p>

        <div class="sb-panel sb-chat">
          <div class="sb-chat__history">
            <div t-foreach="state.history" t-as="msg" t-key="msg.id" t-att-class="msg.role === 'user' ? 'sb-chat__user' : 'sb-chat__bot'">
              <strong><t t-esc="msg.role === 'user' ? 'You' : 'Assistant'"/></strong>
              <span t-if="msg.language" class="sb-tag"><t t-esc="msg.language"/></span>
              <p><t t-esc="msg.text"/></p>
              <p t-if="msg.intent" class="sb-muted">Intent: <t t-esc="msg.intent"/> (<t t-esc="msg.confidence"/>)</p>
            </div>
          </div>

          <t t-if="state.pendingConfirm">
            <div class="sb-panel">
              <h3>Confirm Action</h3>
              <p><t t-esc="state.pendingConfirm.response"/></p>
              <p class="sb-muted">Intent: <t t-esc="state.pendingConfirm.intent"/></p>
              <div class="sb-auth__actions">
                <button type="button" class="sb-btn sb-btn--primary" t-on-click="confirmAction">Confirm</button>
                <button type="button" class="sb-btn sb-btn--ghost" t-on-click="cancelConfirm">Cancel</button>
              </div>
            </div>
          </t>

          <form class="sb-form" t-on-submit.prevent="send">
            <textarea class="sb-input" rows="3" placeholder="Ask in English or 中文…"
                      t-att-value="state.input" t-on-input="(ev) => state.input = ev.target.value"/>
            <div class="sb-auth__actions">
              <button type="submit" class="sb-btn sb-btn--primary" t-att-disabled="state.loading or !state.input.trim()">Send</button>
              <button type="button" class="sb-btn sb-btn--ghost" t-on-click="clearChat">Clear</button>
            </div>
          </form>
        </div>
      </section>
    </AppShell>
  `;

  setup() {
    this.rpc = useService("rpc");
    this.accountSetStore = useStore("accountSetStore");
    this.notificationStore = useStore("notificationStore");
    this.api = createNlpApi(this.rpc);
    this.msgId = 0;
    this.state = useState({
      loading: false,
      error: "",
      input: "",
      sessionId: null,
      history: [],
      pendingConfirm: null,
      lastModelUsed: "",
    });
  }

  isFallback() {
    const m = this.state.lastModelUsed || "";
    return m.includes("rule") || m.includes("fallback") || m === "rule_based";
  }

  pushHistory(role, text, extra = {}) {
    this.msgId += 1;
    this.state.history = [
      ...this.state.history,
      { id: this.msgId, role, text, ...extra },
    ];
  }

  async send(confirmed = false) {
    const asId = accountSetId(this.accountSetStore);
    if (!asId || !this.state.input.trim()) return;
    const message = this.state.input.trim();
    if (!confirmed) {
      this.pushHistory("user", message);
      this.state.input = "";
    }
    this.state.loading = true;
    this.state.error = "";
    try {
      const result = await this.api.chat({
        account_set_id: asId,
        message,
        session_id: this.state.sessionId,
        confirmed,
        params: {},
      });
      this.state.sessionId = result.session_id;
      this.state.lastModelUsed = result.model_used || "";
      const needsConfirm =
        !confirmed &&
        ACTION_INTENTS.has(result.intent) &&
        (result.response || "").toLowerCase().includes("confirm");
      if (needsConfirm) {
        this.state.pendingConfirm = { message, intent: result.intent, response: result.response };
      } else {
        this.state.pendingConfirm = null;
        this.pushHistory("assistant", result.response, {
          intent: result.intent,
          confidence: (result.confidence * 100).toFixed(0) + "%",
          language: result.language,
        });
      }
    } catch (err) {
      this.state.error = formatApiError(err);
    } finally {
      this.state.loading = false;
    }
  }

  async confirmAction() {
    if (!this.state.pendingConfirm) return;
    this.state.input = this.state.pendingConfirm.message;
    this.state.pendingConfirm = null;
    await this.send(true);
  }

  cancelConfirm() {
    this.state.pendingConfirm = null;
  }

  async clearChat() {
    if (this.state.sessionId) {
      try {
        await this.api.clearSession(this.state.sessionId);
      } catch {
        /* ignore */
      }
    }
    this.state.history = [];
    this.state.sessionId = null;
    this.state.pendingConfirm = null;
  }
}
