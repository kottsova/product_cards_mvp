# LG: official regions and DNS fallback (owner decision, 2026-09-27)

## Full article, model and kits

The full catalog article is always retained. A suffix after a dot can identify
a specific color, market or other variant; its meaning is not decoded from the
characters alone. For page discovery, `S3WER.ALWPCOM` may search `S3WER` and
`GC-B459MLWM.ADSQCIS` may search `GC-B459MLWM`, but those family pages remain
`base_model` until they show the full article. A hyphen or space is not
automatically treated as a variant boundary.

An explicit `+` expression such as `P12ED.NSAR + P12ED.USAR` has two retained
component articles and the common search model `P12ED`. A page for `P12ED`
alone does not confirm the exact two-part kit. If an older import placed a
descriptive product title in the Model column, the worker reads its shorter
model for discovery; the importer now classifies such prose as the product
name for newly uploaded batches. Neither action promotes a shorter model to
the exact catalog variant.

## Missing color: exact-code lookup

When the uploaded row has no color, search the **whole catalog article** as
well as the shorter model. The shorter model locates product families; only
the whole article can tie a color to the row. A search result or URL slug is
only a lead. Accept a color only when the opened product page itself states
both the identical full manufacturer article and a clearly labelled color;
save that page URL and the exact evidence with the color. Prefer an official
LG page. A dealer page can fill an empty color under the existing identity
and source rules; contradictory colors require review. Never infer the color
by decoding the suffix after a dot, and never copy a family's color to a
specific variant. A `+` kit needs evidence for each component if their colors
matter. If the exact-color evidence is unavailable, leave color open.

For example, an online search for `S3WER.ALWPCOM` produced dealer pages that
label it differently; that ambiguity is a review case, not a color to pick
from the first result. The current production worker does not run a web search
engine automatically, so this lookup is a research step until a bounded,
policy-aware discovery route is connected.

## Source order

1. Check the observed official LG Kazakhstan and LG Russia product routes.
2. For home appliances when these routes have no product or no usable facts,
   check another **verified official LG market**. A candidate URL must come
   from that market's observed sitemap, search, or first-party link; a code
   in a guessed URL is not proof of the variant. Keep market and URL on each
   field. This route is authorized but is not yet connected to the production
   LG worker; the research-only multi-domain discovery is not a production
   adapter.
3. DNS may supplement missing characteristics, photos, and instructions for
   any LG category, including computers, televisions, watches, and audio.
   Official values win. A disagreement is shown for review.

## DNS identity gate

The **only** automatic variant match on a DNS product page is a single
"Код производителя" attribute whose value equals the full catalog article
after trimming display brackets and whitespace and normalizing case. A page
title, model label, slug, or code elsewhere in body text is insufficient.
Multiple different values are ambiguous. Reject facts, photos, description,
and document fetch from a nonmatching page.

The owner-provided screenshot shows `[32LQ63006LA.ARUG]` at
`https://www.dns-shop.ru/product/dedc85f90ae5d21a/32-80-sm-televizor-lg-32lq63006la-cernyj/`.
The catalog has separate `32LQ63006LA` and `32LQ63006LA.ARUG` rows; this
candidate may serve only the latter. The actual DNS HTML and PDF links have
not been verified through the production HTTP adapter; a prior DNS request
returned 401. Do not bypass a block or claim the live page was parsed.

## Instructions

DNS is a valid dealer-hosted source for manuals once its product page passes
the identity gate. A linked PDF must still be fetched completely and checked
by its own contents for an instruction/manual, model or family applicability,
and language. A filename or dealer label alone does not establish these.
Declarations and certificates do not count as manuals. Russian content in a
multilingual manual is labelled Russian in the card.

LG videos are outside this work; they are not a card-readiness requirement.
