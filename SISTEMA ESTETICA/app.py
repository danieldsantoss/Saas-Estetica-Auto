import os
import sqlite3
from datetime import datetime, date
from pathlib import Path
from functools import wraps

from flask import Flask, render_template, request, jsonify, send_from_directory, session, redirect, url_for
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / 'database.db'
RECIBOS_DIR = BASE_DIR / 'recibos'
UPLOAD_LOGOS_DIR = BASE_DIR / 'uploads' / 'logos'
UPLOAD_ORC_DIR = BASE_DIR / 'uploads' / 'orcamentos'
REPORTS_DIR = BASE_DIR / 'relatorios_pdf'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'troque-esta-chave-em-producao')
app.config['MAX_CONTENT_LENGTH'] = 8 * 1024 * 1024

for folder in [RECIBOS_DIR, UPLOAD_LOGOS_DIR, UPLOAD_ORC_DIR, REPORTS_DIR]:
    folder.mkdir(parents=True, exist_ok=True)


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def rows(sql, params=()):
    conn = get_db(); cur = conn.cursor(); cur.execute(sql, params)
    data = [dict(r) for r in cur.fetchall()]
    conn.close(); return data


def one(sql, params=()):
    conn = get_db(); cur = conn.cursor(); cur.execute(sql, params)
    r = cur.fetchone(); conn.close()
    return dict(r) if r else None


def execute(sql, params=()):
    conn = get_db(); cur = conn.cursor(); cur.execute(sql, params)
    conn.commit(); last = cur.lastrowid; conn.close(); return last


def table_columns(table):
    conn = get_db(); cur = conn.cursor(); cur.execute(f'PRAGMA table_info({table})')
    cols = [r['name'] for r in cur.fetchall()]
    conn.close(); return cols


def add_column_if_missing(table, column, definition):
    if column not in table_columns(table):
        execute(f'ALTER TABLE {table} ADD COLUMN {column} {definition}')


