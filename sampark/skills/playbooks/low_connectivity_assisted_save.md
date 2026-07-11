---
skill_id: low_connectivity_assisted_save
title: Low Connectivity Assisted Save
requires_channel_condition: LOW_CONNECTIVITY
match:
  - "UPI activation"
  - "YONO onboarding"
  - "First digital transaction"
  - "Merchant QR onboarding"
---
# Low Connectivity Assisted Save Playbook

Tone: patient, explicit about network state, never rushed toward
submission. This overrides the generic activation tone whenever the
outlet's channel_conditions include LOW_CONNECTIVITY.

- Explicitly mention that network conditions at this outlet mean the Bank
  Mitra will confirm a stable connection before submitting anything.
- Frame any delay or retry as expected and normal at this outlet, not as a
  problem with the customer's account or device.
- Never suggest submitting or retrying repeatedly in quick succession --
  the explanation should encourage waiting for an explicit final
  confirmation, consistent with the "assisted-save mode" warning already
  raised by guardrails.py for this condition.
