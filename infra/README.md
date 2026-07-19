# Infrastructure

Infrastructure-as-code for the controlled production security boundary
(docs/architecture/03-deployment.md, 04-trust-boundary.md).

| Path | Purpose |
|---|---|
| `terraform/` | Cloud resources (network, database, object storage, secrets, private endpoints) |
| `environments/` | Per-environment overlays: `dev`, `staging`, `prod` |
| `policy/` | IaC guardrails: network isolation, model-egress allow-lists, encryption-at-rest enforcement |

## Security notes

- Services run in a private application boundary; only TLS ingress + WAF is public.
- Model egress goes through the gateway on an **allow-list**; default-deny outbound.
- Governed data and backups are encrypted with scoped, rotated keys (TB-6).
- No infrastructure path controls equipment — decision-support only.

> Terraform vs. Pulumi is not yet decided. If you have a house standard, say so and the
> `terraform/` directory should be renamed accordingly.
