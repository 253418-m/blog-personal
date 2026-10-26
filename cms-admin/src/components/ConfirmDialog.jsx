import { useEffect, useId, useRef } from 'react'

export function ConfirmDialog({ title, children, confirmLabel, danger = false, busy = false, onConfirm, onCancel }) {
  const titleId = useId()
  const cancelRef = useRef(null)

  useEffect(() => {
    const previous = document.activeElement
    cancelRef.current?.focus()
    return () => previous?.focus?.()
  }, [])

  function handleKeyDown(event) {
    if (event.key === 'Escape' && !busy) onCancel()
    if (event.key !== 'Tab') return
    const controls = [...event.currentTarget.querySelectorAll('button:not(:disabled)')]
    if (!controls.length) return
    if (event.shiftKey && document.activeElement === controls[0]) {
      event.preventDefault()
      controls.at(-1).focus()
    } else if (!event.shiftKey && document.activeElement === controls.at(-1)) {
      event.preventDefault()
      controls[0].focus()
    }
  }

  return (
    <div className="dialog-backdrop">
      <div className="confirm-dialog" role="dialog" aria-modal="true" aria-labelledby={titleId} onKeyDown={handleKeyDown}>
        <h2 id={titleId}>{title}</h2>
        <div className="dialog-copy">{children}</div>
        <div className="dialog-actions">
          <button ref={cancelRef} type="button" className="secondary-button" onClick={onCancel} disabled={busy}>Cancelar</button>
          <button type="button" className={danger ? 'danger-button' : 'primary-button'} onClick={onConfirm} disabled={busy}>
            {busy ? 'Procesando…' : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  )
}
