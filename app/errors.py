class AppError(Exception):
    pass


class RuleValidationError(AppError):
    pass


class PersistenceError(AppError):
    pass
