'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { apiFetch, getToken, getCachedUser, usersApi, Tenant } from '@/lib/api'
import Link from 'next/link'
import AdminLayout from '@/components/admin/AdminLayout'

export default function NewUserPage() {
  const router = useRouter()
  const currentUser = getCachedUser()
  const isSuperadmin = currentUser?.role === 'superadmin'

  const [tenants, setTenants] = useState<Tenant[]>([])
  const [form, setForm] = useState({
    email: '',
    password: '',
    confirmPassword: '',
    role: 'user' as 'admin' | 'user',
    first_name: '',
    last_name: '',
    tenant_id: '',
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const token = getToken()
    if (!token) { router.push('/admin/login'); return }

    // Load tenants for superadmin assignment
    if (isSuperadmin) {
      apiFetch<Tenant[]>('/tenants', {}, token).then(setTenants).catch(() => {})
    } else {
      // Pre-set tenant to admin's own tenant
      if (currentUser?.tenant_id) {
        setForm(f => ({ ...f, tenant_id: currentUser.tenant_id! }))
      }
    }
  }, []) // eslint-disable-line

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)

    if (form.password !== form.confirmPassword) {
      setError('Hasła nie są identyczne')
      return
    }
    if (form.password.length < 8) {
      setError('Hasło musi mieć co najmniej 8 znaków')
      return
    }

    const token = getToken()
    setLoading(true)

    try {
      await usersApi.create(token!, {
        email: form.email,
        password: form.password,
        role: form.role,
        first_name: form.first_name || undefined,
        last_name: form.last_name || undefined,
        tenant_id: form.tenant_id || undefined,
      })
      router.push('/admin/users')
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Błąd tworzenia użytkownika')
    } finally {
      setLoading(false)
    }
  }

  const f = (field: keyof typeof form) => (
    e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>
  ) => setForm(p => ({ ...p, [field]: e.target.value }))

  return (
    <AdminLayout title="Nowy użytkownik">
      <div className="max-w-lg mx-auto space-y-5">
        <div className="flex items-center gap-3">
          <Link href="/admin/users" className="text-gray-400 hover:text-gray-600 text-sm">
            ← Użytkownicy
          </Link>
        </div>

        <h1 className="text-2xl font-bold text-gray-900">Nowy użytkownik</h1>

        <form onSubmit={handleSubmit} className="bg-white rounded-xl border shadow-sm p-6 space-y-5">
          {/* Name row */}
          <div className="grid grid-cols-2 gap-4">
            <Field label="Imię">
              <input
                type="text" value={form.first_name} onChange={f('first_name')}
                className="input" placeholder="Jan"
              />
            </Field>
            <Field label="Nazwisko">
              <input
                type="text" value={form.last_name} onChange={f('last_name')}
                className="input" placeholder="Kowalski"
              />
            </Field>
          </div>

          <Field label="Email" required>
            <input
              type="email" value={form.email} onChange={f('email')}
              className="input" required placeholder="jan@firma.pl"
            />
          </Field>

          <Field label="Hasło" required>
            <input
              type="password" value={form.password} onChange={f('password')}
              className="input" required placeholder="Minimum 8 znaków"
              minLength={8}
            />
          </Field>

          <Field label="Potwierdź hasło" required>
            <input
              type="password" value={form.confirmPassword} onChange={f('confirmPassword')}
              className="input" required placeholder="Powtórz hasło"
            />
          </Field>

          <Field label="Rola" required>
            <select value={form.role} onChange={f('role')} className="input">
              <option value="user">Użytkownik (read-only)</option>
              <option value="admin">Admin (zarządza profilem)</option>
              {isSuperadmin && <option value="superadmin">Super Admin</option>}
            </select>
            <p className="text-xs text-gray-400 mt-1">
              {form.role === 'user'
                ? 'Może przeglądać rozmowy i dokumenty swojego profilu.'
                : form.role === 'admin'
                ? 'Może edytować ustawienia profilu, dodawać dokumenty i zarządzać użytkownikami.'
                : 'Pełny dostęp do całej platformy.'}
            </p>
          </Field>

          {/* Tenant assignment (superadmin only) */}
          {isSuperadmin && (
            <Field label="Przypisz do profilu">
              <select value={form.tenant_id} onChange={f('tenant_id')} className="input">
                <option value="">— brak przypisania —</option>
                {tenants.map(t => (
                  <option key={t.id} value={t.id}>{t.name} (/{t.slug})</option>
                ))}
              </select>
            </Field>
          )}

          {error && (
            <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-red-700 text-sm">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-indigo-600 text-white rounded-lg py-2.5 font-medium hover:bg-indigo-700 disabled:opacity-50 transition-colors"
          >
            {loading ? 'Tworzę...' : 'Utwórz użytkownika'}
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
      `}</style>
    </AdminLayout>
  )
}

function Field({ label, required, children }: {
  label: string; required?: boolean; children: React.ReactNode
}) {
  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1">
        {label}{required && <span className="text-red-500 ml-0.5">*</span>}
      </label>
      {children}
    </div>
  )
}
