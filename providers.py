"""Provider adapters and explicit .env loading; no agent framework required."""
import argparse
import json
import os
from pathlib import Path
import re
import threading
import time
import urllib.error
import urllib.request

CONFIG = {
    'openai': ('OPENAI_API_KEY', 'https://api.openai.com/v1/chat/completions'),
    'gemini': ('GEMINI_API_KEY', 'https://generativelanguage.googleapis.com/v1beta/openai/chat/completions'),
    'openrouter': ('OPENROUTER_API_KEY', 'https://openrouter.ai/api/v1/chat/completions'),
    'deepseek': ('DEEPSEEK_API_KEY', 'https://api.deepseek.com/chat/completions'),
    'byteplus': ('ARK_API_KEY', 'https://ark.ap-southeast.bytepluses.com/api/v3/chat/completions'),
    'groq': ('GROQ_API_KEY', 'https://api.groq.com/openai/v1/chat/completions'),
    'anthropic': ('ANTHROPIC_API_KEY', 'https://api.anthropic.com/v1/messages'),
}

CONFIG_NAMES = {
    'PROVIDER', 'MODEL', 'OPENAI_API_KEY', 'GEMINI_API_KEY',
    'ANTHROPIC_API_KEY', 'OPENROUTER_API_KEY', 'DEEPSEEK_API_KEY', 'ARK_API_KEY', 'GROQ_API_KEY',
    'JUDGE_PROVIDER', 'JUDGE_MODEL', 'STATUS_USER_AGENT',
}


def load_env_file(path):
    settings = {}
    for number, line in enumerate(Path(path).read_text(encoding='utf-8-sig').splitlines(), 1):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        match = re.fullmatch(r'(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)', line)
        if not match:
            raise ValueError(f'Invalid .env assignment at line {number}.')
        name, value = match.groups()
        value = value.strip()
        if value.startswith(('"', "'")):
            if len(value) < 2 or value[-1] != value[0]:
                raise ValueError(f'Unclosed .env quote at line {number}.')
            value = value[1:-1]
        else:
            value = value.split(' #', 1)[0].rstrip()
        if name in CONFIG_NAMES:
            settings[name] = value
    # Explicit --env-file overrides stale terminal settings after full validation.
    os.environ.update(settings)


def load_env_from_cli(argv=None):
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--env-file')
    args, _ = parser.parse_known_args(argv)
    if args.env_file:
        load_env_file(args.env_file)


_request_interval = 0.0
_last_request_at = None
_request_lock = threading.Lock()
_groq_tokens_ready_at = 0.0


def configure_request_interval(seconds):
    """Apply one shared delay to agent and judge requests during an eval."""
    global _request_interval, _last_request_at
    if seconds < 0:
        raise ValueError('Request interval must be non-negative.')
    _request_interval = seconds
    _last_request_at = None


def _wait_for_request_slot(url):
    global _last_request_at
    with _request_lock:
        ready_at = _groq_tokens_ready_at if url == CONFIG['groq'][1] else 0.0
        if _last_request_at is not None:
            ready_at = max(ready_at, _last_request_at + _request_interval)
        delay = ready_at - time.monotonic()
        if delay > 0:
            time.sleep(delay)
        _last_request_at = time.monotonic()


def _remember_groq_token_reset(url, headers):
    """Wait for the token bucket to refill; no hidden retries or extra API calls."""
    global _groq_tokens_ready_at
    if url != CONFIG['groq'][1] or headers is None:
        return
    value = headers.get('x-ratelimit-reset-tokens', '')
    if not isinstance(value, str):
        return
    parts = re.findall(r'([0-9]+(?:\.[0-9]+)?)(ms|h|m|s)', value)
    if not parts or ''.join(number + unit for number, unit in parts) != value:
        return
    seconds = sum(float(number) * {'ms': .001, 's': 1, 'm': 60, 'h': 3600}[unit]
                  for number, unit in parts)
    with _request_lock:
        _groq_tokens_ready_at = max(_groq_tokens_ready_at, time.monotonic() + seconds + .25)


