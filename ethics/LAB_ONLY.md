# Lab-only statement

## Vulnerable by design

The `off`, `validate_only` and `parameterise_only` modes of the tiers contain injection flaws on purpose: that is what the experiment measures. Never expose them to a network, never deploy them, never reuse the code outside this testbed. The sandbox rules below are part of the design, not optional hardening.

## Conditions of every run

- Controlled lab, hardware owned by the author.
- Payloads are synthetic and inert: canary files, fixed test badge ids, and stub tools that only append to a log. No payload is built to work against any real product.
- Vulnerable code that executes shell runs only an inert command, in a sandbox with no network, writing only to a canary directory. Services bind to loopback only. The container and Pi variants are specified in the plan (decision D12) and approved at gate G2 before that code exists.

## Scope

Only the simulated stack in this repository is tested. No third-party or in-the-wild system is touched. Testing a commercial device is out of scope (decision D15).

## Ethics review

Not yet recorded in this repository. It is gate G3 in `plan.md`: no run whose output is intended for publication happens before it is confirmed here, with the reference and date.

## Disclosure

Not applicable while the scope above holds. If the scope is ever widened to a real device, this section must be rewritten first: private notice to the vendor, a remediation window before publication, and a report through the relevant CERT or national channel.

## What is released

The defense and the harness. Attack detail is limited to what is needed to validate the threat and the defense.
