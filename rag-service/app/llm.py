"""LLM providers behind one tiny interface. Default: local Ollama (free). Alternative: local HF model."""

from __future__ import annotations

import os
from typing import Protocol

from app.config import Settings


class LLM(Protocol):
    name: str

    def generate(self, system: str, user: str) -> str: ...


class OllamaLLM:
    def __init__(self, base_url: str, model: str) -> None:
        from langchain_ollama import ChatOllama

        self.name = f"ollama:{model}"
        self._chat = ChatOllama(base_url=base_url, model=model, temperature=0.0)

    def generate(self, system: str, user: str) -> str:
        msg = self._chat.invoke([("system", system), ("human", user)])
        return str(msg.content).strip()


class HFLocalLLM:
    """Runs a small instruct model with transformers on CPU (fallback when Ollama is unavailable)."""

    def __init__(self, model: str) -> None:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        self.name = f"hf:{model}"
        self._tok = AutoTokenizer.from_pretrained(model)
        dtype = getattr(torch, os.environ.get("HF_DTYPE", "float32"))  # bfloat16 halves RAM use
        self._model = AutoModelForCausalLM.from_pretrained(model, dtype=dtype)
        self._model.eval()
        self._torch = torch

    def generate(self, system: str, user: str) -> str:
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        ids = self._tok.apply_chat_template(
            messages, add_generation_prompt=True, return_tensors="pt", return_dict=True
        )
        with self._torch.inference_mode():
            out = self._model.generate(**ids, max_new_tokens=220, do_sample=False)
        return self._tok.decode(out[0][ids["input_ids"].shape[1] :], skip_special_tokens=True).strip()


def get_llm(settings: Settings) -> LLM:
    if settings.llm_provider == "ollama":
        return OllamaLLM(settings.ollama_base_url, settings.ollama_model)
    if settings.llm_provider == "hf":
        return HFLocalLLM(settings.hf_model)
    raise ValueError(f"Unknown LLM_PROVIDER '{settings.llm_provider}' (use 'ollama' or 'hf')")
