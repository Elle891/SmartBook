/**
 * ORM-style service — maps model/method calls to REST paths.
 */

const MODEL_ROUTES = {
  "account.set": {
    searchRead: "/account-sets",
    create: "/account-sets",
  },
  voucher: {
    searchRead: (ctx) => `/account-sets/${ctx.accountSetId}/vouchers`,
  },
};

export function createOrmService(rpc) {
  return {
    async call(model, method, args = [], kwargs = {}) {
      const routes = MODEL_ROUTES[model];
      if (!routes || !routes[method]) {
        throw new Error(`ORM route not defined: ${model}.${method}`);
      }
      const route = routes[method];
      const path = typeof route === "function" ? route(kwargs) : route;

      if (method === "searchRead") {
        return rpc.request(path, { method: "GET" });
      }
      if (method === "create") {
        return rpc.request(path, { method: "POST", body: args[0] || kwargs });
      }
      return rpc.request(path, { method: "POST", body: { args, kwargs } });
    },
  };
}
