export function RoleBadge({ role }: { role: string }) {
  const classes: Record<string, string> = {
    superadmin: 'bg-purple-100 text-purple-700',
    admin: 'bg-blue-100 text-blue-700',
    user: 'bg-gray-100 text-gray-600',
  }
  const labels: Record<string, string> = {
    superadmin: 'Super Admin',
    admin: 'Admin',
    user: 'Użytkownik',
  }
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${classes[role] || 'bg-gray-100 text-gray-600'}`}>
      {labels[role] || role}
    </span>
  )
}
