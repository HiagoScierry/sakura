"""Texto das mensagens (HTML suportado pelo Telegram)."""
from datetime import datetime, timedelta
from html import escape

from chalicelib.monitoring.models.dashboard import ServiceOverview
from chalicelib.monitoring.models.events import ServiceRecovered, ServiceWentDown
from chalicelib.notification.models import DailyReport
from chalicelib.notification.rules import DailyReportPolicy
from chalicelib.shared.clock import BRASILIA


def service_went_down(event: ServiceWentDown) -> str:
    check = event.check
    lines = [
        f'🔴 <b>{escape(event.name)} está fora do ar</b>',
        '',
        f'<b>Tipo:</b> {event.kind}',
        f'<b>Motivo:</b> {escape(check.reason or "desconhecido")}',
    ]
    if check.http_status is not None:
        lines.append(f'<b>HTTP:</b> {check.http_status}')
    lines += [
        f'<b>Latência:</b> {check.latency_ms} ms',
        f'<b>Detectado:</b> {local_time(check.checked_at)}',
    ]
    return '\n'.join(lines)


def service_recovered(event: ServiceRecovered) -> str:
    return '\n'.join([
        f'🟢 <b>{escape(event.name)} voltou a funcionar</b>',
        '',
        f'<b>Tipo:</b> {event.kind}',
        f'<b>Ficou fora por:</b> {duration(event.downtime)}',
        f'<b>Latência:</b> {event.check.latency_ms} ms',
        f'<b>Recuperado:</b> {local_time(event.check.checked_at)}',
    ])


def daily_report(report: DailyReport) -> str:
    match DailyReportPolicy.situation(report):
        case 'nothing_monitored':
            return '⚪ <b>Monitor ativo</b>\n\nNenhum serviço habilitado para monitorar.'
        case 'all_up':
            lines = ['✅ <b>Monitor: tudo rodando</b>', '',
                     f'{DailyReportPolicy.up_count(report)} serviço(s) verificados e no ar.']
        case 'some_down':
            lines = [f'⚠️ <b>Monitor: {len(report.down)} de {len(report.monitored)} serviço(s) fora do ar</b>', '']
            lines += [_down_line(s, report.generated_at) for s in report.down]

    if report.never_checked:
        lines += ['', f"⏳ Ainda sem verificação: {', '.join(escape(s.name) for s in report.never_checked)}"]
    lines += ['', f'<i>{local_time(report.generated_at)}</i>']
    return '\n'.join(lines)


def _down_line(service: ServiceOverview, now: datetime) -> str:
    line = f'🔴 <b>{escape(service.name)}</b> ({service.kind})'
    if service.health is None:
        return line
    reason = escape(service.health.reason or 'desconhecido')
    return f'{line}: {reason} · fora há {duration(now - service.health.since)}'


def local_time(moment: datetime) -> str:
    return moment.astimezone(BRASILIA).strftime('%d/%m/%Y %H:%M') + ' (Brasília)'


def duration(delta: timedelta) -> str:
    minutes = max(int(delta.total_seconds() // 60), 0)
    days, minutes = divmod(minutes, 1440)
    hours, minutes = divmod(minutes, 60)
    parts = [f'{days}d' if days else '', f'{hours}h' if hours else '',
             f'{minutes}min' if minutes or not (days or hours) else '']
    return ' '.join(p for p in parts if p)
