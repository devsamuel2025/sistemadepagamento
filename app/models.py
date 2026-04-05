from datetime import datetime, date
from enum import Enum as PyEnum
from sqlalchemy import Column, Integer, String, Float, DateTime, Date, ForeignKey, Enum, Boolean, UniqueConstraint
from sqlalchemy.orm import relationship
from .database import Base

class RecurrenceType(str, PyEnum):
    MONTHLY = "MONTHLY"
    YEARLY = "YEARLY"

class ContractStatus(str, PyEnum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    CANCELED = "CANCELED"

class InvoiceStatus(str, PyEnum):
    PENDING = "pending"
    PAID = "paid"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"

class Customer(Base):
    __tablename__ = "customers"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    phone = Column(String, nullable=True) # Canal de WhatsApp
    gateway_customer_id = Column(String, unique=True, nullable=True) # Token do Stripe/Asaas
    default_payment_token = Column(String, nullable=True) # Token do cartão (PCI safe)
    created_at = Column(DateTime, default=datetime.utcnow)

    contracts = relationship("Contract", back_populates="customer")

class Contract(Base):
    __tablename__ = "contracts"
    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id", ondelete="CASCADE"), nullable=False)
    value = Column(Float, nullable=False)
    recurrence = Column(Enum(RecurrenceType), default=RecurrenceType.MONTHLY)
    start_date = Column(Date, default=date.today)
    status = Column(Enum(ContractStatus), default=ContractStatus.ACTIVE) # NOVO: Provisioning Status
    created_at = Column(DateTime, default=datetime.utcnow)

    customer = relationship("Customer", back_populates="contracts")
    invoices = relationship("Invoice", back_populates="contract")

class Invoice(Base):
    __tablename__ = "invoices"
    id = Column(Integer, primary_key=True, index=True)
    contract_id = Column(Integer, ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False)
    amount = Column(Float, nullable=False)
    due_date = Column(Date, nullable=False)
    status = Column(Enum(InvoiceStatus), default=InvoiceStatus.PENDING)
    
    # Pix Details (Mock)
    pix_code = Column(String, nullable=True) 

    # Idempotency token: contract_id + cycle (e.g., "2024-05")
    idempotency_token = Column(String, unique=True, nullable=False, index=True)
    checkout_token = Column(String, unique=True, index=True) # NOVO: Token público e seguro
    
    payment_token = Column(String, nullable=True) 
    paid_at = Column(DateTime, nullable=True)
    customer_confirmed_at = Column(DateTime, nullable=True) # Data da "Promessa de Pagamento"
    created_at = Column(DateTime, default=datetime.utcnow)

    contract = relationship("Contract", back_populates="invoices")
    logs = relationship("NotificationLog", back_populates="invoice")

class NotificationLog(Base):
    __tablename__ = "notification_logs"
    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=False)
    notification_type = Column(String, nullable=False) # e.g., "reminder_3_days", "overdue_notice"
    sent_at = Column(DateTime, default=datetime.utcnow)
    
    # Avoid spam: unique combination of invoice + type
    __table_args__ = (UniqueConstraint("invoice_id", "notification_type", name="_invoice_notif_uc"),)

    invoice = relationship("Invoice", back_populates="logs")
