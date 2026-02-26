'use client'

import { useEffect, useRef, useState } from 'react'
import { getToken, ollamaApi } from '@/lib/api'

type PullState = 'idle' | 'pulling' | 'done' | 'error'

interface ProviderModel {
  id: string
  size_gb?: number
  builtin?: boolean
}

const BUILTIN_MODELS: Record<string, ProviderModel[]> = {
  ollama: [
    { id: 'llama3.2' },
    { id: 'llama3.1' },
    { id: 'phi4-mini' },
    { id: 'mistral' },
    { id: 'gemma3' },
    { id: 'deepseek-r1:8b' },
    { id: 'nomic-embed-text' },
    { id: 'nomic-embed-text:v1.5' },
    { id: 'mxbai-embed-large' },
  ],
  openai: [
    { id: 'gpt-4o', builtin: true },
    { id: 'gpt-4o-mini', builtin: true },
    { id: 'gpt-4-turbo', builtin: true },
  ],
  anthropic: [
    { id: 'claude-opus-4-5', builtin: true },
    { id: 'claude-sonnet-4-5', builtin: true },
    { id: 'claude-haiku-4-5-20251001', builtin: true },
    { id: 'claude-3-5-sonnet-20241022', builtin: true },
    { id: 'claude-3-5-haiku-20241022', builtin: true },
    { id: 'claude-3-opus-20240229', builtin: true },
  ],
  gemini: [
    { id: 'gemini-2.0-flash', builtin: true },
    { id: 'gemini-2.0-flash-lite', builtin: true },
    { id: 'gemini-1.5-pro', builtin: true },
    { id: 'gemini-1.5-flash', builtin: true },
  ],
}

const PROVIDER_META = [
  { key: 'ollama', label: '🦙 Ollama', desc: 'lokalny, bezpłatny', needsKey: false },
  { key: 'openai', label: '☁ OpenAI', desc: 'wymaga klucza sk-...', needsKey: true },
  { key: 'anthropic', label: '🔵 Anthropic', desc: 'wymaga klucza sk-ant-...', needsKey: true },
  { key: 'gemini', label: '🟢 Gemini', desc: 'wymaga klucza AIza...', needsKey: true },
]

interface Props {
  currentLlmModel: string
  currentEmbModel: string
  apiKey: string
  onSelectLlm: (model: string) => void
  onSelectEmb: (model: string) => void
}

