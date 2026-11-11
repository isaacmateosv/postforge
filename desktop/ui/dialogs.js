// Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
// SPDX-License-Identifier: GPL-3.0-or-later
"use strict";
(() => {
// Only the active, open dialog is modal to assistive technology. A permanent
// aria-modal on hidden dialogs can make later dialogs unreachable in WebKit.
const dialogStack = [];
function syncDialogAccessibility() {
  const active = dialogStack.filter(dialog => dialog.open).at(-1);
  document.querySelectorAll("dialog").forEach(dialog => {
    if (dialog === active) dialog.setAttribute("aria-modal", "true");
    else dialog.removeAttribute("aria-modal");
  });
}
function openDialog(id) {
  const dialog = document.getElementById(id);
  if (dialog.open) return;
  // Keep the active dialog first in document order as well as in the top layer.
  // WebKit can otherwise expose only the earlier, now-closed dialog to AX.
  for (let i=dialogStack.length-1;i>=0;i--) if (dialogStack[i] === dialog) dialogStack.splice(i,1);
  document.body.prepend(dialog);
  dialog.hidden = false;
  dialogStack.push(dialog);
  dialog.showModal();
  syncDialogAccessibility();
}
document.querySelectorAll("dialog").forEach(dialog => dialog.addEventListener("close", () => {
  if (dialog.open) return; // A confirmation may reopen the same dialog before the close event runs.
  dialog.hidden = true;
  for (let i=dialogStack.length-1;i>=0;i--) if (!dialogStack[i].open) dialogStack.splice(i,1);
  syncDialogAccessibility();
}));

window.PostForgeDialogs = {open: openDialog};
})();
