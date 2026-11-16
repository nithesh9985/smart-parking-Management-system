# ParkWise — Smart Parking Management System

A runnable Flask + SQLite web application prototype based on the supplied StarUML class diagram.

## Run locally

```bash
python -m venv .venv
# Windows:
.venv\\Scripts\\activate
# macOS/Linux:
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```
Open http://127.0.0.1:5000

## Demo accounts
- Driver: `driver@parking.local` / `driver123`
- Admin: `admin@parking.local` / `admin123`

## Included workflows
- Driver registration and login; add vehicles
- Browse slot availability by floor; reserve and cancel slots
- Admin overview, slot maintenance, vehicle entry against a confirmed reservation
- Vehicle exit, hourly fee calculation (₹30/hour, minimum one hour), payment record
- Notifications table and reservation confirmation message

## UML mapping
- `User`, `Driver`, `Admin`: users table with role and driver/admin profile fields
- `ParkingLot`, `ParkingFloor`, `ParkingSlot`: parking hierarchy and slot state
- `Vehicle`, `ParkingReservation`, `ParkingSession`, `Payment`: booking-to-entry-to-exit lifecycle
- `ParkingController`: slot selection and state transitions in the service routes
- `EntryExitGate`: represented in the seeded gate records; physical hardware integration is not included
- `Notification`: reservation confirmation records
- `Report`: admin overview aggregates
- `PricingStrategy`, `HourlyPricing`, `FixedPricing`: fee strategy concept; current prototype uses hourly pricing at ₹30/hour
- Enums are stored as constrained application values: `SlotStatus`, `VehicleType`, `ReservationStatus`, `PaymentStatus`, `GateStatus`

## Notes
This is an academic demonstration prototype, not a production payment or access-control system. Payments are recorded as simulated successful transactions; no payment gateway, real sensor, camera, QR reader, or gate hardware is connected. Set a strong `SECRET_KEY` before deployment. For production, add CSRF protection, stricter validation, authorization tests, database migrations, audit logs, and a real payment provider.
