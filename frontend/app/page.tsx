"use client"

import { BrowserPreview } from "@/components/browser-preview"
import { ConversationPanel } from "@/components/conversation-panel"
import { useAssistant } from "@/hooks/use-assistant"
import { Badge } from "@/components/ui/badge"
import { Separator } from "@/components/ui/separator"
import { GlobeIcon, WifiIcon, WifiOffIcon } from "lucide-react"

export default function Page() {
  const assistant = useAssistant()

  return (
    <div className="flex flex-col h-screen bg-background overflow-hidden">
      {/* En-tête */}
      <header className="flex items-center gap-2.5 px-4 py-2.5 border-b shrink-0">
        <GlobeIcon className="size-4 text-muted-foreground" />
        <span className="text-sm font-medium tracking-tight">
          Assistant Démarches Bénin Test
        </span>
        <Separator orientation="vertical" className="h-4 mx-1" />
        <span className="text-xs text-muted-foreground">service-public.bj</span>
        <div className="ml-auto flex items-center gap-1.5">
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
        {/* Panneau gauche : aperçu du navigateur (60%) */}
        <div className="flex-[3] border-r min-w-0">
          <BrowserPreview
            screenshot={assistant.screenshot}
            status={assistant.status}
            currentUrl={assistant.currentUrl}
          />
        </div>

        {/* Panneau droit : conversation (40%) */}
        <div className="flex-[2] min-w-0">
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
