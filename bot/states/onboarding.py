from aiogram.fsm.state import State, StatesGroup


class OnboardingStates(StatesGroup):
    waiting_time = State()
