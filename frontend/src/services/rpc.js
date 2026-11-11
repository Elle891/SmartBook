/** JSON-RPC / REST wrapper for FastAPI backend calls. */

// esbuild inlines process.env.API_BASE_URL as a string literal — do not
// gate on `typeof process` (that object does not exist in the browser bundle).
const DEFAULT_BASE = process.env.API_BASE_URL || "";

export function createRpcService(authStore) {
  return {
    get baseUrl() {
      return DEFAULT_BASE.replace(/\/$/, "");
    },

    async request(path, options = {}) {
      const url = `${this.baseUrl}${path.startsWith("/") ? path : `/${path}`}`;
      const headers = {
        "Content-Type": "application/json",
        ...(options.headers || {}),
      };
      const token = authStore?.accessToken;
      if (token) {
        headers.Authorization = `Bearer ${token}`;
      }

      const response = await fetch(url, {
        method: options.method || "GET",
        headers,
        body: options.body ? JSON.stringify(options.body) : undefined,
      });

      if (response.status === 401 && authStore) {
        authStore.logout();
      }

      const text = await response.text();
      let data = null;
      if (text) {
        try {
          data = JSON.parse(text);
        } catch {
          data = text;
        }
      }

      if (!response.ok) {
        const message =
          (data && data.detail) ||
          (typeof data === "string" ? data : null) ||
          response.statusText;
        throw new Error(typeof message === "object" ? JSON.stringify(message) : message);
      }
      return data;
    },

    /** Download binary export (PDF / Excel / CSV). */
    async download(path, filename = "export") {
      const url = `${this.baseUrl}${path.startsWith("/") ? path : `/${path}`}`;
      const headers = {};
      const token = authStore?.accessToken;
      if (token) headers.Authorization = `Bearer ${token}`;

      const response = await fetch(url, { method: "GET", headers });
      if (response.status === 401 && authStore) authStore.logout();
      if (!response.ok) {
        const text = await response.text();
        let detail = text;
        try {
          detail = JSON.parse(text).detail || text;
        } catch {
          // keep text
        }
        throw new Error(typeof detail === "object" ? JSON.stringify(detail) : detail);
      }
      const blob = await response.blob();
      const disposition = response.headers.get("Content-Disposition") || "";
      const match = disposition.match(/filename="?([^";]+)"?/);
      const name = match ? match[1] : filename;
      const link = document.createElement("a");
      link.href = URL.createObjectURL(blob);
      link.download = name;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(link.href);
    },

    /** Download via POST with JSON body (forecast export). */
    async downloadPost(path, body, filename = "export") {
      const url = `${this.baseUrl}${path.startsWith("/") ? path : `/${path}`}`;
      const headers = { "Content-Type": "application/json" };
      const token = authStore?.accessToken;
      if (token) headers.Authorization = `Bearer ${token}`;
      const response = await fetch(url, { method: "POST", headers, body: JSON.stringify(body) });
      if (response.status === 401 && authStore) authStore.logout();
      if (!response.ok) {
        const text = await response.text();
        let detail = text;
        try {
          detail = JSON.parse(text).detail || text;
        } catch {
          /* keep */
        }
        throw new Error(typeof detail === "object" ? JSON.stringify(detail) : detail);
      }
      const blob = await response.blob();
      const disposition = response.headers.get("Content-Disposition") || "";
      const match = disposition.match(/filename="?([^";]+)"?/);
      const name = match ? match[1] : filename;
      const link = document.createElement("a");
      link.href = URL.createObjectURL(blob);
      link.download = name;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(link.href);
    },

    /** Multipart file upload. */
    async upload(path, file, fieldName = "file") {
      const url = `${this.baseUrl}${path.startsWith("/") ? path : `/${path}`}`;
      const headers = {};
      const token = authStore?.accessToken;
      if (token) headers.Authorization = `Bearer ${token}`;
      const form = new FormData();
      form.append(fieldName, file);
      const response = await fetch(url, { method: "POST", headers, body: form });
      if (response.status === 401 && authStore) authStore.logout();
      const text = await response.text();
      let data = null;
      if (text) {
        try {
          data = JSON.parse(text);
        } catch {
          data = text;
        }
      }
      if (!response.ok) {
        const message =
          (data && data.detail) ||
          (typeof data === "string" ? data : null) ||
          response.statusText;
        throw new Error(typeof message === "object" ? JSON.stringify(message) : message);
      }
      return data;
    },

    /** Odoo-style JSON-RPC call mapped to REST endpoints. */
    async jsonRpc(path, params = {}) {
      return this.request(path, { method: "POST", body: params });
    },
  };
}
