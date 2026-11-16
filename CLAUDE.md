# Project brief: Credit dues assistant for small merchants

An independent product concept for a feature inside a merchant payments app (like Google Pay for Business). This is NOT a Google product. Do not use Google logos or branding; label it "concept prototype".

## Problem
Small shops sell on credit to repeat customers and track dues in a notebook. Asking for payment is awkward, and recovery is slow and manual.

## First user segment (decided)
Small neighbourhood retail shops (kirana) with 100-200 repeat customers. Other segments (dairies, tailors, pharmacies, business-to-business credit) are out of scope for now; note differences in docs/ but do not build for them.

## Core loop (must be fast)
1. Shopkeeper enters customer phone number, bill amount, amount paid. Entry must take under 5 seconds.
2. Customer gets a message with a payment link (simulated).
3. A fixed weekly reminder goes out automatically at a day/time the shopkeeper sets once. The shopkeeper approves wording and schedule ONCE at setup, not per message.
4. If a due is overdue by 30 days (configurable, also consider amount), stop automatic messages and show the shopkeeper a "call this customer" prompt with amount, last reminder date, and any promise made.
5. After the call, the shopkeeper taps an outcome: "promised a date", "disputed", or "written off". The app uses that to decide what happens next.

## Variant to test against the baseline
Reply handling: read customer replies (e.g. "kal dunga", "will pay Friday"), record the promise, set a follow-up. Must be switchable on/off so we can compare against the plain weekly reminder.

## Optional, off the main path
Itemised list of what the customer bought, for dispute reduction. Keep optional; never slow down entry.

## Guardrails
Cap reminders per customer, no messages at night, customer opt-out, polite wording (no shaming), clear consent for storing phone numbers and purchases, a way to delete customer data.

## Metrics
Primary: share of dues recovered within 30 days. Guardrails: opt-outs, customers who stop shopping after a reminder.

## Hard rules for the build
- All messaging and payments are SIMULATED. No real SMS/WhatsApp sending, no real money.
- No API keys in the repo. Use environment variables and a .gitignore'd .env file.
- Stack: FastAPI backend, React frontend, SQLite for now (Postgres later if needed), Gemini API for reply parsing.
- Build in small slices. One working feature per commit, with a clear commit message.
- Explain non-obvious code in plain language; the owner must be able to discuss it in interviews.
- Keep docs/decisions.md updated: what we changed after testing, and why.

## Out of scope
GST billing, inventory, loans, credit scoring, customer-side app, languages beyond Hindi and English.

## Open questions (do not assume)
- Whether the real merchant app supports per-customer payment links for matching payments to dues.
- Messaging provider rules and registration requirements in India.