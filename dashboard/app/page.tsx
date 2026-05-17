"use client";

import { useEffect, useMemo, useState } from "react";

type TrustEvent = {
  timestamp: string;
  agent_id: string;
  request_id: string | null;
  correlation_id: string;
  layer: string;
  verdict: string;
  action: string;
  payload: Record<string, unknown>;
};

const COLLECTOR_URL = "http://localhost:9090";

function LayerBadge({ layer }: { layer: string }) {
  const palette: Record<string, string> = {
    lobster_trap: "bg-blue-100 text-blue-800",
    penny_prompt: "bg-purple-100 text-purple-800",
    claw_crate: "bg-teal-100 text-teal-800",
  };
  return (
    <span className={`rounded px-2 py-1 text-xs font-semibold ${palette[layer] ?? "bg-gray-100 text-gray-800"}`}>
      {layer}
    </span>
  );
}

function VerdictBadge({ verdict }: { verdict: string }) {
  const palette: Record<string, string> = {
    ALLOW: "bg-green-100 text-green-800",
    DENY: "bg-red-100 text-red-800",
    HUMAN_REVIEW: "bg-yellow-100 text-yellow-800",
    LOG: "bg-gray-100 text-gray-800",
    RATE_LIMIT: "bg-orange-100 text-orange-800",
    QUARANTINE: "bg-pink-100 text-pink-800",
  };
  return (
    <span className={`rounded px-2 py-1 text-xs font-semibold ${palette[verdict] ?? "bg-gray-100 text-gray-800"}`}>
      {verdict}
    </span>
  );
}

export default function Home() {
  const [events, setEvents] = useState<TrustEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [correlationFilter, setCorrelationFilter] = useState("");

  useEffect(() => {
    let cancelled = false;

    const fetchEvents = async () => {
      try {
        const response = await fetch(`${COLLECTOR_URL}/events`, { cache: "no-store" });
        if (!response.ok) {
          throw new Error(`collector returned ${response.status}`);
        }
        const data = (await response.json()) as TrustEvent[];
        if (!cancelled) {
          setEvents(Array.isArray(data) ? data : []);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "unknown error");
        }
      }
    };

    fetchEvents();
    const timer = window.setInterval(fetchEvents, 1000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  const rows = useMemo(() => {
    const filter = correlationFilter.trim().toLowerCase();
    if (!filter) {
      return events;
    }
    return events.filter((event) => event.correlation_id.toLowerCase().includes(filter));
  }, [events, correlationFilter]);

  return (
    <main className="min-h-screen bg-slate-950 p-6 text-slate-100">
      <div className="mx-auto max-w-7xl">
        <h1 className="text-2xl font-semibold">CerberusGuard Live Feed</h1>
        <div className="mt-4">
          <input
            type="text"
            value={correlationFilter}
            onChange={(event) => setCorrelationFilter(event.target.value)}
            placeholder="Filter by correlation_id"
            className="w-full max-w-md rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100 outline-none focus:border-slate-500"
          />
        </div>
        {error ? <p className="mt-3 text-sm text-red-300">Collector error: {error}</p> : null}
        <div className="mt-6 overflow-x-auto rounded-lg border border-slate-800 bg-slate-900">
          <table className="min-w-full text-left text-sm">
            <thead className="bg-slate-800/80 text-slate-200">
              <tr>
                <th className="px-4 py-3 font-medium">Time</th>
                <th className="px-4 py-3 font-medium">Agent</th>
                <th className="px-4 py-3 font-medium">Layer</th>
                <th className="px-4 py-3 font-medium">Verdict</th>
                <th className="px-4 py-3 font-medium">Action</th>
                <th className="px-4 py-3 font-medium">Session</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((event, idx) => {
                const rowTone =
                  event.verdict === "DENY"
                    ? "bg-red-950/40"
                    : event.verdict === "HUMAN_REVIEW"
                      ? "bg-yellow-900/25"
                      : "bg-transparent";
                return (
                  <tr key={`${event.correlation_id}-${idx}`} className={`border-t border-slate-800 ${rowTone}`}>
                    <td className="px-4 py-3">{new Date(event.timestamp).toLocaleTimeString()}</td>
                    <td className="px-4 py-3">{event.agent_id}</td>
                    <td className="px-4 py-3"><LayerBadge layer={event.layer} /></td>
                    <td className="px-4 py-3"><VerdictBadge verdict={event.verdict} /></td>
                    <td className="px-4 py-3">{event.action}</td>
                    <td className="px-4 py-3">
                      <button
                        type="button"
                        onClick={() => setCorrelationFilter(event.correlation_id)}
                        className="text-xs font-medium text-cyan-300 hover:text-cyan-200"
                      >
                        View session
                      </button>
                    </td>
                  </tr>
                );
              })}
              {rows.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-4 py-6 text-center text-slate-400">
                    Waiting for events from collector...
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </div>
    </main>
  );
}
