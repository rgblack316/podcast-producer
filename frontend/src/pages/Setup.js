import { useRef, useState } from "react";
import { ArrowLeft, ArrowRight, Check, Loader2, Upload } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { api, errMsg } from "@/lib/api";

const STEPS = ["Admin account", "Podcast", "AI provider"];

function Field({ label, hint, children }) {
  return <div className="space-y-1.5"><Label>{label}</Label>{children}{hint && <p className="text-xs text-stone-500">{hint}</p>}</div>;
}

function RestorePanel({ token, onBack }) {
  const ref = useRef();
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const upload = async (file) => {
    setBusy(true);
    const fd = new FormData();
    fd.append("file", file);
    fd.append("setup_token", token);
    try { setResult((await api.post("/setup/restore", fd)).data); } catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); }
  };
  if (result) {
    return (
      <div className="space-y-4" data-testid="setup-restore-done">
        <h2 className="f-serif text-3xl">Backup restored</h2>
        <p className="text-stone-600">{result.restored.episodes} episodes, {result.restored.users} accounts and {result.restored.documents} documents were restored. Sign in with an account from the backup.</p>
        <Button className="rounded-full" onClick={() => (window.location.href = "/login")} data-testid="setup-go-login-btn">Go to sign in</Button>
      </div>
    );
  }
  return (
    <div className="space-y-5" data-testid="setup-restore-panel">
      <h2 className="f-serif text-3xl">Restore from a backup</h2>
      <p className="text-stone-600">Choose a <span className="f-mono text-sm">bible-bytes-backup-*.zip</span> file. Accounts, episodes, documents, settings and artwork will be restored and the remaining setup steps are skipped.</p>
      <input ref={ref} type="file" accept=".zip" className="hidden" onChange={(e) => e.target.files[0] && upload(e.target.files[0])} data-testid="setup-restore-input" />
      <div className="flex gap-2">
        <Button variant="ghost" onClick={onBack} data-testid="setup-restore-back-btn"><ArrowLeft className="h-4 w-4 mr-1" /> Back</Button>
        <Button className="rounded-full" onClick={() => ref.current.click()} disabled={busy} data-testid="setup-restore-choose-btn">
          {busy ? <Loader2 className="h-4 w-4 mr-1.5 animate-spin" /> : <Upload className="h-4 w-4 mr-1.5" />} Choose backup file
        </Button>
      </div>
    </div>
  );
}

