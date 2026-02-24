'use client'

import { useEffect, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { apiFetch, getToken, getCachedUser, MessageDetail } from '@/lib/api'
import Link from 'next/link'
import { Trash2 } from 'lucide-react'
import { format } from 'date-fns'
import AdminLayout from '@/components/admin/AdminLayout'

export default function ConversationThreadPage() {
  const params = useParams()
  const router = useRouter()
  const conversationId = params.id as string
  const [messages, setMessages] = useState<MessageDetail[]>([])
  const [loading, setLoading] = useState(true)
  const [deleting, setDeleting] = useState(false)
  const user = getCachedUser()
  const canDelete = user?.role === 'superadmin' || user?.role === 'admin'

  useEffect(() => {
    const token = getToken()
    if (!token) { router.push('/admin/login'); return }

    apiFetch<MessageDetail[]>(`/admin/conversations/${conversationId}/messages`, {}, token)
      .then(setMessages)
      .catch(() => router.push('/admin/conversations'))
      .finally(() => setLoading(false))
  }, [conversationId, router])

  const handleDelete = async () => {
    if (!confirm('Usunąć tę rozmowę? Tej operacji nie można cofnąć.')) return
    const token = getToken()
    if (!token) return
    setDeleting(true)
    try {
      await apiFetch(`/admin/conversations/${conversationId}`, { method: 'DELETE' }, token)
      router.push('/admin/conversations')
    } finally {
      setDeleting(false)
    }
  }

  const totalTokens = messages.reduce((sum, m) => sum + (m.total_tokens || 0), 0)

  return (
    <AdminLayout title="Wątek rozmowy">
      <div className="max-w-3xl mx-auto space-y-5">
        <div className="flex items-center justify-between">
          <Link href="/admin/conversations" className="text-indigo-600 text-sm hover:underline">
            ← Historia rozmów
          </Link>
          <div className="flex items-center gap-4">
            {totalTokens > 0 && (
              <span className="text-xs text-gray-400">
                Łącznie: {totalTokens.toLocaleString()} tokenów
              </span>
            )}
            {canDelete && (
              <button
                onClick={handleDelete}
                disabled={deleting}
                className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-red-600 transition-colors disabled:opacity-40"
              >
                <Trash2 className="w-4 h-4" />
                Usuń rozmowę
              </button>
            )}
          </div>
        </div>

        <h1 className="text-2xl font-bold text-gray-900">Wątek rozmowy</h1>

        {loading ? (
          <div className="p-8 text-center text-gray-400">Ładowanie...</div>
        ) : (
          <div className="space-y-3">
            {messages.map(msg => (
              <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div className={`max-w-[80%] rounded-2xl px-4 py-3 ${
                  msg.role === 'user'
                    ? 'bg-indigo-600 text-white rounded-tr-sm'
                    : 'bg-white border shadow-sm text-gray-800 rounded-tl-sm'
                }`}>
                  <p className="text-sm whitespace-pre-wrap leading-relaxed">{msg.content}</p>
                  <div className="flex items-center gap-3 mt-1.5">
                    <span className={`text-xs ${msg.role === 'user' ? 'text-indigo-200' : 'text-gray-400'}`}>
                      {format(new Date(msg.created_at), 'HH:mm:ss')}
                    </span>
                    {msg.total_tokens && (
                      <span className={`text-xs ${msg.role === 'user' ? 'text-indigo-200' : 'text-gray-400'}`}>
                        {msg.total_tokens} tok.
                      </span>
                    )}
                  </div>
                  {msg.retrieved_chunk_ids && msg.retrieved_chunk_ids.length > 0 && (
                    <div className="mt-2 pt-2 border-t border-gray-100">
                      <p className="text-xs text-gray-400">
                        RAG: {msg.retrieved_chunk_ids.length} źródeł
                      </p>
                    </div>
                  )}
                </div>
              </div>
            ))}
            {messages.length === 0 && (
              <div className="text-center text-gray-500 py-12">Brak wiadomości</div>
            )}
          </div>
        )}
      </div>
    </AdminLayout>
  )
}
