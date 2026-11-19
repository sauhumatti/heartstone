// Opening a pack: a sealed paper lantern is lit, rises into the night and lets
// three lights down; each light, touched, shows what it carried. What the pack
// holds is settled (and kept) the moment the lantern is lit, so closing the
// screen early loses nothing.
import React, { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { artOf } from '../progress/art';
import { cosmetic, type Find, openPack, TIERS } from '../progress/rules';
import { updateProfile, useProfile } from '../progress/store';
import { sfx } from '../sound';
import { CosmeticView, KIND_NAME } from './progressBits';

type Phase = 'sealed' | 'lighting' | 'rising' | 'lights';

const quick = () => typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;

export const PackOpening: React.FC<{ onClose: () => void }> = ({ onClose }) => {
  const profile = useProfile();
  const [phase, setPhase] = useState<Phase>('sealed');
  const [finds, setFinds] = useState<Find[]>([]);
  const [shown, setShown] = useState<boolean[]>([]);
  /** Counts the lanterns opened in this sitting, so each one starts its animations afresh. */
  const [round, setRound] = useState(0);
  const timers = useRef<number[]>([]);

  useEffect(() => () => timers.current.forEach((t) => window.clearTimeout(t)), []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  const later = (ms: number, fn: () => void) => {
    timers.current.push(window.setTimeout(fn, ms));
  };

  const light = () => {
    if (phase !== 'sealed') return;
    let got: Find[] = [];
    updateProfile((p) => {
      const opened = openPack(p, Math.random);
      got = opened.finds;
      return opened.profile;
    });
    if (!got.length) return;
    setFinds(got);
    setShown(got.map(() => false));
    setPhase('lighting');
    sfx.cue('heal');
    const fast = quick();
    later(fast ? 200 : 1100, () => setPhase('rising'));
    later(fast ? 400 : 2500, () => setPhase('lights'));
  };

  const reveal = (i: number) => {
    if (phase !== 'lights' || shown[i]) return;
    const tier = cosmetic(finds[i].id)?.tier;
    sfx.cue(tier === 'gilt' ? 'buff' : 'cardAdded');
    setShown((s) => s.map((v, k) => v || k === i));
  };

  const again = () => {
    timers.current.forEach((t) => window.clearTimeout(t));
    timers.current = [];
    setFinds([]);
    setShown([]);
    setPhase('sealed');
    setRound((n) => n + 1);
  };

  const allShown = phase === 'lights' && shown.every(Boolean);
  const embers = finds.reduce((sum, f) => sum + f.embers, 0);
  const lantern = artOf('pack_sealed');
  const nothing = phase === 'sealed' && profile.packs < 1;

  return createPortal(
    <div className="pack-night" data-phase={phase} role="dialog" aria-modal="true" aria-label="Open a pack">
      <div className="pack-stars" aria-hidden="true" />
      <button type="button" className="chip-btn pack-close" onClick={onClose}>
        Close
      </button>

      {phase !== 'lights' && (
        <div className="pack-stage" key={`lantern-${round}`}>
          <button type="button" className="pack-lantern" onClick={light} disabled={phase !== 'sealed' || nothing} aria-label="Light the lantern">
            <span className="pack-lantern-glow" />
            {lantern ? <img src={lantern} alt="" draggable={false} /> : <span className="pack-lantern-plain" />}
            <span className="pack-lantern-flame" />
          </button>
          <p className="pack-hint">
            {nothing ? 'No lantern to light. Win matches to earn one.' : phase === 'sealed' ? 'Light the lantern' : ' '}
          </p>
          {phase === 'sealed' && profile.packs > 1 && <p className="pack-count">{profile.packs} lanterns waiting</p>}
        </div>
      )}

      {phase === 'lights' && (
        <div className="pack-stage" key={`lights-${round}`}>
          <div className="pack-lights">
            {finds.map((f, i) => {
              const item = cosmetic(f.id)!;
              return shown[i] ? (
                <div className={`find tier-${item.tier} ${f.isNew ? 'is-new' : 'is-again'}`} key={i}>
                  <div className="find-kind">{KIND_NAME[item.kind]}</div>
                  <div className="find-art">
                    <CosmeticView item={item} />
                  </div>
                  <strong>{item.name}</strong>
                  <span className="find-tier">{TIERS[item.tier!].name}</span>
                  <span className="find-note">{f.isNew ? 'New' : `Already yours: +${f.embers} embers`}</span>
                </div>
              ) : (
                <button type="button" className="light" key={i} style={{ ['--i' as any]: i }} onClick={() => reveal(i)} aria-label={`Light ${i + 1} of ${finds.length}: show what it carries`}>
                  <span className="light-core" />
                </button>
              );
            })}
          </div>
          <p className="pack-hint">
            {allShown
              ? embers > 0
                ? `You now have ${profile.embers} embers.`
                : 'All three are new.'
              : 'Touch a light to see what it carries'}
          </p>
          {allShown && (
            <div className="pack-actions">
              {profile.packs > 0 && (
                <button type="button" className="btn primary" onClick={again}>
                  Light another ({profile.packs})
                </button>
              )}
              <button type="button" className={`btn ${profile.packs > 0 ? 'ghost' : 'primary'}`} onClick={onClose}>
                Done
              </button>
            </div>
          )}
        </div>
      )}
    </div>,
    document.body,
  );
};
