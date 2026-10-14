import { useState } from "react";
import { ShieldCheck } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, errMsg } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

export default function Account() {
  const { user } = useAuth();
  const [f, setF] = useState({ current_password: "", new_password: "", confirm: "" });
  const submit = async (e) => {
    e.preventDefault();
    if (f.new_password !== f.confirm) return toast.error("New passwords don't match");
    try {
      await api.post("/auth/change-password", { current_password: f.current_password, new_password: f.new_password });
      toast.success("Password changed");
      setF({ current_password: "", new_password: "", confirm: "" });
    } catch (err) {
      toast.error(errMsg(err));
    }
  };
  const field = (k, label, testId) => (
    <div className="space-y-1.5">
      <Label htmlFor={k}>{label}</Label>
      <Input id={k} type="password" value={f[k]} onChange={(e) => setF({ ...f, [k]: e.target.value })} className="bg-[#FFFDF9]" data-testid={testId} required />
    </div>
  );
  return (
    <div className="max-w-3xl mx-auto px-4 sm:px-8 py-10 space-y-8" data-testid="account-page">
      <div className="fade-up">
        <p className="eyebrow">My account</p>
        <h1 className="f-serif text-4xl font-semibold tracking-tight text-[#1C1917] mt-2">{user?.name}</h1>
        <p className="f-mono text-sm text-stone-500 mt-1">@{user?.username} · {user?.role}</p>
      </div>
      <form onSubmit={submit} className="card-warm p-6 space-y-4">
        <h3 className="f-serif text-2xl">Change password</h3>
        {field("current_password", "Current password", "account-current-password-input")}
        {field("new_password", "New password (min 8 characters)", "account-new-password-input")}
        {field("confirm", "Confirm new password", "account-confirm-password-input")}
        <Button type="submit" className="rounded-full" data-testid="account-change-password-btn">Update password</Button>
      </form>
      <div className="card-warm p-6 flex items-start gap-4">
        <ShieldCheck className="h-6 w-6 text-[#3F6212] shrink-0" />
        <div>
          <h3 className="f-serif text-xl">Two-factor authentication</h3>
          <p className="text-sm text-stone-500 mt-1">Authenticator-app codes are planned for a later phase. Your account is already set up to support it.</p>
        </div>
      </div>
    </div>
  );
}
