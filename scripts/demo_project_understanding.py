"""Read-only Phase 2F demos. No transports, credentials, writes or model calls."""
import argparse
import json
from pathlib import Path

from project_understanding import prepare_research
from project_workflow import Projects


def summary(label, plan):
    u = plan['understanding']
    return {'demo': label, 'project_version': plan['project_version'], 'status': plan['status'],
            'focus': plan['research_focus'], 'questions': u['clarification_questions'],
            'queries': [{k:t[k] for k in ('domain','research_question','query','source_categories') if k in t}
                        for t in plan['queries']+plan['queued_topics']],
            'decision_count': len(u['history_context']['decision_heads']),
            'execution_authorized': plan['execution_authorized']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--memory-root', type=Path)
    parser.add_argument('--project-id')
    args = parser.parse_args()
    if bool(args.memory_root) != bool(args.project_id):
        parser.error('Supply both --memory-root and --project-id, or neither.')
    vague = {'project': {'id':'project-demo', 'name':'Business idea',
                        'brief':'I have a small business and want help.'},
             'version':0, 'items':{}, 'briefings':[], 'decisions':[]}
    demos = [summary('Vague marketing project', prepare_research(vague,research_focus='marketing')),
             summary('Marketing after ephemeral clarification', prepare_research(vague,research_focus='marketing',
                 clarifications={'subject':'A bakery serving local families.',
                                 'outcome':'Increase visits from local customers.'}))]
    if args.project_id:
        saved = Projects(args.memory_root).read(args.project_id)
        demos.append(summary(saved['project']['name'],prepare_research(saved,max_queries=1)))
    print(json.dumps(demos,ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
