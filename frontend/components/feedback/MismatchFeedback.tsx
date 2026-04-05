'use client'
import { useState } from 'react'
import { ThumbsUp, ThumbsDown, Pencil, Check } from 'lucide-react'
import { api } from '@/lib/api'

interface Props {
  mismatchId: number
  trainingExampleId?: number | null
}

/**
 * Thumbs-up / thumbs-down buttons for a mismatch card.
 * Calls POST /api/v1/training-examples/{id}/feedback when the user acts.
 * Only renders when trainingExampleId is present (populated by backend after P1-04 ships).
 */
export function MismatchFeedback({ mismatchId, trainingExampleId }: Props) {
  const [submitted, setSubmitted] = useState<'accept' | 'reject' | null>(null)
  const [loading, setLoading] = useState(false)

  // Don't render until the backend is capturing training examples
  if (!trainingExampleId) return null

  async function submit(source: 'accept' | 'reject') {
    if (submitted || loading) return
    setLoading(true)
    try {
      await api.post(`/training-examples/${trainingExampleId}/feedback`, {
        feedback_source: source,
      })
      setSubmitted(source)
    } catch {
      // Silent — feedback is best-effort, never block the user
    } finally {
      setLoading(false)
    }
  }

  if (submitted) {
    return (
      <span className="flex items-center gap-1 text-[11px] text-green-600">
        <Check className="w-3 h-3" />
        Feedback recorded
      </span>
    )
  }

  return (
    <div className="flex items-center gap-1">
      <span className="text-[10px] text-gray-400 mr-0.5">AI correct?</span>
      <button
        onClick={() => submit('accept')}
        disabled={loading}
        title="AI was correct"
        className="p-0.5 rounded hover:bg-green-50 text-gray-400 hover:text-green-600 transition-colors disabled:opacity-50"
      >
        <ThumbsUp className="w-3.5 h-3.5" />
      </button>
      <button
        onClick={() => submit('reject')}
        disabled={loading}
        title="AI was wrong"
        className="p-0.5 rounded hover:bg-red-50 text-gray-400 hover:text-red-600 transition-colors disabled:opacity-50"
      >
        <ThumbsDown className="w-3.5 h-3.5" />
      </button>
    </div>
  )
}
