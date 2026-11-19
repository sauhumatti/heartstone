// What the player sees of playing without a server: the engine getting ready
// on this device, and keeping the whole game on the device for offline play.
import React, { useEffect, useState } from 'react';
import { runtimeProgress, watchRuntime } from '../local/client';
import { makeAvailableOffline, offlineState, watchOffline, type OfflineState } from '../local/offline';
import type { RuntimeProgress } from '../local/protocol';

export function useRuntime(): RuntimeProgress {
  const [p, setP] = useState(runtimeProgress);
  useEffect(() => watchRuntime(setP), []);
  return p;
}

export function useOffline(): OfflineState {
  const [s, setS] = useState(offlineState);
  useEffect(() => {
    setS(offlineState());
    return watchOffline(setS);
  }, []);
  return s;
}

const megabytes = (bytes: number) => `${Math.max(1, Math.round(bytes / 1_000_000))} MB`;

/** One line saying how far the engine is, or nothing once it runs. */
export function runtimeLine(p: RuntimeProgress): string {
  switch (p.phase) {
    case 'download':
      return p.total > 0 ? `Loading the game engine… ${Math.round((p.loaded / p.total) * 100)}%` : 'Loading the game engine…';
    case 'starting':
      return 'Starting the game engine…';
    case 'cards':
      return 'Setting out the cards…';
    case 'failed':
      return `The game engine could not start: ${p.message}`;
    default:
      return '';
  }
}

/** Shown over everything while a match waits for the engine to start (the first start takes a few seconds). */
export const EngineStarting: React.FC<{ waiting: boolean }> = ({ waiting }) => {
  const p = useRuntime();
  if (!waiting || p.phase === 'ready' || p.phase === 'idle' || p.phase === 'failed') return null;
  // Loading is most of the wait when nothing is stored yet; starting is the rest.
  const share = p.phase === 'download' ? (p.total > 0 ? (p.loaded / p.total) * 0.7 : 0.05) : p.phase === 'starting' ? 0.8 : 0.95;
  return (
    <div className="modal engine-start" role="status" aria-live="polite">
      <div className="sheet">
        <h2>Getting ready</h2>
        <p className="sheet-sub">{runtimeLine(p)}</p>
        <div className="meter" style={{ ['--share' as any]: share }}>
          <i />
        </div>
        <p className="note">The game runs on this device. This takes a moment the first time.</p>
      </div>
    </div>
  );
};

/** In the menu's footer: keep the game on this device, and how that is going. */
export const OfflineLine: React.FC = () => {
  const s = useOffline();
  if (s.status === 'bundled' || s.status === 'unsupported') return null;
  let body: React.ReactNode;
  if (s.status === 'ready') {
    body = 'stored for playing offline';
  } else if (s.status === 'working') {
    body = `storing the game on this device… ${s.total > 0 ? Math.round((s.done / s.total) * 100) : 100}%`;
  } else {
    body = (
      <>
        {s.status === 'failed' && <>could not store the game ({s.message}) · </>}
        <button type="button" className="link" onClick={() => void makeAvailableOffline()}>
          {s.status === 'failed' ? 'Try again' : `Make available offline (${megabytes(s.bytes)})`}
        </button>
      </>
    );
  }
  return (
    <>
      {' · '}
      <span className="offline-line">{body}</span>
    </>
  );
};
