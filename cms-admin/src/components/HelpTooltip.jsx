import { useId, useRef, useState } from 'react'

export function HelpTooltip({ text }) {
  const tooltipId = useId()
  const pointerType = useRef(null)
  const [hovered, setHovered] = useState(false)
  const [focused, setFocused] = useState(false)
  const [tapped, setTapped] = useState(false)
  const open = hovered || focused || tapped

  return <span className="help-tooltip">
    <button type="button" className="help-tooltip__trigger" aria-label="Mostrar ayuda"
      aria-expanded={open} aria-describedby={open ? tooltipId : undefined}
      onPointerEnter={(event) => { if (event.pointerType === 'mouse') setHovered(true) }}
      onPointerLeave={(event) => { if (event.pointerType === 'mouse') setHovered(false) }}
      onPointerDown={(event) => { pointerType.current = event.pointerType }}
      onFocus={() => { if (!pointerType.current) setFocused(true) }}
      onBlur={() => { pointerType.current = null; setFocused(false); setTapped(false) }}
      onClick={(event) => {
        if (event.detail === 0) setFocused(true)
        else if (pointerType.current === 'touch' || pointerType.current === 'pen') setTapped((current) => !current)
        pointerType.current = null
      }}
      onKeyDown={(event) => { if (event.key === 'Escape') { setFocused(false); setTapped(false) } }}
    >?</button>
    {open && <span id={tooltipId} className="help-tooltip__content" role="tooltip">{text}</span>}
  </span>
}
