import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import App from './App.vue'

const ok = (data) => ({ ok: true, status: 200, statusText: 'OK', json: async () => data })
const fail = (status = 500) => ({ ok: false, status, statusText: 'Server Error', json: async () => ({}) })

const TASKS = [
  { id: 2, name: 'second', status: 'pending' },
  { id: 1, name: 'first', status: 'done' },
]
const HEALTHY = {
  'GET /api/tasks': ok(TASKS),
  'GET /api/health': ok({ rabbitmq: true }),
}

// fetch جعلی: هر "METHOD /path" یه جواب ثابت می‌گیره
function mockApi(routes) {
  const fetchMock = vi.fn(async (url, options = {}) => {
    const key = `${options.method ?? 'GET'} ${url}`
    if (!(key in routes)) throw new Error(`unexpected request: ${key}`)
    return routes[key]
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

const countCalls = (fetchMock, key) =>
  fetchMock.mock.calls.filter(([url, o]) => `${o?.method ?? 'GET'} ${url}` === key).length

beforeEach(() => {
  // فقط interval جعلی می‌شه؛ اگه setImmediate هم جعلی بشه flushPromises گیر می‌کنه
  vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval'] })
})
afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

describe('App', () => {
  it('renders tasks and the connected status', async () => {
    mockApi(HEALTHY)
    const wrapper = mount(App)
    await flushPromises()

    const rows = wrapper.findAll('tbody tr')
    expect(rows).toHaveLength(2)
    expect(rows[0].text()).toContain('second')
    expect(wrapper.find('td.pending').text()).toBe('pending')
    expect(wrapper.find('td.done').text()).toBe('done')
    expect(wrapper.find('strong').text()).toBe('connected')
  })

  it('shows "down" and the error when the API fails', async () => {
    mockApi({ 'GET /api/tasks': fail(500), 'GET /api/health': fail(500) })
    const wrapper = mount(App)
    await flushPromises()

    expect(wrapper.find('strong').text()).toBe('down')
    expect(wrapper.find('p.bad').text()).toContain('500')
  })

  it('POSTs a new task, clears the input and reloads the list', async () => {
    const fetchMock = mockApi({ ...HEALTHY, 'POST /api/tasks': ok({ id: 3, status: 'pending' }) })
    const wrapper = mount(App)
    await flushPromises()

    await wrapper.find('input').setValue('hello')
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    const [, options] = fetchMock.mock.calls.find(([, o]) => o?.method === 'POST')
    expect(JSON.parse(options.body)).toEqual({ name: 'hello', payload: {} })
    expect(options.headers['Content-Type']).toBe('application/json')
    expect(wrapper.find('input').element.value).toBe('')
    expect(countCalls(fetchMock, 'GET /api/tasks')).toBe(2) // یکی موقع mount، یکی بعد از ساخت
  })

  it('does not send blank names', async () => {
    const fetchMock = mockApi(HEALTHY)
    const wrapper = mount(App)
    await flushPromises()

    await wrapper.find('input').setValue('   ')
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(fetchMock.mock.calls.some(([, o]) => o?.method === 'POST')).toBe(false)
  })

  it('polls every 2 seconds and stops after unmount', async () => {
    const fetchMock = mockApi(HEALTHY)
    const wrapper = mount(App)
    await flushPromises()
    expect(countCalls(fetchMock, 'GET /api/tasks')).toBe(1)

    vi.advanceTimersByTime(2000)
    await flushPromises()
    expect(countCalls(fetchMock, 'GET /api/tasks')).toBe(2)

    wrapper.unmount()
    vi.advanceTimersByTime(10_000)
    await flushPromises()
    expect(countCalls(fetchMock, 'GET /api/tasks')).toBe(2)
  })
})