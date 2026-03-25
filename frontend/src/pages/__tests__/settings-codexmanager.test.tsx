import React from 'react'
import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import Settings from '../Settings'

vi.mock('@/lib/utils', async (orig) => {
  const mod = await orig()
  return { ...mod, apiFetch: vi.fn(async () => ({})) }
})

describe('CodexManager settings controls', () => {
  it('renders a toggle for auto-fill switch', async () => {
    render(<Settings />)
    fireEvent.click(await screen.findByRole('button', { name: 'ChatGPT' }))
    expect(await screen.findByText('自动补号开关')).toBeInTheDocument()
    const toggle = screen.getByRole('switch', { name: '自动补号开关' })
    // aria-checked should exist once switch is implemented
    expect(toggle).toHaveAttribute('aria-checked')
  })

  it('hides advanced settings by default and shows after expand', async () => {
    render(<Settings />)
    fireEvent.click(await screen.findByRole('button', { name: 'ChatGPT' }))
    const advancedButton = await screen.findByRole('button', { name: '高级设置' })
    expect(screen.queryByText('封禁过滤值')).toBeNull()
    fireEvent.click(advancedButton)
    expect(await screen.findByText('封禁过滤值')).toBeInTheDocument()
  })

  it('renders number inputs for interval and thresholds', async () => {
    render(<Settings />)
    fireEvent.click(await screen.findByRole('button', { name: 'ChatGPT' }))

    const interval = await screen.findByLabelText('补号检查间隔(秒)')
    expect(interval).toHaveAttribute('type', 'number')
    expect(interval).toHaveAttribute('min', '60')
    expect(interval).toHaveAttribute('step', '60')

    const minAvailable = await screen.findByLabelText('最低可用账号数')
    expect(minAvailable).toHaveAttribute('type', 'number')
    expect(minAvailable).toHaveAttribute('min', '1')
  })

  it('shows a run-now button', async () => {
    render(<Settings />)
    fireEvent.click(await screen.findByRole('button', { name: 'ChatGPT' }))
    expect(await screen.findByRole('button', { name: '立即检查' })).toBeInTheDocument()
  })
})
