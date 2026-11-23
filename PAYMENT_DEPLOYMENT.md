# Chapa payment deployment

The application now creates orders from database prices, initializes a hosted Chapa checkout, verifies the transaction from the server, and creates dispense jobs only after verification. The customer return URL and webhook are notifications; neither is accepted as proof of payment.

## Configure production

Set these variables in the deployment platform's secret/configuration store. Do not put live values in the frontend or commit them to `.env`:

```dotenv
ENVIRONMENT=production
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@DB_HOST:5432/DB_NAME
SECRET_KEY=<unique random secret, at least 32 characters>
CHAPA_SECRET_KEY=<live secret from the Chapa dashboard>
CHAPA_MODE=live
CHAPA_BASE_URL=https://api.chapa.co/v1
CHAPA_WEBHOOK_SECRET=<same random webhook secret configured in Chapa>
CHAPA_CALLBACK_URL=https://API_HOST/api/payments/chapa/callback
CHAPA_RETURN_URL=https://STORE_HOST/payment/result
FRONTEND_ORIGIN=https://STORE_HOST
```

The app rejects production startup with SQLite, a test-mode Chapa key, missing webhook configuration, short JWT/webhook secrets, or non-HTTPS public URLs. `CHAPA_CALLBACK_URL` is the backend callback route. In the Chapa dashboard, separately register `https://API_HOST/api/payments/chapa/webhook` and configure the matching webhook secret. The frontend build needs `VITE_API_BASE_URL=https://API_HOST` in `frontend/.env` (copy `frontend/.env.example`). Do not put backend secrets in that file.

Run the schema migration before starting the new application version:

```powershell
python -m alembic upgrade head
```

Use a test merchant key and `CHAPA_MODE=test` in development. Live mode is accepted only when `ENVIRONMENT=production`.

## Payment flow

1. The storefront loads online machines and their available products from `/api/machines/` and `/api/store/catalog`.
2. Checkout sends product and slot identifiers plus quantities. The server calculates prices and reserves inventory.
3. The backend persists a unique payment reference before initializing Chapa and returns only the hosted checkout URL.
4. After return, the storefront calls `/api/payments/chapa/verify` with the local order UUID. The backend calls Chapa's verify endpoint, checks reference, status, amount, currency, and mode, then fulfills idempotently.
5. The signed webhook at `/api/payments/chapa/webhook` independently verifies successful events through the same server-side path. Repeated events do not create duplicate dispense jobs.

Chapa instructs merchants to verify transactions server-side after redirect and to re-query transaction details after webhook notifications. See [Accept Payment](https://developer.chapa.co/integrations/accept-payments), [Verify Payments](https://developer.chapa.co/integrations/verify-payments), and [Webhooks](https://developer.chapa.co/integrations/webhooks).

## Before vending real products

Payment success creates queued dispense jobs; it does not directly control hardware. For the planned deployment, the Raspberry Pi should run the kiosk and a machine-side bridge, while an Arduino connected by USB serial drives motors and reads delivery sensors. The Arduino must not be internet-facing. The bridge can use the existing authenticated `/api/mcu/{machine_id}/dispense/next` and `/api/mcu/{machine_id}/dispense/{job_id}/result` endpoints. Add and commission the Arduino serial protocol, replay protection, sensor-confirmed completion, and retry/refund/manual-review operations before enabling live vending. A confirmed payment with invalid stock or machine configuration is recorded as `PAYMENT_REVIEW` and receives no dispense job. See [raspberry_pi/README.md](raspberry_pi/README.md) for the machine-side contract.

For public production traffic, also add edge rate limits to order creation and payment verification, monitor webhook delivery and payment reconciliation, and use backups/restore drills for PostgreSQL.
