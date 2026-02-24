'use client'

import { useEffect, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { apiFetch, getToken, Tenant } from '@/lib/api'
import Link from 'next/link'
import AdminLayout from '@/components/admin/AdminLayout'
import ModelBrowser from '@/components/admin/ModelBrowser'

function getProviderHint(model: string): string | null {
  if (model.startsWith('ollama:')) return null
  if (model.startsWith('gpt-')) return 'Wymagany klucz OpenAI API (sk-...). Używany też do indeksowania dokumentów RAG.'
  if (model.startsWith('claude-')) return 'Wymagany klucz Anthropic API (sk-ant-...). Do indeksowania dokumentów RAG potrzebny osobny klucz OpenAI.'
  if (model.startsWith('gemini-')) return 'Wymagany klucz Google API (AIza...) z aistudio.google.com. Do indeksowania dokumentów RAG potrzebny osobny klucz OpenAI.'
  return 'Wymagany klucz API dla tego modelu.'
}

export default function TenantEditPage() {
  const params = useParams()
  const router = useRouter()
  const tenantId = params.id as string
  const isNew = tenantId === 'new'

  const [form, setForm] = useState({
    name: '',
    slug: '',
    llm_model: 'ollama:llama3.2',
    llm_api_key: '',
    embedding_api_key: '',
    embedding_model: 'ollama:nomic-embed-text',
    system_prompt: '',
    welcome_message: 'Cześć! Jak mogę Ci pomóc? 👋',
    chat_title: 'AI Assistant',
    chat_color: '#6366f1',
    monthly_token_limit: 1000000,
    daily_token_limit: 50000,
  })
  const [showKey, setShowKey] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)


  useEffect(() => {
    if (!isNew) {
      const token = getToken()
      apiFetch<Tenant>(`/tenants/${tenantId}`, {}, token || undefined).then(t => {
        setForm({
          name: t.name,
          slug: t.slug,
          llm_model: t.llm_model,
          llm_api_key: t.llm_api_key || '',
          embedding_api_key: t.embedding_api_key || '',
          embedding_model: t.embedding_model || 'ollama:nomic-embed-text',
          system_prompt: t.system_prompt || '',
          welcome_message: t.welcome_message,
          chat_title: t.chat_title,
          chat_color: t.chat_color,
          monthly_token_limit: t.monthly_token_limit,
          daily_token_limit: t.daily_token_limit,
        })
      }).catch(() => router.push('/admin'))
    }
  }, [tenantId, isNew, router])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setLoading(true)
    const token = getToken()

    try {
      const payload = {
        ...form,
        llm_api_key: form.llm_api_key || null,
        embedding_api_key: form.embedding_api_key || null,
      }
      if (isNew) {
        await apiFetch('/tenants', { method: 'POST', body: JSON.stringify(payload) }, token || undefined)
      } else {
        await apiFetch(`/tenants/${tenantId}`, { method: 'PATCH', body: JSON.stringify(payload) }, token || undefined)
      }
      setSuccess(true)
      setTimeout(() => router.push('/admin'), 1200)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Błąd zapisu')
    } finally {
      setLoading(false)
    }
  }

  const title = isNew ? 'Nowy profil' : 'Edytuj profil'
  const providerHint = getProviderHint(form.llm_model)

  return (
    <AdminLayout title={title}>
      <div className="max-w-2xl mx-auto space-y-5">
        <h1 className="text-2xl font-bold text-gray-900">{title}</h1>

        {!isNew && (
          <div className="space-y-3">
            <div className="flex gap-2 flex-wrap">
              <Link
                href={`/chat/${tenantId}`}
                target="_blank"
                className="text-sm text-indigo-600 hover:underline"
              >
                ↗ Otwórz czat
              </Link>
              <button
                onClick={() => navigator.clipboard.writeText(`${window.location.origin}/chat/${tenantId}`)}
                className="text-sm text-gray-500 hover:text-indigo-600"
              >
                📋 Kopiuj link
              </button>
            </div>

            <EmbedInfo tenantId={tenantId} />
          </div>
        )}

        <form onSubmit={handleSubmit} className="bg-white rounded-xl border shadow-sm p-6 space-y-5">
          <Field label="Nazwa profilu" required>
            <input
              type="text" value={form.name}
              onChange={e => setForm(p => ({ ...p, name: e.target.value }))}
              className="input" required maxLength={255}
              placeholder="Chatbot firmowy"
            />
          </Field>

          {isNew && (
            <Field label="Slug (URL)" required description="Używany w adresie: /chat/twój-slug">
              <input
                type="text" value={form.slug}
                onChange={e => setForm(p => ({
                  ...p,
                  slug: e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, '-')
                }))}
                pattern="^[a-z0-9-]+" className="input" required
                placeholder="chatbot-firmy"
              />
            </Field>
          )}

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Model LLM</label>
              <div className="input flex items-center justify-between bg-gray-50 cursor-default text-sm">
                <span className="font-mono text-gray-700 truncate">{form.llm_model}</span>
                <span className="text-xs text-gray-400 ml-2 shrink-0">aktywny</span>
              </div>
              <p className="text-xs text-gray-500 mt-1">Wybierz poniżej w tabeli modeli.</p>
            </div>
            <Field label="Kolor motywu">
              <div className="flex items-center gap-2">
                <input
                  type="color" value={form.chat_color}
                  onChange={e => setForm(p => ({ ...p, chat_color: e.target.value }))}
                  className="h-10 w-14 border rounded-lg cursor-pointer p-1"
                />
                <span className="text-sm text-gray-500 font-mono">{form.chat_color}</span>
              </div>
            </Field>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <Field label="Model embeddingów (RAG)" description="Do indeksowania i wyszukiwania w dokumentach RAG.">
              <select
                value={form.embedding_model}
                onChange={e => setForm(p => ({ ...p, embedding_model: e.target.value }))}
                className="input"
              >
                <optgroup label="🦙 Ollama – lokalny, bezpłatny">
                  <option value="ollama:nomic-embed-text">nomic-embed-text (768 dim) – domyślny</option>
                  <option value="ollama:nomic-embed-text:v1.5">nomic-embed-text:v1.5 (768 dim)</option>
                </optgroup>
                <optgroup label="☁ OpenAI (wymaga klucza sk-...)">
                  <option value="openai">text-embedding-3-small (768 dim)</option>
                </optgroup>
              </select>
              {form.embedding_model === 'openai' && (
                <p className="text-xs text-amber-600 mt-1">⚠ Wymagany klucz OpenAI (sk-...) powyżej.</p>
              )}
            </Field>
            <Field
              label="Klucz API modelu"
              description="OpenAI: sk-... · Anthropic: sk-ant-... · Gemini: AIza... · Ollama: puste"
            >
              <div className="relative">
                <input
                  type={showKey ? 'text' : 'password'}
                  value={form.llm_api_key}
                  onChange={e => setForm(p => ({ ...p, llm_api_key: e.target.value }))}
                  className="input pr-16"
                  placeholder={form.llm_model.startsWith('ollama:') ? 'Nie wymagany' : 'sk-... / sk-ant-... / AIza...'}
                />
                <button
                  type="button"
                  onClick={() => setShowKey(s => !s)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-gray-400 hover:text-gray-600 px-2 py-1"
                >
                  {showKey ? 'Ukryj' : 'Pokaż'}
                </button>
              </div>
              {providerHint && (
                <p className="text-xs text-amber-600 mt-1">⚠ {providerHint}</p>
              )}
            </Field>
          </div>

          <ModelBrowser
            currentLlmModel={form.llm_model}
            currentEmbModel={form.embedding_model}
            apiKey={form.llm_api_key}
            onSelectLlm={model => setForm(p => ({ ...p, llm_model: model }))}
            onSelectEmb={model => setForm(p => ({ ...p, embedding_model: model }))}
          />

          <Field label="Tytuł czatu">
            <input
              type="text" value={form.chat_title}
              onChange={e => setForm(p => ({ ...p, chat_title: e.target.value }))}
              className="input" maxLength={255} placeholder="AI Assistant"
            />
          </Field>

          <Field
            label="Wiadomość powitalna"
            description="Wyświetlana jako pierwsza wiadomość asystenta (max 500 znaków)"
          >
            <textarea
              value={form.welcome_message}
              onChange={e => setForm(p => ({ ...p, welcome_message: e.target.value }))}
              rows={3} className="input resize-none" maxLength={500}
              placeholder="Cześć! Jak mogę Ci pomóc?"
            />
            <p className="text-xs text-gray-400 mt-1 text-right">{form.welcome_message.length}/500</p>
          </Field>

          <Field label="Prompt systemowy" description="Instrukcja dla AI – jak ma odpowiadać (opcjonalny)">
            <textarea
              value={form.system_prompt}
              onChange={e => setForm(p => ({ ...p, system_prompt: e.target.value }))}
              rows={4} className="input resize-none" maxLength={4000}
              placeholder="Jesteś asystentem firmy XYZ. Odpowiadasz wyłącznie na podstawie dostarczonej bazy wiedzy..."
            />
          </Field>

          <div className="grid grid-cols-2 gap-4">
            <Field label="Limit tokenów / miesiąc">
              <input
                type="number" value={form.monthly_token_limit}
                onChange={e => setForm(p => ({ ...p, monthly_token_limit: parseInt(e.target.value) }))}
                min={1000} className="input"
              />
            </Field>
            <Field label="Limit tokenów / dzień">
              <input
                type="number" value={form.daily_token_limit}
                onChange={e => setForm(p => ({ ...p, daily_token_limit: parseInt(e.target.value) }))}
                min={100} className="input"
              />
            </Field>
          </div>

          {error && (
            <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-red-700 text-sm">
              {error}
            </div>
          )}
          {success && (
            <div className="bg-green-50 border border-green-200 rounded-lg px-4 py-3 text-green-700 text-sm">
              Zapisano pomyślnie! Przekierowuję...
            </div>
          )}

          <button
            type="submit" disabled={loading}
            className="w-full bg-indigo-600 text-white rounded-lg py-2.5 font-medium hover:bg-indigo-700 disabled:opacity-50 transition-colors"
          >
            {loading ? 'Zapisuję...' : isNew ? 'Utwórz profil' : 'Zapisz zmiany'}
          </button>
        </form>
      </div>

      <style jsx global>{`
        .input {
          width: 100%;
          border: 1px solid #e5e7eb;
          border-radius: 0.5rem;
          padding: 0.5rem 0.75rem;
          font-size: 0.875rem;
          background: white;
        }
        .input:focus {
          outline: none;
          border-color: #6366f1;
          box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.15);
        }
        .input:disabled {
          background: #f9fafb;
          color: #9ca3af;
        }
      `}</style>
    </AdminLayout>
  )
}