export default function ModelBrowser({
  currentLlmModel, currentEmbModel, apiKey, onSelectLlm, onSelectEmb,
}: Props) {
  const token = getToken() || ''
  const [ollamaAvailable, setOllamaAvailable] = useState<string[]>([])
  const [pullState, setPullState] = useState<Record<string, PullState>>({})
  const [models, setModels] = useState<Record<string, ProviderModel[]>>(BUILTIN_MODELS)
  const [fetching, setFetching] = useState<Record<string, boolean>>({})
  const [fetchError, setFetchError] = useState<Record<string, string>>({})
  const pollRef = useRef<Record<string, ReturnType<typeof setInterval>>>({})

  useEffect(() => {
    if (token) refreshOllama()
    return () => { Object.values(pollRef.current).forEach(clearInterval) }
  }, []) // eslint-disable-line

  const refreshOllama = () => {
    ollamaApi.listModels(token)
      .then(r => setOllamaAvailable(r.models))
      .catch(() => {})
  }

  const isOllamaAvailable = (name: string) =>
    ollamaAvailable.some(m => m === name || m.startsWith(name + ':') || m.startsWith(name + '-'))

  const pullModel = (name: string) => {
    setPullState(s => ({ ...s, [name]: 'pulling' }))
    ollamaApi.pullModel(token, name).catch(() => {
      setPullState(s => ({ ...s, [name]: 'error' }))
    })
    const interval = setInterval(() => {
      ollamaApi.listModels(token).then(r => {
        setOllamaAvailable(r.models)
        const found = r.models.some(m => m === name || m.startsWith(name + ':'))
        if (found) {
          setPullState(s => ({ ...s, [name]: 'done' }))
          clearInterval(interval)
          delete pollRef.current[name]
        }
      }).catch(() => {})
    }, 5000)
    pollRef.current[name] = interval
  }

  const fetchProvider = async (providerKey: string) => {
    setFetching(s => ({ ...s, [providerKey]: true }))
    setFetchError(s => ({ ...s, [providerKey]: '' }))
    try {
      const res = await ollamaApi.fetchProviderModels(token, providerKey, apiKey)
      if (res.error) {
        setFetchError(s => ({ ...s, [providerKey]: res.error! }))
        return
      }
      // Merge with existing: add new models not already in list
      setModels(prev => {
        const existing = new Set((prev[providerKey] || []).map(m => m.id))
        const newOnes = res.models.filter(m => !existing.has(m.id))
        return { ...prev, [providerKey]: [...(prev[providerKey] || []), ...newOnes] }
      })
      if (providerKey === 'ollama') setOllamaAvailable(res.models.map(m => m.id))
    } catch (e: unknown) {
      setFetchError(s => ({ ...s, [providerKey]: e instanceof Error ? e.message : 'Błąd' }))
    } finally {
      setFetching(s => ({ ...s, [providerKey]: false }))
    }
  }

  const isEmbModel = (id: string) => id.includes('embed') || id.includes('minilm')

  return (
    <div className="border border-gray-200 rounded-xl overflow-hidden">
      <div className="px-4 py-3 bg-gray-50 border-b border-gray-200">
        <p className="text-sm font-medium text-gray-700">Zarządzanie modelami</p>
        <p className="text-xs text-gray-400 mt-0.5">
          Wybierz model klikając &quot;→ LLM&quot; lub &quot;→ Emb&quot;. Aktywny model jest podświetlony.
        </p>
      </div>

      {PROVIDER_META.map(provider => (
        <ProviderSection
          key={provider.key}
          provider={provider}
          models={models[provider.key] || []}
          ollamaAvailable={ollamaAvailable}
          isOllamaAvailable={isOllamaAvailable}
          pullState={pullState}
          fetching={!!fetching[provider.key]}
          fetchError={fetchError[provider.key] || ''}
          currentLlmModel={currentLlmModel}
          currentEmbModel={currentEmbModel}
          isEmbModel={isEmbModel}
          onFetch={() => fetchProvider(provider.key)}
          onPull={pullModel}
          onSelectLlm={onSelectLlm}
          onSelectEmb={onSelectEmb}
        />
      ))}
    </div>
  )
}

