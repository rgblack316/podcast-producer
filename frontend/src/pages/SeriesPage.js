import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ImagePlus, Loader2, PencilLine, Upload } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { API, api, errMsg, fmtDate } from "@/lib/api";
import { StatusBadge } from "@/components/StatusBadge";
import { ArtworkStudio } from "@/components/ArtworkStudio";
import { SeriesDialog } from "@/components/planner/SeriesDialog";
import { SeriesCover } from "@/pages/SeriesList";

function EpisodeArtPicker({ series, onChange }) {
  const [open, setOpen] = useState(false);
  const options = series.entries.flatMap((e) => (e.episode?.artwork?.images || []).map((img) => ({ ep: e.episode, img })));
  const pick = async (o) => {
    try {
      onChange((await api.post(`/series/${series.id}/artwork/from-episode`, { episode_id: o.ep.id, image_id: o.img.id })).data);
      toast.success("Cover set from episode artwork");
      setOpen(false);
    } catch (e) { toast.error(errMsg(e)); }
  };
  return (
    <>
      <Button variant="outline" size="sm" className="bg-[#FFFDF9]" onClick={() => setOpen(true)} disabled={!options.length} data-testid="series-pick-episode-art-btn">
        <ImagePlus className="h-4 w-4 mr-1.5" /> Use episode artwork
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-3xl bg-[#FAF7F2] max-h-[85vh] overflow-y-auto" data-testid="series-episode-art-dialog">
          <DialogHeader><DialogTitle className="f-serif text-2xl">Pick from episode artwork</DialogTitle></DialogHeader>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            {options.map((o) => (
              <button key={o.img.id} onClick={() => pick(o)} className="text-left group" data-testid={`series-episode-art-${o.img.id}`}>
                <img src={`${API}/episodes/${o.ep.id}/artwork/${o.img.id}.png`} alt={o.ep.title} className="w-full aspect-square object-cover rounded-md border-2 border-transparent group-hover:border-[#B45309]" />
                <span className="text-xs text-stone-600 truncate block mt-1">{o.ep.title}</span>
              </button>
            ))}
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}

function UploadCover({ series, onChange }) {
  const ref = useRef();
  const [busy, setBusy] = useState(false);
  const upload = async (file) => {
    setBusy(true);
    const fd = new FormData();
    fd.append("file", file);
    try { onChange((await api.post(`/series/${series.id}/artwork/upload`, fd)).data); toast.success("Cover uploaded"); }
    catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); ref.current.value = ""; }
  };
  return (
    <>
      <input ref={ref} type="file" accept="image/png,image/jpeg,image/webp" className="hidden" onChange={(e) => e.target.files[0] && upload(e.target.files[0])} data-testid="series-cover-upload-input" />
      <Button variant="outline" size="sm" className="bg-[#FFFDF9]" onClick={() => ref.current.click()} disabled={busy} data-testid="series-cover-upload-btn">
        {busy ? <Loader2 className="h-4 w-4 mr-1.5 animate-spin" /> : <Upload className="h-4 w-4 mr-1.5" />} Upload image
      </Button>
    </>
  );
}

function Coverage({ series }) {
  const testaments = ["OT", "NT"].map((t) => [t, series.books.filter((b) => b.testament === t)]);
  return (
    <div className="card-warm p-6 space-y-5" data-testid="series-coverage">
      <h2 className="f-serif text-2xl">Scripture coverage</h2>
      {!series.books.length ? <p className="text-sm text-stone-500 italic">Appears once episodes with scripture are in the series.</p> : testaments.map(([t, books]) => books.length > 0 && (
        <div key={t}>
          <p className="eyebrow mb-2">{t === "OT" ? "Old Testament" : "New Testament"}</p>
          <div className="flex flex-wrap gap-1.5">
            {books.map((b) => (
              <span key={b.name} className="px-2.5 py-1 rounded-md text-xs font-medium text-white" style={{ background: series.color, opacity: 0.55 + Math.min(b.count, 5) * 0.09 }} data-testid={`series-book-${b.name.replace(/\s/g, "-")}`}>
                {b.name} <span className="f-mono">{b.count}</span>
              </span>
            ))}
          </div>
        </div>
      ))}
      {series.themes.length > 0 && (
        <div>
          <p className="eyebrow mb-2">Themes</p>
          <div className="flex flex-wrap gap-1.5">
            {series.themes.map((t) => <span key={t.name} className="px-2.5 py-0.5 rounded-full bg-[#F4EFE6] border border-[#E7E0D6] text-xs capitalize">{t.name} <span className="f-mono text-stone-500">{t.count}</span></span>)}
          </div>
        </div>
      )}
    </div>
  );
}

