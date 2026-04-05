from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class PaymentGateway(ABC):
    @abstractmethod
    async def process_payment(self, amount: float, customer_token: str, invoice_id: int) -> Dict[str, Any]:
        """Process a payment attempt (Card/Pix Mock). Returns transaction response."""
        pass

    @abstractmethod
    async def create_customer_token(self, customer_data: Dict[str, Any]) -> str:
        """Exchange sensitive info for a safe token (PCI Compliance)."""
        pass

    @abstractmethod
    async def generate_pix(self, amount: float) -> str:
        """Simulate Pix code generation."""
        pass

class MockGateway(PaymentGateway):
    """A simulated gateway for Pix and Credit Card processing."""
    
    async def generate_pix(self, amount: float) -> str:
        # Mock Pix String (Standard fintech format)
        import hashlib
        payload = f"00020126580014BR.GOV.BCB.PIX0114samuel@pay.com5204000053039865405{amount:0.2f}5802BR5913Antigravity6009Sao Paulo62070503***6304"
        return f"PIX_{hashlib.md5(payload.encode()).hexdigest().upper()}"

    async def create_customer_token(self, customer_data: Dict[str, Any]) -> str:
        # Simulate generating a safe token from Stripe/Asaas
        # In fact, we'd call their API here.
        email = customer_data.get("email", "unknown")
        return f"tok_mock_{email.split('@')[0]}_001"

    async def process_payment(self, amount: float, customer_token: str, invoice_id: int) -> Dict[str, Any]:
        # Logic to simulate a payment attempt
        # 90% success, 10% failure
        import random
        success = random.random() > 0.1
        
        return {
            "success": success,
            "status": "PAID" if success else "FAILED",
            "transaction_id": f"tx_{random.randint(100000, 999999)}",
            "message": "Payment processed successfully" if success else "Insufficient funds",
            "gateway": "MockPaymentProvider"
        }
