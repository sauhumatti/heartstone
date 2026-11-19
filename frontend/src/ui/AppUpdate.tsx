// The installed app's version and its updates, as one line in the menu's
// footer. Nothing is shown in a browser (see ../appUpdate.ts).
import React, { useEffect, useState } from 'react';
import {
  bundleLabel,
  checkForUpdates,
  downloadUpdate,
  openAppDownload,
  restartForUpdate,
  updateState,
  watchUpdates,
  type UpdateState,
} from '../appUpdate';

export function useAppUpdate(): UpdateState {
  const [s, setS] = useState(updateState);
  useEffect(() => {
    setS(updateState());
    return watchUpdates(setS);
  }, []);
  return s;
}

const megabytes = (bytes: number) => `${Math.max(1, Math.round(bytes / 1_000_000))} MB`;

const Do: React.FC<{ onClick: () => void; children: React.ReactNode }> = ({ onClick, children }) => (
  <button type="button" className="link" onClick={onClick}>
    {children}
  </button>
);

export const AppUpdateLine: React.FC = () => {
  const s = useAppUpdate();
  if (s.status === 'off') return null;

  let body: React.ReactNode;
  switch (s.status) {
    case 'idle':
      body = <Do onClick={() => void checkForUpdates()}>Check for updates</Do>;
      break;
    case 'checking':
      body = 'checking for updates…';
      break;
    case 'current':
      body = (
        <>
          up to date · <Do onClick={() => void checkForUpdates()}>Check again</Do>
        </>
      );
      break;
    case 'available':
      body = (
        <>
          an update is available · <Do onClick={() => void downloadUpdate()}>Download ({megabytes(s.bytes)})</Do>
        </>
      );
      break;
    case 'downloading':
      body = `downloading the update… ${s.total > 0 ? Math.min(100, Math.round((s.received / s.total) * 100)) : 0}%`;
      break;
    case 'ready':
      body = (
        <>
          update ready, used from the next start · <Do onClick={restartForUpdate}>Restart now</Do>
        </>
      );
      break;
    case 'failed':
      body = (
        <>
          update failed: {s.reason} · <Do onClick={() => void checkForUpdates()}>Try again</Do>
        </>
      );
      break;
    case 'app':
      body = (
        <>
          {s.needed ? 'the next update needs a new version of the app' : 'a new version of the app is available'}
          {s.versionName ? ` (${s.versionName})` : ''} ·{' '}
          <Do onClick={() => void openAppDownload()}>Download it{s.bytes > 0 ? ` (${megabytes(s.bytes)})` : ''}</Do>
        </>
      );
      break;
  }

  return (
    <span className="app-update" role="status" aria-live="polite">
      <br />
      Version {s.appVersion}
      {s.bundle ? ` · ${bundleLabel(s.bundle)}` : ''}
      {' · '}
      {body}
      {s.rolledBack && s.status !== 'downloading' && s.status !== 'ready' ? ' · the last update did not start and was removed' : ''}
    </span>
  );
};
