from aiogram import Router

from bot.handlers import (
    admin,
    admin_broadcast,
    admin_users,
    broadcast,
    cancel,
    fsm_reprompt,
    goals,
    onboarding,
    screenshot_import,
    start,
    stats,
    transaction,
    welcome,
)


def setup_routers() -> Router:
    root = Router()
    root.include_router(onboarding.router)
    root.include_router(welcome.router)
    root.include_router(start.router)
    root.include_router(cancel.router)
    root.include_router(admin.router)
    root.include_router(admin_broadcast.router)
    root.include_router(admin_users.router)
    root.include_router(broadcast.router)
    root.include_router(transaction.router)
    root.include_router(screenshot_import.router)
    root.include_router(goals.router)
    root.include_router(stats.router)
    root.include_router(fsm_reprompt.router)
    return root
