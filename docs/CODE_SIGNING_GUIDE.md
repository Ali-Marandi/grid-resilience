# Windows Code Signing and Release Attestation

## Purpose

Every Grid Resilience Control Center Windows release must contain the executable, its SHA-256 digest, and a machine-readable signing-status attestation. The pipeline records an **unsigned** status rather than pretending that an executable is signed when organisation-owned credentials are unavailable.

> A code signature confirms the identity asserted by the signer and protects the signed bytes from undetected alteration. It does **not** validate engineering results, approve network operations, or replace independent security review.

## Current protected release workflow

The repository workflow tests Python 3.10 through 3.13, builds the executable on `windows-latest`, computes SHA-256, emits a signing-status JSON artifact, creates a GitHub provenance attestation, and attaches all of those files to a tagged release. The workflow accepts a certificate only through protected GitHub Actions configuration; it never stores a certificate or password in the repository.

| Configuration key | Where it belongs | Purpose |
|---|---|---|
| `WINDOWS_CERT_BASE64` | Protected GitHub Actions secret | Base64-encoded organisation-owned PFX certificate, used only in a protected release environment |
| `WINDOWS_CERT_PASSWORD` | Protected GitHub Actions secret | Password for the PFX certificate |
| `AUTHENTICODE_TIMESTAMP_URL` | GitHub Actions variable | Trusted RFC 3161/AuthentiCode timestamp service URL |
| `GridResilienceStudio-signing-status.json` | Release asset | Declares the signature status, signer subject when available, artifact digest, and workflow run URL |

For the PFX path, use a dedicated protected environment with required reviewers and restrict the workflow to signed tags. Base64 encoding is transport only; it is not encryption. Prefer a managed signing service rather than exporting a private key where company policy permits.

## Azure Artifact Signing configuration

Azure Artifact Signing supports GitHub Actions and SignTool integrations. It requires an Artifact Signing account, identity validation, certificate profile, and an identity granted the **Certificate Profile Signer** role. Microsoft documents that the endpoint must match the region of the signing account and profile; a mismatch can cause a `403` or signing failure. [1]

Create the Artifact Signing account and certificate profile in the intended Azure region. Configure GitHub OpenID Connect federation for a dedicated Azure application or managed identity, then grant the least-privileged signer role at the certificate-profile scope. Keep tenant, subscription, client ID and endpoint references in protected GitHub environment variables; do not place client secrets or certificates in source files.

The Azure signing step should use the organisation-approved integration from the [Artifact Signing GitHub Action](https://github.com/azure/artifact-signing-action) and receive its values through the protected environment. Microsoft’s SignTool guidance specifies SHA-256 file digesting and a timestamp URL, with `http://timestamp.acs.microsoft.com/` shown as the Artifact Signing public timestamp authority. Artifact Signing certificates are short-lived, which makes timestamping essential for later signature validation. [1]

| Required Azure value | Example format | Security control |
|---|---|---|
| Artifact Signing endpoint | `https://<region>.codesigning.azure.net` | Match the account/profile region exactly |
| Code Signing account name | Azure resource name | Environment variable, not source code |
| Certificate profile name | Azure resource name | Environment variable, least-privileged role assignment |
| GitHub OIDC identity | Azure application/client identity | Federated credential limited to the repository and protected environment |
| Timestamp URL | `http://timestamp.acs.microsoft.com/` | Keep SHA-256 timestamping enabled |

## Activation checklist

Before enabling a real signing path, have a security owner approve the certificate identity, the protected GitHub environment, the tag policy, and the retention policy. Run a test release, inspect the signing-status attestation and provenance artifact, and validate the downloaded executable with `Get-AuthenticodeSignature` on a clean Windows system. Only then should the release be presented as signed.

## References

[1] [Microsoft Learn, *Set up signing integrations to use Artifact Signing*](https://learn.microsoft.com/en-us/azure/artifact-signing/how-to-signing-integrations).