def init_db():
    conn = get_db(); cur = conn.cursor()
    cur.executescript('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT DEFAULT 'admin',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT
    );
    CREATE TABLE IF NOT EXISTS clientes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        telefone TEXT,
        cpf TEXT,
        email TEXT,
        placa TEXT,
        modelo TEXT,
        marca TEXT,
        cor TEXT,
        ano TEXT,
        observacoes TEXT,
        criado_em TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS servicos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        descricao TEXT,
        preco REAL NOT NULL DEFAULT 0,
        ativo INTEGER DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS employees (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        role TEXT,
        phone TEXT,
        email TEXT,
        status TEXT DEFAULT 'ativo',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS orcamentos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cliente_id INTEGER,
        employee_id INTEGER,
        status TEXT DEFAULT 'orcamento',
        subtotal REAL DEFAULT 0,
        desconto REAL DEFAULT 0,
        entrada REAL DEFAULT 0,
        total REAL DEFAULT 0,
        forma_pagamento TEXT,
        data_servico TEXT,
        hora_servico TEXT,
        retorno_cliente TEXT,
        observacoes TEXT,
        assinatura TEXT,
        recibo_pdf TEXT,
        criado_em TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(cliente_id) REFERENCES clientes(id),
        FOREIGN KEY(employee_id) REFERENCES employees(id)
    );
    CREATE TABLE IF NOT EXISTS budget_photos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        budget_id INTEGER,
        image_path TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(budget_id) REFERENCES orcamentos(id)
    );
    CREATE TABLE IF NOT EXISTS itens_orcamento (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        orcamento_id INTEGER,
        servico_id INTEGER,
        nome TEXT,
        descricao TEXT,
        valor REAL,
        FOREIGN KEY(orcamento_id) REFERENCES orcamentos(id)
    );
    CREATE TABLE IF NOT EXISTS financeiro (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tipo TEXT NOT NULL,
        nome TEXT NOT NULL,
        valor REAL NOT NULL,
        categoria TEXT,
        data TEXT,
        observacoes TEXT,
        orcamento_id INTEGER,
        criado_em TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS estoque (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        categoria TEXT,
        quantidade REAL DEFAULT 0,
        unidade TEXT,
        custo REAL DEFAULT 0,
        venda REAL DEFAULT 0,
        minimo REAL DEFAULT 0,
        fornecedor TEXT,
        data_compra TEXT,
        observacoes TEXT,
        criado_em TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS movimentacoes_estoque (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        produto_id INTEGER,
        tipo TEXT,
        quantidade REAL,
        motivo TEXT,
        data TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(produto_id) REFERENCES estoque(id)
    );
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT,
        task_date TEXT,
        task_time TEXT,
        status TEXT DEFAULT 'pendente',
        employee_id INTEGER,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(employee_id) REFERENCES employees(id)
    );
    CREATE TABLE IF NOT EXISTS services_agenda (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_name TEXT,
        vehicle TEXT,
        service_name TEXT,
        service_date TEXT,
        service_time TEXT,
        price REAL DEFAULT 0,
        status TEXT DEFAULT 'agendado',
        employee_id INTEGER,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(employee_id) REFERENCES employees(id)
    );
    CREATE TABLE IF NOT EXISTS configuracoes_empresa (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        nome_sistema TEXT DEFAULT 'AutoDetail Manager',
        nome TEXT,
        telefone TEXT,
        endereco TEXT,
        instagram TEXT,
        mensagem_recibo TEXT,
        cor_principal TEXT,
        logo TEXT,
        tema TEXT DEFAULT 'light'
    );
    ''')
    conn.commit(); conn.close()

    for col, definition in [('employee_id','INTEGER'),('hora_servico','TEXT'),('retorno_cliente','TEXT')]:
        add_column_if_missing('orcamentos', col, definition)
    add_column_if_missing('users', 'updated_at', 'TEXT')
    add_column_if_missing('configuracoes_empresa', 'nome_sistema', "TEXT DEFAULT 'AutoDetail Manager'")
    add_column_if_missing('configuracoes_empresa', 'tema', "TEXT DEFAULT 'light'")

    if one('SELECT COUNT(*) total FROM users')['total'] == 0:
        execute('INSERT INTO users(username,password_hash,role) VALUES (?,?,?)',
                ('admin', generate_password_hash('admin123'), 'admin'))
    if one('SELECT COUNT(*) total FROM servicos')['total'] == 0:
        servicos = [
            ('Lavagem simples','Lavagem externa rápida e acabamento básico',60),
            ('Lavagem completa','Lavagem externa e interna com acabamento',120),
            ('Higienização interna','Limpeza profunda de bancos, carpete e painel',280),
            ('Polimento comercial','Polimento de brilho e remoção leve de marcas',350),
            ('Polimento técnico','Correção técnica de pintura em etapas',700),
            ('Vitrificação','Proteção de pintura com coating',950),
            ('Revitalização de farol','Recuperação e proteção dos faróis',150),
            ('Hidratação de couro','Limpeza e hidratação de couro',180)
        ]
        conn = get_db(); cur = conn.cursor(); cur.executemany('INSERT INTO servicos(nome,descricao,preco) VALUES (?,?,?)', servicos); conn.commit(); conn.close()
    if one('SELECT COUNT(*) total FROM configuracoes_empresa')['total'] == 0:
        execute("""INSERT INTO configuracoes_empresa(id,nome_sistema,nome,telefone,endereco,instagram,mensagem_recibo,cor_principal,logo,tema)
                   VALUES (1,'AutoDetail Manager','Sua Estética Automotiva','(00) 00000-0000','Endereço da empresa','@suaempresa','Obrigado pela preferência!','#3b82f6','','light')""")


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get('user_id'):
            if request.path.startswith('/api/'):
                return jsonify({'ok': False, 'error': 'login_required'}), 401
            return redirect(url_for('login'))
        return fn(*args, **kwargs)
    return wrapper


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def money(v):
    return f"R$ {float(v or 0):.2f}".replace('.', ',')


def get_config():
    return one('SELECT * FROM configuracoes_empresa WHERE id=1') or {}


def save_budget_photo(file, budget_id):
    if not file or not file.filename or not allowed_file(file.filename):
        return None
    ext = secure_filename(file.filename).rsplit('.', 1)[1].lower()
    name = f'orcamento_{budget_id}_{datetime.now().strftime("%Y%m%d%H%M%S")}.{ext}'
    file.save(UPLOAD_ORC_DIR / name)
    execute('INSERT INTO budget_photos(budget_id,image_path) VALUES (?,?)', (budget_id, name))
    return name


def gerar_orcamento_pdf(orcamento_id):
    orc = one('''SELECT o.*, c.nome cliente_nome, c.telefone, c.placa, c.modelo, c.marca, c.cor, c.ano, e.name funcionario
                 FROM orcamentos o
                 LEFT JOIN clientes c ON c.id=o.cliente_id
                 LEFT JOIN employees e ON e.id=o.employee_id
                 WHERE o.id=?''', (orcamento_id,))
    itens = rows('SELECT * FROM itens_orcamento WHERE orcamento_id=?', (orcamento_id,))
    fotos = rows('SELECT * FROM budget_photos WHERE budget_id=? ORDER BY id DESC', (orcamento_id,))
    cfg = get_config()
    filename = f"orcamento_{orcamento_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
    path = RECIBOS_DIR / filename
    c = canvas.Canvas(str(path), pagesize=A4); w, h = A4
    primary = colors.HexColor(cfg.get('cor_principal') or '#3b82f6')
    c.setFillColor(colors.HexColor('#111111')); c.rect(0, h-4*cm, w, 4*cm, fill=1, stroke=0)
    c.setFillColor(primary); c.setFont('Helvetica-Bold', 20); c.drawString(2*cm, h-1.7*cm, cfg.get('nome') or cfg.get('nome_sistema') or 'AutoDetail Manager')
    c.setFillColor(colors.white); c.setFont('Helvetica', 9)
    c.drawString(2*cm, h-2.35*cm, f"Tel: {cfg.get('telefone') or ''} | Instagram: {cfg.get('instagram') or ''}")
    c.drawString(2*cm, h-2.85*cm, cfg.get('endereco') or '')
    y = h-5*cm
    c.setFillColor(colors.black); c.setFont('Helvetica-Bold', 15); c.drawString(2*cm, y, f"Orçamento / OS #{orcamento_id}"); y -= .8*cm
    c.setFont('Helvetica', 10)
    lines = [
        f"Cliente: {orc.get('cliente_nome') or 'Não informado'}",
        f"Telefone: {orc.get('telefone') or ''}",
        f"Veículo: {orc.get('marca') or ''} {orc.get('modelo') or ''} | Placa: {orc.get('placa') or ''} | Cor: {orc.get('cor') or ''} | Ano: {orc.get('ano') or ''}",
        f"Funcionário responsável: {orc.get('funcionario') or 'Não informado'}",
        f"Data/Hora do serviço: {orc.get('data_servico') or ''} {orc.get('hora_servico') or ''}",
    ]
    for line in lines:
        c.drawString(2*cm, y, line[:115]); y -= .5*cm
    y -= .4*cm; c.setFont('Helvetica-Bold', 11); c.drawString(2*cm, y, 'Serviço'); c.drawRightString(w-2*cm, y, 'Valor'); y -= .2*cm
    c.setStrokeColor(primary); c.line(2*cm, y, w-2*cm, y); y -= .5*cm
    c.setFont('Helvetica', 10)
    for item in itens:
        if y < 6*cm: c.showPage(); y = h-2*cm
        c.drawString(2*cm, y, (item.get('nome') or '')[:70]); c.drawRightString(w-2*cm, y, money(item.get('valor'))); y -= .5*cm
    y -= .4*cm; c.setFont('Helvetica-Bold', 10)
    c.drawRightString(w-2*cm, y, f"Subtotal: {money(orc.get('subtotal'))}"); y -= .5*cm
    c.drawRightString(w-2*cm, y, f"Desconto: {money(orc.get('desconto'))}"); y -= .5*cm
    c.setFillColor(primary); c.setFont('Helvetica-Bold', 14); c.drawRightString(w-2*cm, y, f"TOTAL: {money(orc.get('total'))}"); y -= .9*cm
    c.setFillColor(colors.black); c.setFont('Helvetica', 10)
    c.drawString(2*cm, y, f"Forma de pagamento: {orc.get('forma_pagamento') or ''}"); y -= .5*cm
    c.drawString(2*cm, y, f"Observações: {(orc.get('observacoes') or '')[:110]}"); y -= .8*cm
    if fotos:
        foto_path = UPLOAD_ORC_DIR / fotos[0]['image_path']
        if foto_path.exists():
            try:
                c.drawString(2*cm, y, 'Foto anexada ao orçamento:'); y -= .3*cm
                c.drawImage(str(foto_path), 2*cm, max(2*cm, y-5*cm), width=7*cm, height=5*cm, preserveAspectRatio=True, mask='auto')
                y -= 5.5*cm
            except Exception:
                pass
    c.setFont('Helvetica-Oblique', 9); c.drawCentredString(w/2, 1.5*cm, cfg.get('mensagem_recibo') or 'Obrigado pela preferência!')
    c.save(); execute('UPDATE orcamentos SET recibo_pdf=? WHERE id=?', (filename, orcamento_id)); return filename


def atualizar_financeiro_por_orcamento(orcamento_id):
    orc = one('SELECT * FROM orcamentos WHERE id=?', (orcamento_id,))
    if not orc or orc['status'] != 'finalizado': return
    existe = one('SELECT id FROM financeiro WHERE orcamento_id=? AND tipo="entrada"', (orcamento_id,))
    if not existe:
        execute('INSERT INTO financeiro(tipo,nome,valor,categoria,data,observacoes,orcamento_id) VALUES (?,?,?,?,?,?,?)',
                ('entrada', f'Serviço finalizado #{orcamento_id}', orc['total'], 'Serviços', orc.get('data_servico') or str(date.today()), 'Entrada automática gerada pelo sistema', orcamento_id))

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'GET':
        if session.get('user_id'): return redirect(url_for('index'))
        return render_template('login.html', cfg=get_config())
    username = request.form.get('username','').strip(); password = request.form.get('password','')
    user = one('SELECT * FROM users WHERE username=?', (username,))
    if user and check_password_hash(user['password_hash'], password):
        session['user_id'] = user['id']; session['username'] = user['username']; return redirect(url_for('index'))
    return render_template('login.html', error='Usuário ou senha inválidos', cfg=get_config())

@app.route('/logout')
def logout():
    session.clear(); return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    return render_template('index.html', username=session.get('username'), cfg=get_config())

@app.route('/api/me')
@login_required
def me():
    return jsonify({'username': session.get('username')})

@app.route('/api/account', methods=['POST'])
@login_required
def account():
    d = request.json or {}; user = one('SELECT * FROM users WHERE id=?', (session['user_id'],))
    current = d.get('current_password',''); new_username = (d.get('username') or user['username']).strip()
    new_password = d.get('new_password') or ''; confirm = d.get('confirm_password') or ''
    if not check_password_hash(user['password_hash'], current): return jsonify({'ok': False, 'error': 'Senha atual incorreta'}), 400
    if new_password and new_password != confirm: return jsonify({'ok': False, 'error': 'A confirmação da senha não confere'}), 400
    if new_password and len(new_password) < 6: return jsonify({'ok': False, 'error': 'A nova senha precisa ter pelo menos 6 caracteres'}), 400
    pwd_hash = generate_password_hash(new_password) if new_password else user['password_hash']
    execute('UPDATE users SET username=?, password_hash=?, updated_at=? WHERE id=?', (new_username, pwd_hash, datetime.now().isoformat(timespec='seconds'), user['id']))
    session['username'] = new_username
    return jsonify({'ok': True})

@app.route('/api/dashboard')
@login_required
def dashboard():
    hoje = str(date.today()); mes = datetime.now().strftime('%Y-%m')
    faturado = one("SELECT COALESCE(SUM(valor),0) total FROM financeiro WHERE tipo='entrada' AND substr(data,1,7)=?", (mes,))['total']
    despesas = one("SELECT COALESCE(SUM(valor),0) total FROM financeiro WHERE tipo='saida' AND substr(data,1,7)=?", (mes,))['total']
    return jsonify({
        'faturado': faturado, 'despesas': despesas, 'lucro': faturado-despesas,
        'clientes': one('SELECT COUNT(*) total FROM clientes')['total'],
        'orcamentos': one('SELECT COUNT(*) total FROM orcamentos')['total'],
        'servicos_realizados': one("SELECT COUNT(*) total FROM orcamentos WHERE status='finalizado'")['total'],
        'tarefas_hoje': rows('''SELECT t.*, e.name funcionario FROM tasks t LEFT JOIN employees e ON e.id=t.employee_id WHERE t.task_date=? ORDER BY t.task_time''', (hoje,)),
        'servicos_hoje': rows('''SELECT s.*, e.name funcionario FROM services_agenda s LEFT JOIN employees e ON e.id=s.employee_id WHERE s.service_date=? ORDER BY s.service_time''', (hoje,)),
        'orcamentos_pendentes': rows('''SELECT o.*, c.nome cliente, e.name funcionario FROM orcamentos o LEFT JOIN clientes c ON c.id=o.cliente_id LEFT JOIN employees e ON e.id=o.employee_id WHERE o.status IN ('orcamento','aprovado') ORDER BY o.id DESC LIMIT 8'''),
        'retornos': rows('''SELECT o.*, c.nome cliente FROM orcamentos o LEFT JOIN clientes c ON c.id=o.cliente_id WHERE retorno_cliente IS NOT NULL AND retorno_cliente != '' ORDER BY retorno_cliente LIMIT 8'''),
        'ultimos': rows('''SELECT o.id,o.total,o.status,o.criado_em,c.nome cliente,e.name funcionario FROM orcamentos o LEFT JOIN clientes c ON c.id=o.cliente_id LEFT JOIN employees e ON e.id=o.employee_id ORDER BY o.id DESC LIMIT 6''')
    })

@app.route('/api/clientes', methods=['GET','POST'])
@login_required
def clientes():
    if request.method == 'GET':
        q = request.args.get('q','')
        return jsonify(rows('SELECT * FROM clientes WHERE nome LIKE ? OR telefone LIKE ? OR placa LIKE ? ORDER BY id DESC', (f'%{q}%',f'%{q}%',f'%{q}%')))
    d = request.json or {}
    cid = execute('''INSERT INTO clientes(nome,telefone,cpf,email,placa,modelo,marca,cor,ano,observacoes) VALUES (?,?,?,?,?,?,?,?,?,?)''',
                  (d.get('nome'),d.get('telefone'),d.get('cpf'),d.get('email'),d.get('placa'),d.get('modelo'),d.get('marca'),d.get('cor'),d.get('ano'),d.get('observacoes')))
    return jsonify({'ok': True, 'id': cid})

@app.route('/api/clientes/<int:id>', methods=['DELETE'])
@login_required
def cliente_delete(id):
    execute('DELETE FROM clientes WHERE id=?', (id,)); return jsonify({'ok': True})

@app.route('/api/servicos')
@login_required
def servicos(): return jsonify(rows('SELECT * FROM servicos WHERE ativo=1 ORDER BY nome'))

@app.route('/api/employees', methods=['GET','POST'])
@login_required
def employees():
    if request.method == 'GET': return jsonify(rows('SELECT * FROM employees ORDER BY status, name'))
    d = request.json or {}; eid = execute('INSERT INTO employees(name,role,phone,email,status) VALUES (?,?,?,?,?)', (d.get('name'),d.get('role'),d.get('phone'),d.get('email'),d.get('status','ativo')))
    return jsonify({'ok': True, 'id': eid})

@app.route('/api/employees/<int:id>', methods=['PUT','DELETE'])
@login_required
def employee_item(id):
    if request.method == 'DELETE':
        execute('UPDATE employees SET status="inativo" WHERE id=?', (id,)); return jsonify({'ok': True})
    d = request.json or {}; execute('UPDATE employees SET name=?,role=?,phone=?,email=?,status=? WHERE id=?', (d.get('name'),d.get('role'),d.get('phone'),d.get('email'),d.get('status'),id)); return jsonify({'ok': True})

@app.route('/api/tasks', methods=['GET','POST'])
@login_required
def tasks():
    if request.method == 'GET': return jsonify(rows('''SELECT t.*, e.name funcionario FROM tasks t LEFT JOIN employees e ON e.id=t.employee_id ORDER BY t.task_date DESC, t.task_time DESC'''))
    d = request.json or {}; tid = execute('INSERT INTO tasks(title,description,task_date,task_time,status,employee_id) VALUES (?,?,?,?,?,?)', (d.get('title'),d.get('description'),d.get('task_date'),d.get('task_time'),d.get('status','pendente'),d.get('employee_id') or None)); return jsonify({'ok': True, 'id': tid})

@app.route('/api/tasks/<int:id>', methods=['PUT','DELETE'])
@login_required
def task_item(id):
    if request.method == 'DELETE': execute('DELETE FROM tasks WHERE id=?',(id,)); return jsonify({'ok': True})
    d = request.json or {}; execute('UPDATE tasks SET title=?,description=?,task_date=?,task_time=?,status=?,employee_id=? WHERE id=?', (d.get('title'),d.get('description'),d.get('task_date'),d.get('task_time'),d.get('status'),d.get('employee_id') or None,id)); return jsonify({'ok': True})

@app.route('/api/services-agenda', methods=['GET','POST'])
@login_required
def services_agenda():
    if request.method == 'GET': return jsonify(rows('''SELECT s.*, e.name funcionario FROM services_agenda s LEFT JOIN employees e ON e.id=s.employee_id ORDER BY s.service_date DESC, s.service_time DESC'''))
    d = request.json or {}; sid = execute('INSERT INTO services_agenda(client_name,vehicle,service_name,service_date,service_time,price,status,employee_id) VALUES (?,?,?,?,?,?,?,?)', (d.get('client_name'),d.get('vehicle'),d.get('service_name'),d.get('service_date'),d.get('service_time'),float(d.get('price') or 0),d.get('status','agendado'),d.get('employee_id') or None)); return jsonify({'ok': True, 'id': sid})

@app.route('/api/services-agenda/<int:id>', methods=['DELETE'])
@login_required
def service_agenda_delete(id): execute('DELETE FROM services_agenda WHERE id=?',(id,)); return jsonify({'ok': True})

@app.route('/api/orcamentos', methods=['GET','POST'])
@login_required
def orcamentos():
    if request.method == 'GET':
        return jsonify(rows('''SELECT o.*, c.nome cliente, e.name funcionario FROM orcamentos o LEFT JOIN clientes c ON c.id=o.cliente_id LEFT JOIN employees e ON e.id=o.employee_id ORDER BY o.id DESC'''))
    if request.content_type and request.content_type.startswith('multipart/form-data'):
        d = request.form; itens = __import__('json').loads(d.get('itens','[]'))
    else:
        d = request.json or {}; itens = d.get('itens', [])
    subtotal = sum(float(i.get('valor') or 0) for i in itens); desconto = float(d.get('desconto') or 0); total = max(0, subtotal-desconto)
    oid = execute('''INSERT INTO orcamentos(cliente_id,employee_id,status,subtotal,desconto,entrada,total,forma_pagamento,data_servico,hora_servico,retorno_cliente,observacoes,assinatura) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                  (d.get('cliente_id'), d.get('employee_id') or None, d.get('status','orcamento'), subtotal, desconto, float(d.get('entrada') or 0), total, d.get('forma_pagamento'), d.get('data_servico'), d.get('hora_servico'), d.get('retorno_cliente'), d.get('observacoes'), d.get('assinatura')))
    for item in itens:
        execute('INSERT INTO itens_orcamento(orcamento_id,servico_id,nome,descricao,valor) VALUES (?,?,?,?,?)', (oid,item.get('servico_id'),item.get('nome'),item.get('descricao'),float(item.get('valor') or 0)))
    if request.files.get('foto'): save_budget_photo(request.files['foto'], oid)
    if d.get('status') == 'finalizado':
        gerar_orcamento_pdf(oid); atualizar_financeiro_por_orcamento(oid)
    return jsonify({'ok': True, 'id': oid})

