import { Component, onWillStart, useState, xml } from "@odoo/owl";
import { AppShell } from "../components/AppShell";
import { useService, useStore } from "../services/registry";
import { formatApiError } from "../utils/errors";
import { ALL_PERMISSIONS, permissionLabel, rolePermissions } from "../utils/permissions";

export class AccountSetPermissionsPage extends Component {
  static components = { AppShell };
  static template = xml`
    <AppShell title="'Permissions'" loading="state.loading" error="state.error">
      <section class="sb-page">
        <h1><t t-esc="accountSetName"/></h1>
        <p class="sb-muted">Account Set Admin — invite users and manage roles.</p>

        <div class="sb-panel">
          <h2>Invite User</h2>
          <form class="sb-form sb-form--inline" t-on-submit.prevent="onInvite">
            <input class="sb-input" placeholder="Mobile number" t-att-value="state.inviteMobile" t-on-input="(ev) => state.inviteMobile = ev.target.value"/>
            <select class="sb-input" t-on-change="(ev) => state.inviteRoleId = ev.target.value">
              <option value="">Select role</option>
              <option t-foreach="state.roles" t-as="role" t-key="role.id" t-att-value="role.id">
                <t t-esc="role.name"/>
              </option>
            </select>
            <button type="submit" class="sb-btn sb-btn--primary" t-att-disabled="state.saving">Invite</button>
          </form>
        </div>

        <div class="sb-panel">
          <h2>Members</h2>
          <table class="sb-table">
            <thead><tr><th>Name</th><th>Mobile</th><th>Role</th><th>Actions</th></tr></thead>
            <tbody>
              <tr t-foreach="state.members" t-as="m" t-key="m.user_id">
                <td><t t-esc="m.display_name"/></td>
                <td><t t-esc="m.mobile or '—'"/></td>
                <td>
                  <select t-att-value="m.role_id" t-on-change="(ev) => this.onChangeRole(m, ev.target.value)">
                    <option t-foreach="state.roles" t-as="role" t-key="role.id" t-att-value="role.id">
                      <t t-esc="role.name"/>
                    </option>
                  </select>
                </td>
                <td>
                  <button type="button" class="sb-link-btn sb-link-btn--danger" t-on-click="() => this.onRemove(m)">Remove</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="sb-panel">
          <div class="sb-page__header">
            <h2>Roles</h2>
            <button type="button" class="sb-btn sb-btn--primary" t-on-click="openRoleForm">+ Add Custom Role</button>
          </div>
          <div t-foreach="state.roles" t-as="role" t-key="role.id" class="sb-role-card">
            <div class="sb-page__header">
              <h3><t t-esc="role.name"/> <span t-if="role.is_builtin" class="sb-tag">Built-in</span></h3>
              <button t-if="!role.is_builtin" type="button" class="sb-link-btn" t-on-click="() => this.editRole(role)">Edit</button>
            </div>
            <div class="sb-tags">
              <span t-foreach="rolePermList(role)" t-as="perm" t-key="perm" class="sb-tag"><t t-esc="permLabel(perm)"/></span>
            </div>
          </div>
        </div>

        <div t-if="state.showRoleForm" class="sb-modal-backdrop">
          <div class="sb-modal">
            <h3><t t-if="state.editingRole">Edit Role</t><t t-else="">New Custom Role</t></h3>
            <div class="sb-field">
              <label>Role name</label>
              <input class="sb-input" t-att-value="state.roleName" t-att-readonly="state.editingRole" t-on-input="(ev) => state.roleName = ev.target.value"/>
            </div>
            <div class="sb-perm-grid">
              <label t-foreach="allPermissions" t-as="perm" t-key="perm.key" class="sb-check">
                <input type="checkbox" t-att-checked="state.rolePermissions.includes(perm.key)" t-on-change="() => this.togglePerm(perm.key)"/>
                <t t-esc="perm.label"/>
              </label>
            </div>
            <div class="sb-auth__actions">
              <button type="button" class="sb-btn sb-btn--ghost" t-on-click="closeRoleForm">Cancel</button>
              <button type="button" class="sb-btn sb-btn--primary" t-on-click="saveRole">Save</button>
            </div>
          </div>
        </div>
      </section>
    </AppShell>
  `;

