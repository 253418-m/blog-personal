import { afterEach, describe, expect, it } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { HelpTooltip } from '../components/HelpTooltip'

afterEach(cleanup)

function showTooltip() {
  render(<form><div className="field-label-row"><label htmlFor="test-field">Título</label>
    <HelpTooltip text="Ayuda de prueba." /></div><input id="test-field" />
    <button type="submit">Guardar</button></form>)
  return screen.getByRole('button', { name: 'Mostrar ayuda' })
}

describe('HelpTooltip', () => {
  it('aparece al pasar el cursor y desaparece al retirarlo', async () => {
    const button = showTooltip()
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument()
    await userEvent.hover(button)
    expect(screen.getByRole('tooltip')).toHaveTextContent('Ayuda de prueba.')
    expect(button).toHaveAttribute('aria-describedby', screen.getByRole('tooltip').id)
    await userEvent.click(button)
    expect(screen.getByRole('tooltip')).toBeInTheDocument()
    await userEvent.unhover(button)
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument()
  })

  it('funciona al enfocar con teclado y cierra al perder foco', async () => {
    const button = showTooltip()
    await userEvent.tab()
    expect(button).toHaveFocus()
    expect(screen.getByRole('tooltip')).toBeInTheDocument()
    fireEvent.blur(button)
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument()
  })

  it('un toque abre, otro cierra y el botón nunca envía el formulario', () => {
    const button = showTooltip()
    expect(button).toHaveAttribute('type', 'button')
    fireEvent.pointerDown(button, { pointerType: 'touch' })
    fireEvent.focus(button)
    fireEvent.click(button, { detail: 1 })
    expect(screen.getByRole('tooltip')).toBeInTheDocument()
    fireEvent.pointerDown(button, { pointerType: 'touch' })
    fireEvent.click(button, { detail: 1 })
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument()
  })

  it('Enter y Space activan el botón; Escape cierra la ayuda', async () => {
    const button = showTooltip()
    await userEvent.tab()
    expect(button).toHaveFocus()
    expect(screen.getByRole('tooltip')).toBeInTheDocument()
    await userEvent.keyboard('{Escape}')
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument()
    await userEvent.keyboard('{Enter}')
    expect(screen.getByRole('tooltip')).toBeInTheDocument()
    await userEvent.keyboard(' ')
    expect(screen.getByRole('tooltip')).toBeInTheDocument()
  })
})
