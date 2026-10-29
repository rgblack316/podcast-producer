import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { CalendarPlus, Lightbulb, Loader2, Plus, Trash2 } from "lucide-react";
import { PlanItemDialog } from "@/components/planner/PlanItemDialog";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { api, errMsg, fmtDate } from "@/lib/api";

function heat(count, max) {
  if (!count) return "bg-[#FFFDF9] border-[#E7E0D6] text-stone-400";
  const r = count / max;
  if (r > 0.66) return "bg-[#B45309] border-[#92400E] text-white";
  if (r > 0.33) return "bg-[#F59E0B]/70 border-[#D97706] text-[#1C1917]";
  return "bg-[#FDE68A] border-[#FCD34D] text-[#78350F]";
}

function BookGrid({ books, testament, label }) {
  const list = books.filter((b) => b.testament === testament);
  const max = Math.max(1, ...books.map((b) => b.count));
  const covered = list.filter((b) => b.count).length;
  return (
    <div className="card-warm p-6 space-y-4" data-testid={`coverage-${testament.toLowerCase()}`}>
      <div className="flex items-baseline justify-between">
        <h2 className="f-serif text-2xl">{label}</h2>
        <span className="f-mono text-xs text-stone-500">{covered}/{list.length} books covered</span>
      </div>
      <div className="grid grid-cols-3 sm:grid-cols-5 lg:grid-cols-6 gap-1.5">
        {list.map((b) => (
          <Popover key={b.name}>
            <PopoverTrigger asChild>
              <button className={`rounded-md border px-1.5 py-2 text-[11px] leading-tight font-medium transition-transform hover:-translate-y-0.5 ${heat(b.count, max)}`}
                data-testid={`coverage-book-${b.name.replace(/\s/g, "-")}`}>
                <div className="truncate">{b.name}</div>
                <div className="f-mono text-[10px] opacity-80">{b.count}</div>
              </button>
            </PopoverTrigger>
            <PopoverContent className="w-72 bg-[#FFFDF9]">
              <p className="f-serif text-lg">{b.name}</p>
              {b.episodes.length ? (
                <ul className="mt-2 space-y-1">
                  {b.episodes.map((e) => (
                    <li key={e.id}><Link to={`/episodes/${e.id}`} className="text-sm text-[#B45309] hover:underline">{e.episode_number ? `#${e.episode_number} · ` : ""}{e.title}</Link></li>
                  ))}
                </ul>
              ) : <p className="text-sm text-stone-500 mt-1">Not covered yet.</p>}
            </PopoverContent>
          </Popover>
        ))}
      </div>
    </div>
  );
}

