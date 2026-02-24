'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { apiFetch, getToken, Tenant } from '@/lib/api'
import Link from 'next/link'
import { ExternalLink, Copy, Trash2, Plus } from 'lucide-react'
import AdminLayout from '@/components/admin/AdminLayout'

export default function ProfilesPage() {
  const router = useRouter()
  const [tenants, setTenants] = useState<Tenant[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchTenants = () => {
    const token = getToken()
    if (!token) { router.push('/admin/login'); return }
    setLoading(true)
    apiFetch<Tenant[]>('/tenants', {}, token)
      .then(setTenants)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => { fetchTenants() }, []) // eslint-disable-line

  const handleDelete = async (tenant: Tenant) => {
    if (!confirm(`Usunąć profil "${tenant.name}" i WSZYSTKIE jego dane (dokumenty, rozmowy)?`)) return
    const token = getToken()
    try {
      await apiFetch(`/tenants/${tenant.id}`, { method: 'DELETE' }, token || undefined)
      setTenants(prev => prev.filter(t => t.id !== tenant.id))
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Błąd usuwania')
    }
  }

  const copyLink = (tenantId: string) => {
    const url = `${window.location.origin}/chat/${tenantId}`
    navigator.clipboard.writeText(url)
  }

  return (
    <AdminLayout title="Wszystkie profile">
      <div className="max-w-5xl mx-auto space-y-5">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Profile chatbotów</h1>
            <p className="text-sm text-gray-500 mt-0.5">
              Każdy profil to niezależny chatbot z własną bazą wiedzy i modelem LLM.
            </p>
          </div>
          <Link
            href="/admin/tenants/new"
            className="flex items-center gap-2 bg-indigo-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-indigo-700 transition-colors"
          >
            <Plus className="w-4 h-4" />
            Nowy profil
          </Link>
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-red-700 text-sm">
            {error}
          </div>
        )}

        {loading ? (
          <div className="p-8 text-center text-gray-400">Ładowanie...</div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {tenants.map(tenant => (
              <div key={tenant.id} className="bg-white rounded-xl border shadow-sm p-5 space-y-4">
                {/* Header */}
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-center gap-3">
                    <div
                      className="w-10 h-10 rounded-lg flex-shrink-0 flex items-center justify-center text-white font-bold"
                      style={{ backgroundColor: tenant.chat_color }}
                    >
                      {tenant.name[0]}
                    </div>
                    <div>
                      <p className="font-semibold text-gray-900">{tenant.name}</p>
                      <p className="text-xs text-gray-400 font-mono">/{tenant.slug}</p>
                    </div>
                  </div>
                  <span className={`text-xs px-2 py-0.5 rounded-full flex-shrink-0 ${
                    tenant.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'
                  }`}>
                    {tenant.is_active ? 'Aktywny' : 'Nieaktywny'}
                  </span>
                </div>

                {/* Details */}
                <div className="grid grid-cols-2 gap-2 text-xs text-gray-500">
                  <div>
                    <span className="text-gray-400">Model:</span>
                    <span className="ml-1 font-mono text-gray-700">{tenant.llm_model}</span>
                  </div>
                  <div>
                    <span className="text-gray-400">Limit dzienny:</span>
                    <span className="ml-1 text-gray-700">{tenant.daily_token_limit.toLocaleString()}</span>
                  </div>
                  <div>
                    <span className="text-gray-400">Zużyto dziś:</span>
                    <span className="ml-1 text-gray-700">{tenant.tokens_used_day.toLocaleString()}</span>
                  </div>
                  <div>
                    <span className="text-gray-400">Zużyto/mies.:</span>
                    <span className="ml-1 text-gray-700">{tenant.tokens_used_month.toLocaleString()}</span>
                  </div>
                </div>

                {/* Usage bar */}
                <div>
                  <div className="flex justify-between text-xs text-gray-400 mb-1">
                    <span>Dzienny limit tokenów</span>
                    <span>{Math.round((tenant.tokens_used_day / tenant.daily_token_limit) * 100)}%</span>
                  </div>
                  <div className="w-full bg-gray-100 rounded-full h-1.5">
                    <div
                      className="h-1.5 rounded-full bg-indigo-500"
                      style={{
                        width: `${Math.min((tenant.tokens_used_day / tenant.daily_token_limit) * 100, 100)}%`
                      }}
                    />
                  </div>
                </div>

                {/* Actions */}
                <div className="flex items-center gap-2 pt-1 border-t">
                  <Link
                    href={`/admin/tenants/${tenant.id}`}
                    className="flex-1 text-center text-sm text-indigo-600 hover:underline py-1"
                  >
                    Edytuj
                  </Link>
                  <Link
                    href={`/admin/documents?tenant_id=${tenant.id}`}
                    className="flex-1 text-center text-sm text-gray-600 hover:text-indigo-600 py-1"
                  >
                    Dokumenty
                  </Link>
                  <button
                    onClick={() => copyLink(tenant.id)}
                    className="text-gray-400 hover:text-indigo-600 p-1"
                    title="Kopiuj link"
                  >
                    <Copy className="w-4 h-4" />
                  </button>
                  <Link
                    href={`/chat/${tenant.id}`}
                    target="_blank"
                    className="text-gray-400 hover:text-indigo-600 p-1"
                    title="Otwórz czat"
                  >
                    <ExternalLink className="w-4 h-4" />
                  </Link>
                  <button
                    onClick={() => handleDelete(tenant)}
                    className="text-red-400 hover:text-red-600 p-1"
                    title="Usuń profil"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ))}

            {tenants.length === 0 && (
              <div className="md:col-span-2 bg-white rounded-xl border shadow-sm p-12 text-center">
                <p className="text-gray-500 mb-3">Brak profili.</p>
                <Link
                  href="/admin/tenants/new"
                  className="inline-flex items-center gap-2 bg-indigo-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-indigo-700"
                >
                  <Plus className="w-4 h-4" />
                  Utwórz pierwszy profil
                </Link>
              </div>
            )}
          </div>
        )}
      </div>
    </AdminLayout>
  )
}
