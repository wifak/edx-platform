"""Exceptions raised by the credit API. """


class InvalidCreditRequirements(Exception):
    """The requirement dictionary provided has invalid format. """
    pass


class InvalidCreditCourse(Exception):
    """The course is not configured for credit. """
    pass


class CreditProviderNotConfigured(Exception):
    """The course has not been configured for credit from the specified provider. """
    pass


class UserIsNotEligible(Exception):
    """The user has not satisfied eligibility requirements for credit. """
    pass


class InvalidGrade(Exception):
    """The grade is not in the range [0.0, 1.0]. """
    pass


class RequestAlreadyCompleted(Exception):
    """The user has already submitted a request and received a response from the credit provider. """
    pass


class CreditRequestNotFound(Exception):
    """The request does not exist. """
    pass


class InvalidCreditStatus(Exception):
    """The status is not either "approved" or "rejected" """
    pass