@app.route('/api/orcamentos/<int:id>/finalizar', methods=['POST'])
@login_required
def finalizar_orcamento(id):
    execute("UPDATE orcamentos SET status='finalizado' WHERE id=?", (id,)); pdf = gerar_orcamento_pdf(id); atualizar_financeiro_por_orcamento(id); return jsonify({'ok': True, 'pdf': pdf})

@app.route('/api/orcamentos/<int:id>/pdf')
@login_required
def pdf_orcamento(id):
    pdf = gerar_orcamento_pdf(id); return jsonify({'ok': True, 'pdf': pdf})

@app.route('/recibos/<filename>')
@login_required
def recibos_file(filename): return send_from_directory(RECIBOS_DIR, filename)

@app.route('/uploads/orcamentos/<filename>')
@login_required
def orc_file(filename): return send_from_directory(UPLOAD_ORC_DIR, filename)

@app.route('/api/financeiro', methods=['GET','POST'])
@login_required
def financeiro():
    if request.method == 'GET': return jsonify(rows('SELECT * FROM financeiro ORDER BY data DESC, id DESC'))
    d = request.json or {}; fid = execute('INSERT INTO financeiro(tipo,nome,valor,categoria,data,observacoes) VALUES (?,?,?,?,?,?)', (d.get('tipo'),d.get('nome'),float(d.get('valor') or 0),d.get('categoria'),d.get('data') or str(date.today()),d.get('observacoes'))); return jsonify({'ok': True, 'id': fid})

