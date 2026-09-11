# FactorAtlas Submission Evidence

## How judges find the evidence

The submission form has no separate upload control for each material. The project description explains the work, while the **Submission Materials Link** field contains one labeled link per line. Judges therefore review the evidence through the links we submit; the Bitget UID is for eligibility and follow-up, not a substitute for a paper-log link.

## Required links for FactorAtlas

Use public, reviewable links with no access request required:

```text
Project / Demo: <public repository or hosted runnable demo>
Paper trading log: <public JSONL/CSV export or repository artifact>
Runbook / README: <instructions showing how the demo and paper runner work>
Demo video: <optional but strongly recommended, three minutes or less>
X project post: <public post URL>
```

The exact URLs are placeholders until the project is built and published. Never submit a private local path, a screenshot as the only evidence, an expired link, or a link that requires the judge to request access.

## What the paper log must prove

The log must be produced by the paper runner during the competition period. It should contain accepted and rejected cycles and, for each cycle, enough information to connect:

`event timestamp → cycle ID → hypotheses/validation → selected decision → risk gates → execution/rejection → balance change`

Required execution evidence includes timestamp, instrument, direction/side, price, quantity, pre/post balance, fees, slippage, status, validation summary, gate results, and software/config version. Include a log header or companion manifest containing the actual run start/end timestamps, timezone, code commit, and configuration hash.

## Two evidence layers

### Runnable demo

This is the short deterministic fixture run judges can reproduce. It proves the event → decision → execution behavior and can run without credentials.

### Competition-period paper run

This is the separately scheduled run that generates the required paper log. It should use Bitget Demo paper trading. A local simulator or Agentic account must not be substituted unless the organizers explicitly confirm that path is accepted for this material. The demo fixture must not be presented as a two-week competition log.

## Account verification boundary

The handbook screenshots specify the materials-link review path but do not state that judges can query a Bitget account by UID to retrieve hidden logs. We should therefore assume they review the submitted public/exported records and may inspect or run the linked code. The submission must explain the account mode used, while never exposing API keys, secrets, passphrases, or private account data.
