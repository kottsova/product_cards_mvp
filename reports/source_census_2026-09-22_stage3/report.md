# All-brand source census — stage 3

Stage 2 preserved as immutable baseline. No SamsungAdapter, AEM discovery, production JSON-LD adapter, or production discovery orchestration was implemented.

## Normalization and coverage

- Source labels: 289; canonical brands: 284; source families: 283.
- Researched priority families: 50; newly verified official sources: 49; official source not found: 1.
- Official coverage after safe normalization: 91.0% (15368 / 16888 products); stage 2: 77.2%.
- Explicit label outcomes: {"mapped_to_verified_source_family": 14, "official_source_not_found": 1, "unresolved_requires_human_review": 186, "verified_independent_brand": 88}.

Mappings marked requires_human_review never inherit source coverage. Bosch Home and Bosch Tools remain separate routed families. POCO remains a distinct brand identity routed through the verified Xiaomi family; exact identity still requires structured model/variant evidence.

## Bounded research and probes

The registry contains the next 50 priority unresolved families. Accesstyle is an explicit negative result: the guessed domain is unrelated and no first-party source was accepted. Probe results are checkpointed per family, use declared allowlisted hosts only, retain redirects/status/protection/fingerprints, and stop the whole host after 403, 429, or a confirmed challenge. No bypass is attempted.
Bounded pass: 148 endpoints; access statuses {"captcha_or_blocked": 4, "direct_access": 121, "regional_redirect": 1, "unavailable": 22}; checkpoints {"complete": 45, "not_applicable": 1, "stopped": 4}.

A probe completing homepage/robots/sitemap is access_checked only. It is not product discovery, exact identity, or production readiness. Product samples remain incomplete where no bounded reproducible product route was found.

## Readiness

- Official-domain, access, discovery, exact-identity, and production-ready levels are independent.
- Arbitrary body substring matches no longer qualify as exact identity in stage 3.
- Existing stage-2 readiness is not promoted by the new research registry.

## Recommendation

Implement the bounded sitemap/catalog-feed discovery strategy described in docs/DISCOVERY_ORCHESTRATION_PLAN.md before any product adapter. Shopify (Dreame + HyperX) is the first platform-adapter evaluation candidate, but not implementation-ready until reproducible discovery and structured exact identity are sampled. Current evidence still does not justify a common JSON-LD or AEM production adapter.
