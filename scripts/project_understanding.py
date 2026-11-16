"""Offline project understanding and evidence-oriented query composition.

No transport, credentials or persistence. Rules are a bounded semantic fallback,
not a language model: unsupported meaning remains an explicit question. Reviewed
semantic topics use the existing planning contract rather than a new provider.
"""
import copy
import re

POLICY = 'project-understanding-v1'
FOCUSES = {'general': None, 'technology': 'technology', 'product': 'product',
           'product development': 'product', 'marketing': 'marketing',
           'sales': 'commercial', 'funding': 'financial', 'operations': 'operations'}
# Controlled public vocabulary avoids projecting arbitrary private brief tokens.
SUBJECTS = (
    (r'\b(recipes?|meal plans?|meal planning)\b', 'recipe generation meal planning'),
    (r'\b(bakery|bakeries)\b', 'bakery'),
    (r'\b(dental|dentist)\b', 'dental practice'),
    (r'\b(clinic|appointment|booking|rendez-vous)\b', 'appointment scheduling'),
    (r'\b(bookshop|bookstore)\b', 'bookshop'),
    (r'\b(craft|handmade)\b', 'handmade products'),
    (r'\b(museum)\b', 'museum'),
    (r'\b(learning platform|education|school)\b', 'learning platform'),
    (r'\b(restaurant)\b', 'restaurant'),
    (r'\b(inventory|warehouse)\b', 'inventory management'),
    (r'\b(accessibility|navigation)\b', 'accessible user interfaces'),
    (r'\b(onboarding|retention)\b', 'customer onboarding retention'),
    (r'\b(invoices?|cash flow)\b', 'invoicing cash flow'),
)
ROLE_RULES = {
    'goals': r'\b(goal|objective|aim|want|deliver|improve|reduce|increase|objectif|but|souhaite|quiero)\b',
    'needs': r'\b(needs?|requires?|must|besoin|doit|necesito)\b',
    'problems': r'\b(problems?|struggle|fail|slow|waste|difficult|manual|losing|probl[eè]me)\b',
    'constraints': r'\b(constraints?|limited|budget|do not|avoid|must not|contrainte|ne pas)\b',
    'resources': r'\b(resources?|team|environment|windows|ram|staff|available|[eé]quipe|ressources)\b',
    'uncertainties': r'\b(unknown|uncertain|whether|not sure|unsure|inconnu|incertain)\b|\?',
    'priorities': r'\b(priority|priorities|first|most important|priorit[eé]|primero)\b',
}
DETAILS = ((r'\b(structured.output|json|schema)\b', 'structured output JSON schema'),
           (r'\b(dietary|allergies|food preferences)\b', 'dietary constraints'),
           (r'\b(inventory|waste)\b', 'inventory waste'),
           (r'\b(delivery|scheduling)\b', 'delivery scheduling'),
           (r'\b(checkout|conversion)\b', 'checkout conversion'),
           (r'\b(retention|onboarding)\b', 'onboarding retention'))
AUDIENCES = ((r'\b(local customers|local families)\b', 'local customers'),
             (r'\b(parents|families)\b', 'families'), (r'\b(students)\b', 'students'),
             (r'\b(patients)\b', 'patients'), (r'\b(retailers)\b', 'retailers'),
             (r'\b(business owners)\b', 'business owners'), (r'\b(tourists)\b', 'tourists'))
OUTCOMES = ((r'\b(visits|foot traffic)\b', 'store visits'),
            (r'\b(leads)\b', 'qualified leads'), (r'\b(signups)\b', 'signup conversion'),
            (r'\b(retention)\b', 'retention'))
