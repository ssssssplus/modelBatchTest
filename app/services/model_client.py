import copy
import time

import requests


class ModelClientError(Exception):
    pass


class ModelClient:
    def __init__(self, api_url, model, timeout=60):
        self.api_url = api_url
        self.model = model
        self.timeout = timeout

    def generate(self, prompt, request_body=None):
        payload = self._build_payload(prompt, request_body)

        started = time.perf_counter()
        try:
            response = requests.post(self.api_url, json=payload, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:
            raise ModelClientError(f"model api request failed: {exc}") from exc
        except ValueError as exc:
            raise ModelClientError("model api returned invalid json") from exc

        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        return {
            "text": self._extract_text(data),
            "raw": data,
            "latency_ms": latency_ms,
            "request_body": payload,
        }

    def _build_payload(self, prompt, request_body):
        if request_body is None:
            return {
                "model": self.model,
                "messages": [
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.7,
                "stream": False,
            }

        if not isinstance(request_body, dict):
            raise ModelClientError("request_body must be a json object")

        payload = copy.deepcopy(request_body)
        payload.setdefault("model", self.model)
        messages = payload.get("messages")
        if not isinstance(messages, list) or not messages:
            payload["messages"] = [{"role": "user", "content": prompt}]
            return payload

        user_message = next(
            (message for message in reversed(messages) if isinstance(message, dict) and message.get("role") == "user"),
            None,
        )
        if user_message is None:
            messages.append({"role": "user", "content": prompt})
        else:
            user_message["content"] = prompt
        return payload

    @staticmethod
    def default_request_body(model, prompt):
        return {
            "model": model,
            "messages": [
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.7,
            "stream": False,
        }

    @staticmethod
    def _extract_text(data):
        choices = data.get("choices")
        if isinstance(choices, list) and choices:
            message = choices[0].get("message") or {}
            content = message.get("content")
            if content is not None:
                return content
            text = choices[0].get("text")
            if text is not None:
                return text
        if "text" in data:
            return data["text"]
        if "output" in data:
            return data["output"]
        return str(data)
