"""Exceptions raised by the credit API. """


class InvalidCreditRequirements(Exception):
    """ The exception occurs when the requirement dictionary has invalid format. """
    pass


class InvalidCreditCourse(Exception):
    """ The exception occurs when the the course is not marked as a Credit Course. """
    pass


class CreditProviderNotFound(Exception):
    """No credit provider exists for the given provider_id. """
    pass


class CreditProviderNotConfiguredForCourse(Exception):
    """The credit provider exists, but has not been enabled for the course. """
    pass


class UserIsNotEligible(Exception):
    """The user has not satisfied eligibility requirements for credit. """
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