@app.route('/api/estoque', methods=['GET','POST'])
@login_required
def estoque():
    if request.method == 'GET': return jsonify(rows('SELECT * FROM estoque ORDER BY nome'))
    d = request.json or {}; pid = execute('''INSERT INTO estoque(nome,categoria,quantidade,unidade,custo,venda,minimo,fornecedor,data_compra,observacoes) VALUES (?,?,?,?,?,?,?,?,?,?)''', (d.get('nome'),d.get('categoria'),float(d.get('quantidade') or 0),d.get('unidade'),float(d.get('custo') or 0),float(d.get('venda') or 0),float(d.get('minimo') or 0),d.get('fornecedor'),d.get('data_compra'),d.get('observacoes'))); return jsonify({'ok': True, 'id': pid})

@app.route('/api/estoque/<int:id>/movimentar', methods=['POST'])
@login_required
def movimentar_estoque(id):
    d = request.json or {}; produto = one('SELECT * FROM estoque WHERE id=?',(id,)); qtd=float(d.get('quantidade') or 0); tipo=d.get('tipo'); nova=float(produto['quantidade'])+qtd if tipo=='entrada' else max(0,float(produto['quantidade'])-qtd); execute('UPDATE estoque SET quantidade=? WHERE id=?',(nova,id)); execute('INSERT INTO movimentacoes_estoque(produto_id,tipo,quantidade,motivo) VALUES (?,?,?,?)',(id,tipo,qtd,d.get('motivo','Movimentação manual'))); return jsonify({'ok': True})

