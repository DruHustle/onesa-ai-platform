import { expect, test } from '@playwright/test';

const id = '765fd0f2-9f1b-48a6-bf1e-b5887b871458';
const user = { id, email: 'native@example.invalid', display_name: 'Native fixture' };
const pending = { request_id: id, app_name: 'Onesa AI Platform', platform: 'ios', expires_at: '2099-01-01T00:00:00Z', status: 'pending', user };

test.beforeEach(async ({ page, baseURL }) => {
  if (!baseURL || !['localhost', '127.0.0.1', '[::1]'].includes(new URL(baseURL).hostname)) throw new Error('Native consent fixture requires loopback.');
  await page.route('**/api/v1/**', route => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/api/v1/auth/onesa/config') return route.fulfill({ json: { enabled: true, account_url: 'https://onesa.eu/account' } });
    if (path === `/api/v1/auth/native/requests/${id}`) return route.fulfill({ json: pending });
    if (path === '/api/v1/auth/me') return route.fulfill({ json: user });
    return route.fulfill({ status: 404, json: { error: { code: 'fixture_route_unavailable', message: 'Fixture route unavailable' } } });
  });
});

test('native consent displays the bound account and waits for explicit approval', async ({ page }) => {
  let approvals = 0;
  await page.route(`**/api/v1/auth/native/requests/${id}/approve`, route => { approvals++; return route.fulfill({ status: 503, json: { error: { code: 'unavailable', message: 'Fixture unavailable' } } }); });
  await page.goto(`/auth/native?request=${id}`);
  await expect(page.getByText(user.email, { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Approve and return to app' })).toBeEnabled();
  expect(approvals).toBe(0);
  await page.getByRole('button', { name: 'Approve and return to app' }).click();
  await expect(page.getByRole('main').getByRole('alert')).toContainText('Approval could not be confirmed');
  await expect(page.getByRole('button', { name: 'Approve and return to app' })).toBeDisabled();
  expect(approvals).toBe(1);
});

test('a foreign return URL cannot receive the authorization code', async ({ page }) => {
  await page.route(`**/api/v1/auth/native/requests/${id}/approve`, route => route.fulfill({ json: { redirect_url: 'https://example.invalid/steal?code=synthetic' } }));
  await page.goto(`/auth/native?request=${id}`);
  await page.getByRole('button', { name: 'Approve and return to app' }).click();
  await expect(page.getByRole('main').getByRole('alert')).toContainText('Approval could not be confirmed');
  expect(new URL(page.url()).pathname).toBe('/auth/native');
  await expect(page.getByRole('link', { name: 'Return to Onesa AI Platform' })).toHaveCount(0);
});

test('invalid or expired requests never offer approval', async ({ page }) => {
  await page.goto('/auth/native?request=invalid');
  await expect(page.getByRole('main').getByRole('alert')).toContainText('Open sign-in from the installed');
  await expect(page.getByRole('button', { name: 'Approve and return to app' })).toHaveCount(0);
  await page.route(`**/api/v1/auth/native/requests/${id}`, route => route.fulfill({ json: { ...pending, expires_at: '2000-01-01T00:00:00Z' } }));
  await page.goto(`/auth/native?request=${id}`);
  await expect(page.getByRole('main').getByRole('alert')).toContainText('unavailable or expired');
  await expect(page.getByRole('button', { name: 'Approve and return to app' })).toHaveCount(0);
});
