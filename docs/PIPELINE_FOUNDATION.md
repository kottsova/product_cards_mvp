# Multi-brand pipeline foundation

The additive pipeline is:

`ProductIdentity -> SourceRegistry -> SiteAdapter -> IdentityVerifier -> FetchAttempt/SourceSnapshot -> Normalizer/CategorySchema -> ResolutionPolicy -> HumanReview`

The existing LG worker remains the active adapter implementation. Its `source_pages` and
LG-specific attribute resolver remain available while new adapters migrate to the shared
contracts.

## Identity

`ProductIdentity` retains raw and canonical brand/category values, seller and WB SKU,
the original title, all model candidates, market, and an extensible variant map. Variant
fields are category-driven. Missing seller SKU on a manufacturer page is recorded as
missing evidence, not a conflict.

`IdentityVerifier` only compares fields extracted by an adapter. It never searches a SKU
through arbitrary HTML. Its outcomes are `exact_variant`, `exact_model`, `family_only`,
`conflict`, and `insufficient`.

## Bosch routing

No Bosch adapter is implemented in this stage. The registry nevertheless keeps the two
source families independent so a future adapter cannot accidentally route both product
lines through one site.

| Family | Explicit category fragments | Adapter ID | Identity strategy | Verified official page hosts |
| --- | --- | --- | --- | --- |
| `bosch_home` | ovens, hobs, refrigerators/freezers, dishwashers, washing/drying machines, hoods, coffee machines, kitchen appliances | `bosch_home` | base E-Nr plus significant `/NN` service index | `bosch-home.com` |
| `bosch_tools` | drills/drivers, rotary hammers, grinders, jigsaws/saws, routers/planers, tools, rangefinders/levels | `bosch_tools` | manufacturer model plus hardware revision/configuration | `bosch-professional.com`, `bosch-diy.com` |
| review | unknown categories or a category matching both families | none | human classification | none |

The current repository and local SQLite batch contained no Bosch product categories on
2026-09-21, so this conservative table is a pilot allowlist rather than a claim about the
full assortment. Add a category only after observing it in input data. Unknown or
ambiguous categories remain in review.

Every source has independent page and asset host allowlists. `validate_redirect_chain`
checks every hop, including the final URL; unknown hosts are denied by default. The Bosch
root domains above were checked against their official global product/location pages on
2026-09-21.

## Fetch history and derived data

`FetchAttempt` records every success, HTTP failure, timeout, URL and final URL. An
immutable `SourceSnapshot` is created only for a successful attempt. Failed refreshes do
not delete or replace the latest successful snapshot. Derived data can be recalculated
from a stored snapshot with `reprocess_snapshot` without making another network request.

## Resolution

The shared `ResolutionPolicy` only considers exact model/variant evidence for the target
variant key. Exact first-party values outrank retailers. A dealer or retailer may fill a
field missing from first-party data, but cannot overwrite a confirmed manufacturer value.
First-party conflicts produce a review item with provenance. Values from another variant
key are excluded.

## Migrations

Migrations are additive and idempotent in `product_tool/migrations.py`:

1. `schema_migrations` version 1 adds `products.identity_json`, `fetch_attempts`,
   `source_snapshots`, `identity_verifications`, and `human_reviews`.
2. `job_schema_migrations` version 1 holds the former legacy LG source-key compatibility
   migration and `resolved_attributes.full_sku_confirmed` addition.

They are applied automatically by `storage.initialize()` and `jobs.initialize()`.
No destructive migration or data deletion is performed.
