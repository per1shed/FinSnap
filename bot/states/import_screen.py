from aiogram.fsm.state import State, StatesGroup


class ImportStates(StatesGroup):
    waiting_photo = State()
    reviewing = State()
