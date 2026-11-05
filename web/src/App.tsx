import { useCallback, useEffect, useRef, useState } from "react";
import {
  AudioLines,
  Check,
  ChevronRight,
  CircleHelp,
  Download,
  Headphones,
  LoaderCircle,
  LockKeyhole,
  Pause,
  Play,
  Plus,
  Radio,
  RotateCcw,
  Trash2,
  Upload,
  X,
} from "lucide-react";
type Segment = {
  id: number;
  start: number;
  end: number;
  speaker: string;
  text: string;
};
type Item = {
  id: string;
  segment_id: number;
  text: string;
  owner: string;
  due_date: string | null;
  kind: "action" | "question";
  accepted: boolean;
  version: number;
};
type Recording = {
  id: string;
  title: string;
  status: string;
  duration: number;
  fixture: boolean;
  error: string | null;
  segments: Segment[];
  commitments?: Item[];
};
const pending = (s: string) =>
  ["queued", "transcribing", "extracting"].includes(s);
const stamp = (s: number) =>
  `${Math.floor(s / 60)
    .toString()
    .padStart(2, "0")}:${Math.floor(s % 60)
    .toString()
    .padStart(2, "0")}`;
const statuses: Record<string, string> = {
  queued: "Waiting for worker",
  transcribing: "Loading fixture transcript",
  extracting: "Mapping fixture commitments",
  ready: "Ready for review",
  failed: "Provider unavailable",
  cancelled: "Job cancelled",
};
function Editor({
  item,
  index,
  busy,
  save,
  seek,
}: {
  item: Item;
  index: number;
  busy: boolean;
  save: (item: Item, accepted: boolean) => void;
  seek: () => void;
}) {
  const [draft, setDraft] = useState(item);
  useEffect(() => setDraft(item), [item.id, item.version]);
  const changed =
    draft.text !== item.text ||
    draft.owner !== item.owner ||
    draft.due_date !== item.due_date ||
    draft.kind !== item.kind;
  return (
    <article
      className={`commitment ${item.accepted && !changed ? "reviewed" : ""}`}
    >
      <span className="step">{String(index + 1).padStart(2, "0")}</span>
      <div className="item-top">
        <span className={`tag ${draft.kind}`}>
          {draft.kind === "question" ? (
            <CircleHelp size={11} />
          ) : (
            <ChevronRight size={11} />
          )}{" "}
          {draft.kind === "question" ? "Open question" : "Commitment"}
        </span>
        <button className="source" onClick={seek}>
          Hear source ↗
        </button>
      </div>
      <label className="sr-only" htmlFor={item.id}>
        Commitment text
      </label>
      <textarea
        id={item.id}
        value={draft.text}
        maxLength={600}
        onChange={(e) => setDraft({ ...draft, text: e.target.value })}
      />
      <div className="item-fields">
        <label>
          Owner
          <input
            aria-label={`Owner for item ${index + 1}`}
            value={draft.owner}
            maxLength={100}
            placeholder="Unassigned"
            onChange={(e) => setDraft({ ...draft, owner: e.target.value })}
          />
        </label>
        <label>
          Due date
          <input
            aria-label={`Due date for item ${index + 1}`}
            type="date"
            value={draft.due_date || ""}
            onChange={(e) =>
              setDraft({ ...draft, due_date: e.target.value || null })
            }
          />
        </label>
      </div>
      <div className="item-bottom">
        <select
          aria-label={`Type for item ${index + 1}`}
          value={draft.kind}
          onChange={(e) =>
            setDraft({ ...draft, kind: e.target.value as Item["kind"] })
          }
        >
          <option value="action">Action</option>
          <option value="question">Open question</option>
        </select>
        <div>
          {changed && (
            <button
              className="text-button"
              disabled={busy}
              onClick={() => save(draft, false)}
            >
              Save draft
            </button>
          )}
          <button
            className={`review-button ${item.accepted && !changed ? "done" : ""}`}
            disabled={busy || !draft.text.trim()}
            onClick={() => save(draft, !(item.accepted && !changed))}
          >
            {busy ? (
              <LoaderCircle size={12} className="spin" />
            ) : (
              <Check size={12} />
            )}{" "}
            {item.accepted && !changed
              ? "Reviewed · undo"
              : draft.kind === "question"
                ? "Review question"
                : "Accept action"}
          </button>
        </div>
      </div>
    </article>
  );
}
export default function App() {
  const [token, setToken] = useState(
    () => sessionStorage.getItem("callmap-token") || "",
  );
  const [tokenInput, setTokenInput] = useState(""),
    [connected, setConnected] = useState(false),
    [rows, setRows] = useState<Recording[]>([]);
  const [id, setId] = useState<string | null>(null),
    [current, setCurrent] = useState<Recording | null>(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState("");
  const [audioUrl, setAudioUrl] = useState(""),
    [peaks, setPeaks] = useState<number[]>([]),
    [time, setTime] = useState(0),
    [playing, setPlaying] = useState(false),
    [rate, setRate] = useState(1),
    [follow, setFollow] = useState(true),
    [exported, setExported] = useState(false);
  const audio = useRef<HTMLAudioElement>(null),
    file = useRef<HTMLInputElement>(null),
    segmentRefs = useRef<Record<number, HTMLButtonElement | null>>({});
  const active =
      current?.segments.find((s) => s.start <= time && s.end > time)?.id ?? -1,
    items = current?.commitments || [],
    reviewed = items.filter((i) => i.accepted).length;
  const request = useCallback(
    async (path: string, init?: RequestInit) => {
      const response = await fetch(`/api${path}`, {
        ...init,
        headers: { Authorization: `Bearer ${token}`, ...init?.headers },
      });
      if (!response.ok) {
        if (response.status === 401) setConnected(false);
        const body = await response.json().catch(() => null);
        throw new Error(
          typeof body?.detail === "string"
            ? body.detail
            : `Request failed (${response.status}). Check the API and retry.`,
        );
      }
      return response;
    },
    [token],
  );
  const refresh = useCallback(async () => {
    const result: Recording[] = await (await request("/recordings")).json();
    setRows(result);
    setConnected(true);
    if (id) {
      if (!result.some((r) => r.id === id)) {
        setId(null);
        setCurrent(null);
        return;
      }
      setCurrent(await (await request(`/recordings/${id}`)).json());
    }
  }, [request, id]);
  useEffect(() => {
    if (!token) return;
    let live = true;
    const update = async () => {
      try {
        if (live) await refresh();
      } catch (e) {
        if (live) setError((e as Error).message);
      }
    };
    void update();
    const timer = setInterval(update, 1800);
    return () => {
      live = false;
      clearInterval(timer);
    };
  }, [token, refresh]);
  useEffect(() => {
    setTime(0);
    setPlaying(false);
    setAudioUrl("");
    setPeaks([]);
    setExported(false);
    if (!id || !token) return;
    const controller = new AbortController();
    let url = "";
    void (async () => {
      try {
        const blob = await (
          await request(`/recordings/${id}/audio`, {
            signal: controller.signal,
          })
        ).blob();
        if (controller.signal.aborted) return;
        url = URL.createObjectURL(blob);
        setAudioUrl(url);
        const context = new AudioContext();
        try {
          const buffer = await context.decodeAudioData(
              await blob.arrayBuffer(),
            ),
            samples = buffer.getChannelData(0);
          const bars = Array.from({ length: 110 }, (_, i) => {
            let peak = 0;
            for (
              let n = Math.floor((i * samples.length) / 110);
              n < Math.floor(((i + 1) * samples.length) / 110);
              n++
            )
              peak = Math.max(peak, Math.abs(samples[n]));
            return peak;
          });
          if (!controller.signal.aborted) setPeaks(bars);
        } finally {
          await context.close();
        }
      } catch (e) {
        if (!controller.signal.aborted) setError((e as Error).message);
      }
    })();
    return () => {
      controller.abort();
      if (url) URL.revokeObjectURL(url);
    };
  }, [id, token, request]);
  const seek = useCallback((value: number) => {
    if (audio.current) {
      audio.current.currentTime = Math.max(
        0,
        Math.min(audio.current.duration || 0, value),
      );
      setTime(audio.current.currentTime);
    }
  }, []);
  const toggle = useCallback(() => {
    if (!audio.current || !audioUrl) return;
    if (audio.current.paused)
      void audio.current
        .play()
        .catch(() => setError("Playback was blocked. Press play again."));
    else audio.current.pause();
  }, [audioUrl]);
  useEffect(() => {
    const key = (e: KeyboardEvent) => {
      if (
        e.target instanceof HTMLElement &&
        (["INPUT", "TEXTAREA", "SELECT", "BUTTON"].includes(e.target.tagName) ||
          e.target.isContentEditable)
      )
        return;
      if (e.code === "Space") {
        e.preventDefault();
        toggle();
      }
      if (e.key.toLowerCase() === "j")
        seek((audio.current?.currentTime || 0) - 5);
      if (e.key.toLowerCase() === "l")
        seek((audio.current?.currentTime || 0) + 5);
    };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, [seek, toggle]);
  useEffect(() => {
    if (follow && playing && active >= 0)
      segmentRefs.current[active]?.scrollIntoView({
        behavior: "smooth",
        block: "nearest",
      });
  }, [active, follow, playing]);
  useEffect(() => {
    if (audio.current) audio.current.playbackRate = rate;
  }, [rate, audioUrl]);
  async function mutate(name: string, action: () => Promise<void>) {
    setBusy(name);
    setError("");
    try {
      await action();
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy("");
    }
  }
  const loadSample = () =>
    mutate("sample", async () => {
      const row = await (
        await request("/recordings/sample", { method: "POST" })
      ).json();
      setId(row.id);
      setCurrent(row);
    });
  const upload = (chosen: File) =>
    mutate("upload", async () => {
      if (chosen.size > 24 * 1024 * 1024)
        throw new Error("Audio exceeds the 24 MiB limit.");
      const row = await (
        await request(
          `/recordings/upload?title=${encodeURIComponent(chosen.name.slice(0, 120))}`,
          {
            method: "POST",
            headers: { "Content-Type": "audio/wav" },
            body: chosen,
          },
        )
      ).json();
      setId(row.id);
      setCurrent(row);
    });
  const save = (draft: Item, accepted: boolean) =>
    mutate(draft.id, async () => {
      await request(`/recordings/${id}/commitments/${draft.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text: draft.text,
          owner: draft.owner,
          due_date: draft.due_date,
          kind: draft.kind,
          version: draft.version,
          accepted,
        }),
      });
    });
  const download = () =>
    mutate("export", async () => {
      const url = URL.createObjectURL(
          await (await request(`/recordings/${id}/export`)).blob(),
        ),
        a = document.createElement("a");
      a.href = url;
      a.download = "callmap-reviewed-items.json";
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      setExported(true);
    });
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a className="brand" href="/">
          <span className="brand-icon">
            <AudioLines size={23} />
          </span>
          callmap<span className="brand-dot">.</span>
        </a>
        <div className="workspace-label">
          <span className="workspace-avatar">W</span>
          <div>
            Your workspace<small>Private · on this device</small>
          </div>
          <LockKeyhole size={13} />
        </div>
        <div className="nav-heading">
          LIBRARY <span>{rows.length}</span>
        </div>
        <button className="nav-selected">
          <Headphones size={17} /> Conversations
        </button>
        <div className="recent-heading">
          RECENT RECORDINGS <span>Latest 100</span>
        </div>
        <nav className="recording-list" aria-label="Recordings">
          {rows.length ? (
            rows.map((row) => (
              <button
                className={`recording-link ${id === row.id ? "selected" : ""}`}
                key={row.id}
                onClick={() => {
                  setId(row.id);
                  setCurrent(null);
                  setError("");
                }}
              >
                <AudioLines size={16} />
                <span>
                  <strong>{row.title}</strong>
                  <small>
                    {stamp(row.duration)} ·{" "}
                    {row.status === "ready" ? "Ready" : row.status}
                  </small>
                </span>
                {id === row.id && <i />}
              </button>
            ))
          ) : (
            <p className="sidebar-empty">Your conversations will live here.</p>
          )}
        </nav>
        <div className="sidebar-footer">
          <i className="local-dot" />
          <span>
            Local fixture mode<small>No audio leaves this device</small>
          </span>
        </div>
      </aside>
      <main>
        <header className="topbar">
          <div className="breadcrumb">
            Workspace <ChevronRight size={13} /> <span>Conversations</span>
          </div>
          <span className="demo-pill">
            <Radio size={12} /> SYNTHETIC DEMO
          </span>
        </header>
        <div className="page-content">
          <div className="page-heading">
            <div>
              <div className="eyebrow">
                LESS REPLAYING. MORE FOLLOW-THROUGH.
              </div>
              <h1>
                Every conversation.
                <br className="mobile-break" /> A clearer next step.
              </h1>
              <p>Listen closely. Find the promises. Make them a plan.</p>
            </div>
            <div className="heading-buttons">
              <button
                className="secondary"
                disabled={!connected || !!busy}
                onClick={() => file.current?.click()}
              >
                <Upload size={15} /> Upload WAV
              </button>
              <button
                className="primary"
                disabled={!connected || !!busy}
                onClick={loadSample}
              >
                {busy === "sample" ? (
                  <LoaderCircle className="spin" size={15} />
                ) : (
                  <Plus size={16} />
                )}{" "}
                Load sample
              </button>
              <input
                hidden
                ref={file}
                type="file"
                accept=".wav,audio/wav"
                onChange={(e) => {
                  const chosen = e.target.files?.[0];
                  if (chosen) void upload(chosen);
                  e.target.value = "";
                }}
              />
            </div>
          </div>
          {error && (
            <div className="error-banner" role="alert">
              <CircleHelp size={17} />
              <span>{error}</span>
              <button aria-label="Dismiss error" onClick={() => setError("")}>
                <X size={16} />
              </button>
            </div>
          )}
          {!connected ? (
            <section className="connect-card">
              <span className="large-icon">
                <LockKeyhole size={28} />
              </span>
              <h2>Your conversations stay here.</h2>
              <p>
                Connect with the local token printed by{" "}
                <code>scripts/dev.sh</code>. It is held in this browser tab
                only.
              </p>
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  const next = tokenInput.trim();
                  sessionStorage.setItem("callmap-token", next);
                  setToken(next);
                  setError("");
                }}
              >
                <label htmlFor="local-token">Local access token</label>
                <div>
                  <input
                    id="local-token"
                    type="password"
                    autoComplete="off"
                    value={tokenInput}
                    onChange={(e) => setTokenInput(e.target.value)}
                    required
                    placeholder="Paste your local token"
                  />
                  <button className="primary">Open workspace →</button>
                </div>
              </form>
              <small>API :8012 · Workspace :5175 · No hosted account</small>
            </section>
          ) : !id ? (
            <section className="empty-workspace">
              <span className="large-icon">
                <AudioLines size={35} />
              </span>
              <div className="eyebrow">A SMALL CALL. A USEFUL PLAN.</div>
              <h2>Start with a conversation.</h2>
              <p>
                Meet Maya and Leo in a 34-second pilot launch check-in.
                <br />
                Hear the source, review three commitments, and untangle an open
                question.
              </p>
              <button
                className="primary"
                disabled={!!busy}
                onClick={loadSample}
              >
                <Play size={15} /> Explore the sample →
              </button>
              <div className="empty-features">
                <span>
                  <AudioLines size={16} /> Playable synthetic audio
                </span>
                <span>
                  <Check size={16} /> Persisted human reviews
                </span>
                <span>
                  <LockKeyhole size={16} /> Private local storage
                </span>
              </div>
              <div className="fixture-note">
                An authored transcript and predefined extraction are available
                only for the exact bundled sample. Arbitrary uploads require a
                live provider, which is not configured. WAV only · 24 MiB · 2
                minutes maximum.
              </div>
            </section>
          ) : !current ? (
            <div className="loading-state" role="status">
              <LoaderCircle className="spin" /> Opening recording…
            </div>
          ) : (
            <>
              <section className="player-card" aria-label="Audio player">
                <div className="player-heading">
                  <div className="file-mark">
                    <AudioLines size={23} />
                  </div>
                  <div className="player-title">
                    <h2>{current.title}</h2>
                    <div>
                      <i className={`status-dot ${current.status}`} />
                      {statuses[current.status]}{" "}
                      <span className="divider">/</span>{" "}
                      {current.fixture
                        ? "Synthetic sample · authored fixture"
                        : "Uploaded audio · no live provider"}
                    </div>
                  </div>
                  <div className="player-actions">
                    {pending(current.status) && (
                      <button
                        className="text-button"
                        disabled={!!busy}
                        onClick={() =>
                          mutate("cancel", async () => {
                            await request(`/recordings/${id}/cancel`, {
                              method: "POST",
                            });
                          })
                        }
                      >
                        Cancel job
                      </button>
                    )}
                    <button
                      title="Delete recording and audio"
                      aria-label="Delete recording"
                      disabled={!!busy}
                      onClick={() => {
                        if (
                          window.confirm(
                            "Delete this recording, private audio, and all reviews?",
                          )
                        )
                          void mutate("delete", async () => {
                            await request(`/recordings/${id}`, {
                              method: "DELETE",
                            });
                            setId(null);
                            setCurrent(null);
                          });
                      }}
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                </div>
                <div className="waveform" aria-hidden="true">
                  {peaks.length ? (
                    peaks.map((peak, i) => (
                      <i
                        key={i}
                        className={
                          i / peaks.length <= time / current.duration
                            ? "played"
                            : ""
                        }
                        style={{
                          height: `${Math.max(4, Math.pow(peak, 0.6) * 76)}px`,
                        }}
                      />
                    ))
                  ) : (
                    <span>Loading private waveform…</span>
                  )}
                </div>
                <input
                  className="seek"
                  type="range"
                  aria-label="Seek audio position"
                  min={0}
                  max={current.duration}
                  step={0.05}
                  value={Math.min(time, current.duration)}
                  disabled={!audioUrl}
                  onChange={(e) => seek(Number(e.target.value))}
                />
                <div className="wave-ticks">
                  <span>00:00</span>
                  <span>{stamp(current.duration / 3)}</span>
                  <span>{stamp((current.duration * 2) / 3)}</span>
                  <span>{stamp(current.duration)}</span>
                </div>
                <div className="transport">
                  <div className="playback-controls">
                    <button
                      className="skip"
                      title="Back 5 seconds (J)"
                      aria-label="Back five seconds"
                      disabled={!audioUrl}
                      onClick={() => seek(time - 5)}
                    >
                      <RotateCcw size={17} />
                      <span>5</span>
                    </button>
                    <button
                      className="play"
                      aria-label={playing ? "Pause" : "Play"}
                      disabled={!audioUrl}
                      onClick={toggle}
                    >
                      {playing ? (
                        <Pause size={17} fill="currentColor" />
                      ) : (
                        <Play size={17} fill="currentColor" />
                      )}
                    </button>
                    <button
                      className="skip forward"
                      title="Forward 5 seconds (L)"
                      aria-label="Forward five seconds"
                      disabled={!audioUrl}
                      onClick={() => seek(time + 5)}
                    >
                      <RotateCcw size={17} />
                      <span>5</span>
                    </button>
                    <span className="time">
                      <b>{stamp(time)}</b> / {stamp(current.duration)}
                    </span>
                  </div>
                  <div className="transport-right">
                    <span className="shortcut">
                      <kbd>space</kbd> to play / pause
                    </span>
                    <select
                      aria-label="Playback speed"
                      value={rate}
                      onChange={(e) => setRate(Number(e.target.value))}
                    >
                      <option value={0.75}>0.75×</option>
                      <option value={1}>1× speed</option>
                      <option value={1.25}>1.25×</option>
                      <option value={1.5}>1.5×</option>
                      <option value={2}>2×</option>
                    </select>
                  </div>
                </div>
                <audio
                  ref={audio}
                  src={audioUrl || undefined}
                  preload="metadata"
                  onTimeUpdate={(e) => setTime(e.currentTarget.currentTime)}
                  onPlay={() => setPlaying(true)}
                  onPause={() => setPlaying(false)}
                  onEnded={() => setPlaying(false)}
                  onError={() => {
                    if (audioUrl)
                      setError("Browser playback failed. Try 16-bit PCM WAV.");
                  }}
                />
              </section>
              {pending(current.status) && (
                <div className="job-progress" role="status">
                  <LoaderCircle size={17} className="spin" />
                  <span>
                    {statuses[current.status]}…{" "}
                    <small>
                      Fingerprint-gated fixture processing · no live inference
                    </small>
                  </span>
                  <div className="job-steps">
                    <span>01 Audio</span>
                    <span>02 Transcript</span>
                    <span>03 Commitments</span>
                  </div>
                </div>
              )}
              {current.status === "failed" && (
                <div className="error-banner">
                  <CircleHelp size={17} />
                  <span>{current.error}</span>
                </div>
              )}
              {current.status === "cancelled" && (
                <div className="fixture-note">
                  Job cancelled. Audio remains playable. Load or upload another
                  recording to start again.
                </div>
              )}
              <div className="review-grid">
                <section className="transcript-panel">
                  <div className="panel-heading">
                    <div>
                      <h3>
                        Transcript{" "}
                        <span>{current.segments.length || "—"} segments</span>
                      </h3>
                      <p>The conversation, moment by moment.</p>
                    </div>
                    <label className="follow">
                      <input
                        type="checkbox"
                        checked={follow}
                        onChange={(e) => setFollow(e.target.checked)}
                      />{" "}
                      Follow audio
                    </label>
                  </div>
                  <div className="transcript-scroll">
                    {current.segments.length ? (
                      current.segments.map((segment) => (
                        <button
                          key={segment.id}
                          ref={(el) => {
                            segmentRefs.current[segment.id] = el;
                          }}
                          className={`segment ${active === segment.id ? "active" : ""}`}
                          onClick={() => seek(segment.start)}
                          aria-label={`Seek to ${stamp(segment.start)}: ${segment.speaker}`}
                        >
                          <span
                            className={`speaker-avatar ${segment.speaker.toLowerCase()}`}
                          >
                            {segment.speaker[0]}
                          </span>
                          <span className="segment-content">
                            <span className="segment-heading">
                              <strong>{segment.speaker}</strong>
                              <span>{stamp(segment.start)}</span>
                              {active === segment.id && (
                                <span className="now-playing">
                                  <AudioLines size={12} />{" "}
                                  {playing ? "Speaking" : "Selected"}
                                </span>
                              )}
                            </span>
                            <span className="segment-text">{segment.text}</span>
                          </span>
                        </button>
                      ))
                    ) : (
                      <div className="panel-empty">
                        <AudioLines size={29} />
                        <p>
                          {pending(current.status)
                            ? "The fixture transcript will appear here."
                            : "No transcript is available for this recording."}
                        </p>
                      </div>
                    )}
                  </div>
                  <div className="panel-foot">
                    <i className="local-dot" /> Authored transcript · speaker
                    labels are fixture data
                  </div>
                </section>
                <section className="commitments-panel">
                  <div className="panel-heading">
                    <div>
                      <h3>
                        From words to work <span>{items.length}</span>
                      </h3>
                      <p>Review every promise before it leaves.</p>
                    </div>
                    <span className="progress-ring">
                      {reviewed}/{items.length || "—"}
                    </span>
                  </div>
                  <div className="commitment-scroll">
                    {items.length ? (
                      items.map((item, i) => (
                        <Editor
                          key={item.id}
                          item={item}
                          index={i}
                          busy={busy === item.id}
                          save={save}
                          seek={() =>
                            seek(
                              current.segments.find(
                                (s) => s.id === item.segment_id,
                              )?.start || 0,
                            )
                          }
                        />
                      ))
                    ) : (
                      <div className="panel-empty">
                        <CircleHelp size={29} />
                        <p>
                          {pending(current.status)
                            ? "Mapping the sample’s commitments…"
                            : "No commitments to review yet."}
                        </p>
                      </div>
                    )}
                  </div>
                  <div className="export-bar">
                    <span>
                      {exported
                        ? "Reviewed items downloaded"
                        : `${reviewed} reviewed · ${items.length - reviewed} need attention`}
                    </span>
                    <button
                      className="primary"
                      disabled={
                        !reviewed || !!busy || current.status !== "ready"
                      }
                      onClick={download}
                    >
                      <Download size={14} /> Export reviewed
                    </button>
                  </div>
                </section>
              </div>
              <footer className="workspace-foot">
                <span>
                  <LockKeyhole size={12} /> Audio and reviews stay on this
                  installation.
                </span>
                <span>Fixture suggestions need human review · JSON export</span>
              </footer>
            </>
          )}
          {connected && !id && (
            <button
              className="disconnect"
              onClick={() => {
                sessionStorage.removeItem("callmap-token");
                setToken("");
                setConnected(false);
                setRows([]);
              }}
            >
              ← Disconnect local session
            </button>
          )}
        </div>
      </main>
    </div>
  );
}