INTENTS = {
    'technology': ('Which documented interfaces, validation capabilities and recent changes could reduce integration work for {subject}?',
                   'API integration validation documentation changelog', ['official_documentation', 'release_notes']),
    'product': ('Which documented features and published evaluations address user constraints for {subject}?',
                'features user constraints evaluation product documentation case study', ['product_documentation', 'published_case_study']),
    'marketing': ('Which channel changes and published acquisition evidence are relevant to {subject}?',
                  'customer acquisition channel changes official guidance case study', ['official_platform_guidance', 'published_case_study']),
    'commercial': ('Which documented sales channels and conversion practices have evidence for {subject}?',
                   'sales channels conversion evidence case study', ['product_documentation', 'published_case_study']),
    'financial': ('What current pricing, eligibility and cost conditions apply to improvements for {subject}?',
                  'pricing costs eligibility official terms', ['official_pricing', 'official_program_terms']),
    'operations': ('Which documented workflow changes could reduce manual work or waste for {subject}?',
                   'workflow scheduling automation documentation case study', ['product_documentation', 'official_documentation']),
    'productivity': ('Which documented automation interfaces could reduce repeated work for {subject}?',
                      'workflow automation integration documentation case study', ['official_documentation', 'published_case_study']),
    'UX': ('Which accessibility requirements and usability findings apply to {subject}?',
           'accessibility usability standard research', ['accessibility_standard', 'usability_research']),
}
QUESTIONS = {
    'en': {'subject': 'What product or service do you offer, and who is it for?',
           'audience': 'Which customers or audience should this research focus on reaching?',
           'outcome': 'What result should this research improve first, and what is currently getting in the way?',
           'language': 'Which project need should we research? Please provide a reviewed public description in your preferred language.'},
    'fr': {'subject': 'Quel produit ou service proposez-vous, et à qui ?',
           'audience': 'Quels clients ou quel public souhaitez-vous atteindre ?',
           'outcome': 'Quel résultat souhaitez-vous améliorer en priorité, et quel obstacle rencontrez-vous ?',
           'language': 'Quel besoin faut-il étudier ? Donnez une description publique relue dans votre langue.'},
    'es': {'subject': '¿Qué producto o servicio ofrece y para quién?',
           'audience': '¿A qué clientes o público quiere llegar?',
           'outcome': '¿Qué resultado quiere mejorar primero y qué obstáculo encuentra?',
           'language': '¿Qué necesidad debemos investigar? Facilite una descripción pública revisada en su idioma.'},
}


def _clauses(text):
    return [c.strip() for c in re.split(r'[;\n]+|(?<=[.!?])\s+', text) if c.strip()]