@app.route('/api/relatorios')
@login_required
def relatorios():
    mes = request.args.get('mes', datetime.now().strftime('%Y-%m'))
    cliente = request.args.get('cliente',''); servico = request.args.get('servico',''); funcionario = request.args.get('funcionario',''); inicio = request.args.get('inicio',''); fim = request.args.get('fim',''); ano = request.args.get('ano','')
    wh = []; params=[]
    if inicio: wh.append('date(o.data_servico) >= date(?)'); params.append(inicio)
    if fim: wh.append('date(o.data_servico) <= date(?)'); params.append(fim)
    if mes and not inicio and not fim and not ano: wh.append('substr(COALESCE(o.data_servico,o.criado_em),1,7)=?'); params.append(mes)
    if ano: wh.append('substr(COALESCE(o.data_servico,o.criado_em),1,4)=?'); params.append(ano)
    if cliente: wh.append('c.nome LIKE ?'); params.append(f'%{cliente}%')
    if servico: wh.append('io.nome LIKE ?'); params.append(f'%{servico}%')
    if funcionario: wh.append('e.id = ?'); params.append(funcionario)
    where = ('WHERE ' + ' AND '.join(wh)) if wh else ''
    detalhes = rows(f'''SELECT o.id, o.total, COALESCE(o.data_servico,o.criado_em) data, c.nome cliente, e.name funcionario, GROUP_CONCAT(io.nome, ', ') servicos
                         FROM orcamentos o LEFT JOIN clientes c ON c.id=o.cliente_id LEFT JOIN employees e ON e.id=o.employee_id LEFT JOIN itens_orcamento io ON io.orcamento_id=o.id
                         {where} GROUP BY o.id ORDER BY data DESC''', tuple(params))
    return jsonify({
        'faturamento': sum(float(d.get('total') or 0) for d in detalhes),
        'quantidade': len(detalhes),
        'detalhes': detalhes,
        'despesas': one("SELECT COALESCE(SUM(valor),0) total FROM financeiro WHERE tipo='saida' AND substr(data,1,7)=?", (mes,))['total'],
        'servicos': rows('''SELECT io.nome, COUNT(*) qtd, SUM(io.valor) total FROM itens_orcamento io GROUP BY io.nome ORDER BY qtd DESC LIMIT 8'''),
        'clientes_top': rows('''SELECT c.nome, COUNT(o.id) qtd, SUM(o.total) total FROM clientes c JOIN orcamentos o ON o.cliente_id=c.id GROUP BY c.id ORDER BY total DESC LIMIT 8'''),
        'estoque_baixo': rows('SELECT * FROM estoque WHERE quantidade <= minimo ORDER BY quantidade ASC')
    })

