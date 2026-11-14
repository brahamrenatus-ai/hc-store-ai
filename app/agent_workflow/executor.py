"""Adapter penyedia LLM (executor) dengan timeout, retry terbatas, dan penanganan galat.

Executor membungkus satu penyedia (Gemini atau OpenAI) di balik antarmuka tunggal
sehingga penyedia bisa ditukar lewat konfigurasi tanpa mengubah lapisan lain
(PRD AE-FR-080, §9.3).

Kebijakan retry (PRD §18, kontrak API §3):
- Maksimal 2 panggilan provider per request (1 percobaan + 1 retry).
- Retry hanya untuk kondisi transien: timeout, HTTP 5xx, keluaran tak valid.
- Error 4xx dari provider (termasuk kuota 429) TIDAK di-retry.
- Retry memakai sisa waktu dari batas total request.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pydantic import SecretStr

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Hasil executor
# ---------------------------------------------------------------------------

class FailureReason(StrEnum):
    """Alasan kegagalan pemanggilan penyedia LLM."""

    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    QUOTA_EXCEEDED = "QUOTA_EXCEEDED"
    TIMEOUT = "TIMEOUT"
    INVALID_OUTPUT = "INVALID_OUTPUT"
    PROVIDER_NOT_CONFIGURED = "PROVIDER_NOT_CONFIGURED"


@dataclass(frozen=True, slots=True)
class ExecutorResult:
    """Hasil pemanggilan penyedia LLM.

    Attributes:
        success: ``True`` bila penyedia mengembalikan teks yang bisa diproses.
        text: Teks mentah dari penyedia, atau ``None`` bila gagal.
        failure_reason: Kode kegagalan, ``None`` bila sukses.
        model_name: Nama model yang dipakai, bila diketahui.
        provider_name: Nama penyedia (``"gemini"``).
        attempts: Jumlah percobaan pemanggilan yang dilakukan (1 atau 2).
        latency_ms: Total latensi pemanggilan penyedia dalam milidetik.
    """

    success: bool
    text: str | None = None
    failure_reason: FailureReason | None = None
    model_name: str | None = None
    provider_name: str = "gemini"
    attempts: int = 1
    latency_ms: int = 0


# ---------------------------------------------------------------------------
# Executor
# ---------------------------------------------------------------------------

# Batas waktu default (detik) — bisa di-override lewat parameter.
_DEFAULT_CALL_TIMEOUT: float = 15.0
_DEFAULT_TOTAL_DEADLINE: float = 25.0
_MIN_REMAINING_FOR_RETRY: float = 5.0

# Model default Gemini (free tier).
_DEFAULT_MODEL = "gemini-2.0-flash"


@dataclass
class Executor:
    """Adapter penyedia LLM yang memanggil Gemini API.

    Executor bertanggung jawab atas:
    1. Memanggil API penyedia dengan batas waktu per panggilan.
    2. Retry satu kali untuk kegagalan transien (timeout, 5xx).
    3. Mengembalikan ``ExecutorResult`` yang berisi teks mentah atau alasan gagal.
    4. TIDAK melakukan validasi isi teks — itu tanggung jawab head.

    Parameters:
        api_key: Kunci API penyedia (``SecretStr``).
        model: Nama model Gemini.
        call_timeout: Batas waktu satu panggilan penyedia (detik).
        total_deadline: Batas waktu total untuk seluruh siklus retry (detik).
        temperature: Pengaturan keacakan generasi (rendah = lebih konsisten).
        max_output_tokens: Batas panjang keluaran.
    """

    api_key: SecretStr | None = None
    model: str = _DEFAULT_MODEL
    call_timeout: float = _DEFAULT_CALL_TIMEOUT
    total_deadline: float = _DEFAULT_TOTAL_DEADLINE
    temperature: float = 0.2
    max_output_tokens: int = 2048
    _client: object = field(default=None, init=False, repr=False)

    # ------------------------------------------------------------------
    # Panggilan publik
    # ------------------------------------------------------------------

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> ExecutorResult:
        """Memanggil penyedia LLM dan mengembalikan hasilnya.

        Parameters:
            system_prompt: Instruksi sistem untuk model.
            user_prompt: Pesan pengguna berisi fakta dan format keluaran.

        Returns:
            ``ExecutorResult`` dengan teks mentah atau alasan kegagalan.
        """
        if self.api_key is None or not self.api_key.get_secret_value().strip():
            logger.warning("executor: kunci API penyedia tidak terkonfigurasi")
            return ExecutorResult(
                success=False,
                failure_reason=FailureReason.PROVIDER_NOT_CONFIGURED,
                model_name=self.model,
                attempts=0,
                latency_ms=0,
            )

        start_wall = time.monotonic()
        attempts = 0
        last_failure: FailureReason = FailureReason.PROVIDER_UNAVAILABLE

        # Maksimal 2 percobaan (PRD: maks. 2 panggilan provider per request).
        for attempt in range(2):
            elapsed = time.monotonic() - start_wall
            remaining = self.total_deadline - elapsed

            if attempt > 0 and remaining < _MIN_REMAINING_FOR_RETRY:
                logger.info(
                    "executor: sisa waktu %.1f dtk < %.1f dtk, lewati retry",
                    remaining,
                    _MIN_REMAINING_FOR_RETRY,
                )
                break

            timeout = min(self.call_timeout, remaining)
            if timeout <= 0:
                last_failure = FailureReason.TIMEOUT
                break

            attempts += 1
            try:
                text = await self._call_provider(system_prompt, user_prompt, timeout)
                latency_ms = int((time.monotonic() - start_wall) * 1000)
                return ExecutorResult(
                    success=True,
                    text=text,
                    model_name=self.model,
                    attempts=attempts,
                    latency_ms=latency_ms,
                )
            except _QuotaExceededError:
                # Kuota habis: TIDAK di-retry.
                latency_ms = int((time.monotonic() - start_wall) * 1000)
                logger.warning("executor: kuota penyedia habis")
                return ExecutorResult(
                    success=False,
                    failure_reason=FailureReason.QUOTA_EXCEEDED,
                    model_name=self.model,
                    attempts=attempts,
                    latency_ms=latency_ms,
                )
            except _ClientError:
                # Error 4xx selain kuota: TIDAK di-retry.
                latency_ms = int((time.monotonic() - start_wall) * 1000)
                logger.warning("executor: error klien dari penyedia (4xx)")
                return ExecutorResult(
                    success=False,
                    failure_reason=FailureReason.PROVIDER_UNAVAILABLE,
                    model_name=self.model,
                    attempts=attempts,
                    latency_ms=latency_ms,
                )
            except TimeoutError:
                last_failure = FailureReason.TIMEOUT
                logger.info(
                    "executor: panggilan ke-%d timeout setelah %.1f dtk",
                    attempts,
                    timeout,
                )
            except _ProviderError as exc:
                last_failure = FailureReason.PROVIDER_UNAVAILABLE
                logger.warning(
                    "executor: panggilan ke-%d gagal: %s",
                    attempts,
                    exc,
                )

        latency_ms = int((time.monotonic() - start_wall) * 1000)
        return ExecutorResult(
            success=False,
            failure_reason=last_failure,
            model_name=self.model,
            attempts=attempts,
            latency_ms=latency_ms,
        )

    # ------------------------------------------------------------------
    # Lapisan transport (panggilan HTTP ke Gemini)
    # ------------------------------------------------------------------

    async def _call_provider(
        self,
        system_prompt: str,
        user_prompt: str,
        timeout: float,
    ) -> str:
        """Memanggil Gemini ``generateContent`` dan mengembalikan teks mentah.

        Raises:
            asyncio.TimeoutError: Panggilan melebihi ``timeout``.
            _QuotaExceededError: Kuota penyedia habis (HTTP 429).
            _ClientError: Error 4xx selain kuota.
            _ProviderError: Error 5xx atau jaringan.
        """
        import httpx  # noqa: PLC0415 — lazy import agar tes unit tanpa httpx bisa mock

        api_key = self.api_key.get_secret_value()  # type: ignore[union-attr]
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/"
            f"models/{self.model}:generateContent"
        )

        payload = {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"parts": [{"text": user_prompt}]}],
            "generationConfig": {
                "temperature": self.temperature,
                "maxOutputTokens": self.max_output_tokens,
                "responseMimeType": "application/json",
            },
        }

        async with httpx.AsyncClient(timeout=httpx.Timeout(timeout)) as client:
            resp = await client.post(
                url,
                params={"key": api_key},
                json=payload,
            )

        if resp.status_code == 429:
            raise _QuotaExceededError("Kuota penyedia habis")
        if 400 <= resp.status_code < 500:
            raise _ClientError(f"HTTP {resp.status_code}")
        if resp.status_code >= 500:
            raise _ProviderError(f"HTTP {resp.status_code}")

        body = resp.json()

        # Tangani respons kosong atau diblokir oleh safety filter.
        candidates = body.get("candidates", [])
        if not candidates:
            reason = body.get("promptFeedback", {}).get("blockReason", "UNKNOWN")
            raise _ProviderError(f"Tidak ada kandidat respons (blockReason={reason})")

        candidate = candidates[0]
        finish_reason = candidate.get("finishReason", "")
        if finish_reason == "SAFETY":
            raise _ProviderError("Respons diblokir oleh safety filter")

        try:
            text = candidate["content"]["parts"][0]["text"]
        except (KeyError, IndexError, TypeError) as exc:
            raise _ProviderError(f"Struktur respons tidak dikenal: {exc}") from exc

        return text


# ---------------------------------------------------------------------------
# Exception internal — tidak di-export, hanya untuk alur kontrol executor
# ---------------------------------------------------------------------------

class _ProviderError(Exception):
    """Kegagalan transien dari penyedia (5xx, jaringan)."""


class _QuotaExceededError(Exception):
    """Kuota penyedia habis (HTTP 429)."""


class _ClientError(Exception):
    """Error klien dari penyedia (4xx selain kuota)."""
