"""Shared support for Moltbook content verification challenges."""

import re
from decimal import ROUND_HALF_UP, Decimal
from difflib import SequenceMatcher
from typing import Any

from automolt.api.client import MoltbookAPIError, MoltbookClient

NUMBER_WORDS: dict[str, int] = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
}
SCALE_WORDS: dict[str, int] = {"hundred": 100, "thousand": 1000}
OPERATION_ALIASES: dict[str, str] = {
    "plus": "add",
    "add": "add",
    "adds": "add",
    "added": "add",
    "gain": "add",
    "gains": "add",
    "gained": "add",
    "increase": "add",
    "increases": "add",
    "increased": "add",
    "more": "add",
    "sum": "add",
    "minus": "subtract",
    "subtract": "subtract",
    "subtracts": "subtract",
    "subtracted": "subtract",
    "less": "subtract",
    "decrease": "subtract",
    "decreases": "subtract",
    "decreased": "subtract",
    "slow": "subtract",
    "slows": "subtract",
    "slowed": "subtract",
    "drop": "subtract",
    "drops": "subtract",
    "dropped": "subtract",
    "lose": "subtract",
    "loses": "subtract",
    "lost": "subtract",
    "times": "multiply",
    "multiply": "multiply",
    "multiplies": "multiply",
    "multiplied": "multiply",
    "double": "multiply",
    "doubles": "multiply",
    "triples": "multiply",
    "tripled": "multiply",
    "product": "multiply",
    "divide": "divide",
    "divides": "divide",
    "divided": "divide",
    "quotient": "divide",
    "per": "divide",
}
KNOWN_WORDS = tuple(sorted({*NUMBER_WORDS.keys(), *SCALE_WORDS.keys(), *OPERATION_ALIASES.keys(), "and", "by"}, key=len, reverse=True))
NUMBER_PATTERN = re.compile(r"^\d+(?:\.\d+)?$")
TOKEN_PATTERN = re.compile(r"\d+(?:\.\d+)?|[A-Za-z]+")
SYMBOL_OPERATION_PATTERN = re.compile(r"(?P<left>\d+(?:\.\d+)?)\s*(?P<operator>[+\-*/])\s*(?P<right>\d+(?:\.\d+)?)")


