"""Chạy và chấm eval. expected chỉ cung cấp cho judge, không gửi cho agent."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from functools import partial
import json
import os
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent import run_agent
from providers import CONFIG, Provider, configure_request_interval, load_env_from_cli
from scenarios import ScenarioTools
from grading import grade_case, summarize, bonus_points
from bonus.tools import BonusTools


def run_case(case, args):
    saved = getattr(args, '_resume_results', {}).get(case['id'], {})
    result = saved.get('result', {})
    if result.get('status') != 'completed':
        try:
            agent = partial(run_agent, validate_sources=False) if getattr(args, 'baseline', False) else run_agent
            result = agent(case['question'], Provider(args.provider, args.model),
                           (BonusTools('snapshot', scenario=case.get('scenario', 'normal')) if getattr(args, 'bonus', False) else ScenarioTools(case.get('scenario', 'normal'), case.get('fail', False))), max_steps=args.max_steps)
        except Exception as exc:
            result = {'status': 'error', 'answer': '', 'trace': [], 'usage': [], 'error': f'{type(exc).__name__}: {str(exc)[:200]}'}
    if not isinstance(result, dict) or not isinstance(result.get('trace', []), list):
        result = {'status': 'error', 'answer': '', 'trace': [], 'usage': [], 'error': 'run_agent trả kết quả không hợp lệ.'}
    try:
        judge = Provider(args.judge_provider, args.judge_model)
        grade = grade_case(case, result, judge)
    except Exception as exc:
        grade = {'score': None, 'status': 'unscored', 'reason': str(exc), 'judge_usage': {}}
    return {'id': case['id'], 'question': case['question'], 'expected': case['expected'],
            'scenario': case.get('scenario', 'normal'), 'provider': args.provider, 'model': args.model,
            'judge_provider': args.judge_provider, 'judge_model': args.judge_model, 'result': result, 'grade': grade}


def main():
    try:
        load_env_from_cli()
    except (OSError, ValueError) as exc:
        print(f'Lỗi cấu hình: {exc}', file=sys.stderr)
        return 1
    parser = argparse.ArgumentParser(description='Chạy agent và chấm eval 0–100')
    parser.add_argument('--env-file', help='Read configuration before resolving provider/model defaults')
    choices = list(CONFIG)
    parser.add_argument('--provider', choices=choices, default=os.getenv('PROVIDER', 'openai'))
    parser.add_argument('--model', default=os.getenv('MODEL'))
    parser.add_argument('--judge-provider', choices=choices, default=os.getenv('JUDGE_PROVIDER'))
    parser.add_argument('--judge-model', default=os.getenv('JUDGE_MODEL'))
    parser.add_argument('--bonus', action='store_true', help='Chạy bộ bonus riêng; không ảnh hưởng điểm chính')
    parser.add_argument('--case', help='Ví dụ E2 hoặc H1; bỏ trống để chạy toàn bộ')
    parser.add_argument('--max-steps', type=int, default=None, help='Giới hạn model calls mỗi case: mặc định 8, bonus 16')
    parser.add_argument('--workers', type=int, default=1, help='Số case chạy đồng thời (mặc định 1)')
    parser.add_argument('--baseline', action='store_true', help='Chạy bản trước cải tiến: tắt riêng kiểm tra URL nguồn')
    parser.add_argument('--resume', action='store_true', help='Tiếp tục file output, giữ nguyên các case đã chấm')
    parser.add_argument('--request-interval', type=float, default=3.2,
                        help='Khoảng cách tối thiểu giữa các lần gọi agent/judge, mặc định 3.2 giây')
    parser.add_argument('--output', default='eval_results.json')
    args = parser.parse_args()
    args.judge_provider = args.judge_provider or args.provider
    args.judge_model = args.judge_model or args.model
    if not args.model or not args.judge_model:
        parser.error('Thiếu --model hoặc MODEL')
    args.max_steps = args.max_steps if args.max_steps is not None else (16 if args.bonus else 8)
    if args.max_steps < 1 or not 1 <= args.workers <= 8 or args.request_interval < 0:
        parser.error('--max-steps >= 1, --workers từ 1 đến 8, --request-interval >= 0')
    cases_path = (Path(__file__).resolve().parents[1] / 'bonus' / 'cases.json') if args.bonus else (Path(__file__).parent / 'cases.json')
    cases = json.loads(cases_path.read_text(encoding='utf-8'))
    selected = [c for c in cases if not args.case or c['id'] == args.case.upper()]
    if not selected:
        parser.error('Không tìm thấy case')
    config = {'provider': args.provider, 'model': args.model,
              'judge_provider': args.judge_provider, 'judge_model': args.judge_model,
              'max_steps': args.max_steps, 'dataset': 'bonus' if args.bonus else 'core',
              'request_interval': args.request_interval}
    version = 'baseline' if args.baseline else 'improved'
    output = Path(args.output)
    args._resume_results = {}
    if args.resume:
        try:
            saved = json.loads(output.read_text(encoding='utf-8'))
        except (OSError, ValueError) as exc:
            parser.error(f'Không đọc được file để resume: {exc}')
        if saved.get('config') != config or saved.get('agent_version') != version:
            parser.error('File resume khác cấu hình hoặc khác phiên bản agent; giữ đúng --baseline/model/max-steps.')
        current = {c['id']: c for c in selected}
        for item in saved.get('cases', []):
            case = current.get(item['id'])
            if case is None or item.get('question') != case['question'] or item.get('expected') != case['expected']:
                parser.error('File resume không cùng tập case hoặc dữ liệu đề đã thay đổi.')
            args._resume_results[item['id']] = item

    results_by_id = dict(args._resume_results)
    todo = [c for c in selected if results_by_id.get(c['id'], {}).get('grade', {}).get('status') != 'scored']
    configure_request_interval(args.request_interval)
    stop_reason = None

    def pending_case(case):
        return {'id': case['id'], 'question': case['question'], 'expected': case['expected'],
                'result': {'status': 'pending', 'answer': '', 'trace': [], 'usage': []},
                'grade': {'score': None, 'status': 'unscored', 'reason': 'Chưa chạy case này.', 'judge_usage': {}}}

    def checkpoint():
        results = [results_by_id.get(c['id'], pending_case(c)) for c in selected]
        summary = summarize(results)
        if args.bonus:
            summary['bonus_points_0_15'] = bonus_points(
                summary['score_0_100'], not args.case and len(selected) == len(cases))
        report = {'summary': summary, 'config': config, 'agent_version': version,
                  'progress': {'complete': summary['scored_cases'] == len(selected),
                               'scored_cases': summary['scored_cases'], 'total_cases': len(selected),
                               'stop_reason': stop_reason}, 'cases': results}
        temporary = output.with_name(output.name + '.tmp')
        temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        temporary.replace(output)
        return report

    def run_and_print(case):
        print(f"Đang chạy {case['id']}", flush=True)
        item = run_case(case, args)
        print(f"{case['id']}: {item['grade'].get('score')} ({item['grade']['status']})", flush=True)
        return item
    pool = None
    try:
        items = (run_and_print(c) for c in todo)
        if args.workers > 1:
            pool = ThreadPoolExecutor(max_workers=args.workers)
            items = pool.map(run_and_print, todo)
        checkpoint()
        for item in items:
            results_by_id[item['id']] = item
            # Stop on provider errors rather than spending the remaining quota on failing cases.
            error = item.get('result', {}).get('error', '') + ' ' + item.get('grade', {}).get('reason', '')
            if item.get('result', {}).get('status') == 'error' or any(
                    f'HTTP {code}' in error for code in (401, 402, 403, 404, 429, 500, 502, 503, 504)):
                stop_reason = 'Provider gặp lỗi; kết quả đã lưu. Khắc phục rồi chạy lại với --resume.'
            checkpoint()
            if stop_reason:
                print(error.strip()[:800], file=sys.stderr)
                print(stop_reason, file=sys.stderr)
                break
    except KeyboardInterrupt:
        stop_reason = 'Đã dừng bằng Ctrl+C; dùng --resume để tiếp tục.'
        checkpoint()
        return 130
    finally:
        if pool is not None:
            pool.shutdown(wait=True, cancel_futures=True)
        configure_request_interval(0)
    report = checkpoint()
    summary = report['summary']
    if args.bonus:
        print(f"Điểm bonus tham khảo: {summary['bonus_points_0_15']}/15 (chỉ tính khi chấm đủ toàn bộ case).")
    print(f"Điểm: {summary['score_0_100']}/100; đã chấm {summary['scored_cases']}/{summary['total_cases']} case. File: {args.output}")
    if summary['score_0_100'] is None:
        print('Chưa có điểm tổng do có case chưa được chấm; xem reason trong file.', file=sys.stderr)
        return 1
    return 0

if __name__ == '__main__':
    sys.exit(main())
