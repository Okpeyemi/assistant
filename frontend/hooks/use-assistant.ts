"use client"

import { useState, useEffect, useRef, useCallback } from "react"

export type MessageItem = {
  kind: "message"
  role: "user" | "assistant"
  text: string
}

export type LogItem = {
  kind: "log"
  action: string
  text: string
}

export type ConversationItem = MessageItem | LogItem

export type AssistantStatus =
  | "idle"
  | "thinking"
  | "navigation"
  | "clicking"
  | "filling"
  | "searching"

export type FieldPrompt = {
  field_id: string
  label: string
  hint: string
  index: number
  total: number
}

export type ConfirmPrompt = {
  question: string   // "Est-ce bien votre nom ?"
  value: string      // "AHOUANSOU Jean"
}

export function useAssistant() {
  const [items, setItems] = useState<ConversationItem[]>([])
  const [screenshot, setScreenshot] = useState<string | null>(null)
  const [status, setStatus] = useState<AssistantStatus>("idle")
  const [isConnected, setIsConnected] = useState(false)
  const [isRecording, setIsRecording] = useState(false)
  const [isThinking, setIsThinking] = useState(false)
  const [currentUrl, setCurrentUrl] = useState("")
  const [isWaitingForDocument, setIsWaitingForDocument] = useState(false)
  const [currentField, setCurrentField] = useState<FieldPrompt | null>(null)
  const [currentConfirm, setCurrentConfirm] = useState<ConfirmPrompt | null>(null)

  const wsRef = useRef<WebSocket | null>(null)
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const audioChunksRef = useRef<BlobPart[]>([])
  const silenceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  // callback ref used by startRecording to avoid stale closure
  const sendMessageRef = useRef<(text: string) => void>(() => {})
  // field callback ref
  const answerFieldRef = useRef<(fieldId: string, value: string) => void>(() => {})

  // ── Text-to-speech ───────────────────────────────────────────────────────
  const speakFrench = useCallback((text: string) => {
    if (!window.speechSynthesis) return
    // Annule toute lecture en cours avant la nouvelle
    window.speechSynthesis.cancel()
    const utterance = new SpeechSynthesisUtterance(text)
    utterance.lang = "fr-FR"
    utterance.rate = 1.0
    utterance.pitch = 1.0
    // Choisit une voix française si disponible
    const voices = window.speechSynthesis.getVoices()
    const frVoice = voices.find((v) => v.lang.startsWith("fr"))
    if (frVoice) utterance.voice = frVoice
    window.speechSynthesis.speak(utterance)
  }, [])

  // Précharge les voix dès le montage (elles sont chargées de façon asynchrone)
  useEffect(() => {
    if (!window.speechSynthesis) return
    window.speechSynthesis.getVoices()
    window.speechSynthesis.onvoiceschanged = () => {
      window.speechSynthesis.getVoices()
    }
  }, [])

  useEffect(() => {
    const ws = new WebSocket("ws://localhost:8000/ws")
    wsRef.current = ws

    ws.onopen = () => setIsConnected(true)

    ws.onclose = () => {
      setIsConnected(false)
      setStatus("idle")
      setIsThinking(false)
    }

    ws.onerror = () => setIsConnected(false)

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)

        if (data.type === "screenshot") {
          setScreenshot(data.data)
        } else if (data.type === "message") {
          setItems((prev) => [
            ...prev,
            { kind: "message", role: data.role, text: data.text } satisfies MessageItem,
          ])
          if (data.role === "assistant") {
            setIsThinking(false)
            speakFrench(data.text)
          }
        } else if (data.type === "log") {
          setItems((prev) => [
            ...prev,
            { kind: "log", action: data.action, text: data.text } satisfies LogItem,
          ])
        } else if (data.type === "ask_document") {
          setIsWaitingForDocument(true)
          setCurrentField(null)
        } else if (data.type === "ask_document_done") {
          setIsWaitingForDocument(false)
        } else if (data.type === "ask_field") {
          setCurrentField({
            field_id: data.field_id,
            label: data.label,
            hint: data.hint ?? "",
            index: data.index,
            total: data.total,
          })
          setCurrentConfirm(null)
          setIsThinking(false)
        } else if (data.type === "ask_confirm") {
          setCurrentConfirm({
            question: data.question,
            value: data.value,
          })
          setCurrentField(null)
          setIsThinking(false)
        } else if (data.type === "status") {
          const s = data.text as AssistantStatus
          setStatus(s)
          setIsThinking(s === "thinking")
          // When agent starts processing again, clear the field prompt
          if (s === "thinking") {
            setCurrentField(null)
            setCurrentConfirm(null)
          }
        } else if (data.type === "url") {
          setCurrentUrl(data.url)
        }
      } catch {
        // ignore malformed messages
      }
    }

    return () => ws.close()
  }, [])

  const sendMessage = useCallback((text: string) => {
    const ws = wsRef.current
    if (!ws || ws.readyState !== WebSocket.OPEN) return

    ws.send(JSON.stringify({ type: "user_message", text }))
    setItems((prev) => [
      ...prev,
      { kind: "message", role: "user", text } satisfies MessageItem,
    ])
    setIsThinking(true)
    setStatus("thinking")
  }, [])

  // keep ref up to date for use inside closures
  useEffect(() => { sendMessageRef.current = sendMessage }, [sendMessage])

  const answerField = useCallback((fieldId: string, value: string) => {
    const ws = wsRef.current
    if (!ws || ws.readyState !== WebSocket.OPEN || !value.trim()) return

    ws.send(JSON.stringify({ type: "field_answer", field_id: fieldId, value: value.trim() }))
    // Show user answer in conversation
    setItems((prev) => [
      ...prev,
      { kind: "message", role: "user", text: value.trim() } satisfies MessageItem,
    ])
    setCurrentField(null)
    setIsThinking(true)
    setStatus("thinking")
  }, [])

  useEffect(() => { answerFieldRef.current = answerField }, [answerField])

  const confirmAnswer = useCallback((confirmed: boolean, correction?: string) => {
    const ws = wsRef.current
    if (!ws || ws.readyState !== WebSocket.OPEN) return
    setCurrentConfirm(null)

    if (confirmed) {
      ws.send(JSON.stringify({ type: "user_message", text: "oui" }))
      setItems((prev) => [
        ...prev,
        { kind: "message", role: "user", text: "Oui, c\u2019est correct" } satisfies MessageItem,
      ])
    } else {
      const text = correction ?? "non"
      ws.send(JSON.stringify({ type: "user_message", text }))
      setItems((prev) => [
        ...prev,
        { kind: "message", role: "user", text } satisfies MessageItem,
      ])
    }
    setIsThinking(true)
    setStatus("thinking")
  }, [])

  // ── Audio (MediaRecorder) ────────────────────────────────────────────────
  // Capture l'audio brut et l'envoie au backend pour transcription fongbe→français via Gemini.
  // L'utilisateur appuie sur le micro pour démarrer et appuie à nouveau pour arrêter.
  // Un timer de sécurité de 60 s arrête automatiquement si l'utilisateur oublie.

  const startRecording = useCallback(() => {
    if (!navigator.mediaDevices?.getUserMedia) {
      console.warn("getUserMedia non supporté par ce navigateur")
      return
    }

    navigator.mediaDevices.getUserMedia({ audio: true })
      .then((stream) => {
        audioChunksRef.current = []

        const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
          ? "audio/webm;codecs=opus"
          : MediaRecorder.isTypeSupported("audio/webm")
          ? "audio/webm"
          : "audio/ogg;codecs=opus"

        const recorder = new MediaRecorder(stream, { mimeType })
        mediaRecorderRef.current = recorder

        recorder.ondataavailable = (e) => {
          if (e.data.size > 0) audioChunksRef.current.push(e.data)
        }

        recorder.onstop = () => {
          stream.getTracks().forEach((t) => t.stop())
          setIsRecording(false)

          const blob = new Blob(audioChunksRef.current, { type: mimeType })
          audioChunksRef.current = []

          const reader = new FileReader()
          reader.onload = (ev) => {
            const result = ev.target?.result as string
            const b64 = result.split(",")[1]
            const ws = wsRef.current
            if (ws && ws.readyState === WebSocket.OPEN && b64) {
              ws.send(JSON.stringify({ type: "audio_message", data: b64, mime_type: mimeType }))
              setIsThinking(true)
              setStatus("thinking")
            }
          }
          reader.readAsDataURL(blob)
        }

        recorder.onerror = () => {
          stream.getTracks().forEach((t) => t.stop())
          setIsRecording(false)
        }

        recorder.start()
        setIsRecording(true)

        // Timer de sécurité : 60 s max
        if (silenceTimerRef.current) clearTimeout(silenceTimerRef.current)
        silenceTimerRef.current = setTimeout(() => {
          if (mediaRecorderRef.current?.state === "recording") {
            mediaRecorderRef.current.stop()
          }
        }, 60000)
      })
      .catch(() => {
        console.warn("Microphone non accessible")
      })
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const stopRecording = useCallback(() => {
    if (silenceTimerRef.current) {
      clearTimeout(silenceTimerRef.current)
      silenceTimerRef.current = null
    }
    if (mediaRecorderRef.current?.state === "recording") {
      mediaRecorderRef.current.stop()
    }
  }, [])

  const uploadDocument = useCallback((file: File) => {
    const ws = wsRef.current
    if (!ws || ws.readyState !== WebSocket.OPEN) return

    const reader = new FileReader()
    reader.onload = (e) => {
      const result = e.target?.result as string
      const base64 = result.split(",")[1]
      const mimeType = file.type || "image/jpeg"
      ws.send(JSON.stringify({ type: "document", data: base64, mime_type: mimeType }))
      setIsWaitingForDocument(false)
      setItems((prev) => [
        ...prev,
        { kind: "message", role: "user", text: `📎 ${file.name}` } satisfies MessageItem,
      ])
    }
    reader.readAsDataURL(file)
  }, [])

  const skipDocument = useCallback(() => {
    const ws = wsRef.current
    if (!ws || ws.readyState !== WebSocket.OPEN) return
    setIsWaitingForDocument(false)
    sendMessage("Je passe l'étape du document.")
  }, [sendMessage])

  return {
    items,
    screenshot,
    status,
    isConnected,
    isRecording,
    isThinking,
    isWaitingForDocument,
    currentUrl,
    currentField,
    currentConfirm,
    startRecording,
    stopRecording,
    sendMessage,
    answerField,
    confirmAnswer,
    uploadDocument,
    skipDocument,
  }
}
