// Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
// SPDX-License-Identifier: GPL-3.0-or-later
// See COPYRIGHT and LICENSE for copying terms and the no-warranty notice.
import { createHash, timingSafeEqual } from "node:crypto";
import { readFileSync } from "node:fs";
import { Transform } from "node:stream";
import { pipeline } from "node:stream/promises";
import { downloadContentFromMessage } from "baileys/lib/Utils/messages-media.js";

// Run inside the pinned Evolution image. Only metadata goes through stdin.
try {
  const { mediaKey, fileSha256, directPath, size } = JSON.parse(readFileSync(0, "utf8"));
  const key = Buffer.from(mediaKey, "base64");
  const expected = Buffer.from(fileSha256, "base64");
  const url = new URL(directPath, "https://mmg.whatsapp.net");
  if (key.length !== 32 || expected.length !== 32 ||
      !directPath.startsWith("/") || url.origin !== "https://mmg.whatsapp.net" ||
      !Number.isSafeInteger(size) || size < 1 || size > 256 * 1024 * 1024) {
    throw new Error("Invalid WhatsApp video metadata");
  }

  const hash = createHash("sha256");
  let received = 0;
  const verify = new Transform({
    transform(chunk, _encoding, callback) {
      received += chunk.length;
      if (received > size) {
        callback(new Error("Video exceeded its declared size"));
        return;
      }
      hash.update(chunk);
      callback(null, chunk);
    },
    flush(callback) {
      if (received !== size || !timingSafeEqual(hash.digest(), expected)) {
        callback(new Error("Video size or hash did not match"));
        return;
      }
      callback();
    },
  });
  const source = await downloadContentFromMessage({ mediaKey: key, url: url.href }, "video");
  await pipeline(source, verify, process.stdout);
} catch {
  // Avoid leaking CDN URLs or media keys through the logs.
  process.stderr.write("WhatsApp video stream failed or could not be verified.\n");
  process.exitCode = 1;
}
