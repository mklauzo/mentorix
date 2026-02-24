'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { apiFetch, getToken, getCachedUser, Tenant, AppUser } from '@/lib/api'
import Link from 'next/link'
import { Users, FileText, Globe, TrendingUp, ExternalLink, Copy } from 'lucide-react'
import AdminLayout from '@/components/admin/AdminLayout'
import { RoleBadge } from '@/components/admin/RoleBadge'

export default function AdminDashboard() {
  const router = useRouter()
  const [tenants, setTenants] = useState<Tenant[]>([])
  const [users, setUsers] = useState<AppUser[]>([])
  const [loading, setLoading] = useState(true)
  const [fetchError, setFetchError] = useState<string | null>(null)
  const user = getCachedUser()

  useEffect(() => {
    const token = getToken()
    if (!token) { router.push('/admin/login'); return }

    Promise.all([
      apiFetch<Tenant[]>('/tenants', {}, token),
      apiFetch<AppUser[]>('/users', {}, token),
    ])
      .then(([t, u]) => { setTenants(t); setUsers(u) })
      .catch((err: unknown) => {
        const msg = err instanceof Error ? err.message : String(err)
        // Only redirect to login for auth errors
        if (msg.includes('401') || msg.includes('Unauthorized') || msg.includes('credentials')) {
          router.push('/admin/login')
        } else {
          setFetchError(msg)
        }
      })
      .finally(() => setLoading(false))
  }, [router])

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text).catch(() => {})
  }

  const isSuperadmin = user?.role === 'superadmin'

  if (loading) {
    return (
      <AdminLayout title="Dashboard">
        <div className="flex items-center justify-center h-64 text-gray-400">Ładowanie...</div>
      </AdminLayout>
    )
  }

  if (fetchError) {
    return (
      <AdminLayout title="Dashboard">
        <div className="max-w-xl mx-auto mt-10 bg-red-50 border border-red-200 rounded-xl p-6">
          <h2 className="font-semibold text-red-800 mb-2">Błąd ładowania danych</h2>
          <p className="text-sm text-red-700 font-mono break-all">{fetchError}</p>
          <p className="text-xs text-red-500 mt-3">Sprawdź logi: <code>docker compose logs backend --tail=30</code></p>
        </div>
      </AdminLayout>
    )
  }

  return (
    <AdminLayout title="Dashboard">
      <div className="max-w-5xl mx-auto space-y-6">
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>

        {/* Stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <StatCard icon={<Globe className="w-5 h-5" />} label="Profile" value={tenants.length} color="indigo" />
          <StatCard icon={<Users className="w-5 h-5" />} label="Użytkownicy" value={users.length} color="blue" />
          <StatCard
            icon={<FileText className="w-5 h-5" />}
            label="Aktywne"
            value={tenants.filter(t => t.is_active).length}
            color="green"
          />
          <StatCard
            icon={<TrendingUp className="w-5 h-5" />}
            label="Zablokowane"
            value={tenants.filter(t => t.is_blocked).length}
            color="red"
          />
        </div>

        {/* Profiles list */}
        <div className="bg-white rounded-xl border shadow-sm">
          <div className="px-5 py-4 border-b flex justify-between items-center">
            <h2 className="font-semibold text-gray-900">Profile chatbotów</h2>
            {isSuperadmin && (
              <Link
                href="/admin/tenants/new"
                className="bg-indigo-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-indigo-700 transition-colors"
              >
                + Nowy profil
              </Link>
            )}
          </div>
          <div className="divide-y">
            {tenants.map(tenant => (
              <div key={tenant.id} className="px-5 py-4 flex items-center justify-between hover:bg-gray-50">
                <div className="flex items-center gap-3">
                  <div
                    className="w-8 h-8 rounded-lg flex-shrink-0"
                    style={{ backgroundColor: tenant.chat_color }}
                  />
                  <div>
                    <p className="font-medium text-gray-900">{tenant.name}</p>
                    <p className="text-xs text-gray-400 font-mono">/{tenant.slug}</p>
                  </div>
                </div>
                <div className="flex items-center gap-2 flex-wrap justify-end">
                  <span className={`text-xs px-2 py-0.5 rounded-full ${
                    tenant.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'
                  }`}>
                    {tenant.is_active ? 'Aktywny' : 'Nieaktywny'}
                  </span>
                  <span className="text-xs px-2 py-0.5 rounded-full bg-gray-100 text-gray-600">
                    {tenant.llm_model}
                  </span>
                  <button
                    onClick={() => copyToClipboard(`${window.location.origin}/chat/${tenant.id}`)}
                    className="text-gray-400 hover:text-indigo-600 transition-colors"
                    title="Kopiuj link do czatu"
                  >
                    <Copy className="w-4 h-4" />
                  </button>
                  <Link href={`/admin/tenants/${tenant.id}`} className="text-indigo-600 text-sm hover:underline">
                    Edytuj
                  </Link>
                  <Link
                    href={`/chat/${tenant.id}`}
                    target="_blank"
                    className="text-gray-400 hover:text-indigo-600"
                  >
                    <ExternalLink className="w-4 h-4" />
                  </Link>
                </div>
              </div>
            ))}
            {tenants.length === 0 && (
              <div className="px-5 py-10 text-center text-gray-500 text-sm">
                {isSuperadmin
                  ? <>Brak profili. <Link href="/admin/tenants/new" className="text-indigo-600 hover:underline">Utwórz pierwszy profil.</Link></>
                  : 'Nie masz przypisanego profilu. Skontaktuj się z superadminem.'}
              </div>
            )}
          </div>
        </div>

        {/* Recent users */}
        {users.length > 0 && (
          <div className="bg-white rounded-xl border shadow-sm">
            <div className="px-5 py-4 border-b flex justify-between items-center">
              <h2 className="font-semibold text-gray-900">Użytkownicy</h2>
              <Link href="/admin/users" className="text-indigo-600 text-sm hover:underline">
                Zarządzaj →
              </Link>
            </div>
            <div className="divide-y">
              {users.slice(0, 5).map(u => (
                <div key={u.id} className="px-5 py-3 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-7 h-7 bg-indigo-100 rounded-full flex items-center justify-center text-indigo-700 text-xs font-semibold">
                      {u.email[0].toUpperCase()}
                    </div>
                    <div>
                      <p className="text-sm font-medium">{u.full_name || u.email}</p>
                      <p className="text-xs text-gray-400">{u.email}</p>
                    </div>
                  </div>
                  <RoleBadge role={u.role} />
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </AdminLayout>
  )
}

function StatCard({ icon, label, value, color }: {
  icon: React.ReactNode; label: string; value: number; color: string
}) {
  const colorClasses: Record<string, string> = {
    indigo: 'bg-indigo-50 text-indigo-600',
    blue: 'bg-blue-50 text-blue-600',
    green: 'bg-green-50 text-green-600',
    red: 'bg-red-50 text-red-600',
  }
  return (
    <div className="bg-white rounded-xl border shadow-sm p-4">
      <div className={`w-9 h-9 rounded-lg ${colorClasses[color]} flex items-center justify-center mb-3`}>
        {icon}
      </div>
      <p className="text-2xl font-bold text-gray-900">{value}</p>
      <p className="text-sm text-gray-500">{label}</p>
    </div>
  )
}

