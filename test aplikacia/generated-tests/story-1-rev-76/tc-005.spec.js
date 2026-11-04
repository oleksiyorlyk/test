// Generated for TC-005 / AC3
const { test, expect } = require('@playwright/test');
const { resetAppState, seedRegisteredUser, seedTasks } = require('../../tests/helpers/app-state');
const fixtures = require('../../test-data.json');

test("TC-005 | Both empty fields show the required-field message", async ({ page }) => {
  await resetAppState(page);
 await expect(page.getByTestId('login-tab')).toBeVisible();
 await page.getByTestId('login-tab').click();
 await expect(page.getByTestId('login-email')).toBeVisible();
 await expect(page.getByTestId('login-password')).toBeVisible();
 await page.getByTestId('login-submit').click();
 await expect(page.getByTestId('login-email-error')).toHaveText('This field is required');
 await expect(page.getByTestId('login-password-error')).toHaveText('This field is required');
 await expect(page.getByTestId('logout-button')).toBeHidden();
});
