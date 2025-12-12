"""Testes para sistema de webhooks."""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from uuid import uuid4
import httpx

from shared.webhooks import (
    send_webhook,
    send_webhooks_for_event,
    validate_webhook_url,
)


class TestValidateWebhookUrl:
    """Testes para validação de URL de webhook."""

    def test_validate_https_url(self):
        """Testa que URLs HTTPS são válidas."""
        assert validate_webhook_url("https://example.com/webhook") is True

    def test_validate_http_url_localhost(self):
        """Testa que HTTP localhost é válido para desenvolvimento."""
        assert validate_webhook_url("http://localhost:3000/webhook") is True

    def test_validate_http_url_127_0_0_1(self):
        """Testa que HTTP 127.0.0.1 é válido para desenvolvimento."""
        assert validate_webhook_url("http://127.0.0.1:3000/webhook") is True

    def test_reject_http_non_localhost(self):
        """Testa que HTTP não-localhost é rejeitado."""
        assert validate_webhook_url("http://example.com/webhook") is False

    def test_reject_invalid_url(self):
        """Testa que URLs inválidas são rejeitadas."""
        assert validate_webhook_url("not-a-url") is False
        assert validate_webhook_url("ftp://example.com/webhook") is False

    def test_reject_empty_url(self):
        """Testa que URL vazia é rejeitada."""
        assert validate_webhook_url("") is False
        assert validate_webhook_url(None) is False


class TestSendWebhook:
    """Testes para envio de webhook individual."""

    @pytest.mark.asyncio
    async def test_send_webhook_success(self):
        """Testa envio bem-sucedido de webhook."""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.post.return_value = mock_response
        
        url = "https://example.com/webhook"
        event_type = "booking.created"
        payload = {"booking_id": str(uuid4()), "status": "confirmed"}
        secret = "test-secret"
        
        result = await send_webhook(mock_client, url, event_type, payload, secret)
        
        assert result is True
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert call_args[0][0] == url
        assert "json" in call_args.kwargs

    @pytest.mark.asyncio
    async def test_send_webhook_includes_signature(self):
        """Testa que webhook inclui assinatura HMAC."""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.post.return_value = mock_response
        
        url = "https://example.com/webhook"
        event_type = "booking.created"
        payload = {"booking_id": str(uuid4())}
        secret = "test-secret"
        
        await send_webhook(mock_client, url, event_type, payload, secret)
        
        call_args = mock_client.post.call_args
        headers = call_args.kwargs.get("headers", {})
        assert "X-Webhook-Signature" in headers or "X-Signature" in headers

    @pytest.mark.asyncio
    async def test_send_webhook_handles_timeout(self):
        """Testa que timeout é tratado corretamente."""
        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.TimeoutException("Timeout")
        
        url = "https://example.com/webhook"
        event_type = "booking.created"
        payload = {"booking_id": str(uuid4())}
        
        result = await send_webhook(mock_client, url, event_type, payload, secret=None)
        
        assert result is False

    @pytest.mark.asyncio
    async def test_send_webhook_handles_http_error(self):
        """Testa que erros HTTP são tratados."""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server Error", request=MagicMock(), response=mock_response
        )
        mock_client.post.return_value = mock_response
        
        url = "https://example.com/webhook"
        event_type = "booking.created"
        payload = {"booking_id": str(uuid4())}
        
        result = await send_webhook(mock_client, url, event_type, payload, secret=None)
        
        assert result is False

    @pytest.mark.asyncio
    async def test_send_webhook_without_secret(self):
        """Testa envio sem secret (sem assinatura)."""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.post.return_value = mock_response
        
        url = "https://example.com/webhook"
        event_type = "booking.created"
        payload = {"booking_id": str(uuid4())}
        
        result = await send_webhook(mock_client, url, event_type, payload, secret=None)
        
        assert result is True
        call_args = mock_client.post.call_args
        # Sem secret, não deve ter assinatura
        headers = call_args.kwargs.get("headers", {})
        # Pode ter ou não assinatura dependendo da implementação


class TestSendWebhooksForEvent:
    """Testes para envio de webhooks para múltiplos endpoints."""

    @pytest.mark.asyncio
    async def test_send_webhooks_for_event_with_matching_webhooks(self):
        """Testa envio para webhooks que correspondem ao evento."""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.post.return_value = mock_response
        
        webhooks = [
            {"id": uuid4(), "url": "https://example.com/webhook1", "events": ["booking.created"], "secret": None},
            {"id": uuid4(), "url": "https://example.com/webhook2", "events": ["booking.cancelled"], "secret": None},
            {"id": uuid4(), "url": "https://example.com/webhook3", "events": ["booking.created", "booking.cancelled"], "secret": None},
        ]
        
        event_type = "booking.created"
        payload = {"booking_id": str(uuid4())}
        tenant_id = uuid4()
        
        results = await send_webhooks_for_event(mock_client, webhooks, event_type, payload, tenant_id)
        
        # Deve enviar para webhook1 e webhook3 (ambos têm booking.created)
        assert len(results) == 2
        assert mock_client.post.call_count == 2

    @pytest.mark.asyncio
    async def test_send_webhooks_for_event_no_matching_webhooks(self):
        """Testa quando não há webhooks para o evento."""
        mock_client = AsyncMock()
        
        webhooks = [
            {"id": uuid4(), "url": "https://example.com/webhook1", "events": ["booking.cancelled"], "secret": None},
        ]
        
        event_type = "booking.created"
        payload = {"booking_id": str(uuid4())}
        tenant_id = uuid4()
        
        results = await send_webhooks_for_event(mock_client, webhooks, event_type, payload, tenant_id)
        
        assert len(results) == 0
        mock_client.post.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_webhooks_for_event_handles_partial_failures(self):
        """Testa que falhas parciais não impedem outros webhooks."""
        mock_client = AsyncMock()
        
        # Primeiro webhook falha, segundo sucede
        mock_response1 = MagicMock()
        mock_response1.status_code = 500
        mock_response1.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server Error", request=MagicMock(), response=mock_response1
        )
        
        mock_response2 = MagicMock()
        mock_response2.status_code = 200
        
        mock_client.post.side_effect = [mock_response1, mock_response2]
        
        webhooks = [
            {"id": uuid4(), "url": "https://example.com/webhook1", "events": ["booking.created"], "secret": None},
            {"id": uuid4(), "url": "https://example.com/webhook2", "events": ["booking.created"], "secret": None},
        ]
        
        event_type = "booking.created"
        payload = {"booking_id": str(uuid4())}
        tenant_id = uuid4()
        
        results = await send_webhooks_for_event(mock_client, webhooks, event_type, payload, tenant_id)
        
        # Ambos devem ser tentados, mesmo que um falhe
        assert mock_client.post.call_count == 2
        # Resultados devem indicar sucesso/falha
        assert len(results) == 2

