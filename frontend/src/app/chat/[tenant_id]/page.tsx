'use client'

import { useParams } from 'next/navigation'
import ChatWindow from '@/components/chat/ChatWindow'

export default function ChatPage() {
  const params = useParams()
  const tenantId = params.tenant_id as string

  return (
    <div className="h-screen flex flex-col bg-white">
      <ChatWindow tenantId={tenantId} />
    </div>
  )
}
