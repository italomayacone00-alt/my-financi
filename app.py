from flask import Flask, render_template, request, redirect, url_for, Response, session
from werkzeug.security import generate_password_hash, check_password_hash
import json
import os
import csv
import io
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = 'sua_chave_secreta_super_segura' # Necessário para o Login funcionar

# Configuração de Pastas
USER_DATA_FOLDER = 'usuarios_dados'
if not os.path.exists(USER_DATA_FOLDER):
    os.makedirs(USER_DATA_FOLDER)

# Arquivo que guarda login e senha de todos
USERS_DB_FILE = os.path.join(USER_DATA_FOLDER, 'users_login.json')

CATEGORIAS = {
    'Despesa': ['Alimentação', 'Transporte', 'Moradia', 'Contas', 'Lazer', 'Saúde', 'Educação', 'Roupas', 'Outros Despesa'],
    'Receita': ['Salário', 'Freelance', 'Investimentos', 'Presente', 'Vendas', 'Outros Receita']
}

# --- FUNÇÕES DE SISTEMA (LOGIN/USUÁRIOS) ---

def carregar_usuarios():
    """Lê o arquivo de logins."""
    if not os.path.exists(USERS_DB_FILE):
        return {}
    try:
        with open(USERS_DB_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except: return {}

def salvar_usuarios(users_dict):
    """Salva um novo usuário registrado."""
    with open(USERS_DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(users_dict, f, indent=4)

def get_user_file_path(username):
    """Define o caminho do arquivo JSON exclusivo da pessoa."""
    return os.path.join(USER_DATA_FOLDER, f'{username}_dados.json')

# --- FUNÇÕES DE DADOS (TRANSAÇÕES/INVESTIMENTOS) ---

def carregar_dados():
    """
    Carrega os dados APENAS do usuário que está logado na sessão.
    """
    if 'username' not in session:
        return None # Ninguém logado

    username = session['username']
    filepath = get_user_file_path(username)
    
    # Estrutura padrão vazia
    padrao = {
        'transacoes': [], 
        'investimentos': [], 
        'config': {'nome_usuario': username}
    }

    if not os.path.exists(filepath):
        return padrao
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            dados = json.load(f)
            # Garante integridade das chaves
            if 'transacoes' not in dados: dados['transacoes'] = []
            if 'investimentos' not in dados: dados['investimentos'] = []
            if 'config' not in dados: dados['config'] = {'nome_usuario': username}
            return dados
    except:
        return padrao

def salvar_dados(dados):
    """Salva os dados no arquivo do usuário logado."""
    if 'username' not in session: return

    username = session['username']
    filepath = get_user_file_path(username)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(dados, f, indent=4, ensure_ascii=False)

# --- MIDDLEWARE DE SEGURANÇA ---
@app.before_request
def verificar_login():
    """Verifica se o usuário está logado antes de deixar acessar qualquer página."""
    rotas_liberadas = ['login', 'registrar', 'static']
    if request.endpoint not in rotas_liberadas and 'username' not in session:
        return redirect(url_for('login'))

# --- ROTAS DE AUTENTICAÇÃO ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        users = carregar_usuarios()
        
        # Verifica se usuário existe e a senha bate (usando hash)
        if username in users and check_password_hash(users[username], password):
            session['username'] = username
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error="Usuário ou senha incorretos.")
            
    return render_template('login.html')

@app.route('/registrar', methods=['GET', 'POST'])
def registrar():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        users = carregar_usuarios()
        
        if username in users:
            return render_template('login.html', error="Usuário já existe.", mode='register')
        
        # Cria criptografia da senha e salva
        users[username] = generate_password_hash(password)
        salvar_usuarios(users)
        
        session['username'] = username # Loga automaticamente após registrar
        return redirect(url_for('index'))
        
    return render_template('login.html', mode='register')

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))


# --- ROTAS DA APLICAÇÃO (DASHBOARD) ---

