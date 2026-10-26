export function Feedback({ tone = 'info', children }) {
  if (!children) return null
  return <p className={`feedback feedback-${tone}`} role={tone === 'error' ? 'alert' : 'status'}>{children}</p>
}
