// === CONFIGURAÇÃO ===
const API_URL = "http://127.0.0.1:8000";
const API_KEY = "antigravity_secret_2025";
let processedAlerts = new Set();

// === NAVEGAÇÃO DE SEÇÕES ===
function showSection(section) {
    document.querySelectorAll('.page-section').forEach(s => s.style.display = 'none');
    document.getElementById('section-' + section).style.display = 'block';
    document.querySelectorAll('.sidebar ul li').forEach(l => l.classList.remove('active'));
    const nav = document.getElementById('nav-' + section);
    if (nav) nav.classList.add('active');
}

// === TERMINAL DE AUDITORIA ===
function toggleTerminal() {
    const body = document.getElementById('terminalBody');
    body.style.display = body.style.display === 'none' ? 'block' : 'none';
}

function pushLog(msg) {
    const terminal = document.getElementById("terminalBody");
    if (!terminal) return;
    const time = new Date().toLocaleTimeString();
    const div = document.createElement("div");
    div.className = "log-line";
    div.innerHTML = `<span style="color:#10b981">[${time}]</span> >> ${msg}`;
    terminal.prepend(div);
}

// === MODAIS ===
function openModal(id) { document.getElementById(id).style.display = "block"; }
function closeModal(id) { document.getElementById(id).style.display = "none"; }

// === MOTOR DE SINCRONIZAÇÃO ===
async function fetchStats() {
    try {
        const [custRes, invRes, alertRes] = await Promise.all([
            fetch(API_URL + "/customers?api_key=" + API_KEY),
            fetch(API_URL + "/monitoring/invoices?api_key=" + API_KEY),
            fetch(API_URL + "/monitoring/alerts?api_key=" + API_KEY)
        ]);

        if (!custRes.ok || !invRes.ok || !alertRes.ok) {
            pushLog("❌ Erro ao buscar dados da API");
            return;
        }

        const customers = await custRes.json();
        const invoices = await invRes.json();
        const alerts = await alertRes.json();

        renderCustomers(customers);
        renderInvoices(invoices);
        renderAlerts(alerts);
        populateCustomerSelect(customers);
        updateStats(invoices);

        // Processar alertas no terminal
        alerts.forEach(function(a) {
            if (!processedAlerts.has(a.id)) {
                if (a.type === "PAYMENT_CONFIRMED") {
                    pushLog("✅ Pagamento da Fatura #" + a.invoice_id + " (" + a.customer + ") CONFIRMADO!");
                } else if (a.type.indexOf("WHATSAPP_SENT") === 0) {
                    pushLog("📱 [WHATSAPP] Mensagem enviada para: " + a.customer);
                }
                processedAlerts.add(a.id);
            }
        });

        pushLog("Recarregando estatísticas do sistema...");
    } catch (e) {
        console.error("fetchStats error:", e);
    }
}

// === RENDERIZADORES ===
function renderCustomers(customers) {
    var tbody = document.getElementById("customersTableBody");
    if (!tbody) return;
    tbody.innerHTML = "";
    for (var i = 0; i < customers.length; i++) {
        var c = customers[i];
        var tr = document.createElement("tr");
        var phoneClean = (c.phone || "").replace(/\D/g, "");
        var statusClass = c.status === "ACTIVE" ? "badge-paid" : "badge-pending";
        tr.innerHTML =
            "<td>" + c.id + "</td>" +
            "<td><strong>" + c.name + "</strong><br><small>" + c.email + "</small></td>" +
            '<td><a href="https://wa.me/' + phoneClean + '" target="_blank" style="color:#10b981; text-decoration:none"><i class="fab fa-whatsapp"></i> ' + (c.phone || "N/D") + "</a></td>" +
            '<td><span class="badge ' + statusClass + '">' + c.status + "</span></td>" +
            '<td><button onclick="deleteCustomer(' + c.id + ')" class="btn-subtle" style="color:#ef4444"><i class="fas fa-trash"></i></button></td>';
        tbody.appendChild(tr);
    }
}