@app.route('/')
def index():
    dados = carregar_dados()
    transacoes = dados.get('transacoes', [])
    config = dados.get('config', {})

    saldo_atual = 0.0
    despesa_total = 0.0
    receita_total = 0.0

    hoje = datetime.now().date()
    trinta_dias_atras = hoje - timedelta(days=29)
    datas_grafico = []
    valores_saldo_grafico = []
    saldo_cumulativo = 0.0
    transacoes_por_data = {}

    # Processamento de totais
    for t in transacoes:
        try:
            val = float(t['valor'])
            if t['tipo'] == 'Receita':
                saldo_atual += val
                receita_total += val
            else:
                saldo_atual -= val
                despesa_total += val
        except: continue
    
    # Processamento do gráfico
    for t in transacoes:
        try:
            dt = datetime.strptime(t['data'], '%Y-%m-%d').date()
            if trinta_dias_atras <= dt <= hoje:
                if dt not in transacoes_por_data: transacoes_por_data[dt] = {'rec':0, 'desp':0}
                val = float(t['valor'])
                if t['tipo'] == 'Receita': transacoes_por_data[dt]['rec'] += val
                else: transacoes_por_data[dt]['desp'] += val
        except: continue
        
    curr = trinta_dias_atras
    while curr <= hoje:
        datas_grafico.append(curr.strftime('%d/%m'))
        if curr in transacoes_por_data:
            saldo_cumulativo += transacoes_por_data[curr]['rec']
            saldo_cumulativo -= transacoes_por_data[curr]['desp']
        valores_saldo_grafico.append(saldo_cumulativo)
        curr += timedelta(days=1)

    # Resumo 30 dias
    rec_30 = sum(float(t['valor']) for t in transacoes if t['tipo']=='Receita' and trinta_dias_atras <= datetime.strptime(t['data'], '%Y-%m-%d').date() <= hoje)
    desp_30 = sum(float(t['valor']) for t in transacoes if t['tipo']=='Despesa' and trinta_dias_atras <= datetime.strptime(t['data'], '%Y-%m-%d').date() <= hoje)

    return render_template('dashboard.html', 
        saldo_atual=saldo_atual, despesa_total=despesa_total, receita_total=receita_total,
        today_date=datetime.now().strftime('%Y-%m-%d'), categorias=CATEGORIAS,
        chart_labels=json.dumps(datas_grafico), chart_data=json.dumps(valores_saldo_grafico),
        receita_30_dias=rec_30, despesa_30_dias=desp_30, config=config
    )

@app.route('/transacoes')
def transacoes_page():
    dados = carregar_dados()
    lista = dados.get('transacoes', [])
    lista.sort(key=lambda x: x['data'], reverse=True)
    return render_template('transacoes.html', transacoes=lista)

@app.route('/adicionar_transacao', methods=['POST'])
def adicionar_transacao():
    dados = carregar_dados()
    dados['transacoes'].append({
        'tipo': request.form['tipo'],
        'data': request.form['data'],
        'descricao': request.form['descricao'],
        'valor': float(request.form['valor']),
        'categoria': request.form['categoria'],
        'pagar_com_opcao': request.form.get('pagar_com_opcao', '')
    })
    salvar_dados(dados)
    return redirect(url_for('index'))

@app.route('/excluir/<int:indice>')
def excluir_transacao(indice):
    dados = carregar_dados()
    if 0 <= indice < len(dados['transacoes']):
        del dados['transacoes'][indice]
        salvar_dados(dados)
    return redirect(url_for('transacoes_page'))

@app.route('/investimentos')
def investimentos_page():
    dados = carregar_dados()
    invs = dados.get('investimentos', [])
    total = sum(float(i['valor']) for i in invs)
    return render_template('investimentos.html', investimentos=invs, total_investido=total)

@app.route('/adicionar_investimento', methods=['POST'])
def adicionar_investimento():
    dados = carregar_dados()
    dados['investimentos'].append({
        'nome': request.form['nome'],
        'tipo': request.form['tipo'],
        'valor': float(request.form['valor']),
        'descricao': request.form['descricao'],
        'data_criacao': datetime.now().strftime('%Y-%m-%d')
    })
    salvar_dados(dados)
    return redirect(url_for('investimentos_page'))

@app.route('/excluir_investimento/<int:indice>')
def excluir_investimento(indice):
    dados = carregar_dados()
    if 0 <= indice < len(dados['investimentos']):
        del dados['investimentos'][indice]
        salvar_dados(dados)
    return redirect(url_for('investimentos_page'))

