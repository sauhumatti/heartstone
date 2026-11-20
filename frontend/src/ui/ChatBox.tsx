// A line of free text to say at the table, under the ready-made lines and in the log.
// Against Antigravity it answers; in a friend match the friend reads it.
import React, { useState } from 'react';

export const CHAT_MAX = 160;

export const ChatBox: React.FC<{ placeholder: string; onSend: (text: string) => void; autoFocus?: boolean }> = ({
  placeholder,
  onSend,
  autoFocus,
}) => {
  const [text, setText] = useState('');
  const line = text.trim();
  return (
    <form
      className="chat-box"
      onSubmit={(e) => {
        e.preventDefault();
        if (!line) return;
        onSend(line);
        setText('');
      }}
    >
      <input
        type="text"
        value={text}
        maxLength={CHAT_MAX}
        placeholder={placeholder}
        aria-label={placeholder}
        autoComplete="off"
        enterKeyHint="send"
        autoFocus={autoFocus}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          // Escape leaves the text box instead of opening the menu.
          if (e.key === 'Escape') {
            e.stopPropagation();
            e.currentTarget.blur();
          }
        }}
      />
      <button type="submit" className="chip-btn" disabled={!line}>
        Send
      </button>
    </form>
  );
};
