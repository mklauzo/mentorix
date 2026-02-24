import Link from 'next/link'

export default function HomePage() {
  return (
    <main className="min-h-screen flex items-center justify-center">
      <div className="text-center">
        <h1 className="text-4xl font-bold mb-4">Mentorix AI</h1>
        <p className="text-gray-600 mb-8">AI Knowledge Base Assistant</p>
        <Link
          href="/admin"
          className="bg-indigo-600 text-white px-6 py-3 rounded-lg hover:bg-indigo-700 transition-colors"
        >
          Admin Panel
        </Link>
      </div>
    </main>
  )
}