  setup() {
    this.rpc = useService("rpc");
    this.accountSetStore = useStore("accountSetStore");
    this.notificationStore = useStore("notificationStore");
    this.allPermissions = ALL_PERMISSIONS;
    this.state = useState({
      loading: false,
      saving: false,
      error: "",
      members: [],
      roles: [],
      inviteMobile: "",
      inviteRoleId: "",
      showRoleForm: false,
      editingRole: null,
      roleName: "",
      rolePermissions: [],
    });
  }

  get accountSetId() {
    const path = this.env.router.state.path;
    const match = path.match(/^\/account-sets\/([^/]+)\/permissions$/);
    return match ? match[1] : this.accountSetStore.state.currentId;
  }

  get accountSetName() {
    const as = this.accountSetStore.state.accountSets.find((a) => a.id === this.accountSetId);
    return as?.name || "Account Set";
  }

  permLabel(key) {
    return permissionLabel(key);
  }

  rolePermList(role) {
    return rolePermissions(role);
  }

  async onWillStart() {
    await this.load();
  }

  async load() {
    const id = this.accountSetId;
    if (!id) {
      this.state.error = "No account set selected.";
      return;
    }
    this.state.loading = true;
    try {
      const api = this.accountSetStore.accountSetApi(this.rpc);
      const [members, roles] = await Promise.all([api.listMembers(id), api.listRoles(id)]);
      this.state.members = members;
      this.state.roles = roles;
    } catch (err) {
      this.state.error = formatApiError(err);
    } finally {
      this.state.loading = false;
    }
  }

  async onInvite() {
    if (!this.state.inviteMobile || !this.state.inviteRoleId) return;
    this.state.saving = true;
    try {
      await this.accountSetStore.accountSetApi(this.rpc).inviteMember(this.accountSetId, {
        mobile_number: this.state.inviteMobile.trim(),
        role_id: this.state.inviteRoleId,
      });
      this.state.inviteMobile = "";
      this.state.inviteRoleId = "";
      await this.load();
      this.notificationStore.notify("User invited.", { type: "success" });
    } catch (err) {
      this.notificationStore.notify(formatApiError(err), { type: "error" });
    } finally {
      this.state.saving = false;
    }
  }

  async onChangeRole(member, roleId) {
    try {
      await this.accountSetStore.accountSetApi(this.rpc).changeMemberRole(
        this.accountSetId,
        member.user_id,
        roleId
      );
      await this.load();
    } catch (err) {
      this.notificationStore.notify(formatApiError(err), { type: "error" });
    }
  }

  async onRemove(member) {
    if (!window.confirm(`Remove ${member.display_name}?`)) return;
    try {
      await this.accountSetStore.accountSetApi(this.rpc).removeMember(this.accountSetId, member.user_id);
      await this.load();
    } catch (err) {
      this.notificationStore.notify(formatApiError(err), { type: "error" });
    }
  }

  openRoleForm() {
    this.state.editingRole = null;
    this.state.roleName = "";
    this.state.rolePermissions = [];
    this.state.showRoleForm = true;
  }

  editRole(role) {
    this.state.editingRole = role;
    this.state.roleName = role.name;
    this.state.rolePermissions = [...(role.permissions || [])];
    this.state.showRoleForm = true;
  }

  closeRoleForm() {
    this.state.showRoleForm = false;
  }

  togglePerm(key) {
    const idx = this.state.rolePermissions.indexOf(key);
    if (idx >= 0) this.state.rolePermissions.splice(idx, 1);
    else this.state.rolePermissions.push(key);
  }

  async saveRole() {
    const api = this.accountSetStore.accountSetApi(this.rpc);
    try {
      if (this.state.editingRole) {
        await api.updateRole(this.accountSetId, this.state.editingRole.id, {
          permissions: [...this.state.rolePermissions],
        });
      } else {
        await api.createRole(this.accountSetId, {
          name: this.state.roleName.trim(),
          permissions: [...this.state.rolePermissions],
        });
      }
      this.state.showRoleForm = false;
      await this.load();
    } catch (err) {
      this.notificationStore.notify(formatApiError(err), { type: "error" });
    }
  }
}
