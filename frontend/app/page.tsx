"use client"

import { useState } from "react"
import { BrowserPreview } from "@/components/browser-preview"
import { ConversationPanel } from "@/components/conversation-panel"
import { useAssistant } from "@/hooks/use-assistant"
import { Badge } from "@/components/ui/badge"
import { Separator } from "@/components/ui/separator"
import { GlobeIcon, WifiIcon, WifiOffIcon, MessageSquareIcon, MonitorIcon } from "lucide-react"

export default function Page() {
  const assistant = useAssistant()
  const [activeTab, setActiveTab] = useState<"chat" | "browser">("chat")

  return (
    <div className="flex flex-col h-screen bg-background overflow-hidden">
      {/* En-tête */}
      <header className="flex items-center gap-2 px-3 py-2 md:gap-2.5 md:px-4 md:py-2.5 border-b shrink-0">
        <GlobeIcon className="size-4 text-muted-foreground shrink-0" />
        <span className="text-sm font-medium tracking-tight truncate">
          Assistant Démarches Bénin
        </span>
        <Separator orientation="vertical" className="h-4 mx-1 hidden md:block shrink-0" />
        <span className="text-xs text-muted-foreground hidden md:inline shrink-0">service-public.bj</span>

        {/* Spacer */}
        <div className="flex-1" />

        {/* Onglets mobile uniquement */}
        <div className="flex md:hidden items-center rounded-lg border overflow-hidden text-xs mr-1 shrink-0">
          <button
            onClick={() => setActiveTab("chat")}
            className={`flex items-center gap-1 px-2.5 py-1.5 transition-colors ${
              activeTab === "chat"
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            <MessageSquareIcon className="size-3" />
            Chat
          </button>
          <button
            onClick={() => setActiveTab("browser")}
            className={`flex items-center gap-1 px-2.5 py-1.5 transition-colors ${
              activeTab === "browser"
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            <MonitorIcon className="size-3" />
            Aperçu
          </button>
        </div>

        {/* Badge connexion */}
        <div className="flex items-center gap-1.5 shrink-0">
          {assistant.isConnected ? (
            <WifiIcon className="size-3.5 text-muted-foreground" />
          ) : (
            <WifiOffIcon className="size-3.5 text-muted-foreground" />
          )}
          <Badge
            variant={assistant.isConnected ? "secondary" : "outline"}
            className="text-xs"
          >
            {assistant.isConnected ? "Connecté" : "Déconnecté"}
          </Badge>
        </div>
      </header>

      {/* Contenu principal : 2 panneaux */}
      <div className="flex flex-1 min-h-0">
        {/* Panneau gauche : aperçu du navigateur (60% desktop) */}
        <div
          className={`min-w-0 border-r ${
            activeTab === "browser" ? "flex-1" : "hidden"
          } md:block md:flex-3`}
        >
          <BrowserPreview
            screenshot={assistant.screenshot}
            status={assistant.status}
            currentUrl={assistant.currentUrl}
          />
        </div>

        {/* Panneau droit : conversation (40% desktop) */}
        <div
          className={`min-w-0 ${
            activeTab === "chat" ? "flex-1" : "hidden"
          } md:block md:flex-2`}
        >
          <ConversationPanel
            items={assistant.items}
            isRecording={assistant.isRecording}
            isConnected={assistant.isConnected}
            isThinking={assistant.isThinking}
            isWaitingForDocument={assistant.isWaitingForDocument}
            currentField={assistant.currentField}
            currentConfirm={assistant.currentConfirm}
            onStartRecording={assistant.startRecording}
            onStopRecording={assistant.stopRecording}
            onSendMessage={assistant.sendMessage}
            onAnswerField={assistant.answerField}
            onConfirmAnswer={assistant.confirmAnswer}
            onUploadDocument={assistant.uploadDocument}
            onSkipDocument={assistant.skipDocument}
          />
        </div>
      </div>
    </div>
  )
}
