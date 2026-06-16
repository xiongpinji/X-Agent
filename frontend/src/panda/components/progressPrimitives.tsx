import React from 'react'

export function ProgressMeter({ value, label, ariaLabel = '进度' }: { value: number; label?: React.ReactNode; ariaLabel?: string }) {
  const clampedValue = Math.min(100, Math.max(0, Math.round(value)))

  return (
    <>
      {label ? <div className="mb-2 flex justify-between text-xs text-slate-400">{label}</div> : null}
      <div
        className="panda-progress-track"
        role="progressbar"
        aria-label={ariaLabel}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={clampedValue}
        aria-valuetext={`${clampedValue}%`}
      >
        <div className="panda-progress-fill" style={{ width: `${clampedValue}%` }} />
      </div>
    </>
  )
}

export function ProgressSummary({ value, ariaLabel }: { value: number; ariaLabel?: string }) {
  return (
    <div className="mt-4">
      <ProgressMeter value={value} ariaLabel={ariaLabel} />
      <div className="mt-2 text-right text-xs text-slate-400">{Math.min(100, Math.max(0, Math.round(value)))}%</div>
    </div>
  )
}
