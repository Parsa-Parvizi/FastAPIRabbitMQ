import net from 'node:net'
import { test, expect } from '@playwright/test'

const isOpen = (port) =>
  new Promise((resolve) => {
    const socket = net.connect({ port, host: '127.0.0.1' })
    socket.setTimeout(1000)
    socket.once('connect', () => { socket.destroy(); resolve(true) })
    socket.once('error', () => resolve(false))
    socket.once('timeout', () => { socket.destroy(); resolve(false) })
  })

test('only the web port is published', async () => {
  expect(await isOpen(8080), 'web 8080 should be open').toBe(true)
  for (const port of [8000, 5672, 15672]) {
    expect(await isOpen(port), `port ${port} should be closed`).toBe(false)
  }
})