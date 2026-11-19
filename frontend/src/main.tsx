import React from 'react';
import ReactDOM from 'react-dom/client';
import '@fontsource-variable/fraunces/opsz.css';
import '@fontsource-variable/fraunces/opsz-italic.css';
import '@fontsource-variable/inter';
import { startAppUpdates } from './appUpdate';
import { BUNDLED, url } from './paths';
import { App } from './App';
import './styles/base.css';
import './styles/pieces.css';
import './styles/board.css';
import './styles/screens.css';
import './styles/progress.css';
// Last: it adjusts everything above for small screens and touch.
import './styles/mobile.css';

ReactDOM.createRoot(document.getElementById('root')!).render(<App />);

// An installed app: say that this version of the page started (one that never does is dropped
// by the app), and look for a newer one. Does nothing in a browser.
void startAppUpdates();

// Installable app: the service worker keeps the shell and card art on the device.
// (A packaged app has all its files inside it and needs none.)
if (import.meta.env.PROD && !BUNDLED && 'serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register(url('sw.js'), { scope: url('./') }).catch(() => {
      /* not a secure page, or blocked: the game works without it */
    });
  });
}
