import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Layers, X } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { api, errMsg } from "@/lib/api";
import { AddToSeriesDialog } from "@/components/AddToSeriesDialog";

export function EpisodeSeries({ episode }) {
  const [series, setSeries] = useState([]);
  const [current, setCurrent] = useState(null);
  const [open, setOpen] = useState(false);
  const load = useCallback(async () => {
    const [s, m] = await Promise.all([api.get("/series"), api.get("/series/membership")]);
    setSeries(s.data);
    setCurrent(s.data.find((x) => x.id === m.data[episode.id]) || null);
  }, [episode.id]);
  useEffect(() => { load(); }, [load]);

  const remove = async () => {
    try {
      await api.post("/series/remove-episodes", { episode_ids: [episode.id] });
      toast.success("Removed from series");
      load();
    } catch (e) { toast.error(errMsg(e)); }
  };

  return (
    <div data-testid="episode-series-panel">
      <p className="eyebrow mb-2">Series</p>
      <div className="flex flex-wrap items-center gap-2">
        {current ? (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-[#FFFDF9] border border-[#E7E0D6] text-sm" data-testid="episode-series-badge">
            <span className="h-2.5 w-2.5 rounded-full" style={{ background: current.color }} /><Link to={`/series/${current.id}`} className="hover:text-[#B45309]" data-testid="episode-series-link">{current.name}</Link>
            <button onClick={remove} className="text-stone-400 hover:text-red-700" title="Remove from series" data-testid="episode-series-remove-btn"><X className="h-3.5 w-3.5" /></button>
          </span>
        ) : <span className="text-sm text-stone-500 italic">Not in a series</span>}
        <Button variant="ghost" size="sm" onClick={() => setOpen(true)} data-testid="episode-add-to-series-btn">
          <Layers className="h-4 w-4 mr-1.5" /> {current ? "Change" : "Add to series"}
        </Button>
      </div>
      <AddToSeriesDialog open={open} episodeIds={[episode.id]} series={series} onClose={() => setOpen(false)} onDone={load} />
    </div>
  );
}
