import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { AiSettings } from "@/components/settings/AiSettings";
import { DocumentsSettings } from "@/components/settings/DocumentsSettings";
import { UsersSettings } from "@/components/settings/UsersSettings";

export default function Settings() {
  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-8 py-10 space-y-8" data-testid="settings-panel">
      <div className="fade-up">
        <p className="eyebrow">Admin</p>
        <h1 className="f-serif text-4xl sm:text-5xl font-semibold tracking-tight text-[#1C1917] mt-2">Settings</h1>
      </div>
      <Tabs defaultValue="ai">
        <TabsList className="bg-[#F4EFE6]">
          <TabsTrigger value="ai" data-testid="settings-tab-ai">AI provider & keys</TabsTrigger>
          <TabsTrigger value="docs" data-testid="settings-tab-docs">Reference documents</TabsTrigger>
          <TabsTrigger value="users" data-testid="settings-tab-users">Users</TabsTrigger>
        </TabsList>
        <TabsContent value="ai" className="mt-6"><AiSettings /></TabsContent>
        <TabsContent value="docs" className="mt-6"><DocumentsSettings /></TabsContent>
        <TabsContent value="users" className="mt-6"><UsersSettings /></TabsContent>
      </Tabs>
    </div>
  );
}
