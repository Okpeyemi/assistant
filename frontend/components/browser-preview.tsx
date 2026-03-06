"use client"

import { Badge } from "@/components/ui/badge"
import { MonitorIcon, CircleIcon, GlobeIcon } from "lucide-react"
import type { AssistantStatus } from "@/hooks/use-assistant"

interface BrowserPreviewProps {
  screenshot: string | null
  status: AssistantStatus
  currentUrl: string
}

const STATUS_LABELS: Record<AssistantStatus, string> = {
  idle: "En direct",
  thinking: "Réflexion...",
  navigation: "Navigation...",
  clicking: "Interaction...",
  filling: "Saisie du formulaire...",
  searching: "Recherche...",
}

export function BrowserPreview({ screenshot, status, currentUrl }: BrowserPreviewProps) {
  const isActive = status !== "idle"

  return (
    <div className="flex flex-col h-full">
      {/* Barre du navigateur simulée */}
      <div className="flex items-center gap-2 px-3 py-2.5 bg-muted/40 border-b shrink-0">
        {/* Boutons macOS simulés */}
        <div className="flex gap-1.5 shrink-0">
          <div className="size-2.5 rounded-full bg-destructive/50" />
          <div className="size-2.5 rounded-full bg-muted-foreground/25" />
          <div className="size-2.5 rounded-full bg-muted-foreground/25" />
        </div>

        {/* Barre d'URL */}
        <div className="flex flex-1 min-w-0 items-center gap-1.5 bg-background rounded-md border px-2.5 py-1">
          <GlobeIcon className="size-3 text-muted-foreground shrink-0" />
          <span className="text-xs text-muted-foreground truncate">
            {currentUrl || "service-public.bj"}
          </span>
        </div>

        {/* Badge statut */}
        <Badge
          variant={isActive ? "default" : "secondary"}
          className="shrink-0 gap-1 text-xs"
        >
          {isActive && (
            <CircleIcon className="size-1.5 fill-current animate-pulse" />
          )}
          {STATUS_LABELS[status]}
        </Badge>
      </div>

      {/* Zone de capture d'écran */}
      <div className="flex-1 relative overflow-hidden bg-muted/10 min-h-0">
        {screenshot ? (
          <img
            src={`data:image/jpeg;base64,${screenshot}`}
            alt="Aperçu du navigateur en direct"
            className="w-full h-full object-contain"
          />
        ) : (
          <div className="flex flex-col items-center justify-center h-full gap-4 text-muted-foreground select-none">
            <MonitorIcon className="size-20 opacity-[0.07]" />
            <div className="text-center space-y-1">
              <p className="text-sm font-medium text-muted-foreground/60">
                Aperçu du navigateur
              </p>
              <p className="text-xs text-muted-foreground/40">
                Connectez-vous pour voir le navigateur en direct
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
