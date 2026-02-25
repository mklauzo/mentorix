'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { apiFetch, getToken, getCachedUser, Tenant } from '@/lib/api'
import Link from 'next/link'
import { ExternalLink, Copy, FileText } from 'lucide-react'
import AdminLayout from '@/components/admin/AdminLayout'

export default function MyProfilePage() {
  const router = useRouter()
  const currentUser = getCachedUser()
  const [tenant, setTenant] = useState<Tenant | null>(null)
  const [loading, setLoading] = useState(true)
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    const token = getToken()
    if (!token) { router.push('/admin/login'); return }

    if (!currentUser?.tenant_id) {
      setLoading(false)
      return
    }

    apiFetch<Tenant[]>('/tenants', {}, token)
      .then(tenants => {
        const mine = tenants.find(t => t.id === currentUser.tenant_id)
        setTenant(mine || null)
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, []) // eslint-disable-line

  const chatUrl = tenant ? `${window?.location?.origin || ''}/chat/${tenant.id}` : ''

  const copyLink = () => {
    if (!chatUrl) return
    navigator.clipboard.writeText(chatUrl)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  if (loading) return <AdminLayout title="Mój profil"><div className="p-8 text-gray-400 text-center">Ładowanie...</div></AdminLayout>

  if (!tenant) {
    return (
      <AdminLayout title="Mój profil">
        <div className="max-w-lg mx-auto bg-white rounded-xl border p-8 text-center space-y-3">
          <p className="text-gray-500">Nie masz przypisanego profilu.</p>
          <p className="text-sm text-gray-400">Skontaktuj się z superadminem.</p>
        </div>
      </AdminLayout>
    )
  }

  const usagePercent = tenant.daily_token_limit > 0
    ? Math.round((tenant.tokens_used_day / tenant.daily_token_limit) * 100)
    : 0

  return (
    <AdminLayout title="Mój profil">
      <div className="max-w-3xl mx-auto space-y-5">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold text-gray-900">Mój profil</h1>
          <Link
            href={`/admin/tenants/${tenant.id}`}
            className="text-sm bg-indigo-600 text-white px-4 py-2 rounded-lg hover:bg-indigo-700"
          >
            Edytuj ustawienia
          </Link>
        </div>

        {/* Profile card */}
        <div className="bg-white rounded-xl border shadow-sm p-5">
          <div className="flex items-start gap-4">
            <div
              className="w-14 h-14 rounded-xl flex-shrink-0 flex items-center justify-center text-white text-xl font-bold"
              style={{ backgroundColor: tenant.chat_color }}
            >
              {tenant.name[0]}
            </div>
            <div className="flex-1">
              <h2 className="text-xl font-semibold text-gray-900">{tenant.name}</h2>
              <p className="text-sm text-gray-500">{tenant.chat_title}</p>
              <div className="flex items-center gap-2 mt-2">
                <span className={`text-xs px-2 py-0.5 rounded-full ${
                  tenant.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'
                }`}>
                  {tenant.is_active ? 'Aktywny' : 'Nieaktywny'}
                </span>
                <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full">
                  {tenant.llm_model}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Chat link */}
        <div className="bg-white rounded-xl border shadow-sm p-5">
          <h3 className="font-semibold text-gray-900 mb-3">Link do czatu</h3>
          <div className="flex items-center gap-2 bg-gray-50 rounded-lg px-3 py-2 border">
            <code className="text-sm text-gray-700 flex-1 truncate">{chatUrl}</code>
            <button onClick={copyLink} className="text-indigo-600 hover:text-indigo-700 flex-shrink-0" title="Kopiuj">
              <Copy className="w-4 h-4" />
            </button>
            <Link href={`/chat/${tenant.id}`} target="_blank" className="text-gray-400 hover:text-indigo-600 flex-shrink-0">
              <ExternalLink className="w-4 h-4" />
            </Link>
          </div>
          {copied && <p className="text-xs text-green-600 mt-1">Skopiowano!</p>}
          <p className="text-xs text-gray-400 mt-2">
            Możesz osadzić ten link w iframe na swojej stronie.
          </p>
          <div className="mt-3 bg-gray-900 rounded-lg p-3">
            <code className="text-xs text-green-400">
              {`<iframe src="${chatUrl}" width="400" height="600" frameborder="0"></iframe>`}
            </code>
          </div>
        </div>

        {/* Usage */}
        <div className="bg-white rounded-xl border shadow-sm p-5">
          <h3 className="font-semibold text-gray-900 mb-4">Zużycie tokenów</h3>
          <div className="space-y-3">
            <div>
              <div className="flex justify-between text-sm mb-1">
                <span className="text-gray-600">Dziś</span>
                <span className="font-medium">
                  {tenant.tokens_used_day.toLocaleString()} / {tenant.daily_token_limit.toLocaleString()}
                </span>
              </div>
              <div className="w-full bg-gray-100 rounded-full h-2">
                <div
                  className={`h-2 rounded-full ${usagePercent > 80 ? 'bg-red-500' : 'bg-indigo-500'}`}
                  style={{ width: `${Math.min(usagePercent, 100)}%` }}
                />
              </div>
              <p className="text-xs text-gray-400 mt-0.5">{usagePercent}% dziennego limitu</p>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-gray-600">W tym miesiącu</span>
              <span className="font-medium">
                {tenant.tokens_used_month.toLocaleString()} / {tenant.monthly_token_limit.toLocaleString()}
              </span>
            </div>
          </div>
        </div>

        {/* Quick actions */}
        <div className="bg-white rounded-xl border shadow-sm p-5">
          <h3 className="font-semibold text-gray-900 mb-3">Szybkie akcje</h3>
          <div className="flex gap-3 flex-wrap">
            <Link
              href={`/admin/documents?tenant_id=${tenant.id}`}
              className="flex items-center gap-2 px-4 py-2 border rounded-lg text-sm hover:bg-gray-50"
            >
              <FileText className="w-4 h-4 text-indigo-600" />
              Zarządzaj dokumentami
            </Link>
            <Link
              href={`/admin/conversations?tenant_id=${tenant.id}`}
              className="flex items-center gap-2 px-4 py-2 border rounded-lg text-sm hover:bg-gray-50"
            >
              Historia rozmów
            </Link>
          </div>
        </div>
      </div>
    </AdminLayout>
  )
}
