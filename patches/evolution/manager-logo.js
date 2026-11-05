// Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
// SPDX-License-Identifier: GPL-3.0-or-later
// See COPYRIGHT and LICENSE for copying terms and the no-warranty notice.
// Pre-boot patch for the pinned Evolution API v2.3.7 image: the Evolution Manager login page.
//
// The manager loads its logo from https://evolution-api.com/files/evo/evolution-logo(-white).svg. Those
// files no longer exist (HTTP 404), so the login page shows a broken-image icon above the form. This copies
// two plain wordmarks next to the manager's own assets and points the two URLs at them, so the page needs no
// internet for its logo.
//
// docker-compose.yml runs this before Evolution starts. It is idempotent (re-running changes nothing) and
// always exits 0: if the manager is missing or already fixed, Evolution just boots.
const fs = require("fs");
const path = require("path");

const ASSETS = process.env.PM_MANAGER_ASSETS || "/evolution/manager/dist/assets";
const SOURCE = process.env.PM_LOGO_SOURCE || path.join(__dirname, "assets");
const LOGOS = {
  "https://evolution-api.com/files/evo/evolution-logo-white.svg": "postforge-evolution-logo-white.svg",
  "https://evolution-api.com/files/evo/evolution-logo.svg": "postforge-evolution-logo.svg",
};

try {
  if (!fs.existsSync(ASSETS)) {
    console.log("[pm-patch] manager-logo: no manager assets at " + ASSETS + "; skipped");
    process.exit(0);
  }
  for (const file of Object.values(LOGOS)) fs.copyFileSync(path.join(SOURCE, file), path.join(ASSETS, file));
  let patched = 0;
  for (const name of fs.readdirSync(ASSETS).filter((n) => n.endsWith(".js"))) {
    const target = path.join(ASSETS, name);
    let text = fs.readFileSync(target, "utf8");
    let changed = false;
    for (const [url, file] of Object.entries(LOGOS)) {
      if (text.includes(url)) {
        text = text.split(url).join("/assets/" + file);
        changed = true;
      }
    }
    if (changed) {
      fs.writeFileSync(target, text);
      patched++;
    }
  }
  console.log("[pm-patch] manager-logo: " + (patched ? "logo URLs rewritten in " + patched + " file(s)" : "already fixed"));
} catch (error) {
  console.log("[pm-patch] manager-logo: skipped (" + error.message + ")");
}
process.exit(0);
