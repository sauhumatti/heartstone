// Glue between the Android app and the page, run by the app after every page load
// (see MainActivity). It covers two things until the page handles them itself:
//
//   Back button   The app calls window.onAppBack(); return true if the press was used.
//                 If the page does not define it, the version below is used.
//   Screen on     window.AndroidApp.keepAwake(true|false). If the page calls it
//                 itself it should set window.__appAwakeHandled = true first;
//                 otherwise the screen is kept on while a match is on screen.
(function () {
  var app = window.AndroidApp;
  if (!app || window.__androidShim) return;
  window.__androidShim = true;
  document.documentElement.classList.add('in-android-app');

  if (typeof window.onAppBack !== 'function') {
    window.onAppBack = function () {
      // In a match the page already has a "back": Escape cancels an aim or a choice,
      // and otherwise opens or closes the match menu.
      if (document.querySelector('.arena')) {
        window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
        return true;
      }
      // On a sub-page, its own "back to the menu" button.
      var back = document.querySelector('.page-head .btn.ghost');
      if (back) {
        back.click();
        return true;
      }
      return false; // the main menu: the app asks whether to leave
    };
  }

  var awake = null;
  var pending = false;
  var check = function () {
    pending = false;
    if (window.__appAwakeHandled) return;
    var inMatch = !!document.querySelector('.arena');
    if (inMatch === awake) return;
    awake = inMatch;
    try {
      app.keepAwake(inMatch);
    } catch (e) {
      /* an older app without it */
    }
  };
  new MutationObserver(function () {
    if (pending) return;
    pending = true;
    setTimeout(check, 400);
  }).observe(document.documentElement, { childList: true, subtree: true });
  check();
})();
