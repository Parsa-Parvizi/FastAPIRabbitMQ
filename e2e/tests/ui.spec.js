import { test, expect } from '@playwright/test'

test('create a task from the UI and watch it become done', async ({ page }) => {
  const name = `ui-${Date.now()}`
  await page.goto('/')
  await expect(page.locator('strong')).toHaveText('connected')

  await page.getByPlaceholder('task name').fill(name)
  await page.getByRole('button', { name: 'Send' }).click()

  const row = page.getByRole('row', { name: new RegExp(name) })
  await expect(row).toBeVisible()
  await expect(row).toContainText('done', { timeout: 15_000 })
})