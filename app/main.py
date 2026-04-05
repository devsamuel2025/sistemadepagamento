import asyncio
from typing import List, Optional
from datetime import datetime, date
from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks, Header, Body, Query, APIRouter
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_, exists
from .database import engine, Base, get_db, AsyncSessionLocal
from .models import Customer, Contract, Invoice, InvoiceStatus, RecurrenceType, NotificationLog, ContractStatus
from .schemas import CustomerCreate, ContractCreate, ContractResponse, WebhookData, InvoiceResponse
from .integrations.gateway import MockGateway
from .services.billing import RecurrenceService
from .core.events import event_bus, BILLING_GENERATED, BILLING_PAID
from .services.pdf_service import PDFInvoiceGenerator
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from starlette.status import HTTP_403_FORBIDDEN

API_KEY = "antigravity_secret_2025"
api_key_header = APIKeyHeader(name="X-API-KEY", auto_error=False)

async def check_api_key(
    api_key_h: Optional[str] = Depends(api_key_header),
    api_key_q: Optional[str] = Query(None, alias="api_key")
):
    key = api_key_h or api_key_q
    if key != API_KEY:
        raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="Not authenticated")
    return key

app = FastAPI(
    title="Antigravity Payment Platform v2.1", 
    version="2.1.0 (Provisioning Suite)"
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# EVENT HANDLERS
async def notify_invoice_created(data):
    async with AsyncSessionLocal() as db:
        service = RecurrenceService(db)
        await service.notify_safely(data["invoice_id"], "CREATED_NOTIF")

async def notify_payment_received(data):
    # REGISTRO DE AUDITORIA: Salva o sucesso no banco para o Terminal Admin ler
    async with AsyncSessionLocal() as db:
        log = NotificationLog(invoice_id=data["invoice_id"], notification_type="PAYMENT_CONFIRMED")
        db.add(log)
        await db.commit()
    print(f"NOTIFICATION [WebHook Success]: Payment for invoice {data['invoice_id']} confirmed.")

event_bus.subscribe(BILLING_GENERATED, notify_invoice_created)
event_bus.subscribe(BILLING_PAID, notify_payment_received)

# ROUTER PROTEGIDO (Admin)
admin = APIRouter(dependencies=[Depends(check_api_key)])

@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

# --- Endpoints Administrativos (Protegidos) ---

@admin.post("/customers", tags=["Customers"])
async def create_customer(customer_data: CustomerCreate, db: AsyncSession = Depends(get_db)):
    gateway = MockGateway()
    mock_token = await gateway.create_customer_token(customer_data.model_dump())
    new_customer = Customer(
        name=customer_data.name, 
        email=customer_data.email, 
        phone=customer_data.phone,
        default_payment_token=mock_token
    )
    db.add(new_customer)
    try:
        await db.commit()
        await db.refresh(new_customer)
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Email já cadastrado no sistema.")
    return {"id": new_customer.id, "name": new_customer.name, "email": new_customer.email, "phone": new_customer.phone}

@admin.get("/customers", tags=["Customers"])
async def list_customers(db: AsyncSession = Depends(get_db)):
    stmt = select(Customer, Contract.status).outerjoin(Contract, Customer.id == Contract.customer_id).order_by(Customer.id.desc())
    result = await db.execute(stmt)
    customers = []
    for row in result.all():
        c = row[0]
        customers.append({
            "id": c.id, 
            "name": c.name, 
            "email": c.email, 
            "phone": c.phone or "N/D", # NOVO
            "status": row[1] or "INACTIVE"
        })
    return customers

@admin.delete("/customers/{customer_id}", tags=["Customers"])
async def delete_customer(customer_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Customer).where(Customer.id == customer_id))
    customer = result.scalar_one_or_none()
    if not customer: raise HTTPException(status_code=404, detail="Cliente não encontrado")
    res_cont = await db.execute(select(Contract).where(Contract.customer_id == customer_id))
    contracts = res_cont.scalars().all()
    contract_ids = [c.id for c in contracts]
    if contract_ids:
        from sqlalchemy import delete as sa_delete
        # Buscar IDs das faturas
        inv_result = await db.execute(select(Invoice.id).where(Invoice.contract_id.in_(contract_ids)))
        invoice_ids = [row[0] for row in inv_result.all()]
        # Deletar na ordem correta: Logs -> Faturas -> Contratos
        if invoice_ids:
            await db.execute(sa_delete(NotificationLog).where(NotificationLog.invoice_id.in_(invoice_ids)))
        await db.execute(sa_delete(Invoice).where(Invoice.contract_id.in_(contract_ids)))
        await db.execute(sa_delete(Contract).where(Contract.id.in_(contract_ids)))
    await db.delete(customer)
    await db.commit()
    return {"status": "success", "message": f"Cliente {customer_id} removido."}

@admin.post("/contracts", tags=["Contracts"])
async def create_contract(contract_data: ContractCreate, db: AsyncSession = Depends(get_db)):
    new_contract = Contract(customer_id=contract_data.customer_id, value=contract_data.value, recurrence=contract_data.recurrence, start_date=contract_data.start_date)
    db.add(new_contract)
    await db.commit()
    await db.refresh(new_contract)
    return new_contract

