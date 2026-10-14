import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { Loader2, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { api, errMsg } from "@/lib/api";
import { EpisodeForm, fromForm, toForm } from "@/components/EpisodeForm";
import { SimilarEpisodes } from "@/components/SimilarEpisodes";
import { StepIndicator } from "@/components/StepIndicator";

export default function NewEpisode() {
  const navigate = useNavigate();
  const location = useLocation();
  const [form, setForm] = useState(() => toForm(location.state?.prefill || null));
  const [busy, setBusy] = useState(null);
  const valid = form.title.trim() && form.topic.trim() && form.primary_scripture.trim();

  const create = async (draftOutline) => {
    setBusy(draftOutline ? "draft" : "save");
    try {
      const { data } = await api.post("/episodes", fromForm(form));
      if (location.state?.plan_id) await api.patch(`/plan/${location.state.plan_id}`, { episode_id: data.id }).catch(() => {});
      if (draftOutline) {
        await api.post(`/episodes/${data.id}/outline/generate`, { notes: "" })
          .catch((e) => toast.error(`Episode saved, but outline could not start: ${errMsg(e)}`));
      }
      toast.success("Episode created");
      navigate(`/episodes/${data.id}`);
    } catch (e) {
      toast.error(errMsg(e));
      setBusy(null);
    }
  };

  const scripture = [form.primary_scripture, form.supporting_text.replace(/\n/g, ";")].filter(Boolean).join(";");
  return (
    <div className="max-w-[1400px] mx-auto px-4 sm:px-8 py-10 space-y-8">
      <div className="space-y-4 fade-up">
        <StepIndicator status="intake" />
        <h1 className="f-serif text-4xl sm:text-5xl font-semibold tracking-tight text-[#1C1917]">New episode</h1>
        <p className="text-stone-600 max-w-2xl">Describe the episode. The outline will follow your planning template and learn from your example episodes.</p>
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        <div className="lg:col-span-8 card-warm p-6 sm:p-8 fade-up">
          <EpisodeForm form={form} setForm={setForm} />
          <div className="flex flex-wrap gap-3 mt-8 pt-6 border-t border-[#EFE8DC]">
            <Button className="rounded-full" disabled={!valid || busy} onClick={() => create(true)} data-testid="intake-submit-button">
              {busy === "draft" ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Sparkles className="h-4 w-4 mr-2" />}
              Create & draft outline
            </Button>
            <Button variant="outline" className="rounded-full bg-[#FFFDF9]" disabled={!valid || busy} onClick={() => create(false)} data-testid="intake-save-draft-button">
              {busy === "save" && <Loader2 className="h-4 w-4 mr-2 animate-spin" />} Save without generating
            </Button>
          </div>
        </div>
        <aside className="lg:col-span-4 space-y-4 fade-up" style={{ animationDelay: "100ms" }}>
          <div className="rounded-xl bg-[#F4EFE6]/70 border border-[#E2DACD] p-6 space-y-4">
            <p className="eyebrow">Repetition check</p>
            <SimilarEpisodes scripture={scripture} themes={form.themes_text} topic={form.topic} />
          </div>
        </aside>
      </div>
    </div>
  );
}
