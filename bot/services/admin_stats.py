from decimal import Decimal

from bot.db.admin_queries import AdminDashboardStats
from bot.texts.messages import MONTH_NAMES_RU, format_money


def _pct(value: Decimal) -> str:
    return f"{value.quantize(Decimal('0.1'))}%"


def _num(value: Decimal) -> str:
    return f"{value.quantize(Decimal('0.01'))}"


def _format_top_list(items: list[tuple[str, Decimal]]) -> str:
    if not items:
        return "  — нет данных"
    lines = []
    for i, (name, amount) in enumerate(items, 1):
        lines.append(f"  {i}. {name}: <b>{format_money(amount)}</b>")
    return "\n".join(lines)


def format_admin_dashboard(stats: AdminDashboardStats) -> str:
    ts = stats.generated_at.strftime("%d.%m.%Y %H:%M")
    month_name = MONTH_NAMES_RU[stats.generated_at.month]
    peak = (
        f"{stats.peak_day.strftime('%d.%m.%Y')} ({stats.peak_day_count} оп.)"
        if stats.peak_day
        else "—"
    )
    top_cat = (
        f"{stats.top_category_name} ({stats.top_category_count} оп.)"
        if stats.top_category_name
        else "—"
    )

    return (
        f"👑 <b>Панель администратора</b>\n"
        f"<i>Обновлено: {ts}</i>\n"
        f"<i>Период для блока «Операции»: {stats.period_label}</i>\n\n"
        f"👥 <b>Пользователи</b>\n"
        f"• Всего: <b>{stats.users_total}</b>\n"
        f"• Новые сегодня: <b>{stats.users_new_today}</b>\n"
        f"• Новые за 7 / 30 дн.: <b>{stats.users_new_7d}</b> / <b>{stats.users_new_30d}</b>\n"
        f"• С часовым поясом: <b>{stats.users_with_tz}</b>\n"
        f"• Прошли ознакомление: <b>{stats.users_welcome_seen}</b>\n"
        f"• Без транзакций: <b>{stats.users_no_transactions}</b>\n"
        f"• Активные за 7 / 30 дн.: <b>{stats.users_active_7d}</b> / "
        f"<b>{stats.users_active_30d}</b>\n\n"
        f"💳 <b>Операции</b>\n"
        f"• Всего в БД: <b>{stats.tx_total}</b>\n"
        f"• За сегодня / 7 / 30 дн.: <b>{stats.tx_today}</b> / "
        f"<b>{stats.tx_7d}</b> / <b>{stats.tx_30d}</b>\n"
        f"• За период ({stats.period_label}): <b>{stats.tx_period}</b>\n"
        f"• Расходы / доходы (шт.): <b>{stats.tx_expense_period}</b> / "
        f"<b>{stats.tx_income_period}</b>\n"
        f"• Сумма расходов: <b>{format_money(stats.sum_expense_period)}</b>\n"
        f"• Сумма доходов: <b>{format_money(stats.sum_income_period)}</b>\n"
        f"• Средняя сумма операции: <b>{format_money(stats.avg_tx_amount_period)}</b>\n"
        f"• Среднее оп. на активного пользователя: <b>{_num(stats.avg_tx_per_user_period)}</b>\n"
        f"• Пиковый день (все время): <b>{peak}</b>\n\n"
        f"📂 <b>Категории</b> ({month_name})\n"
        f"<b>Топ-5 расходов (месяц):</b>\n{_format_top_list(stats.top_expense_month)}\n"
        f"<b>Топ-5 расходов (всё время):</b>\n{_format_top_list(stats.top_expense_all)}\n"
        f"<b>Топ-5 доходов (месяц):</b>\n{_format_top_list(stats.top_income_month)}\n"
        f"<b>Топ-5 доходов (всё время):</b>\n{_format_top_list(stats.top_income_all)}\n"
        f"• Самая частая категория ({stats.period_label}): <b>{top_cat}</b>\n\n"
        f"🎯 <b>Цели</b>\n"
        f"• Всего: <b>{stats.goals_total}</b>\n"
        f"• Активные / завершённые: <b>{stats.goals_active}</b> / "
        f"<b>{stats.goals_completed}</b>\n"
        f"• Создано за 7 / 30 дн.: <b>{stats.goals_created_7d}</b> / "
        f"<b>{stats.goals_created_30d}</b>\n"
        f"• Средний прогресс активных: <b>{_pct(stats.goals_avg_progress_pct)}</b>\n"
        f"• Сумма накоплений: <b>{format_money(stats.goals_sum_saved)}</b>\n"
        f"• Пользователей с целями: <b>{stats.goals_users_count}</b>\n\n"
        f"💵 <b>Балансы (агрегат)</b>\n"
        f"• Суммарный общий баланс: <b>{format_money(stats.balance_sum)}</b>\n"
        f"• Средний у пользователей с операциями: "
        f"<b>{format_money(stats.balance_avg)}</b>\n"
        f"• С отрицательным балансом: <b>{stats.balance_negative_users}</b>\n\n"
        f"📈 <b>Использование</b>\n"
        f"• С операциями в текущем месяце: <b>{stats.users_with_tx_month}</b>\n"
        f"• Доля пользователей с целями: <b>{_pct(stats.users_with_goals_pct)}</b>\n"
        f"• Среднее целей на пользователя (с целями): "
        f"<b>{_num(stats.goals_avg_per_user)}</b>"
    )
