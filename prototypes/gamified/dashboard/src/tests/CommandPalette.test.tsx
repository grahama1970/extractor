import { render, screen, fireEvent } from '@testing-library/react'
import { CommandPalette } from '../components/CommandPalette'
import React from 'react'

test('command palette renders actions and runs selection', () => {
  const ran: string[] = []
  const items = [
    { id: 'a', label: 'Filter: Errors', onSelect: () => ran.push('a') },
    { id: 'b', label: 'Filter: Variant mul_*', onSelect: () => ran.push('b') }
  ]
  render(<CommandPalette open={true} onOpenChange={() => {}} items={items} />)
  fireEvent.click(screen.getByText('Filter: Errors'))
  expect(ran).toContain('a')
})