class ContentVerificationService:
    """Solve and complete Moltbook content verification challenges."""

    def __init__(self, api_client: MoltbookClient):
        self._api = api_client

    def verify_if_required(self, api_key: str, raw_response: dict[str, Any], content_key: str) -> tuple[dict[str, Any], bool]:
        content_payload = raw_response.get(content_key)
        if not isinstance(content_payload, dict):
            raise MoltbookAPIError(message=f"Unexpected API response: missing '{content_key}' payload")

        if not self._is_verification_required(raw_response, content_payload):
            return raw_response, False

        verification_payload = content_payload.get("verification")
        if not isinstance(verification_payload, dict):
            raise MoltbookAPIError(message="Verification was required but challenge details were missing.")

        verification_code = self._read_required_string(verification_payload, "verification_code")
        challenge_text = self._read_required_string(verification_payload, "challenge_text")
        answer = self.solve_challenge(challenge_text)
        self._api.verify_content(api_key, verification_code, answer)

        updated_response = dict(raw_response)
        updated_content = dict(content_payload)
        updated_content["verification_status"] = "verified"
        updated_response[content_key] = updated_content
        return updated_response, True

    def solve_challenge(self, challenge_text: str) -> str:
        normalized_tokens = self._normalize_tokens(challenge_text)
        operands = self._extract_operands(normalized_tokens)
        operation = self._extract_operation(challenge_text, normalized_tokens)

        if len(operands) < 2:
            raise MoltbookAPIError(message="Could not solve verification challenge: missing operands.")

        left_operand = operands[0]
        right_operand = operands[1]

        if operation == "add":
            result = left_operand + right_operand
        elif operation == "subtract":
            result = left_operand - right_operand
        elif operation == "multiply":
            result = left_operand * right_operand
        elif operation == "divide":
            if right_operand == 0:
                raise MoltbookAPIError(message="Could not solve verification challenge: division by zero.")
            result = left_operand / right_operand
        else:
            raise MoltbookAPIError(message="Could not solve verification challenge: unsupported operation.")

        return self._format_answer(result)

    def _is_verification_required(self, raw_response: dict[str, Any], content_payload: dict[str, Any]) -> bool:
        if raw_response.get("verification_required") is True:
            return True

        verification_status = str(content_payload.get("verification_status") or "").strip().lower()
        if verification_status == "pending" and isinstance(content_payload.get("verification"), dict):
            return True

        return False

    def _read_required_string(self, payload: dict[str, Any], field_name: str) -> str:
        raw_value = payload.get(field_name)
        if not isinstance(raw_value, str):
            raise MoltbookAPIError(message=f"Verification payload missing '{field_name}'.")

        value = raw_value.strip()
        if not value:
            raise MoltbookAPIError(message=f"Verification payload missing '{field_name}'.")

        return value

    def _normalize_tokens(self, challenge_text: str) -> list[str]:
        raw_tokens = TOKEN_PATTERN.findall(challenge_text.lower())
        normalized_tokens: list[str] = []
        index = 0

        while index < len(raw_tokens):
            token = raw_tokens[index]
            if NUMBER_PATTERN.match(token) or token in NUMBER_WORDS or token in SCALE_WORDS or token in OPERATION_ALIASES or token in {"and", "by"}:
                normalized_tokens.append(token)
                index += 1
                continue

            best_match: str | None = None
            best_length = 0
            best_score = 0.0

            for length in range(5, 0, -1):
                end_index = index + length
                if end_index > len(raw_tokens):
                    continue

                candidate_tokens = raw_tokens[index:end_index]
                if any(NUMBER_PATTERN.match(candidate) for candidate in candidate_tokens):
                    continue

                candidate_text = "".join(candidate_tokens)
                candidate_match, candidate_score = self._match_known_word(candidate_text)
                if candidate_match is None:
                    continue

                if candidate_length_is_better(length, candidate_score, best_length, best_score):
                    best_match = candidate_match
                    best_length = length
                    best_score = candidate_score

            if best_match is not None:
                normalized_tokens.append(best_match)
                index += best_length
                continue

            normalized_tokens.append(token)
            index += 1

        return normalized_tokens

    def _match_known_word(self, candidate_text: str) -> tuple[str | None, float]:
        best_match: str | None = None
        best_score = 0.0

        candidate_forms = {candidate_text, self._collapse_repeated_letters(candidate_text)}

        for candidate_form in candidate_forms:
            for known_word in KNOWN_WORDS:
                if abs(len(candidate_form) - len(known_word)) > 3:
                    continue

                score = SequenceMatcher(a=candidate_form, b=known_word).ratio()
                if score < self._minimum_similarity(known_word):
                    continue
                if score > best_score:
                    best_match = known_word
                    best_score = score

        return best_match, best_score

    def _minimum_similarity(self, known_word: str) -> float:
        if len(known_word) <= 2:
            return 1.0
        if len(known_word) <= 4:
            return 0.84
        if len(known_word) <= 6:
            return 0.78
        return 0.72

    def _extract_operands(self, normalized_tokens: list[str]) -> list[Decimal]:
        operands: list[Decimal] = []
        index = 0

        while index < len(normalized_tokens):
            token = normalized_tokens[index]
            if NUMBER_PATTERN.match(token):
                operands.append(Decimal(token))
                index += 1
                continue

            parsed_value, next_index = self._parse_word_number(normalized_tokens, index)
            if parsed_value is not None and next_index > index:
                operands.append(parsed_value)
                index = next_index
                continue

            index += 1

        return operands

    def _parse_word_number(self, normalized_tokens: list[str], start_index: int) -> tuple[Decimal | None, int]:
        index = start_index
        current_value = 0
        total_value = 0
        saw_number_word = False
        saw_scale_word = False

        while index < len(normalized_tokens):
            token = normalized_tokens[index]

            if token == "and" and saw_number_word and saw_scale_word:
                index += 1
                continue

            if token in NUMBER_WORDS:
                current_value += NUMBER_WORDS[token]
                saw_number_word = True
                saw_scale_word = False
                index += 1
                continue

            if token in SCALE_WORDS:
                if current_value == 0:
                    current_value = 1
                current_value *= SCALE_WORDS[token]
                if SCALE_WORDS[token] >= 1000:
                    total_value += current_value
                    current_value = 0
                saw_number_word = True
                saw_scale_word = True
                index += 1
                continue

            break

        if not saw_number_word:
            return None, start_index

        return Decimal(total_value + current_value), index

    def _extract_operation(self, challenge_text: str, normalized_tokens: list[str]) -> str:
        symbol_match = SYMBOL_OPERATION_PATTERN.search(challenge_text)
        if symbol_match is not None:
            operator_symbol = symbol_match.group("operator")
            return {
                "+": "add",
                "-": "subtract",
                "*": "multiply",
                "/": "divide",
            }[operator_symbol]

        for token in normalized_tokens:
            operation = OPERATION_ALIASES.get(token)
            if operation is not None:
                return operation

        raise MoltbookAPIError(message="Could not solve verification challenge: missing operation.")

    def _format_answer(self, value: Decimal) -> str:
        return format(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), "f")

    def _collapse_repeated_letters(self, value: str) -> str:
        return re.sub(r"(.)\1+", r"\1", value)


def candidate_length_is_better(candidate_length: int, candidate_score: float, best_length: int, best_score: float) -> bool:
    if candidate_length > best_length:
        return True
    if candidate_length == best_length and candidate_score > best_score:
        return True
    return False