function Timeline({ timeline }) {
  const max = Math.max(1, ...timeline.map((m) => m.count));
  return (
    <div className="card-warm p-6 space-y-4" data-testid="coverage-timeline">
      <h2 className="f-serif text-2xl">Over time</h2>
      {!timeline.length ? <p className="text-sm text-stone-500 italic">No episodes yet.</p> : (
        <div className="flex items-end gap-2 h-44 overflow-x-auto pb-1">
          {timeline.map((m) => {
            const top = Object.entries(m.themes).sort((a, b) => b[1] - a[1]).slice(0, 3).map(([t]) => t).join(", ");
            return (
              <div key={m.month} className="flex flex-col items-center gap-1 min-w-[44px]" title={top ? `Themes: ${top}` : ""}>
                <span className="f-mono text-[10px] text-stone-500">{m.count}</span>
                <div className="w-7 rounded-t bg-[#B45309]/80" style={{ height: `${(m.count / max) * 120}px` }} />
                <span className="f-mono text-[10px] text-stone-500">{m.month.slice(2)}</span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function Themes({ themes }) {
  return (
    <div className="card-warm p-6 space-y-3" data-testid="coverage-themes">
      <h2 className="f-serif text-2xl">Themes</h2>
      {!themes.length ? <p className="text-sm text-stone-500 italic">No themes yet.</p> : (
        <ul className="divide-y divide-[#EFE8DC]">
          {themes.slice(0, 20).map((t) => (
            <li key={t.name} className="flex items-center gap-3 py-2">
              <Link to={`/episodes?theme=${encodeURIComponent(t.name)}`} className="capitalize text-sm flex-1 hover:text-[#B45309]">{t.name}</Link>
              <span className="f-mono text-[11px] text-stone-500">{t.first === t.last ? t.first : `${t.first} → ${t.last}`}</span>
              <span className="f-mono text-xs w-6 text-right">{t.count}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function Suggestions({ data, onNew, onChange }) {
  const navigate = useNavigate();
  const [focus, setFocus] = useState("");
  const [busy, setBusy] = useState(false);
  const run = async () => {
    setBusy(true);
    try {
      const { data: r } = await api.post("/coverage/suggest", { focus, count: 6 });
      onNew(r.suggestions);
      toast.success("New topic ideas ready");
    } catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); }
  };
  const remove = async (s) => {
    try {
      await api.delete(`/coverage/suggestions/${s.id}`);
      onChange({ ...data, suggestions: data.suggestions.filter((x) => x.id !== s.id) });
    } catch (e) { toast.error(errMsg(e)); }
  };
  const clearAll = async () => {
    if (!window.confirm("Clear all suggested topics? Items you already added to the planner or started as episodes are not affected.")) return;
    try {
      await api.delete("/coverage/suggestions");
      onChange({ ...data, suggestions: [], suggested_at: null });
      toast.success("Suggestions cleared");
    } catch (e) { toast.error(errMsg(e)); }
  };
  const start = (s) => navigate("/episodes/new", { state: { prefill: s } });
  const [plan, setPlan] = useState(null);
  const [series, setSeries] = useState([]);
  const addToPlan = async (s) => {
    setSeries((await api.get("/series")).data);
    setPlan({ title: s.title, topic: s.topic, primary_scripture: s.primary_scripture, supporting_scriptures: s.supporting_scriptures, themes: s.themes, notes: s.why });
  };
  return (
    <div className="card-warm p-6 space-y-4" data-testid="coverage-suggestions">
      <div className="flex flex-col md:flex-row md:items-end gap-3 justify-between">
        <div>
          <h2 className="f-serif text-2xl flex items-center gap-2"><Lightbulb className="h-5 w-5 text-[#B45309]" /> Suggested topics to fill gaps</h2>
          {data.suggested_at && <p className="f-mono text-[11px] text-stone-500 mt-1">Last suggested {fmtDate(data.suggested_at)}</p>}
        </div>
        <div className="flex gap-2 w-full md:w-auto">
          <Input value={focus} onChange={(e) => setFocus(e.target.value)} placeholder="Optional focus, e.g. minor prophets, Advent" className="bg-[#FFFDF9] md:w-72" data-testid="coverage-focus-input" />
          <Button onClick={run} disabled={busy} className="rounded-full shrink-0" data-testid="coverage-suggest-btn">
            {busy ? <Loader2 className="h-4 w-4 mr-1.5 animate-spin" /> : <Lightbulb className="h-4 w-4 mr-1.5" />} Suggest
          </Button>
          {data.suggestions.length > 0 && (
            <Button variant="outline" onClick={clearAll} className="rounded-full shrink-0 bg-[#FFFDF9]" data-testid="coverage-clear-btn">
              <Trash2 className="h-4 w-4 mr-1.5" /> Clear all
            </Button>
          )}
        </div>
      </div>
      {!data.suggestions.length ? <p className="text-sm text-stone-500 italic">Ask the AI for ideas based on the books and themes you haven't covered yet.</p> : (
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
          {data.suggestions.map((s) => (
            <div key={s.id} className="rounded-lg border border-[#E7E0D6] bg-[#FFFDF9] p-4 flex flex-col gap-2" data-testid={`suggestion-${s.id}`}>
              <p className="f-serif text-lg text-[#1C1917]">{s.title}</p>
              <p className="f-serif italic text-sm text-[#92400E]">{s.primary_scripture}</p>
              <p className="text-sm text-stone-600">{s.topic}</p>
              <p className="text-xs text-stone-500 flex-1">{s.why}</p>
              <div className="flex flex-wrap gap-1">{s.themes.map((t) => <span key={t} className="px-2 py-0.5 rounded-full bg-[#F4EFE6] text-[11px]">{t}</span>)}</div>
              <div className="flex gap-2 mt-1">
                <Button size="sm" variant="outline" className="bg-[#FFFDF9] w-fit" onClick={() => start(s)} data-testid={`suggestion-start-${s.id}`}><Plus className="h-4 w-4 mr-1" /> Start episode</Button>
                <Button size="sm" variant="ghost" onClick={() => addToPlan(s)} data-testid={`suggestion-plan-${s.id}`}><CalendarPlus className="h-4 w-4 mr-1" /> Add to plan</Button>
                <Button size="sm" variant="ghost" className="text-red-700 hover:text-red-800 ml-auto" onClick={() => remove(s)} data-testid={`suggestion-delete-${s.id}`}><Trash2 className="h-4 w-4 mr-1" /> Delete</Button>
              </div>
            </div>
          ))}
        </div>
      )}
      {plan && <PlanItemDialog item={plan} series={series} onClose={() => setPlan(null)} onSaved={() => {}} />}
    </div>
  );
}

export default function Coverage() {
  const [data, setData] = useState(null);
  useEffect(() => { api.get("/coverage").then((r) => setData(r.data)); }, []);
  if (!data) return <div className="p-10 f-serif italic text-stone-500">Loading coverage…</div>;
  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-8 py-10 space-y-6" data-testid="coverage-page">
      <div className="fade-up">
        <p className="eyebrow">Coverage map</p>
        <h1 className="f-serif text-4xl sm:text-5xl font-semibold tracking-tight text-[#1C1917] mt-2">What we've covered</h1>
        <p className="text-[#44403C] mt-2">{data.total} episodes across {data.books.filter((b) => b.count).length} of 66 books.</p>
      </div>
      <Suggestions data={data} onChange={setData} onNew={(s) => setData({ ...data, suggestions: s, suggested_at: new Date().toISOString() })} />
      <div className="grid lg:grid-cols-2 gap-6">
        <BookGrid books={data.books} testament="OT" label="Old Testament" />
        <BookGrid books={data.books} testament="NT" label="New Testament" />
      </div>
      <div className="grid lg:grid-cols-2 gap-6">
        <Timeline timeline={data.timeline} />
        <Themes themes={data.themes} />
      </div>
    </div>
  );
}
