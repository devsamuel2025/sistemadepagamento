import datetime
import uuid
from sqlalchemy import select, and_, exists, update
from sqlalchemy.ext.asyncio import AsyncSession
from ..models import Contract, Invoice, InvoiceStatus, RecurrenceType, NotificationLog, ContractStatus, Customer
from ..core.events import event_bus, BILLING_GENERATED, BILLING_OVERDUE
from ..integrations.gateway import MockGateway
from ..integrations.whatsapp import send_whatsapp

class RecurrenceService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def generate_daily_invoices(self, advance_days: int = 30):
        today = datetime.date.today()
        contract_stmt = select(Contract).where(Contract.status == ContractStatus.ACTIVE)
        result = await self.db.execute(contract_stmt)
        contracts = result.scalars().all()

        for contract in contracts:
            period_token = f"{today.year}-{today.month}-{contract.id}"
            exists_q = await self.db.execute(select(exists().where(Invoice.idempotency_token == period_token)))
            if not exists_q.scalar():
                bill_day = min(contract.start_date.day, 28)
                target_date = datetime.date(today.year, today.month, bill_day)
                if target_date <= today + datetime.timedelta(days=advance_days):
                    gateway = MockGateway()
                    pix_qr = await gateway.generate_pix(contract.value)
                    new_invoice = Invoice(
                        contract_id=contract.id,
                        amount=contract.value,
                        due_date=target_date,
                        idempotency_token=period_token,
                        checkout_token=uuid.uuid4().hex,
                        status=InvoiceStatus.PENDING,
                        pix_code=pix_qr
                    )
                    self.db.add(new_invoice)
                    await self.db.commit()
                    await self.db.refresh(new_invoice)
                    await event_bus.emit(BILLING_GENERATED, {"invoice_id": new_invoice.id, "customer_id": contract.customer_id})

    async def notify_safely(self, invoice_id: int, notification_type: str):
        """Notifica o cliente e registra no banco (idempotente)."""
        exists_log = await self.db.execute(select(exists().where(and_(
            NotificationLog.invoice_id == invoice_id,
            NotificationLog.notification_type == notification_type
        ))))
        if not exists_log.scalar():
            # Buscar dados do cliente
            stmt = (
                select(Customer, Invoice)
                .join(Contract, Customer.id == Contract.customer_id)
                .join(Invoice, Contract.id == Invoice.contract_id)
                .where(Invoice.id == invoice_id)
            )
            result = await self.db.execute(stmt)
            res = result.first()
            
            if res:
                cust, inv = res
                # ENVIAR WHATSAPP REAL via Evolution API
                if cust.phone:
                    checkout_link = f"http://127.0.0.1:5500/frontend/checkout.html?token={inv.checkout_token}"
                    msg = (
                        f"🔔 *Antigravity Payments*\n\n"
                        f"Olá {cust.name}!\n\n"
                        f"📄 Sua fatura de *R$ {inv.amount:.2f}* "
                        f"(Venc: {inv.due_date.strftime('%d/%m/%Y')}) está disponível.\n\n"
                        f"💳 Pague agora pelo link:\n{checkout_link}\n\n"
                        f"_Mensagem automática do sistema Antigravity._"
                    )
                    sent = await send_whatsapp(cust.phone, msg)
                    if sent:
                        wa_log = NotificationLog(
                            invoice_id=invoice_id,
                            notification_type=f"WHATSAPP_SENT_{notification_type}"
                        )
                        self.db.add(wa_log)

            log = NotificationLog(invoice_id=invoice_id, notification_type=notification_type)
            self.db.add(log)
            await self.db.commit()
            return True
        return False

    async def process_overdue_invoices(self):
        today = datetime.date.today()
        result = await self.db.execute(
            select(Invoice).where(Invoice.status == InvoiceStatus.PENDING, Invoice.due_date < today)
        )
        overdue_invoices = result.scalars().all()
        for inv in overdue_invoices:
            delay = (today - inv.due_date).days
            severity = "CRITICAL" if delay >= 7 else ("MEDIUM" if delay >= 3 else "LOW")
            await self.notify_safely(inv.id, f"OVERDUE_L{severity}_{delay}D")
            if delay >= 7:
                await self.db.execute(
                    update(Contract).where(Contract.id == inv.contract_id).values(status=ContractStatus.SUSPENDED)
                )
                await self.notify_safely(inv.id, "PROVISIONING_CUT_D7")
        await self.db.commit()

    async def enforce_trust_pact(self):
        now = datetime.datetime.utcnow()
        limit = now - datetime.timedelta(days=3)
        stmt = select(Invoice).where(and_(
            Invoice.status == InvoiceStatus.PENDING,
            Invoice.customer_confirmed_at != None,
            Invoice.customer_confirmed_at < limit
        ))
        result = await self.db.execute(stmt)
        for inv in result.scalars().all():
            await self.db.execute(
                update(Contract).where(Contract.id == inv.contract_id).values(status=ContractStatus.SUSPENDED)
            )
            await self.notify_safely(inv.id, "TRUST_BREACH_SUSPENSION")
        await self.db.commit()
