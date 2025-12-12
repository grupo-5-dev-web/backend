"""Sistema de webhooks para notificações de eventos."""

import hashlib
import hmac
import json
import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

import httpx

logger = logging.getLogger(__name__)


def validate_webhook_url(url: Optional[str]) -> bool:
    """Valida se uma URL de webhook é segura e permitida.
    
    Regras:
    - HTTPS é sempre permitido
    - HTTP apenas para localhost/127.0.0.1 (desenvolvimento)
    - Outros protocolos são rejeitados
    
    Parameters
    ----------
    url : str | None
        URL a ser validada
        
    Returns
    -------
    bool
        True se a URL é válida, False caso contrário
    """
    if not url:
        return False
    
    url_lower = url.lower().strip()
    
    # HTTPS é sempre permitido
    if url_lower.startswith("https://"):
        return True
    
    # HTTP apenas para localhost/127.0.0.1 (desenvolvimento)
    if url_lower.startswith("http://"):
        return url_lower.startswith("http://localhost") or url_lower.startswith("http://127.0.0.1")
    
    # Outros protocolos não são permitidos
    return False


def _generate_signature(payload: str, secret: str) -> str:
    """Gera assinatura HMAC-SHA256 para o payload.
    
    Parameters
    ----------
    payload : str
        Payload JSON serializado
    secret : str
        Secret para assinatura
        
    Returns
    -------
    str
        Assinatura hexadecimal
    """
    return hmac.new(
        secret.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()


async def send_webhook(
    client: httpx.AsyncClient,
    url: str,
    event_type: str,
    payload: Dict[str, Any],
    secret: Optional[str] = None,
    timeout: float = 10.0,
) -> bool:
    """Envia um webhook para uma URL específica.
    
    Parameters
    ----------
    client : httpx.AsyncClient
        Cliente HTTP assíncrono
    url : str
        URL de destino do webhook
    event_type : str
        Tipo do evento (ex: "booking.created")
    payload : dict
        Dados do evento
    secret : str | None
        Secret opcional para assinatura HMAC
    timeout : float
        Timeout em segundos (padrão: 10.0)
        
    Returns
    -------
    bool
        True se o webhook foi enviado com sucesso, False caso contrário
    """
    if not validate_webhook_url(url):
        logger.warning(f"URL de webhook inválida: {url}")
        return False
    
    webhook_payload = {
        "event": event_type,
        "data": payload,
    }
    
    payload_json = json.dumps(webhook_payload, default=str)
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Booking-System-Webhook/1.0",
    }
    
    # Adiciona assinatura se secret for fornecido
    if secret:
        signature = _generate_signature(payload_json, secret)
        headers["X-Webhook-Signature"] = f"sha256={signature}"
    
    try:
        response = await client.post(
            url,
            content=payload_json,
            headers=headers,
            timeout=timeout,
        )
        response.raise_for_status()
        logger.info(f"Webhook enviado com sucesso para {url} (evento: {event_type})")
        return True
    except httpx.TimeoutException:
        logger.warning(f"Timeout ao enviar webhook para {url} (evento: {event_type})")
        return False
    except httpx.HTTPStatusError as e:
        logger.warning(
            f"Erro HTTP ao enviar webhook para {url} (evento: {event_type}): "
            f"{e.response.status_code}"
        )
        return False
    except Exception as e:
        logger.exception(f"Erro inesperado ao enviar webhook para {url} (evento: {event_type})")
        return False


async def send_webhooks_for_event(
    client: httpx.AsyncClient,
    webhooks: List[Dict[str, Any]],
    event_type: str,
    payload: Dict[str, Any],
    tenant_id: UUID,
) -> List[Dict[str, Any]]:
    """Envia webhooks para todos os endpoints configurados para um evento específico.
    
    Parameters
    ----------
    client : httpx.AsyncClient
        Cliente HTTP assíncrono
    webhooks : list[dict]
        Lista de webhooks configurados. Cada webhook deve ter:
        - id: UUID do webhook
        - url: URL de destino
        - events: Lista de eventos que o webhook escuta
        - secret: Secret opcional para assinatura
        - tenant_id: UUID do tenant (para filtro)
    event_type : str
        Tipo do evento (ex: "booking.created")
    payload : dict
        Dados do evento
    tenant_id : UUID
        ID do tenant que gerou o evento
        
    Returns
    -------
    list[dict]
        Lista de resultados com informações sobre cada tentativa de envio:
        - webhook_id: UUID do webhook
        - success: bool indicando sucesso
        - error: str com mensagem de erro (se houver)
    """
    results = []
    
    # Filtra webhooks que correspondem ao evento e tenant
    matching_webhooks = [
        wh for wh in webhooks
        if event_type in wh.get("events", []) and wh.get("tenant_id") == tenant_id
    ]
    
    if not matching_webhooks:
        logger.debug(f"Nenhum webhook configurado para evento {event_type} do tenant {tenant_id}")
        return results
    
    # Envia webhook para cada endpoint correspondente
    for webhook in matching_webhooks:
        webhook_id = webhook.get("id")
        url = webhook.get("url")
        secret = webhook.get("secret")
        
        if not url:
            logger.warning(f"Webhook {webhook_id} não tem URL configurada")
            results.append({
                "webhook_id": webhook_id,
                "success": False,
                "error": "URL não configurada",
            })
            continue
        
        success = await send_webhook(client, url, event_type, payload, secret)
        results.append({
            "webhook_id": webhook_id,
            "success": success,
            "error": None if success else "Falha ao enviar webhook",
        })
    
    return results

