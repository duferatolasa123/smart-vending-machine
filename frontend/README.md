# Smart Vending Machine Frontend

React + Vite customer storefront for the Raspberry Pi kiosk.

## Requirements
- Node.js 20.19+ or 22.12+
- npm

## Run
```powershell
npm install
Copy-Item .env.example .env
npm run dev
```

Open http://localhost:5173.

Set `VITE_API_BASE_URL` in `frontend/.env` to the URL of the hosted backend before building for the Raspberry Pi. The browser kiosk should never contain backend secrets.

```powershell
npm run build
npm run preview -- --host 0.0.0.0
```

The product catalog, prices, payments, orders, and dispense jobs come from the backend API. The frontend only keeps the current cart in browser memory and uses bundled product photos for kiosk presentation.