@app.route('/relatorios')
def relatorios_page():
    dados = carregar_dados()
    transacoes = dados.get('transacoes', [])
    
    gastos_cat = {}
    fluxo = {}
    
    for t in transacoes:
        val = float(t['valor'])
        if t['tipo'] == 'Despesa':
            gastos_cat[t['categoria']] = gastos_cat.get(t['categoria'], 0) + val
        
        mes = t['data'][:7]
        if mes not in fluxo: fluxo[mes] = {'receita': 0, 'despesa': 0}
        if t['tipo'] == 'Receita': fluxo[mes]['receita'] += val
        else: fluxo[mes]['despesa'] += val
        
    meses_ord = sorted(fluxo.keys())[-6:]
    labels, d_rec, d_desp = [], [], []
    for m in meses_ord:
        p = m.split('-')
        labels.append(f"{p[1]}/{p[0]}")
        d_rec.append(fluxo[m]['receita'])
        d_desp.append(fluxo[m]['despesa'])
        
    total_inv = sum(float(i['valor']) for i in dados.get('investimentos', []))
    
    return render_template('relatorios.html', 
        gastos_cat_labels=list(gastos_cat.keys()), gastos_cat_values=list(gastos_cat.values()),
        chart_meses=labels, chart_receita=d_rec, chart_despesa=d_desp, total_investido=total_inv)

@app.route('/configuracoes')
def configuracoes_page():
    dados = carregar_dados()
    return render_template('configuracoes.html', config=dados.get('config', {}))

@app.route('/salvar_configuracoes', methods=['POST'])
def salvar_configuracoes():
    dados = carregar_dados()
    dados['config']['nome_usuario'] = request.form['nome_usuario']
    salvar_dados(dados)
    return redirect(url_for('configuracoes_page'))

@app.route('/acao_perigo/<tipo>')
def acao_perigo(tipo):
    dados = carregar_dados()
    if tipo == 'limpar_transacoes': dados['transacoes'] = []
    elif tipo == 'limpar_investimentos': dados['investimentos'] = []
    elif tipo == 'reset_fabrica': 
        dados['transacoes'] = []
        dados['investimentos'] = []
    salvar_dados(dados)
    return redirect(url_for('configuracoes_page'))

# --- ROTA: DOWNLOAD CSV (LADO A LADO) ---
@app.route('/download_csv')
def download_csv():
    dados = carregar_dados()
    transacoes = dados.get('transacoes', [])
    investimentos = dados.get('investimentos', [])

    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')

    # Cabeçalho duplo na mesma linha
    writer.writerow([
        'DATA', 'TIPO', 'CATEGORIA', 'DESCRIÇÃO', 'VALOR', 'PAGAMENTO',
        '', # Coluna vazia para separar
        'DATA CRIAÇÃO', 'ATIVO', 'TIPO INVEST', 'VALOR ATUAL', 'NOTA'
    ])

    # Determina quem tem mais linhas para o loop
    max_linhas = max(len(transacoes), len(investimentos))

    for i in range(max_linhas):
        # Linha da Transação (Esquerda)
        if i < len(transacoes):
            t = transacoes[i]
            v_str = str(t['valor']).replace('.', ',')
            col_esq = [t['data'], t['tipo'], t['categoria'], t['descricao'], v_str, t.get('pagar_com_opcao','')]
        else:
            col_esq = ['', '', '', '', '', '']

        # Espaçador
        separador = ['']

        # Linha do Investimento (Direita)
        if i < len(investimentos):
            inv = investimentos[i]
            v_inv_str = str(inv['valor']).replace('.', ',')
            col_dir = [inv.get('data_criacao',''), inv['nome'], inv['tipo'], v_inv_str, inv['descricao']]
        else:
            col_dir = ['', '', '', '', '']

        # Junta tudo na mesma linha do CSV
        writer.writerow(col_esq + separador + col_dir)

    output.seek(0)
    user = session.get('username', 'usuario')
    return Response(
        output.getvalue().encode('utf-8-sig'),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename=relatorio_{user}.csv"}
    )

if __name__ == '__main__':
    app.run(debug=True)