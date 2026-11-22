import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import translate


class TranslateTests(unittest.TestCase):
    def successful_post(self, _url, **kwargs):
        payload = json.loads(kwargs["data"])
        response = mock.Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "translations": [
                {"text": f"translated: {text}"} for text in payload["text"]
            ]
        }
        return response

    def test_translate_splits_requests_at_deepl_item_limit(self):
        texts = [f"text-{index}" for index in range(75)]

        with (
            mock.patch.object(translate, "KEY", "test-key"),
            mock.patch.object(
                translate.requests, "post", side_effect=self.successful_post
            ) as post,
        ):
            translated = translate.translate(texts, "fr")

        self.assertEqual(
            translated, [f"translated: {text}" for text in texts]
        )
        self.assertEqual(
            [
                len(json.loads(call.kwargs["data"])["text"])
                for call in post.call_args_list
            ],
            [50, 25],
        )

    def test_batch_texts_respects_request_body_limit(self):
        large_text = "x" * ((translate.MAX_REQUEST_BODY_BYTES // 2) - 10)

        batches = list(translate.batch_texts([large_text, large_text], "fr"))

        self.assertEqual(len(batches), 2)
        self.assertTrue(
            all(
                len(translate.request_body(batch, "fr"))
                <= translate.MAX_REQUEST_BODY_BYTES
                for batch in batches
            )
        )

    def test_batch_texts_rejects_an_oversized_single_value(self):
        oversized = "x" * translate.MAX_REQUEST_BODY_BYTES

        with self.assertRaisesRegex(ValueError, "exceeds DeepL"):
            list(translate.batch_texts([oversized], "fr"))

    def test_translate_rejects_incomplete_api_response(self):
        response = mock.Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"translations": []}

        with (
            mock.patch.object(translate, "KEY", "test-key"),
            mock.patch.object(translate.requests, "post", return_value=response),
        ):
            with self.assertRaisesRegex(RuntimeError, "invalid translation count"):
                translate.translate(["hello"], "fr")

    def test_main_preserves_keys_and_waits_for_all_translations(self):
        with tempfile.TemporaryDirectory() as directory:
            locale_dir = Path(directory)
            (locale_dir / "en.json").write_text(
                json.dumps({"greeting": "hello", "title": "Welcome"}),
                encoding="utf-8",
            )

            with (
                mock.patch.object(translate, "DIR", locale_dir),
                mock.patch.object(translate, "KEY", "test-key"),
                mock.patch.object(translate, "TARGETS", ["fr"]),
                mock.patch.object(
                    translate,
                    "translate",
                    return_value=["bonjour", "Bienvenue"],
                ) as translate_values,
            ):
                translate.main()

            translate_values.assert_called_once_with(
                ["hello", "Welcome"], "fr"
            )
            self.assertEqual(
                json.loads((locale_dir / "fr.json").read_text(encoding="utf-8")),
                {"greeting": "bonjour", "title": "Bienvenue"},
            )

    def test_main_does_not_write_partial_outputs_on_translation_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            locale_dir = Path(directory)
            (locale_dir / "en.json").write_text(
                json.dumps({"greeting": "hello"}), encoding="utf-8"
            )

            with (
                mock.patch.object(translate, "DIR", locale_dir),
                mock.patch.object(translate, "KEY", "test-key"),
                mock.patch.object(translate, "TARGETS", ["fr", "de"]),
                mock.patch.object(
                    translate,
                    "translate",
                    side_effect=[["bonjour"], RuntimeError("DeepL failed")],
                ),
            ):
                with self.assertRaisesRegex(RuntimeError, "DeepL failed"):
                    translate.main()

            self.assertFalse((locale_dir / "fr.json").exists())
            self.assertFalse((locale_dir / "de.json").exists())

    def test_main_requires_api_key(self):
        with mock.patch.object(translate, "KEY", None):
            with self.assertRaisesRegex(SystemExit, "DEEPL_API_KEY"):
                translate.main()


if __name__ == "__main__":
    unittest.main()
