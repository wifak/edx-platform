"""
Discussion API test utilities
"""
import json
import re

import httpretty


class CommentsServiceMockMixin(object):
    """Mixin with utility methods for mocking the comments service"""
    def register_get_threads_response(self, threads, page, num_pages):
        """Register a mock response for GET on the CS thread list endpoint"""
        url = "http://localhost:4567/api/v1/threads"
        httpretty.register_uri(
            httpretty.GET,
            url,
            body=json.dumps({
                "collection": threads,
                "page": page,
                "num_pages": num_pages,
            }),
            status=200
        )

    def register_post_thread_response(self, response_overrides):
        """Register a mock response for POST on the CS commentable endpoint"""
        def callback(request, _uri, headers):
            """
            Simulate the thread creation endpoint by returning the provided data
            along with the data from response_overrides.
            """
            response_data = make_minimal_cs_thread(
                {key: val[0] for key, val in request.parsed_body.items()}
            )
            response_data.update(response_overrides)
            return (200, headers, json.dumps(response_data))

        httpretty.register_uri(
            httpretty.POST,
            re.compile(r"http://localhost:4567/api/v1/(\w+)/threads"),
            body=callback
        )

    def register_get_thread_error_response(self, thread_id, status_code):
        """Register a mock error response for GET on the CS thread endpoint."""
        httpretty.register_uri(
            httpretty.GET,
            "http://localhost:4567/api/v1/threads/{id}".format(id=thread_id),
            body="",
            status=status_code
        )

    def register_get_thread_response(self, thread):
        """
        Register a mock response for GET on the CS thread instance endpoint.
        """
        httpretty.register_uri(
            httpretty.GET,
            "http://localhost:4567/api/v1/threads/{id}".format(id=thread["id"]),
            body=json.dumps(thread),
            status=200
        )

    def register_post_comment_response(self, response_overrides, thread_id=None, parent_id=None):
        """
        Register a mock response for POST on the CS comments endpoint for the
        given thread or parent; exactly one of thread_id and parent_id must be
        specified.
        """
        def callback(request, _uri, headers):
            """
            Simulate the comment creation endpoint by returning the provided data
            along with the data from response_overrides.
            """
            response_data = make_minimal_cs_comment(
                {key: val[0] for key, val in request.parsed_body.items()}
            )
            response_data.update(response_overrides or {})
            return (200, headers, json.dumps(response_data))

        if thread_id and not parent_id:
            url = "http://localhost:4567/api/v1/threads/{}/comments".format(thread_id)
        elif parent_id and not thread_id:
            url = "http://localhost:4567/api/v1/comments/{}".format(parent_id)
        else:  # pragma: no cover
            raise ValueError("Exactly one of thread_id and parent_id must be provided.")

        httpretty.register_uri(httpretty.POST, url, body=callback)

    def register_get_comment_error_response(self, comment_id, status_code):
        """
        Register a mock error response for GET on the CS comment instance
        endpoint.
        """
        httpretty.register_uri(
            httpretty.GET,
            "http://localhost:4567/api/v1/comments/{id}".format(id=comment_id),
            body="",
            status=status_code
        )

    def register_get_comment_response(self, response_overrides):
        """
        Register a mock response for GET on the CS comment instance endpoint.
        """
        comment = make_minimal_cs_comment(response_overrides)
        httpretty.register_uri(
            httpretty.GET,
            "http://localhost:4567/api/v1/comments/{id}".format(id=comment["id"]),
            body=json.dumps(comment),
            status=200
        )

    def register_get_user_response(self, user, subscribed_thread_ids=None, upvoted_ids=None):
        """Register a mock response for GET on the CS user instance endpoint"""
        httpretty.register_uri(
            httpretty.GET,
            "http://localhost:4567/api/v1/users/{id}".format(id=user.id),
            body=json.dumps({
                "id": str(user.id),
                "subscribed_thread_ids": subscribed_thread_ids or [],
                "upvoted_ids": upvoted_ids or [],
            }),
            status=200
        )

    def register_subscription_response(self, user):
        """
        Register a mock response for POST on the CS user subscription endpoint
        """
        httpretty.register_uri(
            httpretty.POST,
            "http://localhost:4567/api/v1/users/{id}/subscriptions".format(id=user.id),
            body=json.dumps({}),  # body is unused
            status=200
        )

    def assert_query_params_equal(self, httpretty_request, expected_params):
        """
        Assert that the given mock request had the expected query parameters
        """
        actual_params = dict(httpretty_request.querystring)
        actual_params.pop("request_id")  # request_id is random
        self.assertEqual(actual_params, expected_params)

    def assert_last_query_params(self, expected_params):
        """
        Assert that the last mock request had the expected query parameters
        """
        self.assert_query_params_equal(httpretty.last_request(), expected_params)


def make_minimal_cs_thread(overrides=None):
    """
    Create a dictionary containing all needed thread fields as returned by the
    comments service with dummy data and optional overrides
    """
    ret = {
        "id": "dummy",
        "course_id": "dummy/dummy/dummy",
        "commentable_id": "dummy",
        "group_id": None,
        "user_id": "0",
        "username": "dummy",
        "anonymous": False,
        "anonymous_to_peers": False,
        "created_at": "1970-01-01T00:00:00Z",
        "updated_at": "1970-01-01T00:00:00Z",
        "thread_type": "discussion",
        "title": "dummy",
        "body": "dummy",
        "pinned": False,
        "closed": False,
        "abuse_flaggers": [],
        "votes": {"up_count": 0},
        "comments_count": 0,
        "unread_comments_count": 0,
        "children": [],
        "resp_total": 0,
    }
    ret.update(overrides or {})
    return ret


def make_minimal_cs_comment(overrides=None):
    """
    Create a dictionary containing all needed comment fields as returned by the
    comments service with dummy data and optional overrides
    """
    ret = {
        "id": "dummy",
        "thread_id": "dummy",
        "user_id": "0",
        "username": "dummy",
        "anonymous": False,
        "anonymous_to_peers": False,
        "created_at": "1970-01-01T00:00:00Z",
        "updated_at": "1970-01-01T00:00:00Z",
        "body": "dummy",
        "abuse_flaggers": [],
        "votes": {"up_count": 0},
        "endorsed": False,
        "children": [],
    }
    ret.update(overrides or {})
    return ret
