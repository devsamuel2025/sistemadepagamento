from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import date, datetime
from enum import Enum

class RecurrenceType(str, Enum):
    MONTHLY = "MONTHLY"
    YEARLY = "YEARLY"

class ContractStatus(str, Enum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    CANCELED = "CANCELED"

class CustomerCreate(BaseModel):
    name: str
    email: EmailStr
    phone: Optional[str] = None # Para notificações automáticas

class CustomerResponse(BaseModel):
    id: int
    name: str
    email: EmailStr
    phone: Optional[str] = None
    created_at: datetime
    class Config:
        from_attributes = True

class ContractCreate(BaseModel):
    customer_id: int
    value: float
    recurrence: RecurrenceType = RecurrenceType.MONTHLY
    start_date: date = date.today()

class ContractResponse(BaseModel):
    id: int
    customer_id: int
    value: float
    recurrence: RecurrenceType
    start_date: date
    status: ContractStatus
    class Config:
        from_attributes = True

class InvoiceResponse(BaseModel):
    id: int
    contract_id: int
    amount: float
    due_date: date
    status: str
    idempotency_token: str
    checkout_token: Optional[str] = None
    pix_code: Optional[str] = None
    paid_at: Optional[datetime] = None
    customer_confirmed_at: Optional[datetime] = None
    class Config:
        from_attributes = True

class WebhookData(BaseModel):
    transaction_id: str
    invoice_id: int
    status: str
    payload: Optional[dict] = None