export default function SeriesPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [series, setSeries] = useState(null);
  const [providers, setProviders] = useState({ default_provider: "gemini" });
  const [editing, setEditing] = useState(false);
  const load = useCallback(() => api.get(`/series/${id}/detail`).then((r) => setSeries(r.data))
    .catch(() => { toast.error("Series not found"); navigate("/series"); }), [id, navigate]);
  useEffect(() => { load(); api.get("/settings/public").then((r) => setProviders(r.data)); }, [load]);
  useEffect(() => {
    if (!series?.art_generating) return;
    const t = setInterval(load, 3000);
    return () => clearInterval(t);
  }, [series?.art_generating, load]);

  if (!series) return <div className="p-10 f-serif italic text-stone-500">Loading series…</div>;
  const done = series.entries.filter((e) => e.episode?.status === "published").length;
  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-8 py-10 space-y-8" data-testid="series-page">
      <section className="grid md:grid-cols-[280px_1fr] gap-8 items-end fade-up">
        <SeriesCover series={series} className="w-full rounded-xl shadow-lg" />
        <div className="space-y-3">
          <p className="eyebrow flex items-center gap-2"><span className="h-2.5 w-2.5 rounded-full" style={{ background: series.color }} /> Series</p>
          <h1 className="f-serif text-4xl sm:text-5xl lg:text-6xl font-semibold tracking-tight text-[#1C1917]" data-testid="series-title">{series.name}</h1>
          {series.description && <p className="text-[#44403C] max-w-2xl text-lg">{series.description}</p>}
          <p className="f-mono text-sm text-stone-500" data-testid="series-stats">{series.entries.length} episodes · {done} published · {series.books.length} books</p>
          <Button variant="outline" size="sm" className="bg-[#FFFDF9]" onClick={() => setEditing(true)} data-testid="series-edit-btn"><PencilLine className="h-4 w-4 mr-1.5" /> Edit series</Button>
        </div>
      </section>
      <div className="grid lg:grid-cols-12 gap-6 items-start">
        <div className="lg:col-span-7 card-warm p-6" data-testid="series-episodes">
          <h2 className="f-serif text-2xl mb-2">Episodes</h2>
          {!series.entries.length ? <p className="text-sm text-stone-500 italic">Add episodes from the Library, an episode page or the Planner.</p> : (
            <ol className="divide-y divide-[#EFE8DC]">
              {series.entries.map((e, i) => {
                const row = (
                  <div className="flex items-center gap-4 py-3">
                    <span className="f-serif text-2xl text-stone-300 w-8 text-right">{i + 1}</span>
                    <div className="min-w-0 flex-1">
                      <div className="f-serif text-lg text-[#1C1917] truncate">{e.episode?.episode_number ? `#${e.episode.episode_number} · ` : ""}{e.title}</div>
                      <div className="text-sm text-stone-500 truncate"><span className="f-serif italic">{e.primary_scripture}</span>{e.date ? ` · ${fmtDate(`${e.date}T12:00:00`)}` : ""}</div>
                    </div>
                    {e.episode ? <StatusBadge status={e.episode.status} testId={`series-entry-status-${e.plan_id}`} /> : <span className="text-xs text-stone-500 italic">Idea</span>}
                  </div>
                );
                return <li key={e.plan_id} data-testid={`series-entry-${e.plan_id}`}>{e.episode ? <Link to={`/episodes/${e.episode.id}`} className="block hover:bg-[#F4EFE6] -mx-2 px-2 rounded-md">{row}</Link> : row}</li>;
              })}
            </ol>
          )}
        </div>
        <div className="lg:col-span-5"><Coverage series={series} /></div>
      </div>
      <section className="card-warm p-6 space-y-4" data-testid="series-cover-studio">
        <h2 className="f-serif text-2xl">Cover art</h2>
        <ArtworkStudio episode={series} providers={providers} onChange={setSeries} basePath={`/series/${series.id}/artwork`} selectLabel="series cover"
          extra={<div className="flex gap-2"><UploadCover series={series} onChange={setSeries} /><EpisodeArtPicker series={series} onChange={setSeries} /></div>} />
      </section>
      <SeriesDialog open={editing} series={series} onClose={() => setEditing(false)} onSaved={(r) => (r === "deleted" ? navigate("/series") : load())} />
    </div>
  );
}
