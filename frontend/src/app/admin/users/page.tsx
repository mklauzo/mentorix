'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { getToken, getCachedUser, usersApi, AppUser } from '@/lib/api'
import Link from 'next/link'
import { Trash2, UserPlus, Lock } from 'lucide-react'
import AdminLayout from '@/components/admin/AdminLayout'
import { RoleBadge } from '@/components/admin/RoleBadge'
import { format } from 'date-fns'

export default function UsersPage() {
  const router = useRouter()
  const [users, setUsers] = useState<AppUser[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [roleFilter, setRoleFilter] = useState<string>('')
  const currentUser = getCachedUser()

  const fetchUsers = () => {
    const token = getToken()
    if (!token) { router.push('/admin/login'); return }
    setLoading(true)
    usersApi.list(token, roleFilter || undefined)
      .then(setUsers)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => { fetchUsers() }, [roleFilter]) // eslint-disable-line

  const handleDelete = async (user: AppUser) => {
    if (!confirm(`Usunąć użytkownika ${user.email}?`)) return
    const token = getToken()
    try {
      await usersApi.delete(token!, user.id)
      setUsers(prev => prev.filter(u => u.id !== user.id))
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : 'Błąd usuwania')
    }
  }

  const canDelete = (target: AppUser) => {
    if (!currentUser) return false
    if (target.id === currentUser.id) return false
    if (currentUser.role === 'superadmin') return true
    if (currentUser.role === 'admin' && target.role === 'user') return true
    return false
  }

  return (
    <AdminLayout title="Użytkownicy">
      <div className="max-w-5xl mx-auto space-y-5">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold text-gray-900">Użytkownicy</h1>
          <Link
            href="/admin/users/new"
            className="flex items-center gap-2 bg-indigo-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-indigo-700 transition-colors"
          >
            <UserPlus className="w-4 h-4" />
            Dodaj użytkownika
          </Link>
        </div>

        {/* Filters */}
        <div className="flex gap-2">
          {['', 'superadmin', 'admin', 'user'].map(r => (
            <button
              key={r}
              onClick={() => setRoleFilter(r)}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                roleFilter === r
                  ? 'bg-indigo-600 text-white'
                  : 'bg-white border text-gray-600 hover:bg-gray-50'
              }`}
            >
              {r === '' ? 'Wszyscy' : r === 'superadmin' ? 'Super Admin' : r === 'admin' ? 'Admin' : 'Użytkownicy'}
            </button>
          ))}
        </div>

        {error && <p className="text-red-600 text-sm">{error}</p>}

        <div className="bg-white rounded-xl border shadow-sm overflow-hidden">
          {loading ? (
            <div className="p-8 text-center text-gray-400">Ładowanie...</div>
          ) : (
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b">
                <tr>
                  <th className="text-left px-5 py-3 font-medium text-gray-600">Użytkownik</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Rola</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600 hidden md:table-cell">Profil</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600 hidden lg:table-cell">Dołączył</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Status</th>
                  <th className="px-4 py-3"></th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {users.map(u => (
                  <tr key={u.id} className="hover:bg-gray-50">
                    <td className="px-5 py-3">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 bg-indigo-100 rounded-full flex items-center justify-center text-indigo-700 text-xs font-semibold flex-shrink-0">
                          {u.email[0].toUpperCase()}
                        </div>
                        <div>
                          <p className="font-medium text-gray-900">
                            {u.full_name || u.email}
                          </p>
                          <p className="text-xs text-gray-400">{u.email}</p>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <RoleBadge role={u.role} />
                    </td>
                    <td className="px-4 py-3 hidden md:table-cell text-gray-500 text-xs font-mono">
                      {u.tenant_id ? u.tenant_id.substring(0, 8) + '…' : '—'}
                    </td>
                    <td className="px-4 py-3 hidden lg:table-cell text-gray-500">
                      {format(new Date(u.created_at), 'dd.MM.yyyy')}
                    </td>
                    <td className="px-4 py-3">
                      <span className={`text-xs px-2 py-0.5 rounded-full ${
                        u.is_active ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-600'
                      }`}>
                        {u.is_active ? 'Aktywny' : 'Zablokowany'}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2 justify-end">
                        {canDelete(u) && (
                          <button
                            onClick={() => handleDelete(u)}
                            className="text-red-400 hover:text-red-600 transition-colors"
                            title="Usuń użytkownika"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        )}
                        {!canDelete(u) && u.id !== currentUser?.id && (
                          <span title="Brak uprawnień">
                            <Lock className="w-4 h-4 text-gray-300" />
                          </span>
                        )}
                        {u.id === currentUser?.id && (
                          <span className="text-xs text-gray-400">Ty</span>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
                {users.length === 0 && (
                  <tr>
                    <td colSpan={6} className="px-5 py-10 text-center text-gray-500">
                      Brak użytkowników.{' '}
                      <Link href="/admin/users/new" className="text-indigo-600 hover:underline">
                        Dodaj pierwszego.
                      </Link>
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          )}
        </div>

        <p className="text-xs text-gray-400">
          Łącznie: {users.length} użytkownik{users.length === 1 ? '' : 'ów'}
        </p>
      </div>
    </AdminLayout>
  )
}