def understand(state, *, research_focus='general', clarifications=None, language=None):
    """Return attributed user statements and provisional interpretations separately.

    Clarifications are ephemeral reviewed answers, never amendments to saved facts.
    They authorize neither model interpretation nor external research.
    """
    from project_opportunities import _text, _language_context, _digest, _heads
    if not isinstance(research_focus, str) or research_focus not in FOCUSES:
        raise ValueError('Choose a supported research focus.')
    clarifications = {} if clarifications is None else clarifications
    if (not isinstance(clarifications, dict) or set(clarifications)-{'subject', 'outcome', 'audience'}
            or any(not isinstance(v, str) or not 1 <= len(v.strip()) <= 2000
                   for v in clarifications.values())):
        raise ValueError('Clarifications must be bounded subject/outcome/audience answers.')
    project = state['project']
    facts = []
    for field in ('brief', 'goals', 'needs', 'problems', 'constraints', 'resources', 'uncertainties', 'priorities'):
        if field in project:
            for clause in _clauses(_text(project[field])):
                kinds = [k for k, pattern in ROLE_RULES.items() if re.search(pattern, clause, re.I)]
                if field != 'brief': kinds = list(dict.fromkeys([field]+kinds))
                facts.append({'text': clause, 'field': 'project.'+field, 'kinds': kinds or ['description'],
                              'classification_status': 'rule_interpretation',
                              'provenance': 'saved_user_statement', 'independently_verified': False})
    for key, value in clarifications.items():
        facts.append({'text': value.strip(), 'field': 'clarifications.'+key,
                      'kinds': ['goals' if key == 'outcome' else 'description'],
                      'classification_status': 'answer_slot',
                      'provenance': 'current_user_answer', 'independently_verified': False})
    language_context = _language_context(state, language)
    if language is not None and (not isinstance(language,str) or not re.fullmatch(r'[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*',language)):
        raise ValueError('Language must be a language tag.')
    if not language and not project.get('language') and not language_context['english_rules_available']:
        text = ' '.join(f['text'] for f in facts)
        signals = set(re.findall(r'\b(?:goal|want|help|have|business|reduce|increase|improve|deliver|our|with|and|for|need)\b', text.lower()))
        if len(signals)>=2 and not re.search(r'[^\x00-\x7f]|\b(?:je|nous|notre|pour|quiero|nuestro|para|ich|wir|unser)\b',text,re.I):
            language_context = {**language_context, 'english_rules_available':True,
                                'basis':'bounded_English_intent_applicability_check'}
    # A non-English or mixed-language brief is not silently translated.
    english = language_context['english_rules_available']
    subjects = []
    if english:
        for pattern, label in SUBJECTS:
            basis = [f for f in facts if re.search(pattern, f['text'], re.I)
                     and not re.search(r'\b(do not|avoid|exclude|not interested in)\b', f['text'], re.I)]
            if basis:
                subjects.append({'value': label, 'basis': basis, 'status': 'rule_interpretation'})
    subject = subjects[0] if subjects else None
    unanswered = []
    if not english:
        unanswered.append('language')
    elif subject is None:
        unanswered.append('subject')
    if any(re.search(r'\b(?:whether|either)\b.+\bor\b',f['text'],re.I)
           and sum(bool(re.search(pattern,f['text'],re.I)) for pattern,_ in SUBJECTS)>1
           for f in facts):
        subject = None
        if 'subject' not in unanswered: unanswered.append('subject')
    explicit_outcome = any(('goals' in f['kinds'] or 'problems' in f['kinds']) and re.search(
        r'\b(deliver|improve|reduce|increase|generate|adapt|automate|manage|problem|manual|fail|losing)\b',f['text'],re.I)
        for f in facts)
    explicit_outcome = explicit_outcome or 'outcome' in clarifications
    if english and research_focus in ('marketing','sales'):
        text = ' '.join(f['text'] for f in facts)
        if subject and 'audience' not in clarifications and not re.search(
                r'\b(local customers|families|parents|students|patients|retailers|business owners|tourists)\b', text, re.I):
            unanswered.append('audience')
        explicit_outcome = 'outcome' in clarifications or bool(re.search(
            r'\b(leads|conversion|sales|signups|acquisition|traffic|visits|new clients|retention|revenue)\b', text, re.I))
    # A focus such as "marketing" alone says nothing about the desired outcome.
    if not explicit_outcome:
        unanswered.append('outcome')
    lang = (language or project.get('language') or 'en').lower().split('-')[0]
    question_text = QUESTIONS.get(lang, QUESTIONS['en'])
    questions = [{'id': key, 'question': question_text[key], 'material_reason':
                  {'subject': 'The offer and audience determine useful sources and search specificity.',
                   'audience': 'Audience differences change channel selection and applicable case studies.',
                   'outcome': 'The desired result changes research priorities and evidence criteria.',
                   'language': 'The offline rules cannot safely interpret this language or mixed wording.'}[key]}
                 for key in unanswered[:2]]
    return {'policy': POLICY, 'confirmed_facts': facts,
            'interpretations': subjects, 'hypotheses': [],
            'unanswered_questions': unanswered, 'clarification_questions': questions,
            'open_project_questions': [f['text'] for f in facts if 'uncertainties' in f['kinds']],
            'research_focus': research_focus, 'user_priorities': [{'focus': research_focus,
                'provenance': 'selected_research_scope', 'changes_saved_project': False}],
            'language_context': language_context,
            'subject': subject, 'execution_authorized': False, 'model_call_authorized': False,
            'history_context': {'decision_heads': copy.deepcopy(_heads(state)),
                'evidence': [{'candidate_id': key, 'content_sha256': item.get('content_sha256'),
                              'status': 'saved_source_not_project_fact'} for key,item in state.get('items',{}).items()],
                'evidence_history_count': len(state.get('discovery_evidence_history',[])),
                'briefing_ids': [b.get('id') for b in state.get('briefings',[])]},
            'input_sha256': _digest({'project': project, 'clarifications': clarifications, 'focus': research_focus}),
            'limitations': ['Confirmed facts are attributed user statements, not independently verified claims.',
                           'Offline interpretation uses bounded concepts; unsupported vocabulary needs clarification.',
                           'Architecture, numerical budget and measured bottlenecks remain unknown unless stated.']}


