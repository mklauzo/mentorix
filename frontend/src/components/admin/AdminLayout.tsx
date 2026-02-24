'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import {
  LayoutDashboard, Users, MessageSquare, FileText,
  LogOut, ChevronRight, Menu, X, Settings, Layers
} from 'lucide-react'
import { clearToken, getToken, getCachedUser, setCachedUser, authApi, AuthUser } from '@/lib/api'

interface NavItem {
  href: string
  label: string
  icon: React.ReactNode
  roles?: Array<'superadmin' | 'admin' | 'user'>
}

const navItems: NavItem[] = [
  { href: '/admin', label: 'Dashboard', icon: <LayoutDashboard className="w-4 h-4" /> },
  {
    href: '/admin/profiles',
    label: 'Profile',
    icon: <Layers className="w-4 h-4" />,
    roles: ['superadmin'],
  },
  {
    href: '/admin/my-profile',
    label: 'Mój profil',
    icon: <Settings className="w-4 h-4" />,
    roles: ['admin', 'user'],
  },
  {
    href: '/admin/users',
    label: 'Użytkownicy',
    icon: <Users className="w-4 h-4" />,
    roles: ['superadmin', 'admin'],
  },
  {
    href: '/admin/conversations',
    label: 'Rozmowy',
    icon: <MessageSquare className="w-4 h-4" />,
  },
]

const ROLE_LABELS: Record<string, string> = {
  superadmin: 'Super Admin',
  admin: 'Admin',
  user: 'Użytkownik',
}

const ROLE_COLORS: Record<string, string> = {
  superadmin: 'bg-purple-100 text-purple-700',
  admin: 'bg-blue-100 text-blue-700',
  user: 'bg-gray-100 text-gray-600',
}

interface Props {
  children: React.ReactNode
  title?: string
}

export default function AdminLayout({ children, title }: Props) {
  const router = useRouter()
  const pathname = usePathname()
  const [user, setUser] = useState<AuthUser | null>(getCachedUser())
  const [sidebarOpen, setSidebarOpen] = useState(false)

  useEffect(() => {
    const token = getToken()
    if (!token) {
      router.push('/admin/login')
      return
    }
    // Refresh user from API if not cached
    if (!user) {
      authApi.me(token)
        .then(u => { setUser(u); setCachedUser(u) })
        .catch(() => { clearToken(); router.push('/admin/login') })
    }
  }, []) // eslint-disable-line

  const handleLogout = () => {
    clearToken()
    router.push('/admin/login')
  }

  const isActive = (href: string) =>
    href === '/admin' ? pathname === '/admin' : pathname.startsWith(href)

  const visibleNav = navItems.filter(item =>
    !item.roles || (user && item.roles.includes(user.role as 'superadmin' | 'admin' | 'user'))
  )

  const Sidebar = () => (
    <aside className="flex flex-col h-full bg-white border-r w-60">
      {/* Logo */}
      <div className="px-5 py-4 border-b">
        <Link href="/admin" className="flex items-center gap-2">
          <div className="w-7 h-7 bg-indigo-600 rounded-lg flex items-center justify-center text-white text-xs font-bold">M</div>
          <span className="font-semibold text-gray-900">Mentorix Admin</span>
        </Link>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
        {visibleNav.map(item => (
          <Link
            key={item.href}
            href={item.href}
            onClick={() => setSidebarOpen(false)}
            className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
              isActive(item.href)
                ? 'bg-indigo-50 text-indigo-700 font-medium'
                : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
            }`}
          >
            {item.icon}
            {item.label}
            {isActive(item.href) && <ChevronRight className="w-3 h-3 ml-auto" />}
          </Link>
        ))}
      </nav>

      {/* User info + logout */}
      {user && (
        <div className="border-t px-4 py-3">
          <div className="flex items-center gap-3 mb-2">
            <div className="w-8 h-8 bg-indigo-100 rounded-full flex items-center justify-center text-indigo-700 text-sm font-semibold">
              {user.email[0].toUpperCase()}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-gray-900 truncate">
                {user.full_name || user.email}
              </p>
              <span className={`text-xs px-1.5 py-0.5 rounded-full ${ROLE_COLORS[user.role]}`}>
                {ROLE_LABELS[user.role] || user.role}
              </span>
            </div>
          </div>
          <button
            onClick={handleLogout}
            className="flex items-center gap-2 text-xs text-gray-500 hover:text-red-600 transition-colors w-full"
          >
            <LogOut className="w-3.5 h-3.5" />
            Wyloguj się
          </button>
        </div>
      )}
    </aside>
  )

  return (
    <div className="flex h-screen bg-gray-50">
      {/* Desktop sidebar */}
      <div className="hidden md:flex flex-shrink-0">
        <Sidebar />
      </div>

      {/* Mobile sidebar overlay */}
      {sidebarOpen && (
        <div className="fixed inset-0 z-40 md:hidden">
          <div className="absolute inset-0 bg-black/30" onClick={() => setSidebarOpen(false)} />
          <div className="relative flex h-full w-60">
            <Sidebar />
          </div>
        </div>
      )}

      {/* Main content */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Top bar (mobile) */}
        <div className="md:hidden flex items-center gap-3 px-4 py-3 bg-white border-b">
          <button onClick={() => setSidebarOpen(true)} className="text-gray-600">
            <Menu className="w-5 h-5" />
          </button>
          <span className="font-medium text-sm">{title || 'Mentorix Admin'}</span>
        </div>

        {/* Page content */}
        <main className="flex-1 overflow-y-auto p-6">
          {children}
        </main>
      </div>
    </div>
  )
}
