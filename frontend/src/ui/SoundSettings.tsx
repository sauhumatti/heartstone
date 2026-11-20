// Music and sound effects: each on or off, each with its own volume. The same controls sit in
// the settings and in the match's pause menu, so the sound can be set while playing.
import React, { useState } from 'react';
import { sfx } from '../sound';

export const SoundSettings: React.FC = () => {
  const [musicOn, setMusicOn] = useState(sfx.musicEnabled);
  const [musicVol, setMusicVol] = useState(sfx.musicVolume);
  const [sfxOn, setSfxOn] = useState(sfx.enabled);
  const [sfxVol, setSfxVol] = useState(sfx.volume);
  return (
    <>
      <div className="settings-group">
        <button
          type="button"
          className={`btn btn-toggle ${musicOn ? 'is-on' : ''}`}
          onClick={() => {
            sfx.setMusicEnabled(!musicOn);
            setMusicOn(!musicOn);
          }}
        >
          <span>Music</span>
          <span className="btn-pip">{musicOn ? 'On' : 'Off'}</span>
        </button>
        <label className="field">
          <span>
            Music volume <em className="field-val">{Math.round(musicVol * 100)}%</em>
          </span>
          <input
            type="range"
            min={0}
            max={1}
            step={0.05}
            value={musicVol}
            onChange={(e) => {
              const v = Number(e.target.value);
              setMusicVol(v);
              sfx.setMusicVolume(v);
            }}
          />
        </label>
      </div>
      <div className="settings-group">
        <button
          type="button"
          className={`btn btn-toggle ${sfxOn ? 'is-on' : ''}`}
          onClick={() => {
            sfx.setEnabled(!sfxOn);
            setSfxOn(!sfxOn);
          }}
        >
          <span>Sound effects</span>
          <span className="btn-pip">{sfxOn ? 'On' : 'Off'}</span>
        </button>
        <label className="field">
          <span>
            Effects volume <em className="field-val">{Math.round(sfxVol * 100)}%</em>
          </span>
          <input
            type="range"
            min={0}
            max={1}
            step={0.05}
            value={sfxVol}
            onChange={(e) => {
              const v = Number(e.target.value);
              setSfxVol(v);
              sfx.setVolume(v);
            }}
            // A tick at the new level when the slider is let go, so it can be heard.
            onPointerUp={() => sfx.cue('uiClick')}
            onKeyUp={() => sfx.cue('uiClick')}
          />
        </label>
      </div>
    </>
  );
};
