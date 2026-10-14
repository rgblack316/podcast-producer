import { CheckCircle2, Lock, Radio, Unlock } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { api, errMsg } from "@/lib/api";

const ACTIONS = {
  outline: {
    draft: [{ to: "outline_approved", label: "Approve outline", icon: CheckCircle2, primary: true, msg: "Outline approved. Script step unlocked." }],
    outline_approved: [{ to: "draft", label: "Reopen outline", icon: Unlock }],
    script_complete: [{ to: "draft", label: "Reopen outline", icon: Unlock }],
  },
  script: {
    outline_approved: [{ to: "script_complete", label: "Mark script complete", icon: CheckCircle2, primary: true, msg: "Script marked complete" }],
    script_complete: [
      { to: "published", label: "Mark published", icon: Radio, primary: true, msg: "Episode published" },
      { to: "outline_approved", label: "Reopen script", icon: Unlock },
    ],
    published: [{ to: "script_complete", label: "Unpublish", icon: Unlock }],
  },
};

export function StageActions({ episode, stage, disabled, onChange }) {
  const actions = ACTIONS[stage][episode.status] || [];
  const locked = stage === "outline" ? episode.status !== "draft" : episode.status !== "outline_approved";

  const run = async (a) => {
    try {
      const { data } = await api.post(`/episodes/${episode.id}/status`, { status: a.to });
      onChange(data);
      toast.success(a.msg || "Status updated");
    } catch (e) {
      toast.error(errMsg(e));
    }
  };

  if (!actions.length && !locked) return null;
  return (
    <div className="flex flex-wrap items-center gap-3 pt-4 border-t border-[#EFE8DC]">
      {locked && (
        <span className="flex items-center gap-1.5 text-sm text-stone-500" data-testid={`${stage}-locked-note`}>
          <Lock className="h-3.5 w-3.5" /> {stage === "outline" ? "Outline approved and locked" : "Script locked"}
        </span>
      )}
      <div className="ml-auto flex flex-wrap gap-2">
        {actions.map((a) => (
          <Button key={a.to} variant={a.primary ? "default" : "outline"} className={a.primary ? "rounded-full" : "rounded-full bg-[#FFFDF9]"}
            disabled={disabled || (a.primary && !(episode[stage] || "").trim())} onClick={() => run(a)}
            data-testid={`${stage}-action-${a.to}`}>
            <a.icon className="h-4 w-4 mr-1.5" /> {a.label}
          </Button>
        ))}
      </div>
    </div>
  );
}
