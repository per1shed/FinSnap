from aiogram.fsm.state import State, StatesGroup


class TransactionStates(StatesGroup):
    choosing_category = State()
    waiting_input = State()
