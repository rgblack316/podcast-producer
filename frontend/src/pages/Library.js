import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Layers, Search } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { AddToSeriesDialog } from "@/components/AddToSeriesDialog";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { api, errMsg, fmtDate, STATUS_LABELS } from "@/lib/api";
import { StatusBadge } from "@/components/StatusBadge";

const ALL = "__all";

function FilterSelect({ value, onChange, placeholder, options, testId }) {
  return (
    <Select value={value || ALL} onValueChange={(v) => onChange(v === ALL ? "" : v)}>
      <SelectTrigger className="w-full sm:w-[190px] bg-[#FFFDF9]" data-testid={testId}><SelectValue placeholder={placeholder} /></SelectTrigger>
      <SelectContent>
        <SelectItem value={ALL}>{placeholder}</SelectItem>
        {options.map(([v, label]) => <SelectItem key={v} value={v} className="capitalize">{label}</SelectItem>)}
      </SelectContent>
    </Select>
  );
}

export default function Library() {
  const [params, setParams] = useSearchParams();
  const [q, setQ] = useState(params.get("q") || "");
  const [episodes, setEpisodes] = useState(null);
  const [meta, setMeta] = useState({ themes: [], books: [] });
  const filters = { status: params.get("status") || "", theme: params.get("theme") || "", book: params.get("book") || "" };
  const seriesFilter = params.get("series") || "";
  const [series, setSeries] = useState([]);
  const [membership, setMembership] = useState({});
  const [sel, setSel] = useState(new Set());
  const [adding, setAdding] = useState(false);
  const seriesById = Object.fromEntries(series.map((s) => [s.id, s]));
  const loadSeries = () => {
    api.get("/series").then((r) => setSeries(r.data));
    api.get("/series/membership").then((r) => setMembership(r.data));
  };
  const toggle = (id, v) => { const n = new Set(sel); v ? n.add(id) : n.delete(id); setSel(n); };
  const removeFromSeries = async () => {
    try {
      await api.post("/series/remove-episodes", { episode_ids: [...sel] });
      toast.success("Removed from series");
      setSel(new Set());
      loadSeries();
    } catch (e) { toast.error(errMsg(e)); }
  };

  const setFilter = (k, v) => {
    const next = new URLSearchParams(params);
    v ? next.set(k, v) : next.delete(k);
    setParams(next, { replace: true });
  };

  useEffect(() => { api.get("/episodes/meta").then((r) => setMeta(r.data)); loadSeries(); }, []);
  useEffect(() => {
    const t = setTimeout(() => {
      api.get("/episodes", { params: { q, ...filters } }).then((r) => setEpisodes(r.data));
    }, 250);
    return () => clearTimeout(t);
  }, [q, filters.status, filters.theme, filters.book]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-8 py-10 space-y-8" data-testid="episode-library">
      <div className="fade-up">
        <p className="eyebrow">Archive</p>
        <h1 className="f-serif text-4xl sm:text-5xl font-semibold tracking-tight text-[#1C1917] mt-2">Episode library</h1>
      </div>
      <div className="flex flex-col sm:flex-row gap-3 fade-up">
        <div className="relative flex-1">
          <Search className="h-4 w-4 absolute left-3 top-1/2 -translate-y-1/2 text-stone-400" />
          <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search title, topic, scripture, theme…"
            className="pl-9 bg-[#FFFDF9]" data-testid="library-search-input" />
        </div>
        <FilterSelect value={filters.status} onChange={(v) => setFilter("status", v)} placeholder="All statuses"
          options={Object.entries(STATUS_LABELS)} testId="library-status-filter" />
        <FilterSelect value={filters.theme} onChange={(v) => setFilter("theme", v)} placeholder="All themes"
          options={meta.themes.map((t) => [t.name, t.name])} testId="library-theme-filter" />
        <FilterSelect value={filters.book} onChange={(v) => setFilter("book", v)} placeholder="All books"
          options={meta.books.map((t) => [t.name, t.name])} testId="library-book-filter" />
        <FilterSelect value={seriesFilter} onChange={(v) => setFilter("series", v)} placeholder="All series"
          options={series.map((x) => [x.id, x.name])} testId="library-series-filter" />
      </div>
      {sel.size > 0 && (
        <div className="sticky top-20 z-40 card-warm px-4 py-3 flex flex-wrap items-center gap-3" data-testid="library-selection-bar">
          <span className="text-sm font-medium mr-auto">{sel.size} selected</span>
          <Button size="sm" className="rounded-full" onClick={() => setAdding(true)} data-testid="library-add-to-series-btn"><Layers className="h-4 w-4 mr-1.5" /> Add to series</Button>
          <Button size="sm" variant="outline" className="rounded-full bg-[#FFFDF9]" onClick={removeFromSeries} data-testid="library-remove-from-series-btn">Remove from series</Button>
          <Button size="sm" variant="ghost" onClick={() => setSel(new Set())} data-testid="library-clear-selection-btn">Clear</Button>
        </div>
      )}
      <div className="card-warm overflow-hidden fade-up">
        <div className="hidden md:grid grid-cols-12 gap-4 px-6 py-3 border-b border-[#E7E0D6] bg-[#F4EFE6]/60 eyebrow !text-stone-500">
          <div className="col-span-1 pl-6">#</div><div className="col-span-4">Episode</div><div className="col-span-3">Scripture</div>
          <div className="col-span-2">Themes</div><div className="col-span-2 text-right">Status</div>
        </div>
        {episodes === null ? <p className="p-6 text-stone-500 italic">Loading…</p> : episodes.length === 0 ? (
          <p className="p-6 text-stone-500 italic" data-testid="library-empty">No episodes match.</p>
        ) : episodes.filter((e) => !seriesFilter || membership[e.id] === seriesFilter).map((e) => (
          <div key={e.id} className="flex items-center border-b border-[#EFE8DC] last:border-0 hover:bg-[#F4EFE6]/70 transition-colors">
          <div className="pl-4"><Checkbox checked={sel.has(e.id)} onCheckedChange={(v) => toggle(e.id, v)} data-testid={`library-check-${e.id}`} /></div>
          <Link to={`/episodes/${e.id}`} data-testid={`episode-row-item-${e.id}`}
            className="flex-1 grid grid-cols-1 md:grid-cols-12 gap-1 md:gap-4 px-4 md:px-6 py-4 items-center min-w-0">
            <div className="md:col-span-1 f-mono text-sm text-stone-500">{e.episode_number || "—"}</div>
            <div className="md:col-span-4 min-w-0">
              <div className="f-serif text-lg text-[#1C1917] truncate">{e.title}</div>
              <div className="text-sm text-stone-500 truncate">{e.topic}</div>
              {seriesById[membership[e.id]] && (
                <span className="inline-flex items-center gap-1 text-[11px] font-medium mt-1" data-testid={`library-series-${e.id}`}>
                  <span className="h-2 w-2 rounded-full" style={{ background: seriesById[membership[e.id]].color }} />{seriesById[membership[e.id]].name}
                </span>
              )}
            </div>
            <div className="md:col-span-3 f-serif italic text-[#44403C] truncate">{e.primary_scripture}</div>
            <div className="md:col-span-2 text-xs text-stone-600 truncate">{(e.themes || []).join(", ")}</div>
            <div className="md:col-span-2 flex md:flex-col md:items-end gap-2 md:gap-1">
              <StatusBadge status={e.status} testId={`library-status-${e.id}`} />
              <span className="f-mono text-[11px] text-stone-500">{fmtDate(e.published_at || e.updated_at)}</span>
            </div>
          </Link>
          </div>
        ))}
      </div>
      <AddToSeriesDialog open={adding} episodeIds={[...sel]} series={series} onClose={() => setAdding(false)}
        onDone={() => { setSel(new Set()); loadSeries(); }} />
    </div>
  );
}
