'use client'

import { Suspense } from 'react'
import { useEffect, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { apiFetch, getToken, getCachedUser, Document as MDocument } from '@/lib/api'
import { Upload, Trash2, RefreshCw } from 'lucide-react'
import { format } from 'date-fns'
import AdminLayout from '@/components/admin/AdminLayout'

const STATUS_CONFIG: Record<string, { label: string; classes: string }> = {
  pending: { label: 'Oczekuje', classes: 'bg-yellow-100 text-yellow-700' },
  processing: { label: 'Przetwarza', classes: 'bg-blue-100 text-blue-700' },
  done: { label: 'Gotowy', classes: 'bg-green-100 text-green-700' },
  error: { label: 'Błąd', classes: 'bg-red-100 text-red-700' },
}

export default function DocumentsPage() {
  return (
    <Suspense fallback={<div className="p-8 text-center text-gray-400">Ładowanie...</div>}>
      <DocumentsContent />
    </Suspense>
  )
}

function DocumentsContent() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const currentUser = getCachedUser()

  // Use tenant from query param OR from user's own tenant
  const [tenantId, setTenantId] = useState<string | null>(
    searchParams.get('tenant_id') || currentUser?.tenant_id || null
  )
  const [documents, setDocuments] = useState<MDocument[]>([])
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchDocuments = () => {
    if (!tenantId) return
    const token = getToken()
    setLoading(true)
    apiFetch<{ items: MDocument[]; total: number }>(
      `/documents?tenant_id=${tenantId}`, {}, token || undefined
    )
      .then(res => setDocuments(res.items))
      .catch(e => setError(e.message || 'Błąd ładowania'))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    const token = getToken()
    if (!token) { router.push('/admin/login'); return }
    if (!tenantId) { router.push('/admin'); return }
    fetchDocuments()
  }, [tenantId]) // eslint-disable-line

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file || !tenantId) return

    setUploading(true)
    setError(null)
    const token = getToken()
    const formData = new FormData()
    formData.append('file', file)

    try {
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/documents/upload?tenant_id=${tenantId}`,
        {
          method: 'POST',
          headers: { Authorization: `Bearer ${token}` },
          body: formData,
        }
      )
      if (!res.ok) throw new Error('Błąd przesyłania')
      fetchDocuments()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Błąd przesyłania')
    } finally {
      setUploading(false)
      e.target.value = ''
    }
  }

  const handleDelete = async (docId: string) => {
    if (!confirm('Usunąć dokument i wszystkie jego chunki?')) return
    const token = getToken()
    try {
      await apiFetch(`/documents/${docId}?tenant_id=${tenantId}`, { method: 'DELETE' }, token || undefined)
      setDocuments(prev => prev.filter(d => d.id !== docId))
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Błąd usuwania')
    }
  }

  return (
    <AdminLayout title="Dokumenty">
      <div className="max-w-5xl mx-auto space-y-5">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold text-gray-900">Dokumenty</h1>
          <div className="flex items-center gap-2">
            <button
              onClick={fetchDocuments}
              className="p-2 border rounded-lg hover:bg-gray-50 text-gray-500"
              title="Odśwież"
            >
              <RefreshCw className="w-4 h-4" />
            </button>
            <label className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium cursor-pointer transition-colors ${
              uploading
                ? 'bg-gray-200 text-gray-500 cursor-not-allowed'
                : 'bg-indigo-600 text-white hover:bg-indigo-700'
            }`}>
              <Upload className="w-4 h-4" />
              {uploading ? 'Przesyłam...' : 'Wgraj plik'}
              <input
                type="file"
                className="hidden"
                accept=".pdf,.docx,.txt,.md,.html,.htm"
                onChange={handleUpload}
                disabled={uploading}
              />
            </label>
          </div>
        </div>

        <p className="text-sm text-gray-500">
          Obsługiwane formaty: PDF, DOCX, TXT, MD, HTML · Maks. 25 MB
        </p>

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-red-700 text-sm">
            {error}
          </div>
        )}

        <div className="bg-white rounded-xl border shadow-sm overflow-hidden">
          {loading ? (
            <div className="p-8 text-center text-gray-400">Ładowanie...</div>
          ) : (
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b">
                <tr>
                  <th className="text-left px-5 py-3 font-medium text-gray-600">Dokument</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Status</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600 hidden md:table-cell">Chunki</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600 hidden lg:table-cell">Rozmiar</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600 hidden lg:table-cell">Data</th>
                  <th className="px-4 py-3"></th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {documents.map(doc => {
                  const status = STATUS_CONFIG[doc.status] || { label: doc.status, classes: 'bg-gray-100 text-gray-600' }
                  return (
                    <tr key={doc.id} className="hover:bg-gray-50">
                      <td className="px-5 py-3">
                        <p className="font-medium text-gray-900 truncate max-w-xs">{doc.name}</p>
                        <p className="text-xs text-gray-400">{doc.mime_type}</p>
                        {doc.error_message && (
                          <p className="text-xs text-red-500 mt-0.5">{doc.error_message}</p>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${status.classes}`}>
                          {status.label}
                        </span>
                      </td>
                      <td className="px-4 py-3 hidden md:table-cell text-gray-600">{doc.chunk_count}</td>
                      <td className="px-4 py-3 hidden lg:table-cell text-gray-500">
                        {doc.size_bytes ? `${(doc.size_bytes / 1024).toFixed(1)} KB` : '—'}
                      </td>
                      <td className="px-4 py-3 hidden lg:table-cell text-gray-500">
                        {format(new Date(doc.created_at), 'dd.MM.yyyy')}
                      </td>
                      <td className="px-4 py-3">
                        <button
                          onClick={() => handleDelete(doc.id)}
                          className="text-red-400 hover:text-red-600 transition-colors"
                          title="Usuń dokument"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </td>
                    </tr>
                  )
                })}
                {documents.length === 0 && (
                  <tr>
                    <td colSpan={6} className="px-5 py-12 text-center text-gray-500">
                      Brak dokumentów. Wgraj plik PDF, DOCX, TXT, MD lub HTML.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </AdminLayout>
  )
}