function renderInvoices(invoices) {
    // Tabela da página de faturas
    var tbody = document.getElementById("invoicesTableBody");
    if (tbody) {
        tbody.innerHTML = "";
        for (var i = 0; i < invoices.length; i++) {
            var inv = invoices[i];
            var tr = document.createElement("tr");
            var checkoutUrl = "checkout.html?token=" + inv.checkout_token;
            var badgeClass = inv.status === "paid" ? "badge-paid" : "badge-pending";
            tr.innerHTML =
                "<td>#" + inv.id + "</td>" +
                "<td>CTR #" + inv.contract_id + "</td>" +
                "<td>R$ " + inv.amount.toFixed(2) + "</td>" +
                '<td><span class="badge ' + badgeClass + '">' + inv.status.toUpperCase() + "</span></td>" +
                '<td><button onclick="copyToClipboard(\'' + checkoutUrl + '\')" class="btn-subtle"><i class="fas fa-link"></i> Link</button></td>';
            tbody.appendChild(tr);
        }
    }

    // Tabela do dashboard (faturas recentes)
    var tbody2 = document.getElementById("invoiceTableBody");
    if (tbody2) {
        tbody2.innerHTML = "";
        for (var i = 0; i < invoices.length; i++) {
            var inv = invoices[i];
            var tr = document.createElement("tr");
            var badgeClass = inv.status === "paid" ? "badge-paid" : "badge-pending";
            tr.innerHTML =
                "<td>#" + inv.id + "</td>" +
                "<td>R$ " + inv.amount.toFixed(2) + "</td>" +
                '<td><span class="badge ' + badgeClass + '">' + inv.status.toUpperCase() + "</span></td>" +
                "<td>" + inv.due_date + "</td>" +
                '<td><button onclick="copyToClipboard(\'checkout.html?token=' + inv.checkout_token + '\')" class="btn-subtle"><i class="fas fa-link"></i> Link</button></td>';
            tbody2.appendChild(tr);
        }
    }

    // Tabela global de faturas (seção Faturas)
    var tbody3 = document.getElementById("fullInvoiceTableBody");
    if (tbody3) {
        tbody3.innerHTML = "";
        for (var i = 0; i < invoices.length; i++) {
            var inv = invoices[i];
            var tr = document.createElement("tr");
            var badgeClass = inv.status === "paid" ? "badge-paid" : "badge-pending";
            tr.innerHTML =
                "<td>#" + inv.id + "</td>" +
                "<td>CTR #" + inv.contract_id + "</td>" +
                "<td>R$ " + inv.amount.toFixed(2) + "</td>" +
                '<td><span class="badge ' + badgeClass + '">' + inv.status.toUpperCase() + "</span></td>" +
                '<td><button onclick="copyToClipboard(\'checkout.html?token=' + inv.checkout_token + '\')" class="btn-subtle"><i class="fas fa-link"></i> Link</button></td>';
            tbody3.appendChild(tr);
        }
    }
}

function renderAlerts(alerts) {
    var tbody = document.getElementById("alertsTableBody");
    if (!tbody) return;
    tbody.innerHTML = "";
    for (var i = 0; i < alerts.length; i++) {
        var a = alerts[i];
        var tr = document.createElement("tr");
        tr.innerHTML =
            "<td>#" + a.invoice_id + "</td>" +
            "<td>" + a.type + "</td>" +
            "<td>" + a.customer + "</td>";
        tbody.appendChild(tr);
    }
}

function populateCustomerSelect(customers) {
    // O select de contrato usa id="selectCustomer" no HTML
    var sel = document.getElementById("selectCustomer");
    if (!sel) return;
    sel.innerHTML = '<option value="">Selecione o Cliente...</option>';
    for (var i = 0; i < customers.length; i++) {
        var opt = document.createElement("option");
        opt.value = customers[i].id;
        opt.textContent = customers[i].name;
        sel.appendChild(opt);
    }
}

