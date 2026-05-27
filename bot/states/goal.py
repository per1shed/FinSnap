from aiogram.fsm.state import State, StatesGroup


class GoalStates(StatesGroup):
    waiting_title = State()
    waiting_target = State()
    waiting_deposit = State()
