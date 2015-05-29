""" Contains the APIs for course credit requirements """

from .exceptions import InvalidCreditRequirements
from .models import CreditCourse, CreditRequirement
from openedx.core.djangoapps.credit.exceptions import InvalidCreditCourse


def set_credit_requirements(course_key, requirements):
    """ Add requirements to given course

    Args:
        course_key(CourseKey): The identifier for course
        requirements(list): List of requirements to be added

    Example:
        >>> set_credit_requirements(
                "course-v1-edX-DemoX-1T2015",
                [
                    {
                        "namespace": "verification",
                        "name": "verification",
                        "criteria": {},
                    },
                    {
                        "namespace": "reverification",
                        "name": "midterm",
                        "criteria": {},
                    },
                    {
                        "namespace": "proctored_exam",
                        "name": "final",
                        "criteria": {},
                    },
                    {
                        "namespace": "grade",
                        "name": "grade",
                        "criteria": {"min_grade": 0.8},
                    },
                ])

    Raises:
        InvalidCreditRequirements

    Returns:
        None
    """

    invalid_requirements = _validate_requirements(requirements)
    if invalid_requirements:
        invalid_requirements = ", ".join(invalid_requirements)
        raise InvalidCreditRequirements(invalid_requirements)

    try:
        credit_course = CreditCourse.get_credit_course(course_key=course_key)
    except CreditCourse.DoesNotExist:
        raise InvalidCreditCourse()

    old_requirements = CreditRequirement.get_course_requirements(course_key=course_key)
    requirements_to_disable = _get_requirements_to_disable(old_requirements, requirements)
    if requirements_to_disable:
        CreditRequirement.disable_credit_requirements(requirements_to_disable)

    for requirement in requirements:
        CreditRequirement.add_or_update_course_requirement(credit_course, requirement)


def get_credit_requirements(course_key, namespace=None):
    """ Returns the requirements of a given course and namespace

    Args:
        course_key(CourseKey): The identifier for course
        namespace(str): Namespace of requirements

    Example:
        >>> get_credit_requirements("course-v1-edX-DemoX-1T2015")
                {
                    requirements =
                    [
                        {
                            "namespace": "verification",
                            "name": "verification",
                            "criteria": {},
                        },
                        {
                            "namespace": "reverification",
                            "name": "midterm",
                            "criteria": {},
                        },
                        {
                            "namespace": "proctored_exam",
                            "name": "final",
                            "criteria": {},
                        },
                        {
                            "namespace": "grade",
                            "name": "grade",
                            "criteria": {"min_grade": 0.8},
                        },
                    ]
                }

    Returns:
        Dict of requirements in the given namespace
    """

    requirements = CreditRequirement.get_course_requirements(course_key, namespace)
    return [
        {
            "namespace": requirement.namespace,
            "name": requirement.name,
            "criteria": requirement.criteria
        }
        for requirement in requirements
    ]


def create_credit_request(course_key, provider_id, user_info, grade):
    """Initiate a request for credit from a credit provider.

    This will return the parameters that the user's browser will need to POST
    to the credit provider.  It does NOT calculate the signature

    Only users who are eligible for credit (have satisfied all credit requirements) are allowed to make requests.

    A database record will be created to track the request with a 32-character UUID.
    The returned dictionary can be used by the user’s browser to send a POST request to the credit provider.

    If a pending request already exists, this function should return a request description with the same UUID.
    (Other parameters, such as the user’s full name may be different than the original request).

    If a completed request (either accepted or rejected) already exists, this function will
    raise an exception.  Users are not allowed to make additional requests once a request
    has been completed.

    Arguments:
        course_key (CourseKey): The identifier for the course.
        provider_id (str): The identifier of the credit provider.
        user_info (dict): Dictionary of user information.
        grade (float): The user’s final grade in the course, which is a value in the range [0.0, 1.0] (inclusive).

    Returns: dict

    Raises:
        CreditProviderNotFound: No credit provider exists for the given provider_id.
        CreditProviderNotConfiguredForCourse: The credit provider exists, but has not been enabled for the course.
        UserIsNotEligible: The user has not satisfied eligibility requirements for credit.
        RequestAlreadyCompleted: The user has already submitted a request and received a response
            from the credit provider.

    Example Usage:
        >>> user_info = {
        >>>     "username": "ron"
        >>>     "email": "ron@example.com",
        >>>     "full_name": "Ron Weasley",
        >>>     "mailing_address": "",
        >>>     "country": "US",
        >>> }
        >>>
        >>> create_credit_request(course.id, "hogwarts", 0.95, user_info)
        {
            "request_uuid": "557168d0f7664fe59097106c67c3f847",
            "timestamp": "2015-05-04T20:57:57.987119+00:00",
            "course_org": "HogwartsX",
            "course_num": "Potions101",
            "course_run": "1T2015",
            "final_grade": 0.95,
            "user_username": "ron",
            "user_email": "ron@example.com",
            "user_full_name": "Ron Weasley",
            "user_mailing_address": "",
            "user_country": "US",
        }

    """
    pass


def update_credit_request_status(request_uuid, status):
    """Update the status of a credit request.

    Approve or reject a request for a student to receive credit in a course
    from a particular credit provider.

    This function does NOT check that the status update is authorized.
    The caller needs to handle authentication and authorization (checking the signature
    of the message received from the credit provider)

    The function is idempotent; if the request has already been updated to the status,
    the function does nothing.

    Arguments:
        request_uuid (str): The unique identifier for the credit request.
        status (str): Either "approved" or "rejected"

    Returns: None

    Raises:
        CreditRequestNotFound: The request does not exist.
        InvalidCreditStatus: The status is not either "approved" or "rejected".

    """
    pass


def get_credit_request_status(request_uuid):
    """Retrieve the status of a credit request.

    Returns either "pending", "accepted", or "rejected"

    Arguments:
        request_uuid (str): The unique identifier for the credit request.

    Returns: string

    Raises:
        CreditRequestNotFound: The request does not exist.

    """
    pass


def _get_requirements_to_disable(old_requirements, new_requirements):
    """ Returns the ids of CreditRequirement to be disabled that are deleted from the courseware

    Args:
        old_requirements(QuerySet): QuerySet of CreditRequirement
        new_requirements(list): List of requirements being added

    Returns:
        List of ids of CreditRequirement that are not in new_requirements
    """
    requirements_to_disable = []
    for old_req in old_requirements:
        found_flag = False
        for req in new_requirements:
            if req["namespace"] == old_req.namespace and req["name"] == old_req.name:
                found_flag = True
                break
        if not found_flag:
            requirements_to_disable.append(old_req.id)
    return requirements_to_disable


def _validate_requirements(requirements):
    """ Validate the requirements

    Args:
        requirements(list): List of requirements

    Returns:
        List of strings of invalid requirements
    """
    invalid_requirements = []
    for requirement in requirements:
        invalid_params = []
        if not requirement.get("namespace"):
            invalid_params.append("namespace")
        if not requirement.get("name"):
            invalid_params.append("name")
        if "criteria" not in requirement:
            invalid_params.append("criteria")

        if invalid_params:
            invalid_requirements.append(
                u"{requirement} has missing/invalid parameters: {params}".format(
                    requirement=requirement,
                    params=invalid_params,
                )
            )
    return invalid_requirements
