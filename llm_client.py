import logging
from config import Config


class LLMClient:
    """LLM client with multiple provider support."""

    def __init__(self, config: Config):
        self.config = config
        self.provider = config.llm_provider

    def complete(self, prompt: str) -> str:
        """Send prompt to LLM and get response."""
        if self.provider == "none":
            return self._placeholder_response()
        elif self.provider == "anthropic":
            return self._call_anthropic(prompt)
        elif self.provider == "openai":
            return self._call_openai(prompt)
        elif self.provider == "deepseek":
            return self._call_deepseek(prompt)
        elif self.provider == "custom":
            return self._call_custom(prompt)
        elif self.provider == "claude_code":
            return self._call_claude_code(prompt)
        else:
            return self._placeholder_response()

    def _placeholder_response(self) -> str:
        """Return placeholder response for dry-run mode."""
        return """## Conclusion
- intro_time_verdict: insufficient_evidence
- vuln_exists_at_intro_version: insufficient_evidence
- manual_review_needed: yes

## Analysis

This is a placeholder response from dry-run mode. No LLM was called.

insufficient_evidence: Unable to verify without actual LLM analysis.
"""

    def _call_anthropic(self, prompt: str) -> str:
        """Call Anthropic API."""
        api_key = self.config.anthropic_api_key
        if not api_key:
            return "Error: ANTHROPIC_API_KEY not configured. Please set it in .env file."

        try:
            import anthropic
            client = anthropic.Anthropic(
                api_key=api_key,
                base_url=self.config.anthropic_api_url,
            )
            message = client.messages.create(
                model=self.config.llm_model,
                max_tokens=self.config.llm_max_tokens,
                messages=[{"role": "user", "content": prompt}]
            )
            return message.content[0].text
        except Exception as e:
            logging.error(f"Anthropic API error: {e}")
            return f"Error calling Anthropic API: {e}"

    def _call_openai(self, prompt: str) -> str:
        """Call OpenAI API."""
        api_key = self.config.openai_api_key
        if not api_key:
            return "Error: OPENAI_API_KEY not configured. Please set it in .env file."

        try:
            import openai
            client = openai.OpenAI(
                api_key=api_key,
                base_url=self.config.openai_api_url,
            )
            response = client.chat.completions.create(
                model=self.config.llm_model,
                max_tokens=self.config.llm_max_tokens,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.choices[0].message.content
        except Exception as e:
            logging.error(f"OpenAI API error: {e}")
            return f"Error calling OpenAI API: {e}"

    def _call_deepseek(self, prompt: str) -> str:
        """Call DeepSeek API (Anthropic-compatible)."""
        api_key = self.config.deepseek_api_key
        if not api_key:
            return "Error: DEEPSEEK_API_KEY not configured. Please set it in .env file."

        try:
            import anthropic
            client = anthropic.Anthropic(
                api_key=api_key,
                base_url=self.config.deepseek_api_url,
            )
            message = client.messages.create(
                model=self.config.llm_model,
                max_tokens=self.config.llm_max_tokens,
                messages=[{"role": "user", "content": prompt}]
            )
            # Handle different content block types
            for block in message.content:
                if hasattr(block, "text"):
                    return block.text
            # If no text block found, try to get any content
            if message.content:
                return str(message.content[0])
            return "Error: No content in response"
        except Exception as e:
            logging.error(f"DeepSeek API error: {e}")
            return f"Error calling DeepSeek API: {e}"

    def _call_custom(self, prompt: str) -> str:
        """Call custom API endpoint."""
        import requests

        api_key = self.config.custom_api_key
        api_url = self.config.custom_api_url

        if not api_url:
            return "Error: CUSTOM_API_URL not configured. Please set it in .env file."

        try:
            headers = {"Content-Type": "application/json"}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"

            payload = {
                "model": self.config.llm_model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": self.config.llm_max_tokens,
            }

            response = requests.post(api_url, json=payload, headers=headers, timeout=120)
            response.raise_for_status()
            data = response.json()

            # Try OpenAI-compatible response format
            if "choices" in data:
                return data["choices"][0]["message"]["content"]
            # Try other formats
            elif "content" in data:
                return data["content"]
            elif "text" in data:
                return data["text"]
            else:
                return str(data)
        except Exception as e:
            logging.error(f"Custom API error: {e}")
            return f"Error calling custom API: {e}"

    def _call_claude_code(self, prompt: str) -> str:
        """Call Claude Code CLI (placeholder)."""
        return "Claude Code integration not yet implemented."
