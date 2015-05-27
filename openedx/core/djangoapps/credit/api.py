""" Contains the APIs for course credit requirements """

from .exceptions import InvalidCreditRequirements
from .models import CreditCourse, CreditRequirement, CreditRequirementStatus
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


def get_credit_requirement(course_key, namespace, name):
    """ Returns the requirement of a given course, namespace and name

    Args:
        course_key(CourseKey): The identifier for course
        namespace(str): Namespace of requirement
        name: Name of the requirement

    Returns:
        Credit Requirement object
    """
    return CreditRequirement.get_course_requirement(course_key, namespace, name)


def set_credit_requirement_status(user_name, requirement, status="satisfied"):
    """Update Credit Requirement Status for given username and requirement
        if exists else add new

    Args:
        user_name(str): username of the user
        requirement(CreditRequirement): CreditRequirement object
        status(str): status of the requirement
    """
    CreditRequirementStatus.add_or_update_requirement_status(user_name, requirement, status)



def _get_requirements_to_disable(old_requirements, new_requirements):
    """ Returns the ids of CreditRequirement to be disabled that are deleted
        from the courseware

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
