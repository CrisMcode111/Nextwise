"""Versioned opportunity sidecar over the unchanged canonical assessment."""
import copy
import json
import re

import semantic_discovery as semantic

VERSION = 'project-opportunity-v2'
DOMAINS = ('technology','product','UX','productivity','financial','commercial','marketing','operations','other')
FIT = ('plausible_for_bounded_review','unknown','incompatible')


def schema(request):
    text = {'type':'string','minLength':10,'maxLength':semantic.TEXT_MAX}
    texts = {'type':'array','minItems':0,'maxItems':3,'items':text}
    return {'type':'object','additionalProperties':False,
        'required':['impact_domain','improvement_mechanism','feasibility','evidence_quality'],
        'properties':{'impact_domain':{'enum':list(DOMAINS)},
            'evidence_quality':{'type':'string','enum':['publisher_claims_only']},
            'improvement_mechanism':{'type':'object','additionalProperties':False,
                'required':['explanation','project_quote','evidence_claim_ids'],
                'properties':{'explanation':text,'project_quote':text,
                    'evidence_claim_ids':{'type':'array','minItems':1,'maxItems':3,
                        'items':{'type':'string','enum':[c['passage_id'] for c in request['staged_plan']['claims']]}}}},
            'feasibility':{'type':'object','additionalProperties':False,
                'required':['status','rationale','resource_fit','resource_rationale','resource_quotes','conditions','blocking_unknowns'],
                'properties':{'status':{'enum':list(FIT)},'rationale':text,
                    'resource_fit':{'enum':list(FIT)},'resource_rationale':text,
                    'resource_quotes':texts,'conditions':{**texts,'minItems':1},'blocking_unknowns':texts}}}}


def instructions():
    return (' OPPORTUNITY V2: Also return opportunity_details. Explain a concrete improvement mechanism '
        'with exact project_quote and supporting primary-bank evidence_claim_ids. Assess constraints, resources '
        'and practical review effort, not just topical similarity. Copy resource_quotes exactly from explicit '
        'team, budget, staffing, hardware or other resource statements in the saved brief; do not invent resources. '
        'Resource fit must remain unknown when no explicit resource basis is available. '
        'plausible_for_bounded_review means only that a limited evidence-review next step appears plausible, '
        'never that integration or benefits are verified. If incompatible use incompatible; unresolved feasibility '
        'uses unknown. Record conditions and blocking_unknowns honestly; never empty blockers to obtain selection. '
        'evidence_quality must be publisher_claims_only. No numerical benefits or guarantees in any generated prose. '
        'Retain all existing relevance/hypothesis and quotation rules; insufficient evidence may produce no opportunity.')


def validate(details, request, assessment):
    import project_assessment_output as output
    def fail(field):
        raise semantic.AssessmentError('opportunity_details_invalid',field,
            'Opportunity structure or project/evidence grounding is invalid.')
    if not isinstance(details,dict) or set(details)!={'impact_domain','improvement_mechanism','feasibility','evidence_quality'}:
        fail('opportunity_details')
    if details['impact_domain'] not in DOMAINS or details['evidence_quality']!='publisher_claims_only':
        fail('opportunity_details.impact_domain')
    mechanism, fit = details['improvement_mechanism'], details['feasibility']
    if not isinstance(mechanism,dict) or set(mechanism)!={'explanation','project_quote','evidence_claim_ids'}:
        fail('improvement_mechanism')
    if not isinstance(fit,dict) or set(fit)!={'status','rationale','resource_fit','resource_rationale','resource_quotes','conditions','blocking_unknowns'}:
        fail('feasibility')
    if fit['status'] not in FIT or fit['resource_fit'] not in FIT:
        fail('feasibility.status')
    brief = request['context']['profile']['objective']
    def text(value, field, generated=True):
        if not isinstance(value,str) or not 10<=len(value)<=semantic.TEXT_MAX:
            fail(field)
        if generated and (output.quantified_outcome(value,brief) or re.search(
                r'\b(?:guarantee\w*|will|ensures?|proves?)\b|'
                r'\b(?:verified|measured|proven|demonstrated)\s+(?:project|benefits?|savings|gains|improvements?)\b|'
                r'\b(?:is|are|has been)\s+(?:fully\s+)?(?:compatible|ready|verified|proven)\b',value,re.I)):
            fail(field)
    for field in ('explanation',):text(mechanism[field],'improvement_mechanism.'+field)
    if assessment['category']=='potential relevance' and not re.search(
            r'\b(?:could|may|might|possible|potential)\b',mechanism['explanation'],re.I):
        fail('improvement_mechanism.explanation')
    text(mechanism['project_quote'],'improvement_mechanism.project_quote',False)
    if mechanism['project_quote'] not in brief:fail('improvement_mechanism.project_quote')
    ids = mechanism['evidence_claim_ids']
    cited = {e['passage_id'] for e in assessment['evidence']}
    if (not isinstance(ids,list) or not 1<=len(ids)<=3 or any(not isinstance(i,str) or i not in cited for i in ids)
            or len(set(ids))!=len(ids)):
        fail('improvement_mechanism.evidence_claim_ids')
    for field in ('rationale','resource_rationale'):text(fit[field],'feasibility.'+field)
    for field in ('resource_quotes','conditions','blocking_unknowns'):
        values=fit[field]
        if not isinstance(values,list) or not (1 if field=='conditions' else 0)<=len(values)<=3:
            fail('feasibility.'+field)
        for value in values:
            text(value,'feasibility.'+field,field!='resource_quotes')
            if field=='resource_quotes' and (value not in brief or not re.search(
                    r'\b(?:team|staff|administrator|developer|budget|resources?|hours|capacity|Windows|RAM|hardware)\b',value,re.I)):
                fail('feasibility.resource_quotes')
    if fit['resource_fit']=='plausible_for_bounded_review' and not fit['resource_quotes']:
        fail('feasibility.resource_quotes')
    return copy.deepcopy(details)


def evaluate(content, request):
    value = copy.deepcopy(semantic.parse_batch(content,[request['prepared']])[request['prepared']['source']['candidate_id']])
    details = value.pop('opportunity_details',None)
    canonical = json.dumps({'assessments':[value]},ensure_ascii=False)
    result = semantic.evaluate_business_response(canonical,request)
    return result, validate(details,request,value)
