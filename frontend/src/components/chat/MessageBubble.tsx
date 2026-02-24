import { ChatMessage } from '@/lib/api'

interface Props {
  message: ChatMessage
  chatColor: string
  isWelcome?: boolean
}

export default function MessageBubble({ message, chatColor, isWelcome }: Props) {
  const isAssistant = message.role === 'assistant'

  return (
    <div className={`flex ${isAssistant ? 'justify-start' : 'justify-end'}`}>
      <div
        className={`max-w-[80%] px-4 py-2 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap break-words ${
          isAssistant
            ? 'bg-gray-100 text-gray-800 rounded-tl-sm'
            : 'text-white rounded-tr-sm'
        }`}
        style={!isAssistant ? { backgroundColor: chatColor } : undefined}
      >
        {message.content}
      </div>
    </div>
  )
}
