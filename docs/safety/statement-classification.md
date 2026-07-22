# Statement Classification

**Status:** Core safety contract. Enforced by `packages/ikip-statements` and
`contracts/schemas/statement-class.schema.json`.

Every claim in every answer carries exactly one statement class. Conflating these is the
primary way this platform could contribute to industrial harm — e.g. presenting a
*recommendation* as an *approved procedure*, or an *inference* as *completed work*.

| Class | Means | Must NOT be read as |
|---|---|---|
| `historical_observation` | Recorded as observed in the past | A current condition |
| `recommendation` | A source advised it | That it was done or approved |
| `approved_procedure` | An authorized instruction in force | A record that it was performed |
| `completed_work` | Work recorded as actually performed | An instruction to repeat it |
| `inference` | Synthesized from evidence, not stated verbatim | A sourced fact |

## Rules

1. The class is mandatory on every citation. A claim without a defensible class is not
   shown; the system abstains or downgrades to an evidence list.
2. `inference` claims must still cite the evidence they were synthesized from and be
   visibly marked as inference.
3. The classifier is validated against an expert-labeled set; disagreement rate is a
   covered by the deterministic `grounding_citation_regression` suite; production quality metrics require expert labels.
