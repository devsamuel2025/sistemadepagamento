from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
from reportlab.lib import colors
import qrcode
import io
import os

class PDFInvoiceGenerator:
    def generate_invoice_pdf(self, invoice, customer):
        buffer = io.BytesIO()
        p = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4

        # --- Cabeçalho (Design System Antigravity) ---
        p.setFillColor(colors.HexColor("#6366f1"))
        p.rect(0, height - 4*cm, width, 4*cm, fill=1, stroke=0)
        
        p.setFillColor(colors.white)
        p.setFont("Helvetica-Bold", 24)
        p.drawString(1.5*cm, height - 2.5*cm, "ANTIGRAVITY PAYMENTS")
        
        p.setFont("Helvetica", 10)
        p.drawString(1.5*cm, height - 3.2*cm, "Plataforma Core v2 - Sistema de Faturamento Enterprise")

        # --- Dados da Fatura ---
        p.setFillColor(colors.black)
        p.setFont("Helvetica-Bold", 14)
        p.drawString(1.5*cm, height - 6*cm, f"FATURA #{invoice.id}")
        
        p.setFont("Helvetica", 10)
        p.drawString(1.5*cm, height - 6.7*cm, f"Data de Emissão: {invoice.created_at.strftime('%d/%m/%Y')}")
        p.drawString(1.5*cm, height - 7.2*cm, f"Vencimento: {invoice.due_date.strftime('%d/%m/%Y')}")

        # --- Dados do Cliente ---
        p.setFont("Helvetica-Bold", 12)
        p.drawString(11*cm, height - 6*cm, "DADOS DO CLIENTE")
        p.setFont("Helvetica", 10)
        p.drawString(11*cm, height - 6.7*cm, f"Nome: {customer.name}")
        p.drawString(11*cm, height - 7.2*cm, f"E-mail: {customer.email}")

        # --- Tabela de Itens (Simples) ---
        p.setStrokeColor(colors.lightgrey)
        p.line(1.5*cm, height - 8.5*cm, width - 1.5*cm, height - 8.5*cm)
        
        p.setFont("Helvetica-Bold", 11)
        p.drawString(1.5*cm, height - 9.2*cm, "Descrição")
        p.drawString(width - 5*cm, height - 9.2*cm, "Valor Total")
        
        p.line(1.5*cm, height - 9.5*cm, width - 1.5*cm, height - 9.5*cm)
        
        p.setFont("Helvetica", 11)
        p.drawString(1.5*cm, height - 10.2*cm, f"Serviço de Assinatura Recorrente (CTR #{invoice.contract_id})")
        p.drawString(width - 5*cm, height - 10.2*cm, f"R$ {invoice.amount:0.2f}")

        # --- Área do PIX ---
        p.setFillColor(colors.HexColor("#f8fafc"))
        p.rect(1.5*cm, 2*cm, width - 3*cm, 6*cm, fill=1, stroke=1)
        
        p.setFillColor(colors.black)
        p.setFont("Helvetica-Bold", 12)
        p.drawString(2*cm, 7.2*cm, "PAGUE COM PIX")
        
        # Gerar QR Code Real do Pix
        if invoice.pix_code:
            qr = qrcode.QRCode(box_size=4, border=1)
            qr.add_data(invoice.pix_code)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="#f8fafc")
            
            # Converter imagem QR para reportlab
            qr_buffer = io.BytesIO()
            img.save(qr_buffer, format="PNG")
            qr_buffer.seek(0)
            from reportlab.lib.utils import ImageReader
            qr_reader = ImageReader(qr_buffer)
            p.drawImage(qr_reader, 2*cm, 2.5*cm, width=4*cm, height=4*cm)
            
            p.setFont("Helvetica", 8)
            p.drawString(6.5*cm, 5.5*cm, "Código Pix (Copia e Cola):")
            p.setFont("Helvetica-Oblique", 7)
            
            # Quebrar o código pix em linhas para caber
            pix_text = invoice.pix_code
            p.drawString(6.5*cm, 5*cm, pix_text[:60])
            p.drawString(6.5*cm, 4.6*cm, pix_text[60:120])

        # --- Rodapé ---
        p.setFont("Helvetica", 8)
        p.setFillColor(colors.grey)
        p.drawCentredString(width/2, 1*cm, "Documento gerado eletronicamente pela Plataforma Antigravity Payments.")

        p.showPage()
        p.save()
        
        buffer.seek(0)
        return buffer
