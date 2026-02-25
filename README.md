# Smart Parking - Mock Operator Integration

A Flask web application for parking payment in gated parking lots across Rwanda. This module provides a **mock operator integration layer** that simulates the data a real parking operator's system would produce (ANPR cameras reading plates, tracking sessions, calculating fees).

## What the Mock Operator Does

In production, parking operators run their own systems — cameras detect plate numbers at entry/exit gates, and their software tracks sessions and fees. Our app integrates with those systems to enable mobile payment.

During development, we don't have access to real operator APIs. The mock operator layer **simulates this entire flow** so you can:

- Create parking operators with realistic Kigali locations and rates
- Simulate a car entering a gated lot (creates an active session)
- Simulate a car exiting (closes the session)
- Look up active sessions by plate number
- See fees calculated in real-time based on elapsed time

All data is written to the same PostgreSQL tables that production integrations will use, so the rest of the app (payments, notifications, frontend) can be developed and tested against realistic data.

## Components

### Models (`app/models/`)

| File | Class | Description |
|------|-------|-------------|
| `session.py` | `ParkingOperator` | Represents a parking lot operator (name, location, hourly rate) |
| `session.py` | `ParkingSession` | A single parking visit. Includes a computed `current_fee_rwf` property that calculates the fee as `ceil(elapsed_hours) * hourly_rate_rwf` |
| `payment.py` | `Payment` | A mobile money payment record (MTN MoMo / Airtel Money) |
| `driver.py` | `Driver` | A driver profile with saved plates and push subscription |

All models are Python dataclasses with a `to_dict()` method for JSON serialization.

### Mock Service (`app/services/parking_sync.py`)

The `MockOperatorClient` class contains all simulation logic:

| Method | What it does |
|--------|--------------|
| `seed_operators()` | Inserts 2 mock operators (Kigali Heights @ 500 RWF/hr, UTC @ 1000 RWF/hr) if they don't already exist |
| `simulate_car_entry(plate_number, operator_id)` | Creates an active `parking_sessions` row with `entry_time = NOW()` |
| `simulate_car_exit(session_id)` | Sets `exit_time = NOW()` and `status = 'exited'` on the session |
| `get_active_sessions_for_plate(plate_number)` | Returns all active sessions for a plate (case-insensitive), joined with operator name and location |
| `get_session_by_id(session_id)` | Returns a single session with operator details |

### Mock API Routes (`app/routes/mock.py`)

Blueprint mounted at `/mock`:

| Method | Endpoint | Body | Description |
|--------|----------|------|-------------|
| GET | `/mock/seed` | — | Seeds the 2 mock operators |
| POST | `/mock/entry` | `{"plate_number": "RAD123A", "operator_id": 1}` | Simulates a car entering a lot |
| POST | `/mock/exit` | `{"session_id": 1}` | Simulates a car leaving |
| GET | `/mock/sessions/<plate>` | — | Lists active sessions for a plate |

There is also a `GET /health` route at the app root that returns `{"status": "ok"}`.

### Seeded Operators

| Name | Location | Rate | Grace Period |
|------|----------|------|--------------|
| Kigali Heights Parking | Kigali Heights Mall, KG 7 Ave | 500 RWF/hr | 15 min |
| UTC Parking | Union Trade Centre, KN 4 Ave | 1,000 RWF/hr | 10 min |

## How to Run

### Prerequisites

- Python 3.11+
- PostgreSQL with the `smart_parking` database and tables already created

### Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Create your .env from the example
cp .env.example .env
```

Edit `.env` with your actual database credentials:

```
DB_HOST=localhost
DB_PORT=5432
DB_NAME=smart_parking
DB_USER=postgres
DB_PASSWORD=your_password
FLASK_ENV=development
SECRET_KEY=change-me-in-production
```

### Start the server

```bash
python run.py
```

The app runs at `http://127.0.0.1:5000`.

### Test the flow

```bash
# 1. Confirm the app is running
curl http://127.0.0.1:5000/health

# 2. Seed the mock operators (safe to call multiple times)
curl http://127.0.0.1:5000/mock/seed

# 3. Simulate a car entering Kigali Heights (operator_id=1)
curl -X POST http://127.0.0.1:5000/mock/entry \
  -H "Content-Type: application/json" \
  -d '{"plate_number": "RAD123A", "operator_id": 1}'

# 4. Check active sessions for that plate
curl http://127.0.0.1:5000/mock/sessions/RAD123A

# 5. Simulate the car exiting (use the session id from step 3)
curl -X POST http://127.0.0.1:5000/mock/exit \
  -H "Content-Type: application/json" \
  -d '{"session_id": 1}'
```

## When to Use This

- **During development** — to generate realistic parking session data without a real operator API
- **When building the payment flow** — create an active session, then test paying for it via MoMo
- **When building the frontend** — seed operators and create sessions so the UI has data to display
- **When testing notifications** — create sessions and let time pass to trigger fee-increase warnings
- **In demos** — walk through the full parking lifecycle (entry, lookup, payment, exit) without hardware

This mock layer is **not used in production**. In production, session data comes from real operator integrations via API, direct DB, or webhook (configured per operator in the `parking_operators` table).
