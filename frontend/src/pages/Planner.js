import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { addMonths, endOfMonth, endOfWeek, format, startOfMonth, startOfWeek } from "date-fns";
import { ChevronLeft, ChevronRight, Lightbulb, Plus, Settings2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { api, errMsg } from "@/lib/api";
import { CalendarGrid, PlanChip, dragData } from "@/components/planner/CalendarGrid";
import { PlanItemDialog } from "@/components/planner/PlanItemDialog";
import { SeriesDialog } from "@/components/planner/SeriesDialog";

function Section({ title, children, testId, onDrop }) {
  return (
    <div className="card-warm p-4 space-y-2" data-testid={testId} onDragOver={onDrop ? (e) => e.preventDefault() : undefined} onDrop={onDrop}>
      <p className="eyebrow">{title}</p>
      {children}
    </div>
  );
}

function SourceCard({ label, sub, payload, testId, onAdd }) {
  return (
    <div draggable onDragStart={(e) => dragData(e, payload)} data-testid={testId}
      className="group rounded-md border border-[#E7E0D6] bg-[#FFFDF9] p-2 cursor-grab active:cursor-grabbing hover:border-[#B45309] transition-colors">
      <div className="flex items-start gap-1">
        <div className="min-w-0 flex-1">
          <div className="text-sm font-medium truncate">{label}</div>
          {sub && <div className="f-serif italic text-xs text-[#92400E] truncate">{sub}</div>}
        </div>
        <button onClick={onAdd} className="text-stone-400 hover:text-[#B45309]" title="Add to plan" data-testid={`${testId}-add`}><Plus className="h-4 w-4" /></button>
      </div>
    </div>
  );
}

export default function Planner() {
  const [month, setMonth] = useState(startOfMonth(new Date()));
  const [items, setItems] = useState([]);
  const [series, setSeries] = useState([]);
  const [suggestions, setSuggestions] = useState([]);
  const [drafts, setDrafts] = useState([]);
  const [open, setOpen] = useState(null);
  const [seriesEdit, setSeriesEdit] = useState({ open: false, series: null });

  const load = useCallback(() => {
    const start = format(startOfWeek(startOfMonth(month)), "yyyy-MM-dd");
    const end = format(endOfWeek(endOfMonth(month)), "yyyy-MM-dd");
    api.get("/plan", { params: { start, end } }).then((r) => setItems(r.data));
    api.get("/series").then((r) => setSeries(r.data));
    api.get("/coverage").then((r) => setSuggestions(r.data.suggestions || []));
    api.get("/episodes").then((r) => setDrafts(r.data.filter((e) => ["draft", "outline_approved", "script_complete"].includes(e.status))));
  }, [month]);
  useEffect(() => { load(); }, [load]);

  const seriesById = useMemo(() => Object.fromEntries(series.map((s) => [s.id, s])), [series]);
  const plannedEpisodeIds = new Set(items.map((i) => i.episode_id).filter(Boolean));
  const unscheduled = items.filter((i) => !i.date);
  const fromSuggestion = (s) => ({ title: s.title, topic: s.topic, primary_scripture: s.primary_scripture, supporting_scriptures: s.supporting_scriptures, themes: s.themes, notes: s.why });

  const handleDrop = async (e, date) => {
    e.preventDefault();
    let p;
    try { p = JSON.parse(e.dataTransfer.getData("application/json")); } catch { return; }
    try {
      if (p.kind === "plan") await api.patch(`/plan/${p.id}`, { date });
      else if (p.kind === "suggestion") await api.post("/plan", { ...fromSuggestion(p.data), date });
      else if (p.kind === "episode") await api.post("/plan", { episode_id: p.id, date });
      toast.success(date ? `Scheduled for ${format(new Date(`${date}T12:00:00`), "MMM d")}` : "Moved to unscheduled");
      load();
    } catch (err) { toast.error(errMsg(err)); }
  };

  return (
    <div className="max-w-[1600px] mx-auto px-4 sm:px-6 py-8 space-y-6" data-testid="planner-page">
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 fade-up">
        <div>
          <p className="eyebrow">Series planner</p>
          <h1 className="f-serif text-4xl sm:text-5xl font-semibold tracking-tight text-[#1C1917] mt-2">{format(month, "MMMM yyyy")}</h1>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" size="icon" className="bg-[#FFFDF9]" onClick={() => setMonth(addMonths(month, -1))} data-testid="planner-prev-month"><ChevronLeft className="h-4 w-4" /></Button>
          <Button variant="outline" className="bg-[#FFFDF9]" onClick={() => setMonth(startOfMonth(new Date()))} data-testid="planner-today">Today</Button>
          <Button variant="outline" size="icon" className="bg-[#FFFDF9]" onClick={() => setMonth(addMonths(month, 1))} data-testid="planner-next-month"><ChevronRight className="h-4 w-4" /></Button>
          <Button variant="outline" className="rounded-full bg-[#FFFDF9]" onClick={() => setOpen({ title: "" })} data-testid="planner-add-idea-btn"><Plus className="h-4 w-4 mr-1" /> Add idea</Button>
          <Button className="rounded-full" onClick={() => setSeriesEdit({ open: true, series: null })} data-testid="planner-new-series-btn"><Plus className="h-4 w-4 mr-1" /> New series</Button>
        </div>
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        <aside className="lg:col-span-3 space-y-4 lg:max-h-[calc(100vh-8rem)] lg:overflow-y-auto lg:sticky lg:top-24">
          <Section title="Series" testId="planner-series-list">
            {series.length ? series.map((s) => (
              <div key={s.id} className="flex items-center gap-2 text-sm" data-testid={`series-row-${s.id}`}>
                <span className="h-3 w-3 rounded-full shrink-0" style={{ background: s.color }} />
                <Link to={`/series/${s.id}`} className="flex-1 truncate hover:text-[#B45309]" title={s.description} data-testid={`series-link-${s.id}`}>{s.name}</Link>
                <span className="f-mono text-xs text-stone-500">{s.count}</span>
                <button onClick={() => setSeriesEdit({ open: true, series: s })} className="text-stone-400 hover:text-[#1C1917]" data-testid={`series-edit-${s.id}`}><Settings2 className="h-3.5 w-3.5" /></button>
              </div>
            )) : <p className="text-xs text-stone-500 italic">Create a series to group and color episodes.</p>}
          </Section>
          <Section title={`Unscheduled (${unscheduled.length})`} testId="planner-unscheduled" onDrop={(e) => handleDrop(e, null)}>
            {unscheduled.length ? unscheduled.map((i) => <PlanChip key={i.id} item={i} color={seriesById[i.series_id]?.color} onClick={() => setOpen(i)} />)
              : <p className="text-xs text-stone-500 italic">Drop calendar items here to unschedule.</p>}
          </Section>
          <Section title="Coverage suggestions" testId="planner-suggestions">
            {suggestions.length ? suggestions.map((s) => (
              <SourceCard key={s.id} label={s.title} sub={s.primary_scripture} payload={{ kind: "suggestion", data: s }} testId={`planner-suggestion-${s.id}`}
                onAdd={() => setOpen(fromSuggestion(s))} />
            )) : <p className="text-xs text-stone-500 italic flex items-center gap-1"><Lightbulb className="h-3.5 w-3.5" /> Run "Suggest" on the Coverage page to get ideas here.</p>}
          </Section>
          <Section title="Episodes in progress" testId="planner-drafts">
            {drafts.filter((d) => !plannedEpisodeIds.has(d.id)).map((d) => (
              <SourceCard key={d.id} label={d.title} sub={d.primary_scripture} payload={{ kind: "episode", id: d.id }} testId={`planner-draft-${d.id}`}
                onAdd={() => setOpen({ episode_id: d.id, title: d.title, primary_scripture: d.primary_scripture, topic: d.topic })} />
            ))}
            {!drafts.filter((d) => !plannedEpisodeIds.has(d.id)).length && <p className="text-xs text-stone-500 italic">No unplanned drafts.</p>}
          </Section>
          <p className="text-xs text-stone-500 px-1">Drag cards onto a day to schedule. Drag calendar items to move them.</p>
        </aside>
        <section className="lg:col-span-9">
          <CalendarGrid month={month} items={items} seriesById={seriesById} onDrop={handleDrop} onOpen={setOpen} />
        </section>
      </div>
      {open && <PlanItemDialog item={open} series={series} onClose={() => setOpen(null)} onSaved={load} />}
      <SeriesDialog open={seriesEdit.open} series={seriesEdit.series} onClose={() => setSeriesEdit({ open: false, series: null })} onSaved={load} />
    </div>
  );
}
