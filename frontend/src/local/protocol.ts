// What the page and the engine worker say to each other.

/** How far the on-device engine is in getting ready. */
export type RuntimeProgress =
  | { phase: 'idle' }
  | { phase: 'download'; loaded: number; total: number }
  | { phase: 'starting' }
  | { phase: 'cards' }
  | { phase: 'ready' }
  | { phase: 'failed'; message: string };

export interface FileEntry {
  path: string;
  bytes: number;
}

export interface InitMessage {
  kind: 'init';
  id: number;
  /** The page's own address: every path below is relative to it. */
  base: string;
  runtimeDir: string;
  runtimeFiles: FileEntry[];
  engine: string;
}

export interface CallMessage {
  kind: 'call';
  id: number;
  method: string;
  args: Record<string, unknown>;
}

export type ToWorker = InitMessage | CallMessage;

export type FromWorker =
  | { id: number; ok: unknown }
  | { id: number; error: string }
  /** Something happened in a match without the page asking: the opponent moved. */
  | { push: string; payload: unknown }
  /** Something the player should be told: a kept match could not be continued (`gone` is its id, if it was open). */
  | { notice: string; gone?: string }
  | { progress: RuntimeProgress };
