"use client"

import * as React from "react"
import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import {
  MicIcon,
  MicOffIcon,
  BotIcon,
  UserIcon,
  Loader2Icon,
  GlobeIcon,
  MousePointerClickIcon,
  PenLineIcon,
  SearchIcon,
  SendIcon,
  ClockIcon,
  ArrowDownIcon,
  ChevronRightIcon,
  FileTextIcon,
  XIcon,
  ArrowRightIcon,
  CheckIcon,
} from "lucide-react"
import type { ConversationItem, ConfirmPrompt, FieldPrompt, LogItem, MessageItem } from "@/hooks/use-assistant"

const ACTION_META: Record<string, { label: string; Icon: React.ElementType }> = {
  navigate:     { label: "Navigation",        Icon: GlobeIcon },
  click:        { label: "Clic",              Icon: MousePointerClickIcon },
  fill:         { label: "Saisie",            Icon: PenLineIcon },
  fill_multiple:{ label: "Saisie multiple",   Icon: PenLineIcon },
  search:       { label: "Recherche",         Icon: SearchIcon },
  submit:       { label: "Soumission",        Icon: SendIcon },
  wait:         { label: "Attente",           Icon: ClockIcon },
  scroll:       { label: "Défilement",        Icon: ArrowDownIcon },
  ask_user:     { label: "Question",          Icon: ChevronRightIcon },
  respond:      { label: "Réponse",           Icon: ChevronRightIcon },
}

interface ConversationPanelProps {
  items: ConversationItem[]
  isRecording: boolean
  isConnected: boolean
  isThinking: boolean
  isWaitingForDocument: boolean
  currentField: FieldPrompt | null
  currentConfirm: ConfirmPrompt | null
  onStartRecording: () => void
  onStopRecording: () => void
  onSendMessage: (text: string) => void
  onAnswerField: (fieldId: string, value: string) => void
  onConfirmAnswer: (confirmed: boolean, correction?: string) => void
  onUploadDocument: (file: File) => void
  onSkipDocument: () => void
}

