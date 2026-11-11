/**
 * Odoo-style asset bundling: compile SCSS + bundle OWL JS for production.
 */

const esbuild = require("esbuild");
const fs = require("fs");
const path = require("path");
const sass = require("sass");

const ROOT = __dirname;
const DIST = path.join(ROOT, "dist");
const ASSETS = path.join(DIST, "assets");

function ensureDir(dir) {
  fs.mkdirSync(dir, { recursive: true });
}

function copyDir(src, dest) {
  if (!fs.existsSync(src)) return;
  ensureDir(dest);
  for (const entry of fs.readdirSync(src, { withFileTypes: true })) {
    const from = path.join(src, entry.name);
    const to = path.join(dest, entry.name);
    if (entry.isDirectory()) copyDir(from, to);
    else fs.copyFileSync(from, to);
  }
}

async function build() {
  ensureDir(ASSETS);

  const scss = sass.compile(path.join(ROOT, "src/styles/main.scss"), {
    loadPaths: [path.join(ROOT, "src/styles")],
  });
  fs.writeFileSync(path.join(ASSETS, "main.css"), scss.css);

  await esbuild.build({
    entryPoints: [path.join(ROOT, "src/main.js")],
    bundle: true,
    outfile: path.join(ASSETS, "app.js"),
    format: "iife",
    platform: "browser",
    target: ["es2020"],
    minify: true,
    sourcemap: true,
    define: {
      "process.env.API_BASE_URL": JSON.stringify(process.env.API_BASE_URL || ""),
    },
  });

  fs.copyFileSync(path.join(ROOT, "index.html"), path.join(DIST, "index.html"));
  copyDir(path.join(ROOT, "public"), DIST);

  console.log("Build complete → dist/");
}

build().catch((err) => {
  console.error(err);
  process.exit(1);
});
