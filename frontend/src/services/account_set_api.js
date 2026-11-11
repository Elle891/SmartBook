/** Account set REST API (Task 32). */

export function createAccountSetApi(rpc) {
  return {
    list() {
      return rpc.request("/account-sets", { method: "GET" });
    },
    create(body) {
      return rpc.request("/account-sets", { method: "POST", body });
    },
    switch(accountSetId) {
      return rpc.request(`/account-sets/${accountSetId}/switch`, { method: "POST" });
    },
    testDatasource(body) {
      return rpc.request("/account-sets/test-datasource", { method: "POST", body });
    },
    setOpeningBalances(accountSetId, entries) {
      return rpc.request(`/account-sets/${accountSetId}/opening-balances`, {
        method: "POST",
        body: { entries },
      });
    },
    listMembers(accountSetId) {
      return rpc.request(`/account-sets/${accountSetId}/members`, { method: "GET" });
    },
    inviteMember(accountSetId, body) {
      return rpc.request(`/account-sets/${accountSetId}/members`, { method: "POST", body });
    },
    changeMemberRole(accountSetId, userId, roleId) {
      return rpc.request(`/account-sets/${accountSetId}/members/${userId}`, {
        method: "PATCH",
        body: { role_id: roleId },
      });
    },
    removeMember(accountSetId, userId) {
      return rpc.request(`/account-sets/${accountSetId}/members/${userId}`, { method: "DELETE" });
    },
    listRoles(accountSetId) {
      return rpc.request(`/account-sets/${accountSetId}/roles`, { method: "GET" });
    },
    createRole(accountSetId, body) {
      return rpc.request(`/account-sets/${accountSetId}/roles`, { method: "POST", body });
    },
    updateRole(accountSetId, roleId, body) {
      return rpc.request(`/account-sets/${accountSetId}/roles/${roleId}`, {
        method: "PATCH",
        body,
      });
    },
  };
}
