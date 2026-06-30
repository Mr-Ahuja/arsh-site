import { create } from "zustand";

export interface EngineStatus {
  running: boolean;
  mode: string | null;
  strategy: string | null;
  run_id: number | null;
  safe_mode: boolean;
  safe_mode_reason: string | null;
}

export interface ActivityItem {
  id: string;
  kind: string;
  payload: Record<string, unknown>;
  ts: number; // Date.now()
}

export interface LivePosition {
  ltp: number;
  pnl: number;
  in_position: boolean;
}

interface EngineState {
  status: EngineStatus;
  position: LivePosition;
  activity: ActivityItem[];
  wsConnected: boolean;

  setStatus: (s: EngineStatus) => void;
  setWsConnected: (v: boolean) => void;
  handleEvent: (kind: string, payload: Record<string, unknown>) => void;
  clearActivity: () => void;
}

const DEFAULT_STATUS: EngineStatus = {
  running: false,
  mode: null,
  strategy: null,
  run_id: null,
  safe_mode: false,
  safe_mode_reason: null,
};

const DEFAULT_POSITION: LivePosition = { ltp: 0, pnl: 0, in_position: false };

const ACTIVITY_EVENT_KINDS = new Set([
  "engine_started",
  "engine_stopped",
  "kill_switch",
  "trade_closed",
  "order_fill",
  "position_adopted",
  "alert",
]);

export const useEngineStore = create<EngineState>((set) => ({
  status: DEFAULT_STATUS,
  position: DEFAULT_POSITION,
  activity: [],
  wsConnected: false,

  setStatus(s) {
    set({ status: s });
  },

  setWsConnected(v) {
    set({ wsConnected: v });
  },

  handleEvent(kind, payload) {
    // Live tick → update position overlay
    if (kind === "tick") {
      set({
        position: {
          ltp: payload.ltp as number,
          pnl: payload.pnl as number,
          in_position: payload.in_position as boolean,
        },
      });
      return;
    }

    // Engine lifecycle → sync status flags immediately (poll will reconcile)
    if (kind === "engine_started") {
      set((s) => ({
        status: {
          ...s.status,
          running: true,
          mode: payload.mode as string,
          strategy: payload.strategy as string,
          run_id: payload.run_id as number,
        },
      }));
    }
    if (kind === "engine_stopped" || kind === "kill_switch") {
      set((s) => ({ status: { ...s.status, running: false } }));
    }

    // Activity-worthy events → push to feed (cap at 50)
    if (ACTIVITY_EVENT_KINDS.has(kind)) {
      const item: ActivityItem = { id: crypto.randomUUID(), kind, payload, ts: Date.now() };
      set((s) => ({ activity: [item, ...s.activity].slice(0, 50) }));
    }
  },

  clearActivity() {
    set({ activity: [] });
  },
}));

// ── Singleton WS manager (lives outside React) ─────────────────────────────────

let _ws: WebSocket | null = null;
let _retryTimer: ReturnType<typeof setTimeout> | null = null;
let _retryDelay = 1000;
let _destroyed = false;

export function connectEngineWs(): void {
  if (_ws || _destroyed) return;
  _doConnect();
}

export function disconnectEngineWs(): void {
  _destroyed = true;
  _ws?.close();
  _ws = null;
  if (_retryTimer) clearTimeout(_retryTimer);
}

function _doConnect(): void {
  if (_destroyed) return;
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  const url = `${proto}//${window.location.host}/api/ws`;
  const ws = new WebSocket(url);
  _ws = ws;

  ws.onopen = () => {
    _retryDelay = 1000;
    useEngineStore.getState().setWsConnected(true);
  };

  ws.onmessage = (e) => {
    try {
      const msg = JSON.parse(e.data) as { kind: string; payload: Record<string, unknown> };
      useEngineStore.getState().handleEvent(msg.kind, msg.payload);
    } catch {
      // ignore malformed frames
    }
  };

  ws.onclose = (ev) => {
    _ws = null;
    useEngineStore.getState().setWsConnected(false);
    if (_destroyed) return;
    if (ev.code === 4001) return; // auth rejected — don't retry
    _retryTimer = setTimeout(() => {
      _retryDelay = Math.min(_retryDelay * 2, 30_000);
      _doConnect();
    }, _retryDelay);
  };

  ws.onerror = () => {
    ws.close();
  };
}
