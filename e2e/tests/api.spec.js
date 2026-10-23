import { test, expect } from '@playwright/test'

test('health says RabbitMQ is connected', async ({ request }) => {
  const r = await request.get('/api/health')
  expect(r.ok()).toBeTruthy()
  expect(await r.json()).toEqual({ rabbitmq: true })
})

test('a task goes pending -> done through RabbitMQ and the consumer', async ({ request }) => {
  const created = await request.post('/api/tasks', {
    data: { name: `api-${Date.now()}`, payload: { a: 1 } },
  })
  expect(created.status()).toBe(202)
  const { id } = await created.json()

  await expect
    .poll(async () => (await (await request.get(`/api/tasks/${id}`)).json()).status, {
      timeout: 15_000,
    })
    .toBe('done')
})

test('unknown task is 404', async ({ request }) => {
  const r = await request.get('/api/tasks/999999')
  expect(r.status()).toBe(404)
})

test('invalid body is rejected with 422', async ({ request }) => {
  const r = await request.post('/api/tasks', { data: { payload: {} } })
  expect(r.status()).toBe(422)
})