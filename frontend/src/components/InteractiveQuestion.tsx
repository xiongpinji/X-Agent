/**
 * InteractiveQuestion Component
 *
 * Displays interactive questions during agent execution and handles user responses.
 * Supports multiple question types: single choice, multiple choice, text input, confirmation.
 */

import React, { useEffect, useState } from 'react';

interface QuestionOption {
  value: string;
  label: string;
  description?: string;
}

interface InteractiveQuestion {
  question_id: string;
  run_id: string;
  type: 'single_choice' | 'multiple_choice' | 'text_input' | 'confirmation' | 'file_selection' | 'code_review';
  title: string;
  description: string;
  context: Record<string, any>;
  options: QuestionOption[];
  allow_multiple: boolean;
  placeholder: string;
  validation_pattern?: string;
  min_length?: number;
  max_length?: number;
  created_at: string;
  timeout_seconds?: number;
  expires_at?: string;
  status: 'pending' | 'answered' | 'timeout' | 'cancelled';
  answer?: any;
  answered_at?: string;
  priority: string;
  blocking: boolean;
  default_answer?: any;
  tags: string[];
}

interface InteractiveQuestionProps {
  question: InteractiveQuestion;
  onAnswer: (answer: any) => Promise<void>;
  onTimeout?: () => void;
  onCancel?: () => void;
}

export const InteractiveQuestion: React.FC<InteractiveQuestionProps> = ({
  question,
  onAnswer,
  onTimeout,
  onCancel,
}) => {
  const [answer, setAnswer] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [timeRemaining, setTimeRemaining] = useState<number | null>(null);

  // Handle timeout countdown
  useEffect(() => {
    if (!question.expires_at || question.status !== 'pending') return;

    const updateCountdown = () => {
      const now = new Date();
      const expires = new Date(question.expires_at!);
      const remaining = Math.max(0, Math.floor((expires.getTime() - now.getTime()) / 1000));

      setTimeRemaining(remaining);

      if (remaining === 0) {
        onTimeout?.();
      }
    };

    updateCountdown();
    const interval = setInterval(updateCountdown, 1000);

    return () => clearInterval(interval);
  }, [question.expires_at, question.status, onTimeout]);

  const handleSubmit = async () => {
    try {
      setError(null);
      setLoading(true);

      // Validate answer
      if (!validateAnswer(answer)) {
        setError('Invalid answer');
        return;
      }

      await onAnswer(answer);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to submit answer');
    } finally {
      setLoading(false);
    }
  };

  const validateAnswer = (value: any): boolean => {
    switch (question.type) {
      case 'confirmation':
        return typeof value === 'boolean';

      case 'single_choice':
        if (!question.options.length) return true;
        return question.options.some((opt) => opt.value === value);

      case 'multiple_choice': {
        if (!Array.isArray(value)) return false;
        if (!question.options.length) return true;
        const validValues = new Set(question.options.map((opt) => opt.value));
        return value.every((v) => validValues.has(v));
      }

      case 'text_input':
        if (typeof value !== 'string') return false;
        if (question.min_length && value.length < question.min_length) return false;
        if (question.max_length && value.length > question.max_length) return false;
        if (question.validation_pattern) {
          const regex = new RegExp(question.validation_pattern);
          return regex.test(value);
        }
        return true;

      default:
        return true;
    }
  };

  const isAnswered = question.status !== 'pending';
  const priorityColor =
    question.priority === 'critical'
      ? 'border-red-500 bg-red-50'
      : question.priority === 'high'
        ? 'border-orange-500 bg-orange-50'
        : 'border-blue-500 bg-blue-50';

  return (
    <div className={`p-4 border-l-4 rounded-lg ${priorityColor}`}>
      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex-1">
          <h3 className="font-bold text-gray-900 mb-1">{question.title}</h3>
          {question.description && (
            <p className="text-sm text-gray-700 mb-2">{question.description}</p>
          )}
        </div>
        {timeRemaining !== null && question.status === 'pending' && (
          <div className={`text-xs font-semibold px-2 py-1 rounded ${
            timeRemaining < 30 ? 'bg-red-200 text-red-800' : 'bg-gray-200 text-gray-800'
          }`}>
            {timeRemaining}s
          </div>
        )}
      </div>

      {/* Context */}
      {Object.keys(question.context).length > 0 && (
        <div className="mb-3 p-2 bg-white rounded text-xs text-gray-600 max-h-32 overflow-y-auto">
          <pre>{JSON.stringify(question.context, null, 2)}</pre>
        </div>
      )}

      {/* Question Content */}
      {isAnswered ? (
        <div className="p-3 bg-white rounded border border-gray-200">
          <div className="text-xs text-gray-600 mb-1">Your answer:</div>
          <div className="font-mono text-sm text-gray-900">
            {typeof question.answer === 'object'
              ? JSON.stringify(question.answer, null, 2)
              : String(question.answer)}
          </div>
          {question.answered_at && (
            <div className="text-xs text-gray-500 mt-2">
              Answered at {new Date(question.answered_at).toLocaleTimeString()}
            </div>
          )}
        </div>
      ) : (
        <>
          {/* Single Choice */}
          {question.type === 'single_choice' && (
            <div className="space-y-2 mb-3">
              {question.options.map((option) => (
                <label key={option.value} className="flex items-start gap-3 p-2 hover:bg-white rounded cursor-pointer">
                  <input
                    type="radio"
                    name={question.question_id}
                    value={option.value}
                    checked={answer === option.value}
                    onChange={(e) => setAnswer(e.target.value)}
                    disabled={loading}
                    className="mt-1"
                  />
                  <div>
                    <div className="font-medium text-gray-900">{option.label}</div>
                    {option.description && (
                      <div className="text-xs text-gray-600">{option.description}</div>
                    )}
                  </div>
                </label>
              ))}
            </div>
          )}

          {/* Multiple Choice */}
          {question.type === 'multiple_choice' && (
            <div className="space-y-2 mb-3">
              {question.options.map((option) => (
                <label key={option.value} className="flex items-start gap-3 p-2 hover:bg-white rounded cursor-pointer">
                  <input
                    type="checkbox"
                    value={option.value}
                    checked={Array.isArray(answer) && answer.includes(option.value)}
                    onChange={(e) => {
                      const current = Array.isArray(answer) ? answer : [];
                      if (e.target.checked) {
                        setAnswer([...current, option.value]);
                      } else {
                        setAnswer(current.filter((v) => v !== option.value));
                      }
                    }}
                    disabled={loading}
                    className="mt-1"
                  />
                  <div>
                    <div className="font-medium text-gray-900">{option.label}</div>
                    {option.description && (
                      <div className="text-xs text-gray-600">{option.description}</div>
                    )}
                  </div>
                </label>
              ))}
            </div>
          )}

          {/* Text Input */}
          {question.type === 'text_input' && (
            <div className="mb-3">
              <textarea
                value={answer || ''}
                onChange={(e) => setAnswer(e.target.value)}
                placeholder={question.placeholder}
                disabled={loading}
                maxLength={question.max_length}
                className="w-full p-2 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                rows={3}
              />
              {question.max_length && (
                <div className="text-xs text-gray-600 mt-1">
                  {(answer || '').length} / {question.max_length}
                </div>
              )}
            </div>
          )}

          {/* Confirmation */}
          {question.type === 'confirmation' && (
            <div className="flex gap-3 mb-3">
              <button
                onClick={() => setAnswer(true)}
                disabled={loading}
                className={`flex-1 px-4 py-2 rounded font-medium transition-colors ${
                  answer === true
                    ? 'bg-green-500 text-white'
                    : 'bg-gray-200 text-gray-900 hover:bg-gray-300'
                }`}
              >
                ✓ Yes
              </button>
              <button
                onClick={() => setAnswer(false)}
                disabled={loading}
                className={`flex-1 px-4 py-2 rounded font-medium transition-colors ${
                  answer === false
                    ? 'bg-red-500 text-white'
                    : 'bg-gray-200 text-gray-900 hover:bg-gray-300'
                }`}
              >
                ✗ No
              </button>
            </div>
          )}

          {/* Error */}
          {error && (
            <div className="mb-3 p-2 bg-red-100 border border-red-300 rounded text-sm text-red-700">
              {error}
            </div>
          )}

          {/* Actions */}
          <div className="flex gap-2">
            <button
              onClick={handleSubmit}
              disabled={loading || answer === null}
              className="flex-1 px-4 py-2 bg-blue-500 text-white rounded font-medium hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? 'Submitting...' : 'Submit'}
            </button>
            {onCancel && (
              <button
                onClick={onCancel}
                disabled={loading}
                className="px-4 py-2 bg-gray-300 text-gray-900 rounded font-medium hover:bg-gray-400 disabled:opacity-50"
              >
                Cancel
              </button>
            )}
          </div>
        </>
      )}
    </div>
  );
};