@app.route('/api/relatorios/pdf')
@login_required
def relatorios_pdf():
    data = relatorios().get_json(); cfg = get_config(); filename = f"relatorio_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"; path = REPORTS_DIR / filename
    c = canvas.Canvas(str(path), pagesize=landscape(A4)); w,h = landscape(A4); primary = colors.HexColor(cfg.get('cor_principal') or '#3b82f6')
    c.setFillColor(colors.HexColor('#f4f7fb')); c.rect(0,h-3*cm,w,3*cm,fill=1,stroke=0); c.setFillColor(primary); c.setFont('Helvetica-Bold',18); c.drawString(1.5*cm,h-1.3*cm,cfg.get('nome') or cfg.get('nome_sistema') or 'AutoDetail Manager')
    c.setFillColor(colors.HexColor('#334155')); c.setFont('Helvetica',9); c.drawString(1.5*cm,h-2*cm,f"Relatório gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    y=h-4*cm; c.setFillColor(colors.black); c.setFont('Helvetica-Bold',13); c.drawString(1.5*cm,y,f"Faturamento total: {money(data['faturamento'])} | Serviços/Orçamentos: {data['quantidade']}"); y-=.8*cm
    c.setFont('Helvetica-Bold',9); headers=['ID','Cliente','Serviços','Funcionário','Data','Total']; xs=[1.5,3,7,16,21,25]
    for x,hd in zip(xs,headers): c.drawString(x*cm,y,hd)
    y-=.3*cm; c.setStrokeColor(primary); c.line(1.5*cm,y,w-1.5*cm,y); y-=.45*cm; c.setFont('Helvetica',8)
    for d in data['detalhes']:
        if y < 1.5*cm: c.showPage(); y=h-2*cm
        vals=[str(d.get('id') or ''), (d.get('cliente') or '')[:20], (d.get('servicos') or '')[:48], (d.get('funcionario') or '')[:20], (d.get('data') or '')[:10], money(d.get('total'))]
        for x,val in zip(xs,vals): c.drawString(x*cm,y,val)
        y-=.45*cm
    c.save(); return jsonify({'ok': True, 'pdf': filename})

@app.route('/relatorios_pdf/<filename>')
@login_required
def reports_file(filename): return send_from_directory(REPORTS_DIR, filename)

@app.route('/api/config', methods=['GET','POST'])
@login_required
def config():
    if request.method == 'GET': return jsonify(get_config())
    d = request.form; current_cfg = get_config(); logo_name = current_cfg.get('logo') or ''
    if 'logo' in request.files and request.files['logo'].filename and allowed_file(request.files['logo'].filename):
        file = request.files['logo']; logo_name = f"logo_{datetime.now().strftime('%Y%m%d%H%M%S')}_{secure_filename(file.filename)}"; file.save(UPLOAD_LOGOS_DIR / logo_name)
    execute('''UPDATE configuracoes_empresa SET nome_sistema=?,nome=?,telefone=?,endereco=?,instagram=?,mensagem_recibo=?,cor_principal=?,logo=?,tema=? WHERE id=1''', (
        d.get('nome_sistema') or current_cfg.get('nome_sistema') or 'AutoDetail Manager',
        d.get('nome') or current_cfg.get('nome') or '',
        d.get('telefone'),d.get('endereco'),d.get('instagram'),d.get('mensagem_recibo'),
        d.get('cor_principal') or '#3b82f6',logo_name,d.get('tema') or 'light'
    )); return jsonify({'ok': True})

@app.route('/uploads/logos/<filename>')
def logo_file(filename): return send_from_directory(UPLOAD_LOGOS_DIR, filename)

# Inicializa/migra o banco também quando o app é executado por Gunicorn/servidor externo.
init_db()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)