@admin.post("/billing/process-daily", tags=["Engine"])
async def run_billing_engine(db: AsyncSession = Depends(get_db)):
    service = RecurrenceService(db)
    await service.generate_daily_invoices(advance_days=30)
    return {"message": "Success"}

@admin.post("/webhooks/payment-confirmation", tags=["Webhooks"])
async def payment_webhook(webhook: WebhookData, db: AsyncSession = Depends(get_db)):
    stmt = update(Invoice).where(Invoice.id == webhook.invoice_id).values(status=InvoiceStatus.PAID if webhook.status == "success" else InvoiceStatus.PENDING, payment_token=webhook.transaction_id, paid_at=datetime.utcnow() if webhook.status == "success" else None)
    result = await db.execute(stmt)
    await db.commit()
    if result.rowcount > 0 and webhook.status == "success":
        res_inv = await db.execute(select(Invoice).where(Invoice.id == webhook.invoice_id)); inv = res_inv.scalar_one()
        await db.execute(update(Contract).where(Contract.id == inv.contract_id).values(status=ContractStatus.ACTIVE))
        await db.commit()
        await event_bus.emit(BILLING_PAID, {"invoice_id": webhook.invoice_id})
        return {"status": "success"}
    raise HTTPException(status_code=404)

@admin.post("/billing/dunning-run", tags=["Engine"])
async def run_dunning(db: AsyncSession = Depends(get_db)):
    service = RecurrenceService(db)
    await service.process_overdue_invoices()
    await service.enforce_trust_pact()
    return {"status": "success"}

@admin.get("/monitoring/alerts", tags=["Monitoring"])
async def list_alerts(db: AsyncSession = Depends(get_db)):
    stmt = select(NotificationLog.id, NotificationLog.invoice_id, NotificationLog.notification_type, Customer.name.label("customer_name")).join(Invoice, NotificationLog.invoice_id == Invoice.id).join(Contract, Invoice.contract_id == Contract.id).join(Customer, Contract.customer_id == Customer.id).order_by(NotificationLog.id.desc()).limit(10)
    result = await db.execute(stmt)
    return [{"id":r.id, "invoice_id":r.invoice_id, "type":r.notification_type, "customer":r.customer_name} for r in result.all()]

@admin.get("/monitoring/invoices", response_model=List[InvoiceResponse], tags=["Monitoring"])
async def list_invoices(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Invoice))
    return result.scalars().all()

@admin.get("/invoices/{invoice_id}/pdf", tags=["Monitoring"])
async def get_invoice_pdf(invoice_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Invoice).where(Invoice.id == invoice_id))
    invoice = result.scalar_one_or_none()
    res_cust = await db.execute(select(Customer).join(Contract).where(Contract.id == invoice.contract_id))
    customer = res_cust.scalar_one_or_none()
    generator = PDFInvoiceGenerator()
    pdf_buffer = generator.generate_invoice_pdf(invoice, customer)
    return StreamingResponse(pdf_buffer, media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename=fatura_{invoice_id}.pdf"})

# --- Endpoints PÚBLICOS (Sem proteção de API Key) ---

@app.get("/checkout/{token}", tags=["Public Checkout"])
async def get_checkout_data(token: str, db: AsyncSession = Depends(get_db)):
    stmt = select(Invoice, Customer.name).join(Contract, Invoice.contract_id == Contract.id).join(Customer, Contract.customer_id == Customer.id).where(Invoice.checkout_token == token)
    result = await db.execute(stmt)
    row = result.first()
    if not row: raise HTTPException(status_code=404)
    inv, cust_name = row
    return {"id": inv.id, "customer": cust_name, "amount": inv.amount, "due_date": inv.due_date, "status": inv.status, "pix_code": inv.pix_code}

@app.post("/checkout/confirm/{token}", tags=["Public Checkout"], dependencies=[])
async def confirm_checkout_payment(token: str, db: AsyncSession = Depends(get_db)):
    """Public Early Release: The customer pledges he paid (3 days grace)."""
    # 1. Encontrar a fatura pelo checkout_token
    stmt = (
        select(Invoice)
        .where(Invoice.checkout_token == token)
    )
    result = await db.execute(stmt)
    inv = result.scalar_one_or_none()
    if not inv: raise HTTPException(status_code=404, detail="Token Inválido")
    
    # 2. SEGUNDA FASE: Liberação por Confiança!
    # Marcar a data da declaração do cliente (Pacto de 3 dias)
    inv.customer_confirmed_at = datetime.utcnow()
    
    # 3. Provisionamento Antecipado (Ativar o contrato na confiança)
    await db.execute(
        update(Contract)
        .where(Contract.id == inv.contract_id)
        .values(status=ContractStatus.ACTIVE)
    )
    await db.commit()
    
    # Notificação pro Admin: "Pacto de Confiança Iniciado"
    await event_bus.emit(BILLING_PAID, {"invoice_id": inv.id})
    return {"status": "success", "message": "Liberação Antecipada Ativada! Serviço Liberado por 3 dias para compensação bancária."}

# Incluir o roteador protegido
app.include_router(admin)
