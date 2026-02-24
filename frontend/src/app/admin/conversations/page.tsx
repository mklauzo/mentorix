'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { apiFetch, getToken, Conversation } from '@/lib/api'
import Link from 'next/link'
import { format } from 'date-fns'
import AdminLayout from '@/components/admin/AdminLayout'

export default function ConversationsPage() {
  const router = useRouter()
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(1)

  useEffect(() => {
    const token = getToken()
    if (!token) { router.push('/admin/login'); return }

    apiFetch<Conversation[]>(`/admin/conversations?page=${page}&per_page=20`, {}, token)
      .then(setConversations)
      .catch(() => router.push('/admin/login'))
      .finally(() => setLoading(false))
  }, [router, page])

  return (
    <AdminLayout title="Historia rozmów">
      <div className="max-w-5xl mx-auto space-y-5">
        <h1 className="text-2xl font-bold text-gray-900">Historia rozmów</h1>

        <div className="bg-white rounded-xl border shadow-sm overflow-hidden">
          {loading ? (
            <div className="p-8 text-center text-gray-400">Ładowanie...</div>
          ) : (
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b">
                <tr>
                  <th className="text-left px-5 py-3 font-medium text-gray-600">Rozpoczęta</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600 hidden md:table-cell">Ostatnia wiad.</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Wiadomości</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600 hidden lg:table-cell">IP hash</th>
                  <th className="px-4 py-3"></th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {conversations.map(conv => (
                  <tr key={conv.id} className="hover:bg-gray-50">
                    <td className="px-5 py-3">{format(new Date(conv.started_at), 'dd.MM.yyyy HH:mm')}</td>
                    <td className="px-4 py-3 hidden md:table-cell text-gray-500">
                      {format(new Date(conv.last_message_at), 'HH:mm')}
                    </td>
                    <td className="px-4 py-3">
                      <span className="bg-gray-100 text-gray-700 px-2 py-0.5 rounded-full text-xs font-medium">
                        {conv.message_count}
                      </span>
                    </td>
                    <td className="px-4 py-3 hidden lg:table-cell font-mono text-xs text-gray-400">
                      {conv.user_ip_hash?.substring(0, 16)}…
                    </td>
                    <td className="px-4 py-3">
                      <Link href={`/admin/conversations/${conv.id}`}
                        className="text-indigo-600 hover:underline text-sm">
                        Otwórz →
                      </Link>
                    </td>
                  </tr>
                ))}
                {conversations.length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-5 py-10 text-center text-gray-500">
                      Brak rozmów
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          )}
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => setPage(p => Math.max(1, p - 1))}
            disabled={page === 1}
            className="px-4 py-2 border rounded-lg text-sm disabled:opacity-40 hover:bg-gray-50"
          >
            ← Poprzednia
          </button>
          <span className="text-sm text-gray-500">Strona {page}</span>
          <button
            onClick={() => setPage(p => p + 1)}
            disabled={conversations.length < 20}
            className="px-4 py-2 border rounded-lg text-sm disabled:opacity-40 hover:bg-gray-50"
          >
            Następna →
          </button>
        </div>
      </div>
    </AdminLayout>
  )
}
