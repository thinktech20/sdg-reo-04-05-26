import { test, expect } from '@playwright/test'

test.describe('Homepage', () => {
  test('should load the homepage', async ({ page }) => {
    await page.goto('/')
    
    // Check for main heading
    await expect(page.getByRole('heading', { name: /Services Demand Generation/i })).toBeVisible()
  })

  test('should have functional theme toggle', async ({ page }) => {
    await page.goto('/')
    
    // Find and click the theme toggle button (aria-label switches between modes)
    const themeToggle = page.getByRole('button', { name: /Switch to (light|dark) mode/i })
    await expect(themeToggle).toBeVisible()
    
    // Click to toggle theme
    await themeToggle.click()
    
    // Theme should persist on reload
    await page.reload()
    await expect(page.getByRole('button', { name: /Switch to (light|dark) mode/i })).toBeVisible()
  })

  test('should have navigation menu', async ({ page }) => {
    await page.goto('/')
    
    // Check for navigation card items on the home page
    await expect(page.getByText(/Units/i).first()).toBeVisible()
    await expect(page.getByText(/Assessments/i).first()).toBeVisible()
  })

  test('should be responsive', async ({ page }) => {
    // Test desktop view
    await page.setViewportSize({ width: 1920, height: 1080 })
    await page.goto('/')
    await expect(page.getByRole('heading', { name: /Services Demand Generation/i })).toBeVisible()
    
    // Test mobile view
    await page.setViewportSize({ width: 375, height: 667 })
    await expect(page.getByRole('heading', { name: /Services Demand Generation/i })).toBeVisible()
  })
})
