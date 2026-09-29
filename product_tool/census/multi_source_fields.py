"""Stage 7 field provenance contract. No extraction or production card writes."""
from product_tool.policy import ResolutionPolicy
from product_tool.sources import SourceRole
from .multi_domain import dealer_gate

REQUIRED_PROVENANCE={'source','url','fetched_at','identity_level','extraction_method','confidence'}

def resolve_card_fields(values,*,expected,official_result,target_variant_key):
    gate=dealer_gate(expected,official_result);accepted=[];reviews=[]
    for item in values:
        if not REQUIRED_PROVENANCE<=set(item.provenance):
            reviews.append({'field_name':item.field_name,'reason':'incomplete_provenance'});continue
        if item.provenance['source']!=item.source_id or item.provenance['identity_level']!=item.verification.value:
            reviews.append({'field_name':item.field_name,'reason':'inconsistent_provenance'});continue
        if item.variant_key!=target_variant_key:
            reviews.append({'field_name':item.field_name,'reason':'different_variant'});continue
        if item.role in {SourceRole.DEALER,SourceRole.RETAILER} and not (gate['allowed'] and item.source_id==gate['source_id']):
            reviews.append({'field_name':item.field_name,'reason':'dealer_not_approved_for_this_fallback'});continue
        accepted.append(item)
    result=ResolutionPolicy().resolve(accepted,target_variant_key=target_variant_key)
    for official in accepted:
        if official.role not in {SourceRole.MANUFACTURER,SourceRole.SUPPORT}:continue
        for dealer in accepted:
            if dealer.role in {SourceRole.DEALER,SourceRole.RETAILER} and dealer.field_name==official.field_name and dealer.value!=official.value:
                reviews.append({'field_name':official.field_name,'reason':'dealer_official_conflict_official_retained','provenance':[official.provenance,dealer.provenance]})
    return {'fields':[vars(f) for f in result.fields],'reviews':[*result.reviews,*reviews]}