const ALL_OLLAMA_MODELS = [
  { value: 'llama3.2', label: 'llama3.2', desc: '3B – lekki' },
  { value: 'llama3.1', label: 'llama3.1', desc: '8B – dobry balans' },
  { value: 'mistral', label: 'mistral', desc: '7B' },
  { value: 'gemma3', label: 'gemma3', desc: '4B' },
  { value: 'phi4-mini', label: 'phi4-mini', desc: '3.8B – szybki' },
  { value: 'deepseek-r1:8b', label: 'deepseek-r1:8b', desc: '8B' },
  { value: 'nomic-embed-text', label: 'nomic-embed-text', desc: 'embeddingi 768 dim' },
  { value: 'nomic-embed-text:v1.5', label: 'nomic-embed-text:v1.5', desc: 'embeddingi 768 dim' },
]

function OllamaModelManager({ availableModels, pullState, onPull }: {
  availableModels: string[]
  pullState: Record<string, 'idle' | 'pulling' | 'done' | 'error'>
  onPull: (model: string) => void
}) {
  const [open, setOpen] = useState(false)

  const isAvailable = (name: string) =>
    availableModels.some(m => m === name || m.startsWith(name + ':'))

  return (
    <div className="border border-gray-200 rounded-lg overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-4 py-2.5 bg-gray-50 hover:bg-gray-100 text-sm font-medium text-gray-700 transition-colors"
      >
        <span>🦙 Modele Ollama – pobieranie i status</span>
        <span className="text-gray-400 text-xs">{open ? '▲ zwiń' : '▼ rozwiń'}</span>
      </button>
      {open && (
        <div className="divide-y divide-gray-100">
          {ALL_OLLAMA_MODELS.map(m => {
            const key = `ollama:${m.value}`
            const available = isAvailable(m.value)
            const state = pullState[key] || 'idle'
            return (
              <div key={m.value} className="flex items-center justify-between px-4 py-2.5 text-sm bg-white">
                <div>
                  <span className="font-mono text-gray-800">{m.label}</span>
                  <span className="text-gray-400 ml-2 text-xs">{m.desc}</span>
                </div>
                <div className="flex items-center gap-2">
                  {(available || state === 'done') && (
                    <span className="text-xs text-green-600 font-medium">✓ dostępny</span>
                  )}
                  {state === 'pulling' && (
                    <span className="text-xs text-blue-500 animate-pulse">Pobieranie...</span>
                  )}
                  {state === 'error' && (
                    <span className="text-xs text-red-500">Błąd</span>
                  )}
                  {!available && state === 'idle' && (
                    <button
                      type="button"
                      onClick={() => onPull(key)}
                      className="text-xs bg-indigo-50 hover:bg-indigo-100 text-indigo-700 px-2 py-1 rounded transition-colors"
                    >
                      ↓ Pobierz
                    </button>
                  )}
                  {(state === 'done' || available) && state !== 'pulling' && (
                    <button
                      type="button"
                      onClick={() => onPull(key)}
                      className="text-xs text-gray-400 hover:text-gray-600"
                      title="Aktualizuj model"
                    >
                      ↻
                    </button>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

function OllamaBadge({ model, available, state, onPull }: {
  model: string
  available: boolean
  state: 'idle' | 'pulling' | 'done' | 'error'
  onPull: () => void
}) {
  if (!model.startsWith('ollama:')) return null
  if (available || state === 'done') {
    return <span className="text-xs text-green-600 ml-1">✓ dostępny</span>
  }
  if (state === 'pulling') {
    return <span className="text-xs text-blue-500 ml-1 animate-pulse">Pobieranie...</span>
  }
  if (state === 'error') {
    return <span className="text-xs text-red-500 ml-1">Błąd pobierania</span>
  }
  return (
    <button
      type="button"
      onClick={onPull}
      className="text-xs text-amber-600 hover:text-amber-800 ml-1 underline"
    >
      ↓ Pobierz model
    </button>
  )
}

function EmbedInfo({ tenantId }: { tenantId: string }) {
  const [copied, setCopied] = useState(false)
  const origin = typeof window !== 'undefined' ? window.location.origin : ''
  const chatUrl = `${origin}/chat/${tenantId}`
  const iframeCode = `<iframe\n  src="${chatUrl}"\n  width="400"\n  height="600"\n  style="border:none;border-radius:12px;box-shadow:0 4px 24px rgba(0,0,0,0.12);"\n  allow="clipboard-write"\n></iframe>`

  const copyIframe = () => {
    navigator.clipboard.writeText(iframeCode).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  return (
    <div className="bg-gray-50 border border-gray-200 rounded-xl p-4 space-y-3 text-sm">
      <p className="font-medium text-gray-700">Osadź czat na swojej stronie</p>
      <div>
        <p className="text-xs text-gray-500 mb-1">Bezpośredni link:</p>
        <div className="flex items-center gap-2">
          <code className="bg-white border border-gray-200 rounded px-2 py-1 text-xs flex-1 truncate text-gray-700">
            {chatUrl}
          </code>
          <button
            onClick={() => navigator.clipboard.writeText(chatUrl)}
            className="text-xs text-indigo-600 hover:underline whitespace-nowrap"
          >
            Kopiuj
          </button>
        </div>
      </div>
      <div>
        <p className="text-xs text-gray-500 mb-1">Kod iframe (wklej w HTML swojej strony):</p>
        <pre className="bg-white border border-gray-200 rounded px-3 py-2 text-xs text-gray-700 overflow-x-auto whitespace-pre-wrap">{iframeCode}</pre>
        <button
          onClick={copyIframe}
          className="mt-1.5 text-xs text-indigo-600 hover:underline"
        >
          {copied ? '✓ Skopiowano!' : 'Kopiuj kod iframe'}
        </button>
      </div>
    </div>
  )
}

function Field({ label, required, description, children }: {
  label: string; required?: boolean; description?: string; children: React.ReactNode
}) {
  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1">
        {label}{required && <span className="text-red-500 ml-0.5">*</span>}
      </label>
      {children}
      {description && <p className="text-xs text-gray-500 mt-1">{description}</p>}
    </div>
  )
}
