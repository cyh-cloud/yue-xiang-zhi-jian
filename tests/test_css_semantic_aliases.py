# -*- coding: utf-8 -*-
"""Guards the expand phase of the semantic class-name migration."""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPO_ROOT / "frontend" / "src"

PREFIX_ALIASES = {
    "emp-": "employment-",
    "craft-": "crafts-",
    "cs-": "customer-service-",
    "copy-": "copywriting-",
    "msg-": "message-",
    "bo-": "backoffice-",
    "qa-": "agriculture-qa-",
    "fdn-": "farming-",
    "guide-": "purchase-guide-",
}


def alias_for(token: str) -> str:
    for old, new in PREFIX_ALIASES.items():
        if token.startswith(old):
            return new + token[len(old):]
    return ""


class SemanticAliasTest(unittest.TestCase):
    def test_static_legacy_classes_keep_their_semantic_alias(self):
        violations = []
        for path in sorted(SOURCE_ROOT.rglob("*.vue")):
            source = path.read_text(encoding="utf-8")
            start = source.find("<template>")
            end = source.rfind("</template>")
            if start < 0 or end <= start:
                continue
            template = source[start + len("<template>"):end]
            for match in re.finditer(r'(?<!:)class="([^"]*)"', template):
                tokens = match.group(1).split()
                for token in tokens:
                    if any(char in token for char in "{}$`"):
                        continue
                    alias = alias_for(token)
                    if alias and alias not in tokens:
                        violations.append(
                            f"{path.relative_to(REPO_ROOT)}: {token} lacks {alias}"
                        )
        self.assertEqual(violations, [])

    def test_class_attributes_do_not_repeat_tokens(self):
        violations = []
        for path in sorted(SOURCE_ROOT.rglob("*.vue")):
            source = path.read_text(encoding="utf-8")
            start = source.find("<template>")
            end = source.rfind("</template>")
            if start < 0 or end <= start:
                continue
            template = source[start + len("<template>"):end]
            for match in re.finditer(r'(?<!:)class="([^"]*)"', template):
                tokens = match.group(1).split()
                if len(tokens) != len(set(tokens)):
                    violations.append(str(path.relative_to(REPO_ROOT)))
        self.assertEqual(violations, [])


if __name__ == "__main__":
    unittest.main()