function updateStats(invoices) {
    // IDs corretos do HTML: totalMRR, countContracts, countPending
    var totalEl = document.getElementById("totalMRR");
    if (totalEl) {
        var total = 0;
        for (var i = 0; i < invoices.length; i++) {
            if (invoices[i].status === "paid") total += invoices[i].amount;
        }
        totalEl.innerText = "R$ " + total.toFixed(2);
    }
    var pendingEl = document.getElementById("countPending");
    if (pendingEl) {
        var pending = 0;
        for (var i = 0; i < invoices.length; i++) {
            if (invoices[i].status === "pending") pending++;
        }
        pendingEl.innerText = pending;
    }
}

// === AÇÕES ===
function deleteCustomer(id) {
    if (!confirm("Remover cliente?")) return;
    fetch(API_URL + "/customers/" + id + "?api_key=" + API_KEY, { method: "DELETE" })
        .then(function() { fetchStats(); });
}

function runBilling() {
    pushLog("🚀 Iniciando Motor de Faturamento...");
    fetch(API_URL + "/billing/process-daily?api_key=" + API_KEY, { method: "POST" })
        .then(function() {
            pushLog("✅ Faturamento processado!");
            alert("Faturamento executado com sucesso!");
            fetchStats();
        });
}

function runDunning() {
    pushLog("🔍 Iniciando Análise de Cobrança e WhatsApp...");
    fetch(API_URL + "/billing/dunning-run?api_key=" + API_KEY, { method: "POST" })
        .then(function() {
            pushLog("✅ Análise concluída!");
            alert("Análise de cobrança concluída!");
            fetchStats();
        });
}

function copyToClipboard(text) {
    var fullUrl = window.location.origin + "/frontend/" + text;
    navigator.clipboard.writeText(fullUrl);
    pushLog("🔗 Link de pagamento seguro copiado!");
    alert("Link de checkout copiado!");
}

// === INICIALIZAÇÃO ===
document.addEventListener("DOMContentLoaded", function() {
    // Botões do header
    document.getElementById("btnNewCustomer").addEventListener("click", function() {
        openModal("customerModal");
    });
    document.getElementById("btnNewContract").addEventListener("click", function() {
        openModal("contractModal");
    });
    document.getElementById("btnRunBilling").addEventListener("click", function() {
        runBilling();
    });

    // Botão de dunning
    var btnDunning = document.getElementById("btnRunDunning");
    if (btnDunning) {
        btnDunning.addEventListener("click", function() { runDunning(); });
    }

    // Formulário de Cliente
    document.getElementById("customerForm").addEventListener("submit", function(e) {
        e.preventDefault();
        var name = document.getElementById("custName").value;
        var email = document.getElementById("custEmail").value;
        var phone = document.getElementById("custPhone").value;
        pushLog("Registrando cliente: " + name + "...");

        fetch(API_URL + "/customers?api_key=" + API_KEY, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name: name, email: email, phone: phone })
        })
        .then(function(res) {
            if (res.ok) {
                pushLog("✅ Cliente " + name + " registrado!");
                closeModal("customerModal");
                document.getElementById("customerForm").reset();
                fetchStats();
            } else {
                return res.json().then(function(err) {
                    alert("Erro: " + (err.detail || "Falha no registro"));
                });
            }
        })
        .catch(function(err) {
            alert("Erro de rede: " + err.message);
        });
    });

    // Formulário de Contrato - IDs corretos do HTML
    document.getElementById("contractForm").addEventListener("submit", function(e) {
        e.preventDefault();
        var data = {
            customer_id: parseInt(document.getElementById("selectCustomer").value),
            value: parseFloat(document.getElementById("contValue").value),
            start_date: document.getElementById("contStartDate").value
        };

        fetch(API_URL + "/contracts?api_key=" + API_KEY, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(data)
        })
        .then(function(res) {
            if (res.ok) {
                pushLog("✅ Contrato criado!");
                closeModal("contractModal");
                document.getElementById("contractForm").reset();
                fetchStats();
            }
        });
    });

    // Iniciar polling
    pushLog("Sistema inicializado com sucesso!");
    fetchStats();
    setInterval(fetchStats, 5000);
});
