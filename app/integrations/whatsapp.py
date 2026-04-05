import aiohttp

EVOLUTION_URL = "https://evolution-evolution-api.pktrjn.easypanel.host"
EVOLUTION_INSTANCE = "softwarenews"
EVOLUTION_API_KEY = "8C0B6E2A4710-4C79-8C47-0465A4CD7E6F"

async def send_whatsapp(phone: str, message: str) -> bool:
    """Envia mensagem real via Evolution API."""
    # Formatar número (adicionar 55 se necessário)
    clean_phone = phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if not clean_phone.startswith("55"):
        clean_phone = "55" + clean_phone
    
    url = f"{EVOLUTION_URL}/message/sendText/{EVOLUTION_INSTANCE}"
    headers = {
        "apikey": EVOLUTION_API_KEY,
        "Content-Type": "application/json"
    }
    payload = {
        "number": clean_phone,
        "text": message
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as resp:
                if resp.status == 201 or resp.status == 200:
                    print(f"WHATSAPP [OK]: Mensagem enviada para {clean_phone}")
                    return True
                else:
                    body = await resp.text()
                    print(f"WHATSAPP [ERRO]: Status {resp.status} - {body}")
                    return False
    except Exception as e:
        print(f"WHATSAPP [ERRO]: {e}")
        return False
