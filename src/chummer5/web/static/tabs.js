// WP138: the switch warning's question -- is another tab of this app open in this browser?
//
// Switching the open character (open, new, upload, deleting the open one) affects every tab of
// the app in this browser: they share one server-side character, and the others' next edit is
// refused until they reload. Each such control carries `hx-confirm`. This script lets that
// confirmation appear only when it matters: on `htmx:confirm`, it asks the other tabs over a
// BroadcastChannel and waits briefly for an answer. No answer, no dialog; the request just goes.
//
// Asked at click time, not tracked by heartbeat: a background tab's timers are throttled (to once
// a minute after a while, in Chrome), but it still receives and answers messages. Other devices
// can't be seen from here, and aren't affected anyway (the server's revision check covers them).
// A static file, not inline, so a strict Content-Security-Policy (WP141) can allow it.
//
// WP139 adds two things:
// - A control with `data-confirm="always"` (Delete on the character list) always asks. When
//   another tab is open, its `data-confirm-tabs` text, if any, is added to the question (deleting
//   the open character switches this browser to a new one).
// - A page whose <body> has `data-tabs-passive` (the character list) asks, but doesn't answer:
//   switching characters elsewhere doesn't break it, so it is no reason to warn.
(function () {
  if (!("BroadcastChannel" in window)) return; // then htmx simply always asks
  var CHANNEL = "chummer5-tabs";
  var WAIT_MS = 250;
  var me = Math.random().toString(36).slice(2);
  var channel = new BroadcastChannel(CHANNEL);
  var waiting = null; // the pending question's resolver

  channel.onmessage = function (event) {
    var message = event.data || {};
    if (message.from === me) return;
    // Read at message time: this script runs in <head>, before <body> exists.
    if (message.type === "ping" && !document.body.hasAttribute("data-tabs-passive")) {
      channel.postMessage({ type: "pong", from: me, to: message.from });
    } else if (message.type === "pong" && message.to === me && waiting) {
      waiting(true);
    }
  };

  function anotherTabIsOpen(callback) {
    var answered = false;
    function finish(open) {
      if (answered) return;
      answered = true;
      waiting = null;
      callback(open);
    }
    waiting = finish;
    channel.postMessage({ type: "ping", from: me });
    setTimeout(function () {
      finish(false);
    }, WAIT_MS);
  }

  document.addEventListener("htmx:confirm", function (event) {
    var question = event.detail.question;
    if (!question) return; // not a confirmed control: htmx goes ahead as usual
    event.preventDefault();
    var elt = event.detail.elt;
    var always = elt.getAttribute("data-confirm") === "always";
    var extra = elt.getAttribute("data-confirm-tabs");
    anotherTabIsOpen(function (open) {
      if (open && extra) question += "\n\n" + extra;
      if ((!open && !always) || window.confirm(question)) event.detail.issueRequest(true);
    });
  });
})();
