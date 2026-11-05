// Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
// SPDX-License-Identifier: GPL-3.0-or-later
// See COPYRIGHT and LICENSE for copying terms and the no-warranty notice.
// Pre-boot patches for the pinned Evolution API v2.3.7 image (README Gotcha #14).
//
// 1. Receipts. Baileys reports who received and who viewed a WhatsApp status as
//    `message-receipt.update`. Evolution's handler for that event only marks incoming chats as
//    read, so status receipts are lost. This adds one step to the handler: receipts for statuses
//    this instance sent are stored in "MessageUpdate" (one row per recipient and receipt type:
//    DELIVERY_ACK, READ), which is where Evolution keeps per-participant message updates.
//    broadcast-story.sh --history counts them, and the menu bar app lists the viewers.
//
// 2. Other people's statuses. Baileys drops all `status@broadcast` traffic, receipts included,
//    unless the instance setting readStatus is on (Evolution's shouldIgnoreJid). wa_settings.py
//    turns it on only when this patch is in place, because the patch skips the side effect:
//    without it, Evolution would store every status a contact posts (and look up a profile
//    picture for each). Statuses this account posts, here or from the phone, are still stored,
//    so their receipts can be too. In v2.3.7 readStatus does nothing else: its "mark statuses as
//    read" branch compares a message id with "status@broadcast" and never runs. A newer image
//    that fixed it would view contacts' statuses for the account, but they never get that far
//    while this patch is applied.
//
// docker-compose.yml runs this before Evolution starts, on the container's own copy of
// dist/main.js. Every boot patches the image's original file (kept next to it as .pm-orig), so a
// restarted container runs this version of the patches, not whatever an earlier boot left. It
// always exits 0: if the code it expects is missing (another image), Evolution boots unpatched
// and the log says so.
const fs = require("fs");

const FILE = process.env.PM_PATCH_FILE || "/evolution/dist/main.js";
const ORIG = FILE + ".pm-orig";

// Single-quoted on purpose: ${...} below are Prisma query parameters, not interpolations here.
const SQL =
  'INSERT INTO "MessageUpdate" ("id","keyId","remoteJid","fromMe","participant","status","messageId","instanceId") ' +
  'SELECT gen_random_uuid()::text, m."key"->>\'id\', \'status@broadcast\', true, ${pmJid}, ${pmSt}, m."id", m."instanceId" ' +
  'FROM "Message" m WHERE m."instanceId" = ${this.instanceId} AND m."key"->>\'id\' = ${pmK.id} ' +
  'AND m."key"->>\'remoteJid\' = \'status@broadcast\' AND (m."key"->>\'fromMe\')::boolean ' +
  'AND NOT EXISTS (SELECT 1 FROM "MessageUpdate" u WHERE u."messageId" = m."id" ' +
  'AND u."participant" = ${pmJid} AND u."status" = ${pmSt}) LIMIT 1';

const PATCHES = [
  {
    name: "status receipts",
    mark: "/*pm-status-receipts*/",
    // The minified handler starts with `if(<events>["message-receipt.update"]){`.
    anchor: /if\((\w+)\["message-receipt\.update"\]\)\{/g,
    needs: ["this.prismaRepository.$executeRaw`", "this.instanceId", "this.client.signalRepository.lidMapping.getPNForLID"],
    // Receipts name people by LID (a private WhatsApp id, "...@lid"); the phone number is stored
    // instead whenever Baileys knows it (it learns it for every number a status is sent to), so
    // receipts match contact names and the account’s own phone can be left out of the counts.
    // Every receipt gets one log line ("pm-status-receipts: READ status@broadcast from ... stored").
    // Baileys only emits this event for group and status messages, and this instance sends no
    // group messages, so the volume stays low.
    code: (mark, eventsVar) =>
      mark +
      "await(async pmEvents=>{for(const pmR of pmEvents||[]){try{" +
      "const pmK=pmR&&pmR.key||{},pmC=pmR&&pmR.receipt||{};" +
      'let pmJid=pmC.userJid;const pmSt=typeof pmC.readTimestamp=="number"?"READ":"DELIVERY_ACK";let pmN=0;' +
      'if(pmJid&&pmJid.endsWith("@lid")){try{' +
      "const pmPn=await this.client.signalRepository.lidMapping.getPNForLID(pmJid);" +
      'if(pmPn)pmJid=pmPn.replace(/:\\d+@/,"@")}catch(pmE){}}' +
      'if(pmK.remoteJid==="status@broadcast"&&pmK.fromMe&&pmK.id&&pmJid){' +
      "pmN=await this.prismaRepository.$executeRaw`" + SQL + "`}" +
      'this.logger.info("pm-status-receipts: "+pmSt+" "+pmK.remoteJid+" from "+pmJid+" id="+pmK.id+' +
      '" fromMe="+pmK.fromMe+(pmN?" stored":" not stored"))' +
      '}catch(pmErr){this.logger.warn("pm-status-receipts: "+(pmErr&&pmErr.message))}}})(' +
      eventsVar + '["message-receipt.update"]);',
  },
  {
    name: "contact statuses skipped",
    mark: "/*pm-skip-contact-statuses*/",
    // The Baileys upsert handler opens with
    // `"messages.upsert":async({messages:<list>,type:..,requestId:..},<settings>)=>{try{for(let <msg> of <list>){`.
    anchor: /"messages\.upsert":async\(\{messages:(\w+),type:\w+,requestId:\w+\},\w+\)=>\{try\{for\(let (\w+) of \1\)\{/g,
    needs: [],
    code: (mark, listVar, msgVar) =>
      mark + "if(" + msgVar + "?.key?.remoteJid===\"status@broadcast\"&&!" + msgVar + "?.key?.fromMe)continue;",
  },
];

function apply(src, patch) {
  const hits = [...src.matchAll(patch.anchor)];
  if (hits.length !== 1) {
    return [src, "NOT applied: expected 1 anchor, found " + hits.length + " (image changed?)"];
  }
  for (const needed of patch.needs) {
    if (!src.includes(needed)) return [src, "NOT applied: " + needed + " not found (image changed?)"];
  }
  const out = src.replace(patch.anchor, (match, ...groups) => match + patch.code(patch.mark, ...groups));
  return [out, "applied"];
}

function main() {
  let src;
  try {
    if (!fs.existsSync(ORIG)) fs.copyFileSync(FILE, ORIG);
    src = fs.readFileSync(ORIG, "utf8");
  } catch (err) {
    return ["skipped: cannot read " + FILE + " (" + err.message + ")"];
  }
  if (src.includes("/*pm-")) {
    // Only a container patched before .pm-orig existed; recreating it starts from the image.
    return ["NOT re-applied: " + ORIG + " is already patched (docker compose up -d --force-recreate evolution-api)"];
  }
  const results = [];
  let out = src;
  for (const patch of PATCHES) {
    let result;
    try {
      [out, result] = apply(out, patch);
    } catch (err) {
      result = "NOT applied: " + err.message;
    }
    results.push(patch.name + ": " + result);
  }
  fs.writeFileSync(FILE, out);
  return results;
}

let results;
try {
  results = main();
} catch (err) {
  results = ["NOT applied: " + err.message];
}
for (const line of results) console.log("[pm-patch] " + line);
