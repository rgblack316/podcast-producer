import { useCallback, useEffect, useState } from "react";
import { Download, Loader2, PencilLine, Rss, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import { api, errMsg, fmtDate } from "@/lib/api";
import { RssItemDialog } from "@/components/rss/RssItemDialog";

const TABS = [["review", "Ready to review"], ["new", "Not analyzed"], ["imported", "Imported"], ["skipped", "Skipped"], ["", "All"]];

function JobBar({ job }) {
  if (!job?.total) return null;
  const pct = Math.round((job.done / job.total) * 100);
  return (
    <div className="card-warm p-4 space-y-2" data-testid="rss-job-progress">
      <div className="flex justify-between text-sm">
        <span>{job.running ? "Analyzing episodes with AI…" : job.aborted ? "Analysis stopped" : "Last analysis finished"}</span>
        <span className="f-mono text-xs">{job.done}/{job.total}{job.errors ? ` · ${job.errors} errors` : ""}</span>
      </div>
      <Progress value={pct} className="h-2" />
      {job.aborted && !job.running && (
        <p className="text-sm text-red-700 break-words" data-testid="rss-job-aborted">
          Stopped early because the AI provider rejected the API key. Check the key in Settings → AI provider & keys, then analyze again. ({job.aborted.slice(0, 160)})
        </p>
      )}
    </div>
  );
}

function Row({ it, checked, onCheck, onEdit }) {
  const s = it.suggestion;
  return (
    <li className="grid grid-cols-12 gap-3 items-center px-4 py-3 border-b border-[#EFE8DC] last:border-0" data-testid={`rss-row-${it.id}`}>
      <div className="col-span-1"><Checkbox checked={checked} onCheckedChange={onCheck} disabled={it.status === "imported"} data-testid={`rss-check-${it.id}`} /></div>
      <div className="col-span-11 md:col-span-4 min-w-0">
        <div className="font-medium text-[#1C1917] truncate">{it.title}</div>
        <div className="f-mono text-[11px] text-stone-500">{fmtDate(it.published_at)}{it.episode_number ? ` · #${it.episode_number}` : ""}
          {it.content_source && ` · from ${it.content_source}`}{it.transcripts?.length ? " · transcript in feed" : ""}</div>
      </div>
      <div className="col-span-12 md:col-span-5 min-w-0 text-sm">
        {it.error ? <span className="text-red-700 text-xs">{it.error}</span> : s ? (
          <>
            <div className="truncate"><span className="f-serif italic text-[#92400E]">{s.primary_scripture || "—"}</span> · {s.topic || "—"}</div>
            <div className="text-xs text-stone-500 truncate">{(s.themes || []).join(", ")}</div>
          </>
        ) : <span className="text-xs text-stone-400 italic">Not analyzed yet</span>}
      </div>
      <div className="col-span-12 md:col-span-2 flex justify-end">
        {it.status !== "imported" ? (
          <Button size="sm" variant="ghost" onClick={onEdit} data-testid={`rss-edit-${it.id}`}><PencilLine className="h-4 w-4 mr-1" /> Review</Button>
        ) : <span className="text-xs font-semibold text-[#15803D]">In library</span>}
      </div>
    </li>
  );
}

export default function RssImport() {
  const [data, setData] = useState({ items: [], counts: {}, feed_url: "" });
  const [url, setUrl] = useState("");
  const [tab, setTab] = useState("review");
  const [sel, setSel] = useState(new Set());
  const [job, setJob] = useState(null);
  const [busy, setBusy] = useState(null);
  const [editing, setEditing] = useState(null);

  const load = useCallback(() => api.get("/rss/items", { params: { status: tab } }).then((r) => {
    setData(r.data); setUrl((u) => u || r.data.feed_url);
  }), [tab]);
  useEffect(() => { load(); setSel(new Set()); }, [load]);
  useEffect(() => { api.get("/rss/job").then((r) => setJob(r.data)); }, []);
  useEffect(() => {
    if (!job?.running) return;
    const t = setInterval(async () => {
      const { data: j } = await api.get("/rss/job");
      setJob(j);
      if (!j.running) { load(); toast.success("Analysis finished"); }
    }, 3000);
    return () => clearInterval(t);
  }, [job?.running, load]);

  const run = async (key, fn, msg) => {
    setBusy(key);
    try { const r = await fn(); if (msg) toast.success(typeof msg === "function" ? msg(r.data) : msg); await load(); setSel(new Set()); return r; }
    catch (e) { toast.error(errMsg(e)); } finally { setBusy(null); }
  };
  const ids = [...sel];
  const fetchFeed = async () => {
    const r = await run("fetch", () => api.post("/rss/fetch", { feed_url: url }), (d) => `Found ${d.total} episodes (${d.added} new)`);
    if (r?.data.added) setTab("new");
  };
  const analyze = async (only) => {
    const r = await run("analyze", () => api.post("/rss/analyze", { ids: only || [] }));
    if (r) setJob(r.data);
  };
  const importSel = () => run("import", () => api.post("/rss/items/import", { ids }),
    (d) => `Imported ${d.imported} episode${d.imported === 1 ? "" : "s"}${d.skipped.length ? `, skipped ${d.skipped.length} (missing topic/scripture)` : ""}`);
  const toggleAll = (v) => setSel(v ? new Set(data.items.filter((i) => i.status !== "imported").map((i) => i.id)) : new Set());

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-8 py-10 space-y-6" data-testid="rss-import-page">
      <div className="fade-up">
        <p className="eyebrow">Back catalog</p>
        <h1 className="f-serif text-4xl sm:text-5xl font-semibold tracking-tight text-[#1C1917] mt-2">Import from RSS</h1>
        <p className="text-[#44403C] mt-2 max-w-2xl">Pull past episodes from your podcast feed. Transcripts are used when the feed has them, otherwise the show notes. AI fills in the topic, scripture and themes for you to review before they go into the library.</p>
      </div>
      <div className="card-warm p-5 flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Rss className="h-4 w-4 absolute left-3 top-1/2 -translate-y-1/2 text-[#B45309]" />
          <Input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://feeds.example.com/biblebytes.xml" className="pl-9 bg-[#FFFDF9] f-mono text-sm" data-testid="rss-feed-url-input" />
        </div>
        <Button onClick={fetchFeed} disabled={!url.trim() || !!busy} className="rounded-full" data-testid="rss-fetch-btn">
          {busy === "fetch" ? <Loader2 className="h-4 w-4 mr-1.5 animate-spin" /> : <Download className="h-4 w-4 mr-1.5" />} Fetch feed
        </Button>
        <Button variant="outline" className="rounded-full bg-[#FFFDF9]" onClick={() => analyze()} disabled={!data.counts.new || !!busy || job?.running} data-testid="rss-analyze-all-btn">
          <Sparkles className="h-4 w-4 mr-1.5" /> Analyze {data.counts.new || 0} new with AI
        </Button>
      </div>
      <JobBar job={job} />
      <div className="flex flex-wrap gap-2">
        {TABS.map(([k, label]) => (
          <button key={k || "all"} onClick={() => setTab(k)} data-testid={`rss-tab-${k || "all"}`}
            className={`px-3 py-1.5 rounded-full text-sm border transition-colors ${tab === k ? "bg-[#1C1917] text-white border-[#1C1917]" : "bg-[#FFFDF9] border-[#E7E0D6] hover:bg-[#F4EFE6]"}`}>
            {label} <span className="f-mono text-xs opacity-70">{k ? data.counts[k] || 0 : Object.values(data.counts).reduce((a, b) => a + b, 0)}</span>
          </button>
        ))}
      </div>
      <div className="card-warm overflow-hidden">
        <div className="flex flex-wrap items-center gap-2 px-4 py-3 bg-[#F4EFE6]/60 border-b border-[#E7E0D6]">
          <Checkbox checked={sel.size > 0 && sel.size === data.items.filter((i) => i.status !== "imported").length} onCheckedChange={toggleAll} data-testid="rss-select-all" />
          <span className="text-sm text-stone-600 mr-auto">{sel.size} selected</span>
          <Button size="sm" onClick={importSel} disabled={!sel.size || !!busy} data-testid="rss-import-selected-btn">
            {busy === "import" && <Loader2 className="h-4 w-4 mr-1 animate-spin" />} Add to library
          </Button>
          <Button size="sm" variant="outline" className="bg-[#FFFDF9]" onClick={() => analyze(ids)} disabled={!sel.size || !!busy || job?.running} data-testid="rss-analyze-selected-btn">Re-analyze</Button>
          {tab === "skipped" ? (
            <Button size="sm" variant="ghost" onClick={() => run("unskip", () => api.post("/rss/items/unskip", { ids }), "Restored")} disabled={!sel.size} data-testid="rss-unskip-btn">Unskip</Button>
          ) : (
            <Button size="sm" variant="ghost" onClick={() => run("skip", () => api.post("/rss/items/skip", { ids }), "Skipped")} disabled={!sel.size} data-testid="rss-skip-btn">Skip</Button>
          )}
        </div>
        <ul data-testid="rss-items-list">
          {data.items.length ? data.items.map((it) => (
            <Row key={it.id} it={it} checked={sel.has(it.id)} onEdit={() => setEditing(it)}
              onCheck={(v) => { const n = new Set(sel); v ? n.add(it.id) : n.delete(it.id); setSel(n); }} />
          )) : <p className="p-6 text-stone-500 italic" data-testid="rss-empty">Nothing here. Fetch your feed to get started.</p>}
        </ul>
      </div>
      <RssItemDialog item={editing} onClose={() => setEditing(null)} onSaved={load} />
    </div>
  );
}
