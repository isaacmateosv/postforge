// Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
// SPDX-License-Identifier: GPL-3.0-or-later
"use strict";
window.PostForgeCompletionTimer = {
  create({onTick, onDone, isActive = () => true, schedule = setInterval, cancel = clearInterval}) {
    let handle = null, remaining = 0, running = false;
    function pause() { if (handle !== null) cancel(handle); handle = null; }
    function stop() { running = false; pause(); }
    function resume() {
      if (!running || handle !== null) return;
      handle = schedule(() => {
        if (!isActive()) return;
        remaining -= 1; onTick(remaining);
        if (remaining <= 0) { stop(); onDone(); }
      }, 1000);
    }
    return {
      stop, pause, resume,
      start(seconds = 8) {
        stop(); remaining = seconds; running = true; onTick(remaining); resume();
      }
    };
  }
};
