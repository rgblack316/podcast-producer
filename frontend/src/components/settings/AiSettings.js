import { useEffect, useState } from "react";
import { KeyRound, Loader2, PlugZap, Save } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { api, errMsg } from "@/lib/api";

function ProviderCard({ id, name, s, keyVal, setKey, model, setModel, hint }) {
  const [testing, setTesting] = useState(false);
  const test = async () => {
    setTesting(true);
    try {
      const { data } = await api.post("/settings/test", { provider: id });
      toast.success(`${name} connected (${data.model}): ${data.reply}`);
    } catch (e) {
      toast.error(errMsg(e));
    } finally {
      setTesting(false);
    }
  };
  return (
    <div className="card-warm p-6 space-y-4" data-testid={`provider-card-${id}`}>
      <div className="flex items-center justify-between">
        <h3 className="f-serif text-xl">{name}</h3>
        <span className={`text-xs font-semibold px-2 py-0.5 rounded-full border ${s[`${id}_configured`] ? "bg-[#DCFCE7] text-[#15803D] border-[#86EFAC]" : "bg-[#F4EFE6] text-stone-500 border-[#E7E0D6]"}`}
          data-testid={`${id}-key-status`}>
          {s[`${id}_configured`] ? `Key saved ${s[`${id}_api_key_masked`]}` : "No key"}
        </span>
      </div>
      <div className="space-y-1.5">
        <Label htmlFor={`${id}-key`}>API key</Label>
        <Input id={`${id}-key`} type="password" value={keyVal} onChange={(e) => setKey(e.target.value)} autoComplete="off"
          placeholder={s[`${id}_configured`] ? "Leave blank to keep the saved key" : "Paste your API key"} className="bg-[#FFFDF9] f-mono"
          data-testid={`settings-${id}-api-key-input`} />
        <p className="text-xs text-stone-500">{hint}</p>
      </div>
      <div className="space-y-1.5">
        <Label htmlFor={`${id}-model`}>Model</Label>
        <Input id={`${id}-model`} value={model} onChange={(e) => setModel(e.target.value)} className="bg-[#FFFDF9] f-mono"
          data-testid={`settings-${id}-model-input`} />
      </div>
      <Button variant="outline" size="sm" className="bg-[#FFFDF9]" onClick={test} disabled={testing || !s[`${id}_configured`]} data-testid={`settings-${id}-test-btn`}>
        {testing ? <Loader2 className="h-4 w-4 mr-1.5 animate-spin" /> : <PlugZap className="h-4 w-4 mr-1.5" />} Test connection
      </Button>
    </div>
  );
}

export function AiSettings() {
  const [s, setS] = useState(null);
  const [form, setForm] = useState({});
  const [busy, setBusy] = useState(false);

  const apply = (data) => {
    setS(data);
    setForm({ show_name: data.show_name, default_provider: data.default_provider, gemini_model: data.gemini_model,
      openai_model: data.openai_model, extra_instructions: data.extra_instructions, gemini_api_key: "", openai_api_key: "" });
  };
  useEffect(() => { api.get("/settings").then((r) => apply(r.data)); }, []);
  if (!s) return <p className="text-stone-500 italic">Loading…</p>;

  const set = (k) => (v) => setForm({ ...form, [k]: v });
  const save = async () => {
    setBusy(true);
    const body = { ...form };
    if (!body.gemini_api_key) delete body.gemini_api_key;
    if (!body.openai_api_key) delete body.openai_api_key;
    try {
      const { data } = await api.put("/settings", body);
      apply(data);
      toast.success("Settings saved");
    } catch (e) {
      toast.error(errMsg(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="card-warm p-6 grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="space-y-1.5">
          <Label htmlFor="show-name">Show name</Label>
          <Input id="show-name" value={form.show_name} onChange={(e) => set("show_name")(e.target.value)} className="bg-[#FFFDF9]" data-testid="settings-show-name-input" />
        </div>
        <div className="space-y-2">
          <Label>Default AI provider</Label>
          <RadioGroup value={form.default_provider} onValueChange={set("default_provider")} className="flex gap-6" data-testid="settings-ai-provider-select">
            <label className="flex items-center gap-2 text-sm"><RadioGroupItem value="gemini" data-testid="provider-radio-gemini" /> Google Gemini</label>
            <label className="flex items-center gap-2 text-sm"><RadioGroupItem value="openai" data-testid="provider-radio-openai" /> OpenAI ChatGPT</label>
          </RadioGroup>
        </div>
        <div className="md:col-span-2 space-y-1.5">
          <Label htmlFor="extra">Standing instructions for every generation</Label>
          <Textarea id="extra" rows={3} value={form.extra_instructions} onChange={(e) => set("extra_instructions")(e.target.value)}
            placeholder="e.g. Use the ESV when quoting. Keep the host voice conversational and warm." className="bg-[#FFFDF9]" data-testid="settings-extra-instructions-input" />
        </div>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <ProviderCard id="gemini" name="Google Gemini" s={s} keyVal={form.gemini_api_key} setKey={set("gemini_api_key")}
          model={form.gemini_model} setModel={set("gemini_model")} hint="Create a key at aistudio.google.com/apikey" />
        <ProviderCard id="openai" name="OpenAI ChatGPT" s={s} keyVal={form.openai_api_key} setKey={set("openai_api_key")}
          model={form.openai_model} setModel={set("openai_model")} hint="Create a key at platform.openai.com/api-keys" />
      </div>
      <div className="flex items-center gap-3">
        <Button onClick={save} disabled={busy} className="rounded-full" data-testid="settings-save-api-key-btn">
          {busy ? <Loader2 className="h-4 w-4 mr-1.5 animate-spin" /> : <Save className="h-4 w-4 mr-1.5" />} Save settings
        </Button>
        <span className="text-xs text-stone-500 flex items-center gap-1"><KeyRound className="h-3.5 w-3.5" /> Keys are stored only in your server's database.</span>
      </div>
    </div>
  );
}
