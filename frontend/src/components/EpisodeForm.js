import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

export const emptyEpisode = {
  title: "", episode_number: "", topic: "", primary_scripture: "", supporting_scriptures: [],
  themes: [], target_length: "", audience_notes: "", guidance: "",
};

export function toForm(ep) {
  return {
    ...emptyEpisode,
    ...Object.fromEntries(Object.keys(emptyEpisode).map((k) => [k, ep?.[k] ?? emptyEpisode[k]])),
    supporting_text: (ep?.supporting_scriptures || []).join("\n"),
    themes_text: (ep?.themes || []).join(", "),
  };
}

export function fromForm(f) {
  const { supporting_text, themes_text, ...rest } = f;
  return {
    ...rest,
    supporting_scriptures: (supporting_text || "").split(/\n|;/).map((s) => s.trim()).filter(Boolean),
    themes: (themes_text || "").split(",").map((s) => s.trim()).filter(Boolean),
  };
}

function Field({ id, label, hint, children }) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id} className="text-[#44403C]">{label}</Label>
      {children}
      {hint && <p className="text-xs text-stone-500">{hint}</p>}
    </div>
  );
}

export function EpisodeForm({ form, setForm }) {
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });
  const bind = (k, testId, props = {}) => ({ id: k, value: form[k], onChange: set(k), "data-testid": testId, className: "bg-[#FFFDF9]", ...props });
  return (
    <div className="grid grid-cols-1 sm:grid-cols-6 gap-5" data-testid="intake-form">
      <div className="sm:col-span-4">
        <Field id="title" label="Episode title *"><Input {...bind("title", "intake-title-input", { placeholder: "e.g. The God Who Sees" })} /></Field>
      </div>
      <div className="sm:col-span-2">
        <Field id="episode_number" label="Episode #"><Input {...bind("episode_number", "intake-episode-number-input", { placeholder: "42" })} /></Field>
      </div>
      <div className="sm:col-span-6">
        <Field id="topic" label="Topic *"><Input {...bind("topic", "intake-topic-input", { placeholder: "Hagar and God's attentiveness to the overlooked" })} /></Field>
      </div>
      <div className="sm:col-span-3">
        <Field id="primary_scripture" label="Primary scripture *" hint="Free text, e.g. Genesis 16:7-14">
          <Input {...bind("primary_scripture", "intake-scripture-input", { className: "bg-[#FFFDF9] f-serif text-base" })} />
        </Field>
      </div>
      <div className="sm:col-span-3">
        <Field id="themes_text" label="Themes" hint="Comma separated, e.g. Grace, Identity">
          <Input {...bind("themes_text", "intake-themes-input")} />
        </Field>
      </div>
      <div className="sm:col-span-3">
        <Field id="supporting_text" label="Supporting scriptures" hint="One per line">
          <Textarea {...bind("supporting_text", "intake-supporting-input", { rows: 3, className: "bg-[#FFFDF9] f-serif" })} />
        </Field>
      </div>
      <div className="sm:col-span-3">
        <Field id="target_length" label="Target length"><Input {...bind("target_length", "intake-length-input", { placeholder: "e.g. 15 minutes" })} /></Field>
      </div>
      <div className="sm:col-span-6">
        <Field id="audience_notes" label="Audience notes">
          <Textarea {...bind("audience_notes", "intake-audience-input", { rows: 2, placeholder: "Who is this for? What do they already know?" })} />
        </Field>
      </div>
      <div className="sm:col-span-6">
        <Field id="guidance" label="Extra guidance for the writer">
          <Textarea {...bind("guidance", "intake-guidance-input", { rows: 3, placeholder: "Illustrations to include, tone, things to avoid…" })} />
        </Field>
      </div>
    </div>
  );
}
