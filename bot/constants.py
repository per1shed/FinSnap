from enum import Enum

EXPENSE_CATEGORIES: dict[str, str] = {
    "groceries": "Продукты",
    "cafe": "Кафе",
    "transport": "Транспорт",
    "housing": "Жилье",
    "entertainment": "Развлечения",
    "other": "Другое",
}

INCOME_CATEGORIES: dict[str, str] = {
    "salary": "Зарплата",
    "freelance": "Фриланс",
    "other": "Другое",
}


class TransactionType(str, Enum):
    EXPENSE = "expense"
    INCOME = "income"
