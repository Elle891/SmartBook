/**
 * Development server with esbuild watch + SCSS rebuild.
 */

const esbuild = require("esbuild");
const fs = require("fs");
const http = require("http");
const path = require("path");
const sass = require("sass");

const ROOT = __dirname;
const PORT = Number(process.env.PORT || 8080);
const ASSETS = path.join(ROOT, ".dev/assets");

function ensureDir(dir) {
  fs.mkdirSync(dir, { recursive: true });
}

function compileScss() {
  ensureDir(ASSETS);
  const result = sass.compile(path.join(ROOT, "src/styles/main.scss"), {
    loadPaths: [path.join(ROOT, "src/styles")],
  });
  fs.writeFileSync(path.join(ASSETS, "main.css"), result.css);
}

function contentType(filePath) {
  if (filePath.endsWith(".js")) return "application/javascript";
  if (filePath.endsWith(".css")) return "text/css";
  if (filePath.endsWith(".html")) return "text/html";
  if (filePath.endsWith(".json")) return "application/json";
  if (filePath.endsWith(".webmanifest")) return "application/manifest+json";
  if (filePath.endsWith(".svg")) return "image/svg+xml";
  if (filePath.endsWith(".png")) return "image/png";
  if (filePath.endsWith(".ico")) return "image/x-icon";
  return "application/octet-stream";
}

async function start() {
  ensureDir(ASSETS);
  compileScss();

  const ctx = await esbuild.context({
    entryPoints: [path.join(ROOT, "src/main.js")],
    bundle: true,
    outfile: path.join(ASSETS, "app.js"),
    format: "iife",
    platform: "browser",
    target: ["es2020"],
    sourcemap: true,
    define: {
      "process.env.API_BASE_URL": JSON.stringify(process.env.API_BASE_URL || "http://localhost:8000"),
    },
  });
  await ctx.watch();

  fs.watch(path.join(ROOT, "src/styles"), { recursive: true }, () => {
    try {
      compileScss();
    } catch (err) {
      console.error("SCSS error:", err.message);
    }
  });

  const PUBLIC = path.join(ROOT, "public");

  const server = http.createServer((req, res) => {
    const url = req.url.split("?")[0];
    let filePath;

    if (url === "/" || url === "") {
      filePath = path.join(ROOT, "index.html");
    } else if (url.startsWith("/assets/")) {
      filePath = path.join(ASSETS, url.replace("/assets/", ""));
    } else if (url.startsWith("/public/")) {
      filePath = path.join(PUBLIC, url.replace("/public/", ""));
    } else {
      // Serve public/ at site root (manifest, icons, …) then fall back to index.html
      const fromPublic = path.join(PUBLIC, url.replace(/^\//, ""));
      const fromRoot = path.join(ROOT, url.replace(/^\//, ""));
      if (fs.existsSync(fromPublic) && fs.statSync(fromPublic).isFile()) {
        filePath = fromPublic;
      } else if (fs.existsSync(fromRoot) && fs.statSync(fromRoot).isFile()) {
        filePath = fromRoot;
      } else {
        filePath = path.join(ROOT, "index.html");
      }
    }

    if (!fs.existsSync(filePath) || fs.statSync(filePath).isDirectory()) {
      filePath = path.join(ROOT, "index.html");
    }
    res.writeHead(200, { "Content-Type": contentType(filePath) });
    res.end(fs.readFileSync(filePath));
  });

  server.listen(PORT, () => {
    console.log(`Dev server → http://localhost:${PORT}`);
  });
}

start().catch((err) => {
  console.error(err);
  process.exit(1);
});
