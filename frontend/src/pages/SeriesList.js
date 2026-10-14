import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Layers, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { API, api } from "@/lib/api";
import { SeriesDialog } from "@/components/planner/SeriesDialog";

export function SeriesCover({ series, className = "" }) {
  const img = series.artwork?.selected_image_id;
  return img ? (
    <img src={`${API}/series/${series.id}/artwork/${img}.png`} alt={series.name} className={`aspect-square object-cover ${className}`} />
  ) : (
    <div className={`aspect-square grid place-items-center ${className}`} style={{ background: series.color }}>
      <Layers className="h-1/4 w-1/4 text-white/80" />
    </div>
  );
}

export default function SeriesList() {
  const [series, setSeries] = useState(null);
  const [open, setOpen] = useState(false);
  const load = () => api.get("/series").then((r) => setSeries(r.data));
  useEffect(() => { load(); }, []);
  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-8 py-10 space-y-8" data-testid="series-list-page">
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 fade-up">
        <div>
          <p className="eyebrow">Collections</p>
          <h1 className="f-serif text-4xl sm:text-5xl font-semibold tracking-tight text-[#1C1917] mt-2">Series</h1>
        </div>
        <Button className="rounded-full" onClick={() => setOpen(true)} data-testid="series-list-new-btn"><Plus className="h-4 w-4 mr-1" /> New series</Button>
      </div>
      {series === null ? <p className="text-stone-500 italic">Loading…</p> : !series.length ? (
        <p className="text-stone-500 italic" data-testid="series-list-empty">No series yet. Create one, or add episodes to a series from the Library.</p>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
          {series.map((s, i) => (
            <Link key={s.id} to={`/series/${s.id}`} className="group card-warm overflow-hidden fade-up" style={{ animationDelay: `${i * 40}ms` }} data-testid={`series-card-${s.id}`}>
              <SeriesCover series={s} className="w-full transition-transform duration-500 group-hover:scale-[1.03]" />
              <div className="p-4 border-t-4" style={{ borderTopColor: s.color }}>
                <div className="f-serif text-xl text-[#1C1917] truncate">{s.name}</div>
                <div className="text-xs text-stone-500">{s.count} episode{s.count === 1 ? "" : "s"}</div>
              </div>
            </Link>
          ))}
        </div>
      )}
      <SeriesDialog open={open} series={null} onClose={() => setOpen(false)} onSaved={load} />
    </div>
  );
}
