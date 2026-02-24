'use client'

import { useEffect, useRef, useState } from 'react'
import { Send, Loader2 } from 'lucide-react'
import { apiFetch, ChatConfig, ChatMessage, ChatResponse } from '@/lib/api'
import MessageBubble from './MessageBubble'

interface Props {
  tenantId: string
}

function generateSessionId(): string {
  return crypto.randomUUID()
}

export default function ChatWindow({ tenantId }: Props) {
  const [config, setConfig] = useState<ChatConfig | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [configError, setConfigError] = useState(false)
  const sessionIdRef = useRef<string>(generateSessionId())
  const conversationIdRef = useRef<string | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  // Load chat config (title, color, welcome message)
  useEffect(() => {
    apiFetch<ChatConfig>(`/chat/${tenantId}/config`)
      .then(setConfig)
      .catch(() => setConfigError(true))
  }, [tenantId])

  // Auto-scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  const handleSend = async () => {
    const question = input.trim()
    if (!question || loading) return

    setInput('')
    setError(null)
    setMessages((prev) => [...prev, { role: 'user', content: question }])
    setLoading(true)

    try {
      const res = await apiFetch<ChatResponse>(`/chat/${tenantId}/message`, {
        method: 'POST',
        body: JSON.stringify({
          question,
          session_id: sessionIdRef.current,
          conversation_id: conversationIdRef.current,
        }),
      })

      conversationIdRef.current = res.conversation_id
      setMessages((prev) => [...prev, { role: 'assistant', content: res.answer }])
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Wystąpił błąd'
      setError(msg)
      setMessages((prev) => [...prev, {
        role: 'assistant',
        content: `Przepraszam, wystąpił błąd: ${msg}`,
      }])
    } finally {
      setLoading(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  if (configError) {
    return (
      <div className="flex-1 flex items-center justify-center text-gray-500">
        <p>Chat jest niedostępny.</p>
      </div>
    )
  }

  const chatColor = config?.chat_color || '#6366f1'

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div
        className="px-4 py-3 text-white flex items-center gap-3 shadow-sm"
        style={{ backgroundColor: chatColor }}
      >
        <div className="w-8 h-8 bg-white/20 rounded-full flex items-center justify-center text-sm font-bold">
          AI
        </div>
        <h1 className="font-semibold text-lg">
          {config?.chat_title || 'AI Assistant'}
        </h1>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3 chat-scrollbar">
        {/* Welcome message (not saved to DB) */}
        {messages.length === 0 && config && (
          <MessageBubble
            message={{ role: 'assistant', content: config.welcome_message }}
            chatColor={chatColor}
            isWelcome
          />
        )}

        {messages.map((msg, i) => (
          <MessageBubble key={i} message={msg} chatColor={chatColor} />
        ))}

        {loading && (
          <div className="flex items-center gap-2 text-gray-400 text-sm">
            <Loader2 className="w-4 h-4 animate-spin" />
            <span>Myślę...</span>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="border-t p-3 bg-white">
        <div className="flex gap-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Napisz wiadomość... (Enter aby wysłać)"
            rows={1}
            className="flex-1 resize-none border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 max-h-32"
            style={{ '--tw-ring-color': chatColor } as React.CSSProperties}
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || loading}
            className="px-3 py-2 rounded-lg text-white disabled:opacity-50 transition-opacity"
            style={{ backgroundColor: chatColor }}
            aria-label="Wyślij"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
        <p className="text-xs text-gray-400 mt-1 text-center">
          Powered by Mentorix AI
        </p>
      </div>
    </div>
  )
}
