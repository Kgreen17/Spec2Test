import json
from pipeline.test_generator import generator_agent as gen


def test_generate_test_plan_happy_path(monkeypatch):
    # Mock the _call_openai_chat to return a pre-built successful response
    def fake_call(system_prompt, user_prompt, model='gpt-4o', max_tokens=1024, temperature=0.0):
        out = {
            'choices': [
                {'message': {'content': json.dumps({
                    'test_name': 'Login - happy path',
                    'description': 'happy login',
                    'steps': [
                        {'id': 1, 'action': 'navigate', 'target': 'https://example.com/login'},
                        {'id': 2, 'action': 'fill', 'target': '#username', 'value': 'user'},
                        {'id': 3, 'action': 'fill', 'target': '#password', 'value': 'pass'},
                        {'id': 4, 'action': 'click', 'target': '#submit'},
                        {'id': 5, 'action': 'assert', 'target': '#welcome', 'expected': 'Welcome'}
                    ]
                })}}
            ],
            'usage': {'prompt_tokens': 10, 'completion_tokens': 50, 'total_tokens': 60}
        }
        return out

    monkeypatch.setattr(gen, '_call_openai_chat', fake_call)

    context = "Login page contains input id=\'username\' and id=\'password\' and button id=\'submit\'."
    res = gen.generate_test_plan(context, 'verify login', max_steps=10)
    assert 'plan' in res
    assert res['plan']['test_name'] == 'Login - happy path'
    assert len(res['plan']['steps']) == 5


def test_generate_test_plan_parse_error(monkeypatch):
    def fake_call_bad(system_prompt, user_prompt, model='gpt-4o', max_tokens=1024, temperature=0.0):
        return {'choices': [{'message': {'content': 'I cannot help with that right now.'}}]}

    monkeypatch.setattr(gen, '_call_openai_chat', fake_call_bad)

    context = "Login page contains input id=\'username\' and id=\'password\'."
    res = gen.generate_test_plan(context, 'verify login', max_steps=5)
    assert 'error' in res
    assert res['error'] in ('parse_error', 'validation_failed')

