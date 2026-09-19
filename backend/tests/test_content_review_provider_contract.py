import inspect
import tempfile
import unittest
from pathlib import Path
from typing import get_type_hints

from app import create_app
from app.content_review import (
    ContentReviewProvider,
    UnavailableContentReviewProvider,
    get_content_review_provider,
    set_content_review_provider,
)
from app.teacher_console.errors import (
    ProviderAccessDeniedError,
    ProviderConflictError,
    ProviderError,
    ProviderNotFoundError,
    ProviderUnavailableError,
    ProviderValidationError,
)


EXPECTED_METHOD_SIGNATURES = {
    "submit_for_review": (
        (
            ("content_type", str),
            ("content_id", str),
            ("submitter_id", int),
            ("expected_version", int),
            ("payload", dict),
        ),
        dict,
    ),
    "get_review_status": (
        (
            ("content_type", str),
            ("content_id", str),
        ),
        dict | None,
    ),
    "approve": (
        (
            ("content_type", str),
            ("content_id", str),
            ("submitter_id", int),
            ("reviewer_id", int),
            ("reviewer_role", str),
            ("expected_version", int),
        ),
        dict,
    ),
    "reject": (
        (
            ("content_type", str),
            ("content_id", str),
            ("submitter_id", int),
            ("reviewer_id", int),
            ("reviewer_role", str),
            ("expected_version", int),
            ("opinion", str),
        ),
        dict,
    ),
    "edit": (
        (
            ("content_type", str),
            ("content_id", str),
            ("submitter_id", int),
            ("expected_version", int),
            ("payload", dict),
        ),
        dict,
    ),
}


class FakeReviewProvider:
    pass


class TestContentReviewProviderContract(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": str(Path(self.temp_dir.name) / "test.db"),
                "SECRET_KEY": "test-only-secret",
            }
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_provider_error_hierarchy_preserves_contract_fields(self):
        details = {"field": "title"}
        error_types = (
            ProviderValidationError,
            ProviderNotFoundError,
            ProviderConflictError,
            ProviderUnavailableError,
            ProviderAccessDeniedError,
        )

        for error_type in error_types:
            with self.subTest(error_type=error_type.__name__):
                error = error_type(
                    "内容审核失败",
                    code="review_failed",
                    details=details,
                )

                self.assertIsInstance(error, ProviderError)
                self.assertIsInstance(error, RuntimeError)
                self.assertEqual(str(error), "内容审核失败")
                self.assertEqual(error.code, "review_failed")
                self.assertEqual(error.message, "内容审核失败")
                self.assertIs(error.details, details)

    def test_protocol_and_placeholder_have_exact_keyword_only_signatures(self):
        for provider_type in (
            ContentReviewProvider,
            UnavailableContentReviewProvider,
        ):
            for method_name, (
                expected_parameters,
                expected_return,
            ) in EXPECTED_METHOD_SIGNATURES.items():
                with self.subTest(
                    provider_type=provider_type.__name__,
                    method_name=method_name,
                ):
                    method = getattr(provider_type, method_name)
                    signature = inspect.signature(method)
                    parameter_names = tuple(
                        name for name, _annotation in expected_parameters
                    )

                    self.assertEqual(
                        tuple(signature.parameters),
                        ("self", *parameter_names),
                    )
                    for parameter_name in parameter_names:
                        self.assertIs(
                            signature.parameters[parameter_name].kind,
                            inspect.Parameter.KEYWORD_ONLY,
                        )
                    self.assertEqual(
                        get_type_hints(method),
                        {
                            **dict(expected_parameters),
                            "return": expected_return,
                        },
                    )

    def test_placeholder_implements_complete_protocol(self):
        with self.app.app_context():
            provider = get_content_review_provider()
            self.assertIsInstance(provider, UnavailableContentReviewProvider)
            self.assertIsNone(
                provider.get_review_status(
                    content_type="course_video",
                    content_id="1",
                )
            )

            write_calls = (
                (
                    "submit_for_review",
                    {
                        "content_type": "course_video",
                        "content_id": "1",
                        "submitter_id": 7,
                        "expected_version": 1,
                        "payload": {},
                    },
                ),
                (
                    "approve",
                    {
                        "content_type": "course_video",
                        "content_id": "1",
                        "submitter_id": 7,
                        "reviewer_id": 1,
                        "reviewer_role": "admin",
                        "expected_version": 1,
                    },
                ),
                (
                    "reject",
                    {
                        "content_type": "course_video",
                        "content_id": "1",
                        "submitter_id": 7,
                        "reviewer_id": 1,
                        "reviewer_role": "admin",
                        "expected_version": 1,
                        "opinion": "不通过",
                    },
                ),
                (
                    "edit",
                    {
                        "content_type": "course_video",
                        "content_id": "1",
                        "submitter_id": 7,
                        "expected_version": 1,
                        "payload": {},
                    },
                ),
            )

            for method_name, kwargs in write_calls:
                with self.subTest(method_name=method_name):
                    with self.assertRaises(
                        ProviderUnavailableError
                    ) as caught:
                        getattr(provider, method_name)(**kwargs)

                    self.assertEqual(
                        caught.exception.code,
                        "review_unavailable",
                    )
                    self.assertEqual(
                        caught.exception.message,
                        "内容审核服务暂不可用",
                    )
                    self.assertEqual(caught.exception.details, {})

    def test_provider_slot_is_replaceable(self):
        replacement = FakeReviewProvider()

        set_content_review_provider(self.app, replacement)

        with self.app.app_context():
            self.assertIs(get_content_review_provider(), replacement)

        provider_slot_keys = {
            key
            for key in self.app.extensions
            if "content_review_provider" in key
        }
        self.assertEqual(
            provider_slot_keys,
            {"content_review_provider"},
        )


if __name__ == "__main__":
    unittest.main()
