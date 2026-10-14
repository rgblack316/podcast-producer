import { useEffect, useState } from "react";
import { KeyRound, Trash2, UserPlus } from "lucide-react";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter,
  AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { api, errMsg, fmtDate } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

function CreateUser({ onDone }) {
  const [open, setOpen] = useState(false);
  const [f, setF] = useState({ username: "", name: "", password: "", role: "producer" });
  const submit = async () => {
    try {
      await api.post("/users", f);
      toast.success(`Created ${f.username}`);
      setOpen(false);
      setF({ username: "", name: "", password: "", role: "producer" });
      onDone();
    } catch (e) {
      toast.error(errMsg(e));
    }
  };
  return (
    <>
      <Button className="rounded-full" onClick={() => setOpen(true)} data-testid="add-user-btn"><UserPlus className="h-4 w-4 mr-1.5" /> Add team member</Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="bg-[#FAF7F2]">
          <DialogHeader><DialogTitle className="f-serif text-2xl">New team member</DialogTitle></DialogHeader>
          <div className="space-y-4">
            <div className="space-y-1.5"><Label>Username</Label><Input value={f.username} onChange={(e) => setF({ ...f, username: e.target.value })} className="bg-[#FFFDF9]" data-testid="new-user-username-input" /></div>
            <div className="space-y-1.5"><Label>Display name</Label><Input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} className="bg-[#FFFDF9]" data-testid="new-user-name-input" /></div>
            <div className="space-y-1.5"><Label>Temporary password (min 8)</Label><Input type="password" value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} className="bg-[#FFFDF9]" data-testid="new-user-password-input" /></div>
            <div className="space-y-1.5"><Label>Role</Label>
              <Select value={f.role} onValueChange={(v) => setF({ ...f, role: v })}>
                <SelectTrigger className="bg-[#FFFDF9]" data-testid="new-user-role-select"><SelectValue /></SelectTrigger>
                <SelectContent><SelectItem value="producer">Producer</SelectItem><SelectItem value="admin">Admin</SelectItem></SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter><Button onClick={submit} data-testid="new-user-submit-btn">Create account</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

function ResetPassword({ target, onClose }) {
  const [pw, setPw] = useState("");
  const submit = async () => {
    try {
      await api.post(`/users/${target.id}/reset-password`, { new_password: pw });
      toast.success(`Password reset for ${target.username}`);
      setPw("");
      onClose();
    } catch (e) {
      toast.error(errMsg(e));
    }
  };
  return (
    <Dialog open={!!target} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="bg-[#FAF7F2]">
        <DialogHeader><DialogTitle className="f-serif text-2xl">Reset password for {target?.username}</DialogTitle></DialogHeader>
        <Input type="password" value={pw} onChange={(e) => setPw(e.target.value)} placeholder="New password (min 8)" className="bg-[#FFFDF9]" data-testid="reset-password-input" />
        <DialogFooter><Button onClick={submit} disabled={pw.length < 8} data-testid="reset-password-submit-btn">Reset password</Button></DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function UsersSettings() {
  const { user: me } = useAuth();
  const [users, setUsers] = useState([]);
  const [resetting, setResetting] = useState(null);
  const [deleting, setDeleting] = useState(null);
  const load = () => api.get("/users").then((r) => setUsers(r.data));
  useEffect(() => { load(); }, []);

  const removeUser = async () => {
    const u = deleting;
    setDeleting(null);
    try { await api.delete(`/users/${u.id}`); toast.success(`Deleted @${u.username}`); load(); } catch (e) { toast.error(errMsg(e)); }
  };

  const patch = async (u, body) => {
    try { await api.patch(`/users/${u.id}`, body); load(); toast.success("User updated"); } catch (e) { toast.error(errMsg(e)); }
  };

  return (
    <div className="card-warm p-6 space-y-4" data-testid="settings-users">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h3 className="f-serif text-2xl">Team</h3>
          <p className="text-sm text-stone-500">Admins manage settings and documents. Producers create and edit episodes.</p>
        </div>
        <CreateUser onDone={load} />
      </div>
      <ul className="divide-y divide-[#EFE8DC]">
        {users.map((u) => (
          <li key={u.id} className="flex flex-col md:flex-row md:items-center gap-3 py-4" data-testid={`user-row-${u.username}`}>
            <div className="flex-1 min-w-0">
              <div className="font-medium">{u.name} <span className="f-mono text-xs text-stone-500">@{u.username}</span></div>
              <div className="f-mono text-[11px] text-stone-500">Last sign-in {fmtDate(u.last_login_at)} · MFA {u.mfa_enabled ? "on" : "off"}</div>
            </div>
            <div className="flex items-center gap-3">
              <Select value={u.role} onValueChange={(v) => patch(u, { role: v })} disabled={u.id === me.id}>
                <SelectTrigger className="w-[130px] h-9 bg-[#FFFDF9]" data-testid={`user-role-select-${u.username}`}><SelectValue /></SelectTrigger>
                <SelectContent><SelectItem value="producer">Producer</SelectItem><SelectItem value="admin">Admin</SelectItem></SelectContent>
              </Select>
              <label className="flex items-center gap-2 text-xs text-stone-600">
                <Switch checked={u.active} disabled={u.id === me.id} onCheckedChange={(v) => patch(u, { active: v })} data-testid={`user-active-toggle-${u.username}`} />
                {u.active ? "Active" : "Disabled"}
              </label>
              <Button variant="outline" size="sm" className="bg-[#FFFDF9]" onClick={() => setResetting(u)} data-testid={`user-reset-password-${u.username}`}>
                <KeyRound className="h-4 w-4 mr-1" /> Reset
              </Button>
              <Button variant="ghost" size="sm" className="text-red-700 hover:text-red-800 hover:bg-red-50" disabled={u.id === me.id}
                title={u.id === me.id ? "You can't delete your own account" : "Delete user"} onClick={() => setDeleting(u)} data-testid={`user-delete-${u.username}`}>
                <Trash2 className="h-4 w-4" />
              </Button>
            </div>
          </li>
        ))}
      </ul>
      <ResetPassword target={resetting} onClose={() => setResetting(null)} />
      <AlertDialog open={!!deleting} onOpenChange={(o) => !o && setDeleting(null)}>
        <AlertDialogContent data-testid="delete-user-dialog">
          <AlertDialogHeader>
            <AlertDialogTitle>Delete {deleting?.name} (@{deleting?.username})?</AlertDialogTitle>
            <AlertDialogDescription>
              This permanently removes the account and signs them out. Episodes they created stay in the library. To keep the account but block access, turn it to Disabled instead.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel data-testid="delete-user-cancel-btn">Cancel</AlertDialogCancel>
            <AlertDialogAction className="bg-red-700 hover:bg-red-800" onClick={removeUser} data-testid="delete-user-confirm-btn">Delete user</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
