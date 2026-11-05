# First implementation milestone

Project: CallMap

## Workflow

Load synthetic sample audio, observe a clearly labeled fixture transcript, seek timestamped segments, review and correct commitments, and export reviewed action items.

## Interface

Cobalt audio workspace with transport controls, synchronized transcript, and commitment timeline.

## Boundaries

Keep the implementation cohesive and local. No accounts, cloud hosting, production
integrations, or payment infrastructure. Fixture mode must be explicit and limited
to known sample data. Real inference remains unvalidated until a provider is chosen
and authorized. Preserve essential validation and safe execution boundaries.

## Acceptance

A new checkout has documented setup, persistent sample workflow, clear errors,
meaningful domain checks, and truthful notes about what is implemented versus
pending. Prefer direct code over reusable frameworks for imagined future needs.