def _rate_limit_details(exc):
    """Extract quota IDs, numeric limits and retry delays, never raw error text."""
    parts = []
    retry_after = exc.headers.get('Retry-After', '') if exc.headers else ''
    if re.fullmatch(r'[0-9]{1,10}', retry_after):
        parts.append(f'retry_after={retry_after}s')
    try:
        body = json.loads(exc.read(65536))
    except (ValueError, OSError):
        return '; '.join(parts)
    # Gemini's compatibility endpoint can wrap its error object in a list.
    if isinstance(body, list):
        body = next((item for item in body if isinstance(item, dict)
                     and isinstance(item.get('error'), dict)), {})
    error = body.get('error', {}) if isinstance(body, dict) else {}
    message = error.get('message', '') if isinstance(error, dict) else ''
    if isinstance(message, str):
        for limit_type in ('TPD', 'RPD', 'ITPM', 'OTPM', 'TPM', 'RPM'):
            if re.search(r'\b' + limit_type + r'\b', message, re.IGNORECASE):
                parts.append(f'limit_type={limit_type}')
                for field in ('limit', 'used', 'requested'):
                    match = re.search(r'\b' + field + r'\s*[:=]?\s*([0-9]{1,20})(?![0-9])', message, re.IGNORECASE)
                    if match:
                        parts.append(f'{field}={match.group(1)}')
                break
    if isinstance(error, dict) and error.get('status') == 'RESOURCE_EXHAUSTED':
        parts.append('status=RESOURCE_EXHAUSTED')
    details = error.get('details', []) if isinstance(error, dict) else []
    if not isinstance(details, list):
        return '; '.join(parts)
    for detail in details[:10]:
        if not isinstance(detail, dict):
            continue
        if detail.get('@type') == 'type.googleapis.com/google.rpc.RetryInfo':
            delay = detail.get('retryDelay')
            if isinstance(delay, str) and re.fullmatch(r'[0-9]{1,10}(?:\.[0-9]{1,9})?s', delay):
                parts.append(f'retry_after={delay}')
        if detail.get('@type') != 'type.googleapis.com/google.rpc.QuotaFailure':
            continue
        violations = detail.get('violations', [])
        if not isinstance(violations, list):
            continue
        for violation in violations[:5]:
            if not isinstance(violation, dict):
                continue
            quota_id = violation.get('quotaId')
            if not isinstance(quota_id, str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,159}', quota_id):
                continue
            text = f'quota={quota_id}'
            value = violation.get('quotaValue')
            if isinstance(value, (str, int)) and re.fullmatch(r'[0-9]{1,20}', str(value)):
                text += f', limit={value}'
            parts.append(text)
    if parts == ['status=RESOURCE_EXHAUSTED']:
        parts.append('quota_details=not_provided')
    return '; '.join(parts)


def _routing_error_details(exc):
    """Classify a routing failure without exposing response text or metadata."""
    try:
        body = json.loads(exc.read(65536))
    except (ValueError, OSError):
        return ''
    error = body.get('error', {}) if isinstance(body, dict) else {}
    code = error.get('code') if isinstance(error, dict) else None
    ark_errors = {
        'ModelNotOpen': 'reason=ModelNotOpen; activate the model in BytePlus ModelArk before calling it.',
        'InvalidEndpointOrModel.ModelIDAccessDisabled': 'reason=ModelIDAccessDisabled; set MODEL to your authorized BytePlus endpoint ID (ep-...).',
        'InvalidEndpointOrModel.NotFound': 'reason=EndpointOrModelNotFound; check the BytePlus model/endpoint ID, activation and access permissions.',
    }
    if isinstance(code, str) and code in ark_errors:
        return ark_errors[code]
    text = error.get('message', '') if isinstance(error, dict) else ''
    if not isinstance(text, str):
        return ''
    text = text.casefold()
    if 'data policy' in text or 'privacy' in text:
        return 'reason=data_policy; review=https://openrouter.ai/settings/privacy'
    if 'tool' in text and ('no endpoints' in text or 'not support' in text):
        return 'reason=tool_calling_unavailable; choose a model endpoint that supports tools.'
    if 'no endpoints' in text or 'no available' in text:
        return 'reason=no_available_endpoints; choose a model with active endpoints.'
    if 'not a valid model' in text or 'model not found' in text:
        return 'reason=model_not_found; check the full provider/model ID.'
    return ''


def post_json(url, headers, payload):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                 headers={'Content-Type': 'application/json',
                                          'User-Agent': 'StatusInvestigationAgent/1.0', **headers})
    _wait_for_request_slot(url)
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            _remember_groq_token_reset(url, getattr(response, 'headers', None))
            data = json.load(response)
    except urllib.error.HTTPError as exc:
        _remember_groq_token_reset(url, exc.headers)
        # Extract only known diagnostic fields; never print the raw body.
        message = f'Provider tra HTTP {exc.code}; kiem tra model, key va quota.'
        if exc.code == 401:
            message = 'Provider tra HTTP 401; API key bi tu choi.'
            if url == CONFIG['deepseek'][1]:
                message += (' Kiem tra DEEPSEEK_API_KEY trong file --env-file;'
                            ' lay key tai https://platform.deepseek.com/api_keys roi luu file.')
            elif url == CONFIG['byteplus'][1]:
                message += (' Kiem tra ARK_API_KEY trong file --env-file;'
                            ' dung key BytePlus ModelArk khu vuc ap-southeast-1.')
            elif url == CONFIG['groq'][1]:
                message += (' Kiem tra GROQ_API_KEY trong file --env-file;'
                            ' lay key tai https://console.groq.com/keys roi luu file.')
        elif exc.code == 402:
            message = 'Provider tra HTTP 402; tai khoan API khong du so du.'
        elif exc.code == 429 and url == CONFIG['groq'][1]:
            message = 'Groq tra HTTP 429; cham han muc request/token. Kiem tra https://console.groq.com/settings/limits.'
        details = _rate_limit_details(exc) if exc.code == 429 else _routing_error_details(exc) if exc.code == 404 else ''
        if details:
            message += ' ' + details
        raise RuntimeError(message) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f'Khong ket noi duoc provider: {exc.reason}') from exc
    if isinstance(data, dict) and isinstance(data.get('error'), dict):
        code = data['error'].get('code', 'unknown')
        code = code if type(code) is int else 'unknown'
        raise RuntimeError(f'Provider returned an error response (HTTP {code}); no answer generated.')
    return data


