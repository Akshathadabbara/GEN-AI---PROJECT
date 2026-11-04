import os
import json
import logging
import urllib.request
import urllib.error
import config

logger = logging.getLogger("college_lost_found.llm")

try:
    from openai import OpenAI
    _OPENAI_LIB_AVAILABLE = True
except ImportError:
    _OPENAI_LIB_AVAILABLE = False


class MultiProviderLLMService:
    """
    Unified multi-LLM service supporting Google Gemini, OpenRouter, and OpenAI
    with automatic provider detection, strict timeout protection, and grounded deterministic fallbacks.
    Guaranteed to never crash or cause 502 server errors.
    """

    def __init__(self):
        self.timeout = config.LLM_TIMEOUT
        self.gemini_key = config.GEMINI_API_KEY
        self.gemini_model = config.GEMINI_MODEL or "gemini-1.5-flash"
        self.openrouter_key = config.OPENROUTER_API_KEY
        self.openrouter_model = config.OPENROUTER_MODEL or "meta-llama/llama-3.2-3b-instruct:free"
        self.openai_key = config.OPENAI_API_KEY
        self.openai_model = config.OPENAI_MODEL or "gpt-4o-mini"
        self.configured_provider = config.LLM_PROVIDER.lower()

    def is_api_key_configured(self) -> bool:
        """Returns True if at least one supported LLM API key is present."""
        return bool(self._get_available_providers())

    def _get_available_providers(self) -> list:
        """Returns ordered list of usable providers based on configuration and available keys."""
        providers = []
        # Check configured preference first
        pref = self.configured_provider
        
        has_gemini = bool(self.gemini_key and self.gemini_key != "your_gemini_api_key_here")
        has_openrouter = bool(self.openrouter_key and self.openrouter_key != "your_openrouter_api_key_here")
        has_openai = bool(self.openai_key and self.openai_key != "your_openai_api_key_here")

        if pref == "gemini" and has_gemini:
            providers.append("gemini")
        elif pref == "openrouter" and has_openrouter:
            providers.append("openrouter")
        elif pref == "openai" and has_openai:
            providers.append("openai")

        # Add remaining available providers for automatic fallback
        if has_gemini and "gemini" not in providers:
            providers.append("gemini")
        if has_openrouter and "openrouter" not in providers:
            providers.append("openrouter")
        if has_openai and "openai" not in providers:
            providers.append("openai")

        return providers

    # ------------------------------------------------------------------
    # Provider-Specific Callers
    # ------------------------------------------------------------------
    def _call_gemini(self, system_instruction: str, user_prompt: str, max_tokens: int = 150) -> str:
        """Calls Google Gemini REST API safely with strict timeout."""
        if not self.gemini_key:
            return ""

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.gemini_model}:generateContent?key={self.gemini_key}"
        
        combined_prompt = f"{system_instruction}\n\nTask: {user_prompt}" if system_instruction else user_prompt
        payload = {
            "contents": [
                {
                    "parts": [{"text": combined_prompt}]
                }
            ],
            "generationConfig": {
                "maxOutputTokens": max_tokens,
                "temperature": 0.2
            }
        }

        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data_bytes,
            headers={"Content-Type": "application/json"}
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                res_json = json.loads(resp.read().decode("utf-8"))
                candidates = res_json.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts:
                        text = parts[0].get("text", "").strip()
                        return text
        except urllib.error.HTTPError as e:
            error_body = ""
            try:
                error_body = e.read().decode("utf-8")
            except Exception:
                pass
            logger.warning("Gemini API HTTP %d: %s", e.code, error_body[:200])
        except Exception as e:
            logger.warning("Gemini API call failed: %s", e)
        return ""

    def _call_openrouter(self, system_instruction: str, user_prompt: str, max_tokens: int = 150) -> str:
        """Calls OpenRouter REST API safely with strict timeout."""
        if not self.openrouter_key:
            return ""

        url = "https://openrouter.ai/api/v1/chat/completions"
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": user_prompt})

        payload = {
            "model": self.openrouter_model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.2
        }

        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data_bytes,
            headers={
                "Authorization": f"Bearer {self.openrouter_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://college-lost-found.onrender.com",
                "X-Title": "College Lost and Found Portal"
            }
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                res_json = json.loads(resp.read().decode("utf-8"))
                choices = res_json.get("choices", [])
                if choices:
                    text = choices[0].get("message", {}).get("content", "").strip()
                    return text
        except urllib.error.HTTPError as e:
            error_body = ""
            try:
                error_body = e.read().decode("utf-8")
            except Exception:
                pass
            logger.warning("OpenRouter API HTTP %d: %s", e.code, error_body[:200])
        except Exception as e:
            logger.warning("OpenRouter API call failed: %s", e)
        return ""

    def _call_openai(self, system_instruction: str, user_prompt: str, max_tokens: int = 150) -> str:
        """Calls OpenAI API safely with timeout."""
        if not self.openai_key:
            return ""

        if _OPENAI_LIB_AVAILABLE:
            try:
                client = OpenAI(api_key=self.openai_key, timeout=self.timeout)
                messages = []
                if system_instruction:
                    messages.append({"role": "system", "content": system_instruction})
                messages.append({"role": "user", "content": user_prompt})

                resp = client.chat.completions.create(
                    model=self.openai_model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=0.2
                )
                if resp and resp.choices:
                    return (resp.choices[0].message.content or "").strip()
            except Exception as e:
                logger.warning("OpenAI API call failed: %s", e)
        return ""

    def _dispatch_prompt(self, system_instruction: str, user_prompt: str, max_tokens: int = 150) -> tuple:
        """
        Dispatches prompt across available providers in order with automatic fallback.
        Returns (result_text, provider_name_used).
        """
        providers = self._get_available_providers()
        for prov in providers:
            try:
                if prov == "gemini":
                    text = self._call_gemini(system_instruction, user_prompt, max_tokens)
                elif prov == "openrouter":
                    text = self._call_openrouter(system_instruction, user_prompt, max_tokens)
                elif prov == "openai":
                    text = self._call_openai(system_instruction, user_prompt, max_tokens)
                else:
                    text = ""

                if text:
                    logger.info("Successfully received LLM response from provider: %s", prov)
                    return text, prov
            except Exception as e:
                logger.warning("Provider %s encountered unexpected error: %s", prov, e)
                continue

        return "", None

    # ------------------------------------------------------------------
    # Public Services
    # ------------------------------------------------------------------
    def synthesize_rag_response(self, query: str, retrieved_items: list) -> dict:
        """
        Synthesizes a short, grounded response for student's natural language search query.
        Uses ONLY retrieved database records. If API keys are unconfigured or fail,
        falls back gracefully to deterministic analysis without crashing.
        """
        # If no API key configured at all, display setup message
        if not self.is_api_key_configured():
            return {
                "api_key_configured": False,
                "summary": (
                    "AI API key is not configured. Please configure GEMINI_API_KEY, OPENROUTER_API_KEY, "
                    "or OPENAI_API_KEY in your environment to enable conversational AI explanations. "
                    "Matching records retrieved from the database are displayed below."
                ),
                "disclaimer": "Possible matches — not confirmed ownership",
                "status": "missing_api_key",
                "provider": "deterministic"
            }

        # If zero items were retrieved from database
        if not retrieved_items:
            return {
                "api_key_configured": True,
                "summary": (
                    f"No matching records were found in the database for \"{query}\". "
                    "Please try describing the item with different keywords, colors, or locations."
                ),
                "disclaimer": "No matches found in database",
                "status": "empty_results",
                "provider": "local"
            }

        # Build clean retrieved items context
        context_lines = []
        for idx, item in enumerate(retrieved_items, start=1):
            line = (
                f"[{idx}] Name: {item.get('item_name')} | Type: {item.get('type')} | "
                f"Category: {item.get('category')} | Location: {item.get('location')} | "
                f"Date: {item.get('item_date')} | Description: {item.get('description')} | "
                f"Confidence: {item.get('confidence')} ({int(item.get('similarity_score', 0) * 100)}%)"
            )
            context_lines.append(line)
        context_text = "\n".join(context_lines)

        system_instruction = (
            "You are the AI Assistant for a College Lost and Found Portal.\n"
            "Your task is to summarize whether any retrieved database records "
            "might be a potential match for the student's lost or found search query.\n\n"
            "CRITICAL RULES:\n"
            "1. Grounding: Rely EXCLUSIVELY on the retrieved items provided below. Do NOT invent details.\n"
            "2. Non-Commitment: NEVER state confirmed ownership or certainty. Always say 'possible match' or 'potential match'.\n"
            "3. Privacy: NEVER ask for or mention student contact numbers or registration details.\n"
            "4. Conciseness: Keep your response concise, polite, and student-friendly (2 sentences maximum).\n"
            "5. If items are low relevance, state that politely."
        )

        user_prompt = (
            f"Student Search Query: \"{query}\"\n\n"
            f"Retrieved Records from College Database ({len(retrieved_items)} items):\n"
            f"{context_text}\n\n"
            "Please provide a concise, factual summary explaining possible matches."
        )

        text, provider_used = self._dispatch_prompt(system_instruction, user_prompt, max_tokens=180)
        if text:
            return {
                "api_key_configured": True,
                "summary": text,
                "disclaimer": "Possible matches — not confirmed ownership",
                "status": "success",
                "provider": provider_used
            }

        # If all LLM calls failed, fallback gracefully to deterministic grounded summary
        fallback_text = self._generate_fallback_search_summary(query, retrieved_items)
        return {
            "api_key_configured": True,
            "summary": fallback_text,
            "disclaimer": "Possible matches — not confirmed ownership",
            "status": "fallback",
            "provider": "deterministic"
        }

    def generate_explanation(self, lost_item: dict, found_item: dict, score_data: dict) -> str:
        """
        Generates a concise, grounded explanation of why two items might match.
        Used for automated Lost vs. Found candidate pair matching.
        """
        if self.is_api_key_configured():
            prompt = (
                "You are an assistant for a college Lost and Found matching portal.\n"
                "Explain in 1 to 2 clear, objective sentences why the following Lost and Found reports might refer to the same item.\n"
                "CRITICAL RULES:\n"
                "- Only state facts mentioned in the reports. Do NOT invent details.\n"
                "- Do not declare ownership or certainty. Use phrases like 'potential match'.\n"
                "- Keep under 40 words.\n\n"
                f"Lost: {lost_item.get('item_name')} ({lost_item.get('category') or ''}), Color: {lost_item.get('color') or ''}, Loc: {lost_item.get('location') or ''}, Desc: {lost_item.get('description') or ''}\n"
                f"Found: {found_item.get('item_name')} ({found_item.get('category') or ''}), Color: {found_item.get('color') or ''}, Loc: {found_item.get('location') or ''}, Desc: {found_item.get('description') or ''}\n"
                f"Match Score: {int(score_data.get('similarity_score', 0) * 100)}%"
            )
            text, _ = self._dispatch_prompt("", prompt, max_tokens=80)
            if text:
                return text

        return self._generate_fallback_explanation(lost_item, found_item, score_data)

    def _generate_fallback_search_summary(self, query: str, retrieved_items: list) -> str:
        """Deterministic grounded search summary that works completely offline."""
        top_item = retrieved_items[0]
        top_name = top_item.get("item_name") or "Item"
        top_type = top_item.get("type") or "item"
        top_score = int(top_item.get("similarity_score", 0) * 100)
        
        summary = (
            f"Found {len(retrieved_items)} relevant candidate record{'s' if len(retrieved_items) > 1 else ''} in the database. "
            f"The closest potential match is '{top_name}' ({top_type}) with approximately {top_score}% match confidence. "
            "Please review the detailed records below to verify identifying details."
        )
        return summary

    def _generate_fallback_explanation(self, lost_item: dict, found_item: dict, score_data: dict) -> str:
        """Deterministic grounded fallback explanation for candidate pairs."""
        score = score_data.get("similarity_score", 0.0)
        confidence = score_data.get("confidence", "Possible match")
        evidence = score_data.get("evidence", [])
        
        lost_name = lost_item.get("item_name") or "Lost item"
        found_name = found_item.get("item_name") or "Found item"

        reasons = []
        if evidence:
            reasons.append("Identified common factors: " + "; ".join(evidence) + ".")
            
        location_lost = lost_item.get("location")
        location_found = found_item.get("location")
        if location_lost and location_found and location_lost.lower() in location_found.lower():
            reasons.append(f"Both reports cite location near '{location_lost}'.")

        if not reasons:
            reasons.append("Semantic similarities detected between the reported titles and item descriptions.")

        explanation = (
            f"Evaluated as a {confidence.lower()} ({int(score * 100)}% estimated similarity) "
            f"between '{lost_name}' and '{found_name}'. " + " ".join(reasons)
        )
        return explanation


# Compatibility aliases
OpenAIRAGService = MultiProviderLLMService
LLMExplanationService = MultiProviderLLMService
llm_service_instance = MultiProviderLLMService()