function ProviderSection({
  provider, models, isOllamaAvailable, pullState, fetching, fetchError,
  currentLlmModel, currentEmbModel, isEmbModel,
  onFetch, onPull, onSelectLlm, onSelectEmb,
}: {
  provider: { key: string; label: string; desc: string; needsKey: boolean }
  models: ProviderModel[]
  ollamaAvailable: string[]
  isOllamaAvailable: (name: string) => boolean
  pullState: Record<string, PullState>
  fetching: boolean
  fetchError: string
  currentLlmModel: string
  currentEmbModel: string
  isEmbModel: (id: string) => boolean
  onFetch: () => void
  onPull: (name: string) => void
  onSelectLlm: (model: string) => void
  onSelectEmb: (model: string) => void
}) {
  const [open, setOpen] = useState(true)
  const fullId = (id: string) => provider.key === 'ollama' ? `ollama:${id}` : id

  return (
    <div className="border-b border-gray-100 last:border-0">
      {/* Provider header */}
      <div className="flex items-center justify-between px-4 py-2.5 bg-white">
        <button
          type="button"
          onClick={() => setOpen(o => !o)}
          className="flex items-center gap-2 text-sm font-medium text-gray-700 hover:text-gray-900"
        >
          <span>{provider.label}</span>
          <span className="text-xs text-gray-400 font-normal">{provider.desc}</span>
          <span className="text-gray-300 text-xs">{open ? '▲' : '▼'}</span>
        </button>
        <button
          type="button"
          onClick={onFetch}
          disabled={fetching}
          className="text-xs text-indigo-600 hover:text-indigo-800 disabled:opacity-50 flex items-center gap-1"
        >
          {fetching ? (
            <span className="animate-pulse">Sprawdzam...</span>
          ) : (
            <span>↻ Sprawdź nowe</span>
          )}
        </button>
      </div>

      {fetchError && (
        <p className="px-4 pb-2 text-xs text-red-500">{fetchError}</p>
      )}

      {/* Model rows */}
      {open && (
        <div className="divide-y divide-gray-50">
          {models.map(m => {
            const fid = fullId(m.id)
            const isLlmActive = currentLlmModel === fid
            const isEmbActive = currentEmbModel === fid
            const available = provider.key === 'ollama' ? isOllamaAvailable(m.id) : true
            const state = pullState[m.id] || 'idle'
            const embModel = isEmbModel(m.id)

            return (
              <div
                key={m.id}
                className={`flex items-center justify-between px-4 py-2 text-sm ${
                  (isLlmActive || isEmbActive) ? 'bg-indigo-50' : 'bg-white hover:bg-gray-50'
                }`}
              >
                <div className="flex items-center gap-2 min-w-0">
                  <span className="font-mono text-gray-800 text-xs truncate">{m.id}</span>
                  {m.size_gb ? (
                    <span className="text-xs text-gray-400">{m.size_gb}GB</span>
                  ) : null}
                  {isLlmActive && <span className="text-xs bg-indigo-100 text-indigo-700 px-1.5 py-0.5 rounded-full">LLM</span>}
                  {isEmbActive && <span className="text-xs bg-purple-100 text-purple-700 px-1.5 py-0.5 rounded-full">Emb</span>}
                </div>

                <div className="flex items-center gap-1.5 shrink-0 ml-2">
                  {/* Ollama availability */}
                  {provider.key === 'ollama' && (
                    <>
                      {(available || state === 'done') && (
                        <span className="text-xs text-green-600">✓</span>
                      )}
                      {state === 'pulling' && (
                        <span className="text-xs text-blue-500 animate-pulse">↓...</span>
                      )}
                      {state === 'error' && (
                        <span className="text-xs text-red-500">Błąd</span>
                      )}
                      {!available && state === 'idle' && (
                        <button
                          type="button"
                          onClick={() => onPull(m.id)}
                          className="text-xs bg-amber-50 hover:bg-amber-100 text-amber-700 px-1.5 py-0.5 rounded"
                        >
                          ↓ Pobierz
                        </button>
                      )}
                      {(available || state === 'done') && (
                        <button
                          type="button"
                          onClick={() => onPull(m.id)}
                          className="text-xs text-gray-300 hover:text-gray-500"
                          title="Aktualizuj"
                        >↻</button>
                      )}
                    </>
                  )}

                  {/* Select as LLM (skip pure embed models) */}
                  {!embModel && (
                    <button
                      type="button"
                      onClick={() => onSelectLlm(fid)}
                      className={`text-xs px-1.5 py-0.5 rounded transition-colors ${
                        isLlmActive
                          ? 'bg-indigo-600 text-white'
                          : 'bg-gray-100 hover:bg-indigo-100 text-gray-600 hover:text-indigo-700'
                      }`}
                    >
                      → LLM
                    </button>
                  )}

                  {/* Select as Embedding */}
                  {(embModel || provider.key === 'openai') && (
                    <button
                      type="button"
                      onClick={() => {
                        const target = embModel ? fid : 'openai'
                        onSelectEmb(target)
                        // Auto-pull if Ollama embed model not yet available
                        if (provider.key === 'ollama' && embModel && !available && state === 'idle') {
                          onPull(m.id)
                        }
                      }}
                      className={`text-xs px-1.5 py-0.5 rounded transition-colors ${
                        isEmbActive
                          ? 'bg-purple-600 text-white'
                          : 'bg-gray-100 hover:bg-purple-100 text-gray-600 hover:text-purple-700'
                      }`}
                    >
                      → Emb
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
