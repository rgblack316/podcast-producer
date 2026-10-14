import { Check } from "lucide-react";

const STEPS = ["Intake", "Outline", "Script", "Done"];
const ACTIVE = { intake: 0, draft: 1, outline_approved: 2, script_complete: 3, published: 4 };

export function StepIndicator({ status }) {
  const current = ACTIVE[status] ?? 1;
  return (
    <ol className="flex items-center gap-2 sm:gap-3 flex-wrap" data-testid="step-indicator">
      {STEPS.map((label, i) => {
        const done = i < current;
        const active = i === current;
        return (
          <li key={label} className="flex items-center gap-2 sm:gap-3" data-testid={`step-${label.toLowerCase()}`}>
            <span
              className={`h-7 w-7 rounded-full grid place-items-center text-xs font-semibold border transition-colors ${
                done ? "bg-[#3F6212] border-[#3F6212] text-white"
                  : active ? "bg-[#B45309] border-[#B45309] text-white" : "bg-[#FFFDF9] border-[#E2DACD] text-stone-500"
              }`}
            >
              {done ? <Check className="h-3.5 w-3.5" /> : i + 1}
            </span>
            <span className={`text-sm font-medium ${active ? "text-[#1C1917]" : "text-stone-500"}`}>{label}</span>
            {i < STEPS.length - 1 && <span className="w-6 sm:w-10 h-px bg-[#E2DACD]" />}
          </li>
        );
      })}
    </ol>
  );
}