export default function Setup({ tokenRequired, disabled }) {
  const [mode, setMode] = useState(null);
  const [step, setStep] = useState(0);
  const [token, setToken] = useState("");
  const [admin, setAdmin] = useState({ username: "", name: "", password: "", confirm: "" });
  const [podcast, setPodcast] = useState({ show_name: "Bible Bytes", show_tagline: "", host_names: "", show_description: "", audience: "" });
  const [ai, setAi] = useState({ default_provider: "gemini", gemini_api_key: "", openai_api_key: "" });
  const [busy, setBusy] = useState(false);

  const valid = [
    admin.username.trim().length >= 3 && admin.password.length >= 8 && admin.password === admin.confirm,
    podcast.show_name.trim().length > 0,
    true,
  ];
  const finish = async () => {
    setBusy(true);
    try {
      const { confirm, ...a } = admin;
      await api.post("/setup", { setup_token: token, admin: a, podcast, ai });
      toast.success("Setup complete. Welcome!");
      window.location.href = "/";
    } catch (e) { toast.error(errMsg(e)); setBusy(false); }
  };
  if (disabled) {
    return (
      <div className="min-h-screen grid place-items-center p-6 paper-grain" data-testid="setup-locked">
        <div className="card-warm p-8 max-w-lg space-y-3">
          <h1 className="f-serif text-2xl font-semibold">Setup is locked</h1>
          <p className="text-sm text-stone-600">This server has no SETUP_TOKEN, so first-run setup is turned off. Add a line like
            <code className="mx-1">SETUP_TOKEN=some-long-random-value</code> to the server's .env file, then run
            <code className="mx-1">sudo podcast-producer-upgrade</code> and reload this page.</p>
        </div>
      </div>
    );
  }
  const bind = (obj, setObj, k, testId, props = {}) => ({ value: obj[k], onChange: (e) => setObj({ ...obj, [k]: e.target.value }), className: "bg-[#FFFDF9]", "data-testid": testId, ...props });

  return (
    <div className="min-h-screen grid lg:grid-cols-5" data-testid="setup-page">
      <div className="hidden lg:flex lg:col-span-2 bg-black flex-col items-center justify-center p-12 gap-6">
        <img src="/cover.webp" alt="Bible Bytes" className="w-full max-w-[380px] aspect-square object-contain" />
        <p className="eyebrow !text-[#FDE68A]">First-time setup</p>
      </div>
      <div className="lg:col-span-3 flex items-center justify-center p-6 sm:p-12 paper-grain">
        <div className="w-full max-w-xl space-y-8 fade-up">
          <div className="flex items-center gap-3">
            <img src="/logo-mark.png" alt="" className="h-12 w-12 rounded-lg border border-[#E2DACD]" />
            <h1 className="f-serif text-3xl sm:text-4xl font-semibold tracking-tight">Welcome to <span className="italic font-normal text-[#B45309]">Producer</span></h1>
          </div>
          {tokenRequired && (
            <Field label="Setup token" hint="Set as SETUP_TOKEN in your server's .env file.">
              <Input type="password" value={token} onChange={(e) => setToken(e.target.value)} className="bg-[#FFFDF9]" data-testid="setup-token-input" />
            </Field>
          )}
          {mode === null && (
            <div className="grid sm:grid-cols-2 gap-4" data-testid="setup-mode-choice">
              <button onClick={() => setMode("fresh")} className="card-warm p-6 text-left hover:border-[#B45309] transition-colors" data-testid="setup-fresh-btn">
                <p className="f-serif text-xl">Start fresh</p>
                <p className="text-sm text-stone-500 mt-1">Create the admin account and describe your podcast.</p>
              </button>
              <button onClick={() => setMode("restore")} className="card-warm p-6 text-left hover:border-[#B45309] transition-colors" data-testid="setup-restore-btn">
                <p className="f-serif text-xl">Restore a backup</p>
                <p className="text-sm text-stone-500 mt-1">Moving servers? Import a backup .zip and skip setup.</p>
              </button>
            </div>
          )}
          {mode === "restore" && <RestorePanel token={token} onBack={() => setMode(null)} />}
          {mode === "fresh" && (
            <div className="space-y-6">
              <ol className="flex gap-4 text-sm" data-testid="setup-steps">
                {STEPS.map((s, i) => (
                  <li key={s} className={`flex items-center gap-2 ${i === step ? "text-[#1C1917] font-semibold" : "text-stone-500"}`}>
                    <span className={`h-6 w-6 rounded-full grid place-items-center text-xs border ${i < step ? "bg-[#3F6212] border-[#3F6212] text-white" : i === step ? "bg-[#B45309] border-[#B45309] text-white" : "border-[#E2DACD]"}`}>
                      {i < step ? <Check className="h-3 w-3" /> : i + 1}</span>{s}
                  </li>
                ))}
              </ol>
              {step === 0 && (
                <div className="space-y-4" data-testid="setup-step-admin">
                  <Field label="Username" hint="At least 3 characters. Used to sign in."><Input {...bind(admin, setAdmin, "username", "setup-admin-username-input", { autoComplete: "username" })} /></Field>
                  <Field label="Your name"><Input {...bind(admin, setAdmin, "name", "setup-admin-name-input")} /></Field>
                  <Field label="Password" hint="At least 8 characters."><Input type="password" {...bind(admin, setAdmin, "password", "setup-admin-password-input", { autoComplete: "new-password" })} /></Field>
                  <Field label="Confirm password"><Input type="password" {...bind(admin, setAdmin, "confirm", "setup-admin-confirm-input", { autoComplete: "new-password" })} /></Field>
                  {admin.confirm && admin.password !== admin.confirm && <p className="text-sm text-red-700">Passwords don't match.</p>}
                </div>
              )}
              {step === 1 && (
                <div className="space-y-4" data-testid="setup-step-podcast">
                  <Field label="Podcast name *"><Input {...bind(podcast, setPodcast, "show_name", "setup-show-name-input")} /></Field>
                  <Field label="Tagline"><Input {...bind(podcast, setPodcast, "show_tagline", "setup-tagline-input", { placeholder: "Inspiring Faith One Byte at a Time" })} /></Field>
                  <Field label="Host name(s)"><Input {...bind(podcast, setPodcast, "host_names", "setup-hosts-input")} /></Field>
                  <Field label="About the show" hint="The AI reads this before every outline and script."><Textarea rows={3} {...bind(podcast, setPodcast, "show_description", "setup-description-input")} /></Field>
                  <Field label="Audience"><Input {...bind(podcast, setPodcast, "audience", "setup-audience-input", { placeholder: "e.g. busy believers who want a short daily scripture" })} /></Field>
                </div>
              )}
              {step === 2 && (
                <div className="space-y-4" data-testid="setup-step-ai">
                  <Field label="Default AI provider">
                    <RadioGroup value={ai.default_provider} onValueChange={(v) => setAi({ ...ai, default_provider: v })} className="flex gap-6">
                      <label className="flex items-center gap-2 text-sm"><RadioGroupItem value="gemini" data-testid="setup-provider-gemini" /> Google Gemini</label>
                      <label className="flex items-center gap-2 text-sm"><RadioGroupItem value="openai" data-testid="setup-provider-openai" /> OpenAI ChatGPT</label>
                    </RadioGroup>
                  </Field>
                  <Field label="Gemini API key" hint="Optional now; add later in Settings. aistudio.google.com/apikey"><Input type="password" {...bind(ai, setAi, "gemini_api_key", "setup-gemini-key-input", { className: "bg-[#FFFDF9] f-mono" })} /></Field>
                  <Field label="OpenAI API key" hint="Optional. platform.openai.com/api-keys"><Input type="password" {...bind(ai, setAi, "openai_api_key", "setup-openai-key-input", { className: "bg-[#FFFDF9] f-mono" })} /></Field>
                </div>
              )}
              <div className="flex justify-between pt-2">
                <Button variant="ghost" onClick={() => (step ? setStep(step - 1) : setMode(null))} data-testid="setup-back-btn"><ArrowLeft className="h-4 w-4 mr-1" /> Back</Button>
                {step < 2 ? (
                  <Button className="rounded-full" onClick={() => setStep(step + 1)} disabled={!valid[step]} data-testid="setup-next-btn">Next <ArrowRight className="h-4 w-4 ml-1" /></Button>
                ) : (
                  <Button className="rounded-full" onClick={finish} disabled={busy || !valid[0] || !valid[1]} data-testid="setup-finish-btn">
                    {busy && <Loader2 className="h-4 w-4 mr-1.5 animate-spin" />} Finish setup
                  </Button>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