def enrich_plan(state, plan, *, research_focus='general', clarifications=None, language=None):
    """Compose grounded research questions without changing the legacy plan envelope."""
    from project_opportunities import _query_respects_decisions, DOMAINS
    result = copy.deepcopy(plan)
    understanding = understand(state, research_focus=research_focus,
                               clarifications=clarifications, language=language)
    result['understanding'] = understanding
    result['research_focus'] = research_focus
    topics = [t for t in result['queries']+result['queued_topics']
              if _query_respects_decisions(state,t['query'])]
    # New answers may identify needs absent from the original brief. Keep their
    # provenance separate and retain the original plan's saved-context digest.
    for domain, (pattern, _, categories) in DOMAINS.items():
        basis = [f for f in understanding['confirmed_facts'] if (f['field'].startswith('clarifications.')
                 or f['field'] in ('project.needs','project.problems','project.priorities'))
                 and re.search(pattern, f['text'], re.I)
                 and not re.search(r'\b(do not|avoid|exclude)\b', f['text'], re.I)]
        if basis and not any(t['domain'] == domain for t in topics):
            topics.append({'domain': domain, 'score': 40, 'priority': 'high', 'source_categories': list(categories),
                           'basis': basis, 'decision_gap_references': [], 'query': ''})
    subject = understanding['subject']
    focus = FOCUSES[research_focus]
    excluded_focus = any(re.search(r'\b(do not|avoid|exclude|not interested in)\b', f['text'], re.I)
                         and re.search(r'\b'+re.escape(research_focus)+r'\b', f['text'], re.I)
                         for f in understanding['confirmed_facts']) if focus else False
    if excluded_focus:
        understanding['unanswered_questions'].append('focus_conflicts_with_exclusion')
        understanding['clarification_questions'] = [{'id': 'focus_conflict',
            'question': 'Your research focus conflicts with a saved exclusion. Which instruction should apply?',
            'material_reason': 'A focus change cannot silently override a saved constraint.'}]
    if subject and focus and not excluded_focus and not any(t['domain'] == focus for t in topics):
        _, _, categories = INTENTS[focus]
        topics.append({'domain': focus, 'score': 50, 'priority': 'high',
                       'source_categories': categories, 'basis': subject['basis'],
                       'decision_gap_references': [], 'query': ''})
    for topic in topics:
        if topic.get('interpretation') == 'caller_reviewed':
            topic['score'] += 100 if topic['domain'] == focus else 0
            continue  # Preserve the existing reviewed semantic/native-language contract.
        if not subject or not _query_respects_decisions(state, topic['query']):
            continue
        question, suffix, categories = INTENTS[topic['domain']]
        details = [label for pattern,label in DETAILS if any(re.search(pattern,f['text'],re.I)
                   and not re.search(r'\b(do not|avoid|exclude)\b',f['text'],re.I)
                   for f in understanding['confirmed_facts'])]
        audience_details = []
        outcome_details = []
        if topic['domain'] in ('marketing','commercial','product'):
            audience_details = [label for pattern,label in AUDIENCES if any(re.search(pattern,f['text'],re.I)
                        and not re.search(r'\b(do not|avoid|exclude)\b',f['text'],re.I)
                        for f in understanding['confirmed_facts'])]
            # Prefer a specific local audience to its broader overlapping label.
            if 'local customers' in audience_details and 'families' in audience_details:
                audience_details.remove('families')
            outcome_details = [label for pattern,label in OUTCOMES if any(re.search(pattern,f['text'],re.I)
                        and not re.search(r'\b(do not|avoid|exclude)\b',f['text'],re.I)
                        for f in understanding['confirmed_facts'])]
            details += audience_details+outcome_details
        anchor = subject['value']+' '+ ' '.join(d for d in details if d not in subject['value'])
        topic['query'] = (anchor.strip()+' '+suffix)[:500]
        topic['research_question'] = question.format(subject=subject['value'])
        if audience_details:
            topic['research_question'] = topic['research_question'].rstrip('?')+' for '+', '.join(audience_details)+'?'
        if outcome_details:
            topic['research_question'] = topic['research_question'].rstrip('?')+' (desired outcome: '+', '.join(outcome_details)+')?'
        topic['research_targets'] = {'subject':subject['value'], 'capabilities':details,
                                     'audiences':audience_details, 'outcomes':outcome_details}
        topic['interpretation'] = 'offline_composed'
        topic['hypothesis'] = 'Potential improvements are research hypotheses; no benefit or suitability is established.'
        topic['public_query_basis'] = copy.deepcopy(subject['basis'])
        if research_focus == 'funding' and topic['domain'] == 'financial':
            topic['query'] = subject['value']+' funding grants eligibility official program terms'
            topic['research_question'] = 'Which funding programs have documented eligibility relevant to '+subject['value']+'?'
        topic['score'] += 100 if topic['domain'] == focus else 0
    topics.sort(key=lambda t: (-t['score'], t['domain']))
    count = result['limits']['max_queries']
    result['queries'], result['queued_topics'] = topics[:count], topics[count:]
    # Never offer generic legacy strings when the project cannot be interpreted.
    if understanding['clarification_questions'] and not any(t.get('interpretation') == 'caller_reviewed' for t in topics):
        result['queries'] = []
        result['queued_topics'] = []
        result['status'] = ('needs_semantic_interpretation' if not understanding['language_context']['english_rules_available']
                            else 'needs_project_clarification')
    elif result['queries']:
        result['status'] = 'ready_for_review'
    else:
        result['status'] = 'needs_project_clarification'
    understanding['hypotheses'] = [{'text': t['hypothesis'], 'research_question': t['research_question'],
                                    'status': 'unverified', 'basis': t['basis']}
                                   for t in topics if 'hypothesis' in t]
    return result


