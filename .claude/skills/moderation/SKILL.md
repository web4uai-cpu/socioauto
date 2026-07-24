---
name: moderation
description: Mandatory brand-safety and compliance review gate for all outbound content before it can be scheduled or published. Use for every content item, no exceptions.
---

# Moderation Skill

This is a **mandatory gate**. Nothing reaches Scheduling/Publishing without passing this skill.

1. Check for profanity/hate speech, harassment, or discriminatory language.
2. Check for brand policy violations (tone, competitor mentions, off-brand claims).
3. Check for platform ToS violations (spam patterns, prohibited content categories).
4. Check for regulated claims (medical/financial/legal) lacking required disclaimers.
5. Check for PII leakage (emails, phone numbers, addresses) in copy or media briefs.
6. Return `{verdict: approved|rejected|needs_human, reasons: []}`.
7. If `verdict != approved`, the item must NOT proceed to Scheduling/Publishing — route to a human review queue instead.
