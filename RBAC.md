# Roles and authorization

| Role | Read | Investigate | Propose | Approve / execute | Manage users/settings |
|---|---:|---:|---:|---:|---:|
| Viewer | yes | no | no | no | no |
| Analyst | yes | yes | yes | no | no |
| Operator | yes | no | no | yes | no |
| Admin | yes | no implicit operator rights | no | no | yes |

The requester cannot approve their own proposal. The server, not the UI, enforces role and tenant checks. Each browser person has a distinct account; there is no shared browser service token. OIDC/SSO is reserved as an identity-provider seam and is not implemented in this release.
