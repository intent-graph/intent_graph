// Mocked VS Code webview API + host-side messenger for the Playwright harness.
//
// Design:
//  - Webview code calls acquireVsCodeApi() once; we return a shim whose
//    postMessage delivers webview->host messages to our handlers.
//  - Host->webview messages are delivered via window.dispatchEvent so
//    vscode-messenger-webview's window.addEventListener('message', ...)
//    inside Messenger.start() picks them up.
//  - Wire envelope shape (vscode-messenger-common/messages):
//      request:      { sender?, receiver, method, id, params }
//      response:     { sender?, receiver, id, result | error }
//      notification: { sender?, receiver, method, params }
//    Messenger.processMessage ignores messages whose receiver.type === 'extension'.
//    So host->webview messages must use a non-extension receiver. The webview's
//    own messenger sets BROADCAST as default receiver when none matches; we use
//    { type: 'broadcast' } which matches any handler.
//
// Tests interact via window.__igTestBus:
//   bus.handleRequest(method, handler)   register host-side request handler
//   bus.notify(method, params)            push a notification to the webview
//   bus.outbound                          array of all webview->host messages
//   bus.waitFor(predicate, timeoutMs)     resolves to the first outbound message
//                                         matching predicate; rejects on timeout
//   bus.reset()                            clear outbound log & handlers

(function installShim() {
  const HOST = { type: 'extension' };
  const BROADCAST = { type: 'broadcast' };

  const outbound = [];
  const requestHandlers = new Map();
  const waiters = [];

  function dispatchInbound(msg) {
    // Use MessageEvent so window.addEventListener('message', ...) in
    // vscode-messenger-webview's Messenger.start() receives it.
    window.dispatchEvent(new MessageEvent('message', { data: msg }));
  }

  function handleOutbound(msg) {
    outbound.push(msg);
    // Wake any waiters whose predicate matches.
    for (let i = waiters.length - 1; i >= 0; i--) {
      const w = waiters[i];
      try {
        if (w.predicate(msg)) {
          waiters.splice(i, 1);
          clearTimeout(w.timer);
          w.resolve(msg);
        }
      } catch (err) {
        waiters.splice(i, 1);
        clearTimeout(w.timer);
        w.reject(err);
      }
    }

    // If it's a request, route to a registered handler (if any) and
    // synthesise a response back to the webview.
    if (msg.id && msg.method) {
      const handler = requestHandlers.get(msg.method);
      if (handler) {
        Promise.resolve()
          .then(() => handler(msg.params))
          .then((result) => {
            dispatchInbound({
              receiver: BROADCAST,
              sender: HOST,
              id: msg.id,
              result
            });
          })
          .catch((err) => {
            dispatchInbound({
              receiver: BROADCAST,
              sender: HOST,
              id: msg.id,
              error: { message: String(err) }
            });
          });
      }
      // No handler registered => deliberately silent. Tests that need a
      // response should register a handler before triggering the request.
    }
  }

  const vscodeApi = {
    postMessage(msg) {
      handleOutbound(msg);
    },
    getState() {
      return null;
    },
    setState(_state) {
      // no-op
    }
  };

  // The webview's getVsCodeApi() calls acquireVsCodeApi() exactly once.
  window.acquireVsCodeApi = function acquireVsCodeApi() {
    return vscodeApi;
  };

  window.__igTestBus = {
    HOST,
    BROADCAST,
    outbound,

    handleRequest(method, handler) {
      requestHandlers.set(method, handler);
    },

    unhandleRequest(method) {
      requestHandlers.delete(method);
    },

    notify(method, params) {
      dispatchInbound({
        receiver: BROADCAST,
        sender: HOST,
        method,
        params
      });
    },

    waitFor(predicate, timeoutMs = 5000) {
      // Match against already-captured outbound first.
      const existing = outbound.find((m) => {
        try { return predicate(m); } catch { return false; }
      });
      if (existing) return Promise.resolve(existing);

      return new Promise((resolve, reject) => {
        const timer = setTimeout(() => {
          const idx = waiters.findIndex((w) => w.timer === timer);
          if (idx >= 0) waiters.splice(idx, 1);
          reject(new Error(`waitFor timed out after ${timeoutMs}ms`));
        }, timeoutMs);
        waiters.push({ predicate, resolve, reject, timer });
      });
    },

    reset() {
      outbound.length = 0;
      requestHandlers.clear();
      while (waiters.length) {
        const w = waiters.pop();
        clearTimeout(w.timer);
        w.reject(new Error('bus reset'));
      }
    }
  };
})();