class Provider:
    """complete(messages, schemas) -> {message, calls, finish, usage}.

    messages: system/user/assistant/tool theo format Chat Completions. message trả về
    cần được append nguyên vẹn; tool result có role, tool_call_id, content (JSON string).
    """
    def __init__(self, name, model):
        if name not in CONFIG:
            raise ValueError(f'Provider không hợp lệ: {name}')
        if not model:
            raise ValueError('Cần đặt MODEL là model có hỗ trợ tool calling.')
        self.name, self.model = name, model
        key_name, self.url = CONFIG[name]
        self.key = os.getenv(key_name)
        if not self.key or self.key.startswith('YOUR_'):
            raise ValueError(f'Thiếu {key_name}; xem README.md.')

    def complete(self, messages, schemas):
        if self.name == 'anthropic':
            return self._anthropic(messages, schemas)
        payload = {'model': self.model, 'messages': messages}
        if self.name in ('deepseek', 'byteplus'):
            # Keep agent and judge requests bounded, using standard tool calls.
            payload['thinking'] = {'type': 'disabled'}
            payload['max_tokens'] = 4096
        elif self.name == 'groq':
            payload['max_completion_tokens'] = 4096
        if schemas:
            payload['tools'] = schemas
        data = post_json(self.url, {'Authorization': f'Bearer {self.key}'}, payload)
        choice = data['choices'][0]
        message = choice['message']
        calls = [{'id': c['id'], 'name': c['function']['name'], 'arguments': c['function']['arguments']} for c in message.get('tool_calls', [])]
        return {'message': message, 'calls': calls, 'finish': choice.get('finish_reason'), 'usage': data.get('usage', {})}

    def _anthropic(self, messages, schemas):
        system = '\n'.join(m['content'] for m in messages if m['role'] == 'system')
        native = []
        for m in messages:
            if m['role'] == 'system':
                continue
            if m['role'] == 'assistant':
                blocks = []
                if m.get('content'):
                    blocks.append({'type': 'text', 'text': m['content']})
                for call in m.get('tool_calls', []):
                    blocks.append({'type': 'tool_use', 'id': call['id'], 'name': call['function']['name'], 'input': json.loads(call['function']['arguments'])})
                native.append({'role': 'assistant', 'content': blocks})
            elif m['role'] == 'tool':
                block = {'type': 'tool_result', 'tool_use_id': m['tool_call_id'], 'content': m['content']}
                if native and native[-1]['role'] == 'user' and isinstance(native[-1]['content'], list):
                    native[-1]['content'].append(block)
                else:
                    native.append({'role': 'user', 'content': [block]})
            else:
                native.append({'role': 'user', 'content': m['content']})
        tools = [{'name': x['function']['name'], 'description': x['function']['description'], 'input_schema': x['function']['parameters']} for x in schemas]
        payload = {'model': self.model, 'max_tokens': 1024, 'system': system, 'messages': native}
        if tools:
            payload['tools'] = tools
        data = post_json(self.url, {'x-api-key': self.key, 'anthropic-version': '2023-06-01'}, payload)
        blocks = data['content']
        calls = [{'id': b['id'], 'name': b['name'], 'arguments': json.dumps(b['input'], ensure_ascii=False)} for b in blocks if b['type'] == 'tool_use']
        text = '\n'.join(b['text'] for b in blocks if b['type'] == 'text')
        message = {'role': 'assistant', 'content': text or None}
        if calls:
            message['tool_calls'] = [{'id': c['id'], 'type': 'function', 'function': {'name': c['name'], 'arguments': c['arguments']}} for c in calls]
        reason = {'end_turn': 'stop', 'tool_use': 'tool_calls', 'max_tokens': 'length'}.get(data.get('stop_reason'), data.get('stop_reason'))
        return {'message': message, 'calls': calls, 'finish': reason, 'usage': data.get('usage', {})}