export function ConversationPanel({
  items,
  isRecording,
  isConnected,
  isThinking,
  isWaitingForDocument,
  currentField,
  currentConfirm,
  onStartRecording,
  onStopRecording,
  onSendMessage,
  onAnswerField,
  onConfirmAnswer,
  onUploadDocument,
  onSkipDocument,
}: ConversationPanelProps) {
  const scrollRef = React.useRef<HTMLDivElement>(null)
  const fileInputRef = React.useRef<HTMLInputElement>(null)
  const [chatInput, setChatInput] = React.useState("")

  React.useEffect(() => {
    const el = scrollRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [items, isThinking, currentField])

  const handleMicClick = () => {
    if (isRecording) onStopRecording()
    else onStartRecording()
  }

  const handleChatSend = () => {
    const text = chatInput.trim()
    if (!text || !isConnected) return
    onSendMessage(text)
    setChatInput("")
  }

  const handleChatKey = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      handleChatSend()
    }
  }

  return (
    <div className="flex flex-col h-full">
      {/* En-tête */}
      <div className="px-4 py-3 border-b shrink-0">
        <p className="text-sm font-medium">Conversation</p>
        <p className="text-xs text-muted-foreground mt-0.5">
          Parlez à votre assistant pour effectuer vos démarches
        </p>
      </div>

      {/* Flux conversation + logs */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto px-4 py-4 space-y-2 min-h-0"
      >
        {items.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full gap-4 text-muted-foreground py-8 select-none">
            <BotIcon className="size-12 opacity-[0.12]" />
            <div className="text-center space-y-1">
              <p className="text-sm font-medium text-muted-foreground/70">Prêt à vous aider</p>
              <p className="text-xs text-muted-foreground/50 max-w-52 text-center leading-relaxed">
                Cliquez sur le microphone et dites ce que vous souhaitez faire
              </p>
            </div>
          </div>
        )}

        {items.map((item, index) =>
          item.kind === "message" ? (
            <MessageBubble key={index} item={item} />
          ) : (
            <LogEntry key={index} item={item} />
          )
        )}

        {/* Indicateur de réflexion */}
        {isThinking && (
          <div className="flex items-start gap-2 mt-2">
            <div className="size-5 rounded-full bg-secondary flex items-center justify-center shrink-0 mt-0.5">
              <BotIcon className="size-3 text-secondary-foreground" />
            </div>
            <div className="bg-muted rounded-lg rounded-tl-sm px-3 py-1.5 text-xs">
              <div className="flex items-center gap-1.5 text-muted-foreground">
                <Loader2Icon className="size-2.5 animate-spin" />
                <span>Analyse en cours...</span>
              </div>
            </div>
          </div>
        )}
      </div>

      <Separator />

      {/* Zone d'action */}
      <div className="px-4 py-4 shrink-0 space-y-3">
        {isWaitingForDocument ? (
          <DocumentUploadZone
            fileInputRef={fileInputRef}
            onUpload={onUploadDocument}
            onSkip={onSkipDocument}
          />
        ) : currentConfirm ? (
          /* ── Zone de confirmation Oui/Non ── */
          <ConfirmZone
            confirm={currentConfirm}
            isConnected={isConnected}
            onAnswer={onConfirmAnswer}
          />
        ) : currentField ? (
          /* ── Champ inline séquentiel ── */
          <FieldInputZone
            field={currentField}
            isRecording={isRecording}
            isConnected={isConnected}
            onAnswer={onAnswerField}
            onMicClick={handleMicClick}
          />
        ) : (
          /* ── Zone normale : texte + micro ── */
          <div className="flex flex-col gap-3">
            {/* Barre de texte */}
            <div className="flex items-center gap-2 rounded-xl border bg-background px-3 py-1.5 focus-within:ring-1 focus-within:ring-ring">
              <input
                className="flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
                placeholder={isConnected ? "Écrivez un message…" : "Non connecté"}
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                onKeyDown={handleChatKey}
                disabled={!isConnected}
              />
              <Button
                variant="ghost"
                size="icon"
                className="size-7 shrink-0 text-muted-foreground hover:text-foreground"
                disabled={!isConnected || !chatInput.trim()}
                onClick={handleChatSend}
                aria-label="Envoyer"
              >
                <SendIcon className="size-3.5" />
              </Button>
            </div>

            {/* Bouton micro */}
            <div className="flex flex-col items-center gap-2">
              <Button
                variant={isRecording ? "destructive" : "default"}
                size="icon"
                disabled={!isConnected}
                onClick={handleMicClick}
                className="size-12 rounded-full"
                aria-label={isRecording ? "Arrêter" : "Parler"}
              >
                {isRecording ? (
                  <MicOffIcon className="size-5" />
                ) : (
                  <MicIcon className="size-5" />
                )}
              </Button>
              <p className="text-xs text-muted-foreground text-center">
                {!isConnected
                  ? "Non connecté"
                  : isRecording
                  ? "Parlez… (s'arrête automatiquement)"
                  : "Cliquez pour parler"}
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
// ─── Zone de confirmation Oui / Non ──────────────────────────────────────────

function ConfirmZone({
  confirm,
  isConnected,
  onAnswer,
}: {
  confirm: ConfirmPrompt
  isConnected: boolean
  onAnswer: (confirmed: boolean, correction?: string) => void
}) {
  const [showInput, setShowInput] = React.useState(false)
  const [correction, setCorrection] = React.useState("")
  const inputRef = React.useRef<HTMLInputElement>(null)

  React.useEffect(() => {
    if (showInput) setTimeout(() => inputRef.current?.focus(), 50)
  }, [showInput])

  const submitCorrection = () => {
    if (!correction.trim()) return
    onAnswer(false, correction.trim())
    setCorrection("")
    setShowInput(false)
  }

  return (
    <div className="flex flex-col gap-3 rounded-xl border bg-muted/30 px-4 py-4">
      <div className="flex items-start gap-2">
        <div className="size-5 rounded-full bg-secondary flex items-center justify-center shrink-0 mt-0.5">
          <BotIcon className="size-3 text-secondary-foreground" />
        </div>
        <div>
          <p className="text-xs text-muted-foreground">{confirm.question}</p>
          <p className="text-sm font-semibold mt-0.5">{confirm.value}</p>
        </div>
      </div>

      {!showInput ? (
        <div className="flex gap-2">
          <Button
            className="flex-1 gap-1.5"
            disabled={!isConnected}
            onClick={() => onAnswer(true)}
          >
            <CheckIcon className="size-3.5" />
            Oui, c’est correct
          </Button>
          <Button
            variant="outline"
            className="flex-1 gap-1.5"
            disabled={!isConnected}
            onClick={() => setShowInput(true)}
          >
            <XIcon className="size-3.5" />
            Non, corriger
          </Button>
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          <p className="text-xs text-muted-foreground">Entrez la valeur correcte :</p>
          <div className="flex items-center gap-2">
            <input
              ref={inputRef}
              className="flex-1 rounded-lg border bg-background px-3 py-2 text-sm outline-none placeholder:text-muted-foreground focus:ring-1 focus:ring-ring"
              placeholder="Valeur correcte…"
              value={correction}
              onChange={(e) => setCorrection(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") submitCorrection() }}
              disabled={!isConnected}
            />
            <Button
              size="icon"
              className="size-9 shrink-0 rounded-full"
              disabled={!isConnected || !correction.trim()}
              onClick={submitCorrection}
            >
              <ArrowRightIcon className="size-4" />
            </Button>
          </div>
          <Button
            variant="ghost"
            size="sm"
            className="text-muted-foreground"
            onClick={() => setShowInput(false)}
          >
            Annuler
          </Button>
        </div>
      )}
    </div>
  )
}
// ─── Zone de saisie inline pour un champ ───────────────────────────────────

function FieldInputZone({
  field,
  isRecording,
  isConnected,
  onAnswer,
  onMicClick,
}: {
  field: FieldPrompt
  isRecording: boolean
  isConnected: boolean
  onAnswer: (fieldId: string, value: string) => void
  onMicClick: () => void
}) {
  const [value, setValue] = React.useState("")
  const inputRef = React.useRef<HTMLInputElement>(null)

  // Reset et focus auto à chaque nouveau champ
  React.useEffect(() => {
    setValue("")
    setTimeout(() => inputRef.current?.focus(), 50)
  }, [field.field_id])

  const submit = () => {
    if (!value.trim()) return
    onAnswer(field.field_id, value.trim())
    setValue("")
  }

  const handleKey = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") { e.preventDefault(); submit() }
  }

  return (
    <div className="flex flex-col gap-3 rounded-xl border bg-muted/30 px-4 py-4">
      {/* Barre de progression */}
      {field.total > 1 && (
        <div className="flex items-center gap-1.5">
          {Array.from({ length: field.total }, (_, i) => (
            <div
              key={i}
              className={`h-1 flex-1 rounded-full transition-colors ${
                i < field.index ? "bg-primary" : "bg-border"
              }`}
            />
          ))}
          <span className="text-[10px] text-muted-foreground ml-1 shrink-0 tabular-nums">
            {field.index}/{field.total}
          </span>
        </div>
      )}

      {/* Question */}
      <div>
        <p className="text-sm font-medium leading-snug">{field.label}</p>
        {field.hint && (
          <p className="text-xs text-muted-foreground mt-0.5">{field.hint}</p>
        )}
      </div>

      {/* Input + boutons */}
      <div className="flex items-center gap-2">
        <Button
          variant={isRecording ? "destructive" : "outline"}
          size="icon"
          className="size-9 shrink-0 rounded-full"
          disabled={!isConnected}
          onClick={onMicClick}
          aria-label={isRecording ? "Arrêter" : "Répondre par la voix"}
        >
          {isRecording ? <MicOffIcon className="size-4" /> : <MicIcon className="size-4" />}
        </Button>

        <input
          ref={inputRef}
          className="flex-1 rounded-lg border bg-background px-3 py-2 text-sm outline-none placeholder:text-muted-foreground focus:ring-1 focus:ring-ring"
          placeholder="Votre réponse…"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKey}
          disabled={!isConnected}
        />

        <Button
          size="icon"
          className="size-9 shrink-0 rounded-full"
          disabled={!isConnected || !value.trim()}
          onClick={submit}
          aria-label={field.index < field.total ? "Suivant" : "Valider"}
        >
          <ArrowRightIcon className="size-4" />
        </Button>
      </div>

      {isRecording && (
        <p className="text-xs text-muted-foreground text-center animate-pulse">
          Parlez… (s&apos;arrête après 2,5 s de silence)
        </p>
      )}
    </div>
  )
}

// ─── Bulle de message (user / assistant) ───────────────────────────────────

function MessageBubble({ item }: { item: MessageItem }) {
  if (item.role === "user") {
    return (
      <div className="flex items-end gap-2 justify-end mt-3">
        <div className="bg-primary text-primary-foreground rounded-2xl rounded-br-sm px-3.5 py-2 text-sm max-w-[82%] leading-relaxed">
          {item.text}
        </div>
        <div className="size-6 rounded-full bg-primary flex items-center justify-center shrink-0">
          <UserIcon className="size-3.5 text-primary-foreground" />
        </div>
      </div>
    )
  }

  return (
    <div className="flex items-end gap-2 mt-3">
      <div className="size-6 rounded-full bg-secondary flex items-center justify-center shrink-0">
        <BotIcon className="size-3.5 text-secondary-foreground" />
      </div>
      <div className="bg-muted rounded-2xl rounded-bl-sm px-3.5 py-2 text-sm max-w-[82%] leading-relaxed whitespace-pre-wrap">
        {item.text}
      </div>
    </div>
  )
}

// ─── Zone d'upload de document ─────────────────────────────────────────────

function DocumentUploadZone({
  fileInputRef,
  onUpload,
  onSkip,
}: {
  fileInputRef: React.RefObject<HTMLInputElement | null>
  onUpload: (file: File) => void
  onSkip: () => void
}) {
  const [isDragging, setIsDragging] = React.useState(false)

  const handleFile = (file: File) => {
    const allowed = ["image/jpeg", "image/png", "image/webp", "application/pdf"]
    if (!allowed.includes(file.type)) return
    onUpload(file)
  }

  return (
    <div className="flex flex-col gap-3">
      <div
        className={`relative flex flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed px-4 py-5 text-center transition-colors cursor-pointer
          ${isDragging ? "border-primary bg-primary/5" : "border-border hover:border-primary/50 hover:bg-muted/30"}`}
        onClick={() => fileInputRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setIsDragging(true) }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={(e) => {
          e.preventDefault()
          setIsDragging(false)
          const file = e.dataTransfer.files[0]
          if (file) handleFile(file)
        }}
      >
        <div className="size-9 rounded-full bg-muted flex items-center justify-center">
          <FileTextIcon className="size-4 text-muted-foreground" />
        </div>
        <div>
          <p className="text-sm font-medium">Document d&apos;identité</p>
          <p className="text-xs text-muted-foreground mt-0.5">
            Glissez ou cliquez — JPG, PNG, PDF
          </p>
        </div>
        <input
          ref={fileInputRef}
          type="file"
          accept="image/jpeg,image/png,image/webp,application/pdf"
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0]
            if (file) handleFile(file)
          }}
        />
      </div>

      <Button
        variant="ghost"
        size="sm"
        onClick={onSkip}
        className="w-full text-muted-foreground gap-1.5"
      >
        <XIcon className="size-3.5" />
        Passer cette étape
      </Button>
    </div>
  )
}

// ─── Entrée de log (raisonnement de l'agent) ───────────────────────────────

function LogEntry({ item }: { item: LogItem }) {
  const meta = ACTION_META[item.action] ?? { label: item.action, Icon: ChevronRightIcon }
  const { label, Icon } = meta

  return (
    <div className="flex items-start gap-2 pl-1">
      <div className="flex flex-col items-center shrink-0 mt-0.5">
        <div className="size-4 rounded flex items-center justify-center bg-muted">
          <Icon className="size-2.5 text-muted-foreground" />
        </div>
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-baseline gap-1.5 flex-wrap">
          <span className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground/60">
            {label}
          </span>
          <span className="text-xs text-muted-foreground leading-relaxed">
            {item.text}
          </span>
        </div>
      </div>
    </div>
  )
}
