# Raspberry Pi kiosk and Arduino bridge

The Raspberry Pi is the machine-side gateway. It should run:

1. The customer kiosk browser, serving the built `frontend` application.
2. A small hardware bridge that polls the hosted backend for dispense jobs.
3. A USB serial connection to the Arduino that drives motors and reads the drop sensor.

The Arduino must not be exposed to the public internet. The hosted backend remains the source of truth for payment, inventory, and job state.

## Dispense flow

```text
Customer -> Pi kiosk -> hosted API -> queued dispense job
                                      ^
Pi bridge -- HTTPS + X-Machine-Token
    |
    +-- USB serial -> Arduino -> motor + delivery sensor
    |
    +-- HTTPS result -> hosted API
```

The bridge uses these existing backend endpoints:

- `GET /api/mcu/{machine_id}/dispense/next`
- `POST /api/mcu/{machine_id}/dispense/{job_id}/result`

Send the machine token in the `X-Machine-Token` header. Store it only on the Pi, never in the frontend or Arduino firmware repository.

## Arduino serial contract

Use a newline-delimited command/response protocol with an idempotent `command_id`. A bridge implementation should send a command equivalent to:

```text
DISPENSE command_id=<id> channel=<motor_channel> quantity=<quantity> timeout=<seconds>
```

The Arduino should respond with progress and a final result, for example:

```text
STARTED command_id=<id>
COMPLETED command_id=<id> sensor_confirmed=true sensor_event_id=<id>
```

On timeout, jam, invalid channel, or a missing delivery-sensor signal, return `FAILED` with an error code. The Pi bridge then forwards the final status to the backend. Do not report `COMPLETED` unless the physical delivery sensor confirms the item.

Before connecting motors, confirm the Arduino board, motor-driver pins, sensor type, serial baud rate, motor run time, and electrical power isolation. Those hardware values cannot be safely guessed from this repository.
