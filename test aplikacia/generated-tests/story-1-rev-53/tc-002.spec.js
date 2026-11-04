// Generated for TC-002 / AC2
const { test, expect } = require('@playwright/test');
const { resetAppState, seedRegisteredUser, seedTasks } = require('../../tests/helpers/app-state');
const fixtures = require('../../test-data.json');

test("TC-002 | Reject an incorrect password for a registered email", async ({ page }) => {
  await resetAppState(page);
 await seedRegisteredUser(page, fixtures.valid_user);
 await page.getByTestId('login-tab').click();
 await page.getByTestId('login-email').fill(fixtures.valid_user.email);
 await page.getByTestId('login-password').fill('IncorrectPassword!');
 await page.getByTestId('login-submit').click();
 await expect(page.getByTestId('login-global-error')).toHaveText('Invalid email or password');
 await expect(page.getByTestId('login-submit')).toBeVisible();
});
