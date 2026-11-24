# Casino and gambling

- Donor rules live in the decompiled scripts (blackjack, roulette, three-card
  poker, slots, lucky wheel). Re-implement the state machine; do not port bytecode.
- Chips: one cashier converts cash <-> chips; cap conversions until the story
  ends so the campaign economy is not broken.
- NPCs use the same rules engine as the player (parity).
- Verify payouts by simulation (house edge within tolerance), not by feel.