interface InteractiveQuestionsProps {
  runId: string;
  onQuestionsUpdate?: (questions: InteractiveQuestion[]) => void;
}

export const InteractiveQuestions: React.FC<InteractiveQuestionsProps> = ({
  runId,
  onQuestionsUpdate,
}) => {
  const [questions, setQuestions] = useState<InteractiveQuestion[]>([]);
  const [, setLoading] = useState(false);

  const fetchPendingQuestions = async () => {
    try {
      setLoading(true);
      const response = await fetch(`/api/v1/questions/pending?run_id=${runId}`);
      if (!response.ok) throw new Error('Failed to fetch questions');

      const data = await response.json();
      setQuestions(data.questions);
      onQuestionsUpdate?.(data.questions);
    } catch (e) {
      console.error('Failed to fetch questions:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPendingQuestions();
    const interval = setInterval(fetchPendingQuestions, 2000);
    return () => clearInterval(interval);
  }, [runId]);

  const handleAnswer = async (questionId: string, answer: any) => {
    try {
      const response = await fetch(`/api/v1/questions/${questionId}/answer`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ answer }),
      });

      if (!response.ok) throw new Error('Failed to submit answer');

      await fetchPendingQuestions();
    } catch (e) {
      console.error('Failed to submit answer:', e);
      throw e;
    }
  };

  const handleCancel = async (questionId: string) => {
    try {
      const response = await fetch(`/api/v1/questions/${questionId}/cancel`, {
        method: 'POST',
      });

      if (!response.ok) throw new Error('Failed to cancel question');

      await fetchPendingQuestions();
    } catch (e) {
      console.error('Failed to cancel question:', e);
    }
  };

  if (questions.length === 0) {
    return null;
  }

  return (
    <div className="space-y-3">
      {questions.map((question) => (
        <InteractiveQuestion
          key={question.question_id}
          question={question}
          onAnswer={(answer) => handleAnswer(question.question_id, answer)}
          onCancel={() => handleCancel(question.question_id)}
        />
      ))}
    </div>
  );
};

export default InteractiveQuestions;
