/** Application service registry and useService helper. */

import { useComponent } from "@odoo/owl";
import { createOrmService } from "./orm";
import { createRpcService } from "./rpc";

export function makeEnv(stores = {}) {
  const rpc = createRpcService(stores.authStore);
  return {
    stores,
    services: {
      rpc,
      orm: createOrmService(rpc),
    },
  };
}

export function useService(name) {
  const component = useComponent();
  const service = component.env.services[name];
  if (!service) {
    throw new Error(`Unknown service: ${name}`);
  }
  return service;
}

export function useStore(name) {
  const component = useComponent();
  return component.env.stores[name];
}
