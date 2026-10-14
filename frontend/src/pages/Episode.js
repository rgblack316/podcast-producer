import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { PencilLine, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter,
  AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { api, errMsg, fmtDate } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { StepIndicator } from "@/components/StepIndicator";
import { StatusBadge } from "@/components/StatusBadge";
import { format, parseISO } from "date-fns";
import { DocStage } from "@/components/DocStage";
import { AssetsStage } from "@/components/AssetsStage";
import { ArtworkStudio } from "@/components/ArtworkStudio";
import { EpisodeSeries } from "@/components/EpisodeSeries";
import { EpisodeForm, fromForm, toForm } from "@/components/EpisodeForm";
import { SimilarEpisodes } from "@/components/SimilarEpisodes";

function Detail({ label, children }) {
  if (!children || (Array.isArray(children) && !children.length)) return null;
  return (
    <div>
      <p className="eyebrow mb-1">{label}</p>
      <div className="text-[#44403C] text-sm leading-relaxed whitespace-pre-wrap">{children}</div>
    </div>
  );
}

function EditIntake({ episode, onChange }) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(toForm(episode));
  const save = async () => {
    try {
      const { data } = await api.put(`/episodes/${episode.id}`, fromForm(form));
      onChange(data);
      setOpen(false);
      toast.success("Intake updated");
    } catch (e) {
      toast.error(errMsg(e));
    }
  };
  return (
    <>
      <Button variant="ghost" size="sm" onClick={() => { setForm(toForm(episode)); setOpen(true); }} data-testid="edit-intake-btn">
        <PencilLine className="h-4 w-4 mr-1.5" /> Edit intake
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto bg-[#FAF7F2]">
          <DialogHeader><DialogTitle className="f-serif text-2xl">Edit intake</DialogTitle></DialogHeader>
          <EpisodeForm form={form} setForm={setForm} />
          <DialogFooter><Button onClick={save} data-testid="edit-intake-save-btn">Save changes</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

function IntakePanel({ episode, onChange, isAdmin, onDelete }) {
  return (
    <aside className="lg:col-span-4 rounded-xl bg-[#F4EFE6]/70 border border-[#E2DACD] p-6 space-y-6 lg:sticky lg:top-24 lg:max-h-[calc(100vh-7rem)] lg:overflow-y-auto" data-testid="outline-left-scripture-panel">
      <div className="flex items-center justify-between">
        <StatusBadge status={episode.status} testId="episode-status-badge" />
        <EditIntake episode={episode} onChange={onChange} />
      </div>
      <blockquote className="f-serif italic text-xl text-[#292524] bg-[#FFFDF9] p-4 rounded-md border-l-4 border-[#B45309]" data-testid="episode-primary-scripture">
        {episode.primary_scripture}
      </blockquote>
      <Detail label="Topic">{episode.topic}</Detail>
      <EpisodeSeries episode={episode} />
      <Detail label="Supporting scriptures">{(episode.supporting_scriptures || []).join("\n")}</Detail>
      {episode.themes?.length > 0 && (
        <div>
          <p className="eyebrow mb-2">Themes</p>
          <div className="flex flex-wrap gap-1.5">
            {episode.themes.map((t) => <span key={t} className="px-2.5 py-0.5 rounded-full bg-[#FFFDF9] border border-[#E7E0D6] text-xs">{t}</span>)}
          </div>
        </div>
      )}
      <Detail label="Target length">{episode.target_length}</Detail>
      <Detail label="Target publish date">{episode.target_date ? <span data-testid="episode-target-date">{format(parseISO(episode.target_date), "EEEE, MMMM d, yyyy")}</span> : null}</Detail>
      <Detail label="Audience">{episode.audience_notes}</Detail>
      <Detail label="Guidance">{episode.guidance}</Detail>
      <div className="space-y-2">
        <p className="eyebrow">Related past episodes</p>
        <SimilarEpisodes scripture={[episode.primary_scripture, ...(episode.supporting_scriptures || [])].join(";")}
          themes={(episode.themes || []).join(",")} topic={episode.topic} exclude={episode.id} />
      </div>
      <div className="f-mono text-[11px] text-stone-500 space-y-0.5 pt-2 border-t border-[#E2DACD]">
        <div>Created {fmtDate(episode.created_at)} by {episode.created_by}</div>
        {episode.outline_approved_at && <div>Outline approved {fmtDate(episode.outline_approved_at)}</div>}
        {episode.script_completed_at && <div>Script completed {fmtDate(episode.script_completed_at)}</div>}
        {episode.published_at && <div>Published {fmtDate(episode.published_at)}</div>}
      </div>
      {isAdmin && (
        <AlertDialog>
          <AlertDialogTrigger asChild>
            <Button variant="ghost" size="sm" className="text-red-700 hover:text-red-800" data-testid="delete-episode-btn">
              <Trash2 className="h-4 w-4 mr-1.5" /> Delete episode
            </Button>
          </AlertDialogTrigger>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Delete this episode?</AlertDialogTitle>
              <AlertDialogDescription>The outline, script and all versions will be permanently removed.</AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Cancel</AlertDialogCancel>
              <AlertDialogAction onClick={onDelete} data-testid="confirm-delete-episode-btn">Delete</AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      )}
    </aside>
  );
}

export default function Episode() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const [episode, setEpisode] = useState(null);
  const [providers, setProviders] = useState({ default_provider: "gemini" });
  const [tab, setTab] = useState("outline");

  const load = useCallback(() => api.get(`/episodes/${id}`).then((r) => setEpisode(r.data))
    .catch(() => { toast.error("Episode not found"); navigate("/episodes"); }), [id, navigate]);

  useEffect(() => { load(); api.get("/settings/public").then((r) => setProviders(r.data)); }, [load]);
  useEffect(() => {
    if (episode) setTab(episode.status === "draft" ? "outline" : "script");
  }, [episode?.id, episode?.status]); // eslint-disable-line react-hooks/exhaustive-deps

  const generating = !!episode?.generating || !!episode?.art_generating;
  useEffect(() => {
    if (!generating) return;
    const t = setInterval(load, 3000);
    return () => clearInterval(t);
  }, [generating, load]);

  const onDelete = async () => {
    await api.delete(`/episodes/${id}`);
    toast.success("Episode deleted");
    navigate("/episodes");
  };

  if (!episode) return <div className="p-10 f-serif italic text-stone-500">Loading episode…</div>;
  const scriptReady = episode.status !== "draft";
  return (
    <div className="max-w-[1600px] mx-auto px-4 sm:px-6 py-8 space-y-6">
      <div className="space-y-4 fade-up">
        <StepIndicator status={episode.status} />
        <div>
          <p className="eyebrow">{episode.episode_number ? `Episode ${episode.episode_number}` : "Episode"}{episode.imported ? " · Imported" : ""}</p>
          <h1 className="f-serif text-3xl sm:text-4xl lg:text-5xl font-semibold tracking-tight text-[#1C1917] mt-1" data-testid="episode-title">{episode.title}</h1>
        </div>
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        <IntakePanel episode={episode} onChange={setEpisode} isAdmin={user?.role === "admin"} onDelete={onDelete} />
        <section className="lg:col-span-8 card-warm p-4 sm:p-6">
          <Tabs value={tab} onValueChange={setTab}>
            <TabsList className="bg-[#F4EFE6] mb-5">
              <TabsTrigger value="outline" data-testid="tab-outline">Outline</TabsTrigger>
              <TabsTrigger value="script" disabled={!scriptReady && !episode.script} data-testid="tab-script">Script</TabsTrigger>
              <TabsTrigger value="assets" data-testid="tab-assets">Show notes</TabsTrigger>
              <TabsTrigger value="artwork" data-testid="tab-artwork">Artwork</TabsTrigger>
            </TabsList>
            <TabsContent value="outline">
              <DocStage episode={episode} stage="outline" editable={episode.status === "draft"} providers={providers} onChange={setEpisode} />
            </TabsContent>
            <TabsContent value="script">
              <DocStage episode={episode} stage="script" editable={episode.status === "outline_approved"} providers={providers} onChange={setEpisode} />
            </TabsContent>
            <TabsContent value="assets">
              <AssetsStage episode={episode} providers={providers} onChange={setEpisode} />
            </TabsContent>
            <TabsContent value="artwork">
              <ArtworkStudio episode={episode} providers={providers} onChange={setEpisode} />
            </TabsContent>
          </Tabs>
        </section>
      </div>
    </div>
  );
}
