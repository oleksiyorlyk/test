// Generated for TC-003 / AC3
const { test, expect } = require('@playwright/test');
const { resetAppState, seedRegisteredUser, seedTasks } = require('../../tests/helpers/app-state');
const fixtures = require('../../test-data.json');

test("TC-003 | Require the email when the email field is empty", async ({ page }) => {
  await resetAppState(page);
 await page.getByTestId('login-tab').click();
 await page.getByTestId('login-password').fill('AnyPassword!');
 await page.getByTestId('login-submit').click();
 await expect(page.getByTestId('login-email-error')).toHaveText('This field is required');
 await expect(page.getByTestId('login-submit')).toBeVisible();
});