def prepare_research(state, *, research_focus=None, clarifications=None,
                     language=None, semantic_topics=(), max_queries=2,
                     results_per_query=5, max_source_pages=4):
    """Phase 2F entry point. An answer/focus change returns a new preview only.

    No new interpretation transport is added: previously reviewed semantic topics
    (including native-language queries) are validated by the Phase 2 planner.
    """
    from project_opportunities import plan_discovery, _digest
    if research_focus is None:
        research_focus = state['project'].get('research_focus', 'general')
        if research_focus == 'general':
            # Explicit saved priorities can select a focus; mentions alone cannot.
            match = re.search(r'\b(?:priority|focus)\s*:\s*(marketing|sales|technology|product development|funding|operations)\b',
                              state['project']['brief'], re.I)
            if match: research_focus = match[1].lower()
    context = understand(state,research_focus=research_focus,clarifications=clarifications,language=language)
    effective_language = language or ('en' if context['language_context']['english_rules_available'] else None)
    plan = plan_discovery(state, max_queries=max_queries, results_per_query=results_per_query,
                          max_source_pages=max_source_pages, language=effective_language,
                          semantic_topics=semantic_topics)
    result = enrich_plan(state, plan, research_focus=research_focus,
                         clarifications=clarifications, language=language)
    result['language_context'] = {**result['understanding']['language_context'],
        'semantic_interpretation': 'caller_reviewed_topics' if semantic_topics else 'not_provided'}
    if semantic_topics and result['queries']:
        # Reviewed interpretations can resolve language ambiguity, not constraints.
        u = result['understanding']
        u['interpretations'] += [{'query': t['query'], 'basis': copy.deepcopy(t['basis']),
                                 'status': 'caller_reviewed_interpretation'}
                                for t in result['queries']+result['queued_topics']
                                if t.get('interpretation') == 'caller_reviewed']
        resolved = {'language','subject'}
        if any('goals' in f['kinds'] for f in u['confirmed_facts']): resolved.add('outcome')
        u['clarification_questions'] = [q for q in u['clarification_questions'] if q['id'] not in resolved]
        u['unanswered_questions'] = [q for q in u['unanswered_questions'] if q not in resolved]
    if result['understanding']['clarification_questions']:
        result['status'] = ('needs_semantic_interpretation' if 'language' in result['understanding']['unanswered_questions']
                            else 'needs_project_clarification')
    result['research_context'] = {'research_focus': research_focus,
                                  'clarifications': copy.deepcopy(clarifications or {}),
                                  'language': language, 'semantic_topics': copy.deepcopy(list(semantic_topics))}
    result['research_context_sha256'] = _digest(result['research_context'])
    result['understanding_policy'] = POLICY
    return result
