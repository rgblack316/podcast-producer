import { useState } from "react";
import { Loader2, Lock } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/context/AuthContext";
import { errMsg } from "@/lib/api";

export default function Login() {
  const { login } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await login(username, password);
    } catch (err) {
      setError(errMsg(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen grid lg:grid-cols-2" data-testid="login-container">
      <div className="hidden lg:flex flex-col bg-black items-center justify-center gap-8 p-12">
        <img src="/cover.webp" alt="Bible Bytes - Inspiring Faith One Byte at a Time"
          className="w-full max-w-[480px] max-h-[65vh] aspect-square object-contain fade-up" data-testid="login-cover-art" />
        <div className="text-[#FAF7F2] text-center">
          <p className="f-serif italic text-xl leading-snug max-w-md mx-auto">
            "Your word is a lamp to my feet and a light to my path."
          </p>
          <p className="eyebrow !text-[#FDE68A] mt-3">Psalm 119:105</p>
        </div>
      </div>
      <div className="flex items-center justify-center p-6 paper-grain">
        <form onSubmit={submit} className="w-full max-w-sm space-y-7 fade-up">
          <div className="space-y-3">
            <img src="/logo-mark.png" alt="Bible Bytes logo" className="h-14 w-14 rounded-lg border border-[#E2DACD] shadow-sm" data-testid="login-logo" />
            <h1 className="f-serif text-4xl font-semibold tracking-tight text-[#1C1917]">
              Bible Bytes <span className="italic font-normal text-[#B45309]">Producer</span>
            </h1>
            <p className="text-stone-600">Sign in to the writing room.</p>
          </div>
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="username">Username</Label>
              <Input id="username" autoComplete="username" value={username} onChange={(e) => setUsername(e.target.value)}
                className="bg-[#FFFDF9] h-11" data-testid="login-username-input" required />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="password">Password</Label>
              <Input id="password" type="password" autoComplete="current-password" value={password}
                onChange={(e) => setPassword(e.target.value)} className="bg-[#FFFDF9] h-11" data-testid="login-password-input" required />
            </div>
            {error && <p className="text-sm text-red-700" data-testid="login-error">{error}</p>}
            <Button type="submit" className="w-full h-11 rounded-full" disabled={busy} data-testid="login-submit-button">
              {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Lock className="h-4 w-4 mr-2" />} Sign in
            </Button>
          </div>
          <p className="text-xs text-stone-500">Accounts are created by your administrator.</p>
        </form>
      </div>
    </div>
  );
}
