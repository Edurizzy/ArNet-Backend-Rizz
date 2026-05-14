# Meta / WhatsApp Cloud — operations runbook

## Per-tenant credentials

After the DB-backed channel refactor:

- **Access tokens** and **phone number IDs** (`external_id` for provider `whatsapp_cloud`) are stored on **`ConnectedAccount`** rows, scoped by **organization**.
- Do **not** put tenant WhatsApp access tokens in `.env`. Only **global** values belong there, for example:
  - `META_APP_SECRET` — webhook `X-Hub-Signature-256` validation (Meta app secret).
  - `META_GRAPH_API_VERSION` — default Graph API version (overridable per account via `ConnectedAccount.settings["graph_api_version"]`).
  - `META_AUTO_CREATE_CUSTOMERS` — default for inbound auto-create when `settings.auto_create_customers` is not set on the account.

## Deploy / migrate

1. Run migrations (`integrations` then `meta_integration` migrations apply in dependency order).
2. Existing **`WhatsAppBusinessAccountConnection`** rows are copied into **`ConnectedAccount`** with **`access_token` left empty**.
3. For each organization that sends outbound WhatsApp, set the **access token** via Django Admin (**Connected accounts**) or **`PATCH /api/v1/integrations/connected-accounts/{id}/`** with a write-only `access_token` field.
4. Remove any legacy **`META_WHATSAPP_ACCESS_TOKEN`** (or `META_ACCESS_TOKEN`) from environment files so operators are not tempted to use a single shared token.

## Optional one-off (single tenant only)

If you still have one legacy env token during cutover, set the token only on the **one** `ConnectedAccount` row that matches that org’s phone number ID—never assign one env token to multiple tenants.
