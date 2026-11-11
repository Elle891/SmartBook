/** Built-in role permission labels for UI (mirrors backend auth/rbac.py). */

export const ALL_PERMISSIONS = [
  { key: "vouchers", label: "Vouchers" },
  { key: "cashier", label: "Cashier" },
  { key: "invoices", label: "Invoices" },
  { key: "payroll", label: "Payroll" },
  { key: "assets", label: "Assets" },
  { key: "tax", label: "Tax" },
  { key: "period_end", label: "Period End" },
  { key: "ledger", label: "Ledger" },
  { key: "reports", label: "Reports" },
  { key: "create_account_set", label: "Create Account Set" },
  { key: "delete_account_set", label: "Delete Account Set" },
  { key: "backup_restore", label: "Backup / Restore" },
  { key: "reinitialize", label: "Reinitialize" },
  { key: "link_inventory", label: "Link Inventory" },
  { key: "link_cloud_invoices", label: "Link Cloud Invoices" },
  { key: "user_management", label: "User Management" },
  { key: "audit_log", label: "Audit Log" },
];

export const BUILTIN_ROLE_PERMISSIONS = {
  Account_Set_Admin: ALL_PERMISSIONS.map((p) => p.key),
  Supervisor: [
    "vouchers", "cashier", "invoices", "payroll", "assets", "tax",
    "period_end", "ledger", "reports", "create_account_set",
  ],
  Voucher_Clerk: [
    "vouchers", "invoices", "payroll", "assets", "tax",
    "period_end", "ledger", "reports", "create_account_set",
  ],
  Cashier: ["cashier", "vouchers", "assets", "ledger", "reports", "create_account_set"],
  Viewer: ["vouchers", "cashier", "assets", "ledger", "reports", "create_account_set"],
};

export function permissionLabel(key) {
  return ALL_PERMISSIONS.find((p) => p.key === key)?.label || key;
}

export function rolePermissions(role) {
  if (role.is_builtin && BUILTIN_ROLE_PERMISSIONS[role.name]) {
    return BUILTIN_ROLE_PERMISSIONS[role.name];
  }
  return role.permissions || [];
}
