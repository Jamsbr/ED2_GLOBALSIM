import os
from urllib.parse import urlparse

from flask import Flask, flash, redirect, render_template, request, session, url_for
from datetime import timedelta

from servicos import GlobalSIM, REGIOES, STATUS, TECNOLOGIAS

app = Flask(__name__, template_folder="frontend/templates", static_folder="frontend/static")
app.secret_key = os.environ.get("GLOBALSIM_SECRET", "segredo123")
app.permanent_session_lifetime = timedelta(days=30)

sistema = GlobalSIM() # Inicializa o sistema GlobalSIM
POR_PAGINA = 25


@app.before_request #Antes de cada requisição, desloga o usuário se o cliente da sessão não existir mais.
def validarSessao():
    idLogado = session.get("cliente_id")
    if idLogado is not None and sistema.cliente(idLogado, registrar=False) is None:
        session.pop("cliente_id", None)


@app.context_processor # Adiciona previamente o contexto para os templates. Ex: nome do site, usuário logado, pacote do usuário.
def contexto():
    usuario = None
    idLogado = session.get("cliente_id")
    if idLogado is not None:
        cliente = sistema.cliente(idLogado, registrar=False)
        if cliente:
            pacote = sistema.pacote(cliente["pacote"]) if cliente["pacote"] else None
            usuario = dict(cliente, pacoteNome=pacote["pacote"] if pacote else "—")
    return {"nomeSite": "GlobalSIM", "usuario": usuario}


@app.template_global()
def nomePacote(codigo):
    pacote = sistema.pacote(codigo) if codigo else None
    return pacote["pacote"] if pacote else "—"


def destinoSeguro(destino): #Redirecionamento depois do login.
    if destino and destino.startswith("/") and not urlparse(destino).netloc and not destino.startswith("//"):
        return destino
    return url_for("principal")


def numero(texto):
    texto = (texto or "").strip()
    return int(texto) if texto.isdigit() else None


@app.route('/')
def principal():
    return render_template('index.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    proximo = request.values.get('proximo', '')
    if request.method == 'POST':
        idCliente = numero(request.form.get('id'))
        email = request.form.get('email', '').strip().lower()
        cliente = sistema.cliente(idCliente) if idCliente is not None else None
        if cliente and cliente["email"].lower() == email:
            session.permanent = True
            session["cliente_id"] = cliente["id"]
            flash(f"Bem-vindo(a), {cliente['nome']}!", "success")
            return redirect(destinoSeguro(proximo))
        flash("ID ou e-mail incorretos.", "danger")
    return render_template('login.html', proximo=proximo)


@app.route('/logout', methods=['POST'])
def logout():
    session.pop("cliente_id", None)
    flash("Você saiu da sua conta.", "success")
    return redirect(url_for('principal'))


@app.route('/paises')
def listaPaises():
    regiao, tecnologia = request.args.get('regiao', ''), request.args.get('tecnologia', '')
    busca = sistema.buscaPaises(regiao, tecnologia) if regiao or tecnologia else None
    return render_template('paises.html', paises=busca["paises"] if busca else sistema.paises.listar(),
                           busca=busca, regiao=regiao, tecnologia=tecnologia, regioes=REGIOES,
                           tecnologias=TECNOLOGIAS, stats=sistema.paises.estatisticas(),
                           posicoes=sistema.paises.posicoes,
                           indices=[sistema.idxRegiao.estatisticas(), sistema.idxTecnologia.estatisticas()])


@app.route('/paises/cadastrar', methods=['GET', 'POST'])
def cadastrarPais():
    if request.method == 'POST':
        pais = sistema.lerPais(request.form)
        erro = sistema.validarPais(pais)
        if erro:
            flash(erro, "danger")
        elif not sistema.cadastrarPais(pais):
            flash(f"O país {pais['codigo']} já está cadastrado!", "danger")
        else:
            flash(f"País {pais['codigo']} cadastrado com sucesso!", "success")
            return redirect(url_for('listaPaises'))
        return render_template('formPais.html', pais=pais, novo=True, regioes=REGIOES, tecnologias=TECNOLOGIAS)
    return render_template('formPais.html', pais={}, novo=True, regioes=REGIOES, tecnologias=TECNOLOGIAS)


@app.route('/paises/alterar/<codigo>', methods=['GET', 'POST'])
def alterarPais(codigo):
    pais = sistema.buscarPais(codigo)
    if not pais:
        flash(f"País {codigo} não encontrado!", "danger")
        return redirect(url_for('listaPaises'))
    if request.method == 'POST':
        novo = sistema.lerPais(request.form)
        novo["codigo"] = pais["codigo"]
        erro = sistema.validarPais(novo)
        if erro:
            flash(erro, "danger")
            return render_template('formPais.html', pais=novo, novo=False, regioes=REGIOES, tecnologias=TECNOLOGIAS)
        sistema.alterarPais(pais["codigo"], novo)
        flash(f"País {pais['codigo']} atualizado com sucesso!", "success")
        return redirect(url_for('listaPaises'))
    return render_template('formPais.html', pais=pais, novo=False, regioes=REGIOES, tecnologias=TECNOLOGIAS)


@app.route('/paises/remover/<codigo>', methods=['POST'])
def removerPais(codigo):
    removeu, conexoes = sistema.removerPais(codigo.upper())
    if removeu:
        extra = f" e {conexoes} conexão(ões) da rede" if conexoes else ""
        flash(f"País {codigo.upper()} removido com sucesso{extra}!", "success")
    else:
        flash(f"País {codigo} não encontrado!", "danger")
    return redirect(url_for('listaPaises'))


@app.route('/cobertura', methods=['GET', 'POST'])
def cobertura():
    if request.method == 'POST':
        codigo = request.form.get('codigo', '').strip().upper()
        pais = sistema.paises.buscar(codigo)
        return render_template('cobertura.html', codigo=codigo, pais=pais, busca=sistema.paises.ultimaBusca)
    return render_template('cobertura.html')


@app.route('/clientes')
def listaClientes():
    status, pacote = request.args.get('status', ''), request.args.get('pacote', '')
    total = sistema.clientes.tamanho
    paginas = max(1, -(-total // POR_PAGINA))
    pagina = min(max(numero(request.args.get('pagina')) or 1, 1), paginas)
    busca = sistema.buscaClientes(status, pacote) if status or pacote else None
    return render_template('clientes.html', clientes=busca["clientes"] if busca else sistema.listarClientes(pagina, POR_PAGINA),
                           rc=busca, status=status, pacote=pacote, pagina=pagina, paginas=paginas,
                           total=total, estados=STATUS, pacotes=sistema.pacotes,
                           indices=[sistema.idxStatus.estatisticas(), sistema.idxPacote.estatisticas()])


@app.route('/clientes/buscar')
def buscarCliente():
    idCliente = numero(request.args.get('id'))
    if idCliente is None:
        flash("Informe um ID numérico.", "danger")
        return redirect(url_for('listaClientes'))
    return redirect(url_for('detalheCliente', id=idCliente))


@app.route('/clientes/<int:id>')
def detalheCliente(id):
    cliente = sistema.cliente(id)
    busca = dict(sistema.clientes.ultimaBusca)
    if cliente is None:
        flash(f"Cliente {id} não encontrado na Árvore B.", "danger")
        return redirect(url_for('listaClientes'))
    return render_template('cliente.html', cliente=cliente, busca=busca,
                           pacote=sistema.pacote(cliente["pacote"]) if cliente["pacote"] else None)


@app.route('/clientes/cadastrar', methods=['GET', 'POST'])
def cadastrarCliente():
    if request.method == 'POST':
        idCliente = numero(request.form.get('id'))
        nome, email = request.form.get('nome', ''), request.form.get('email', '')
        if idCliente is None or idCliente <= 0:
            flash("O ID deve ser um número positivo.", "danger")
        else:
            cliente, erro = sistema.cadastrarCliente(idCliente, nome, email)
            if erro:
                flash(erro, "danger")
            else:
                flash(f"Cliente {idCliente} cadastrado! Associe um pacote para ativar o eSIM.", "success")
                return redirect(url_for('associarCliente', id=idCliente))
        return render_template('formCliente.html', modo='cadastrar',
                               cliente={"id": request.form.get('id', ''), "nome": nome, "email": email})
    return render_template('formCliente.html', modo='cadastrar',
                           cliente={"id": sistema.proximoId(), "nome": "", "email": ""})


@app.route('/clientes/<int:id>/alterar', methods=['GET', 'POST'])
def alterarCliente(id):
    cliente = sistema.cliente(id, registrar=False)
    if cliente is None:
        flash(f"Cliente {id} não encontrado!", "danger")
        return redirect(url_for('listaClientes'))
    if request.method == 'POST':
        novo, erro = sistema.alterarCliente(id, request.form.get('nome', ''), request.form.get('email', ''),
                                            request.form.get('status', ''))
        if erro:
            flash(erro, "danger")
            cliente = dict(cliente, nome=request.form.get('nome', ''), email=request.form.get('email', ''),
                           status=request.form.get('status', cliente["status"]))
            return render_template('formCliente.html', modo='alterar', cliente=cliente, status=STATUS)
        flash("Dados do cliente atualizados!", "success")
        return redirect(url_for('detalheCliente', id=id))
    return render_template('formCliente.html', modo='alterar', cliente=cliente, status=STATUS)


@app.route('/clientes/<int:id>/associar', methods=['GET', 'POST'])
def associarCliente(id):
    cliente = sistema.cliente(id, registrar=False)
    if cliente is None:
        flash(f"Cliente {id} não encontrado!", "danger")
        return redirect(url_for('listaClientes'))
    if request.method == 'POST':
        novo, erro = sistema.associarEsimPacote(id, request.form.get('pacote', ''), request.form.get('esim', ''))
        if erro:
            flash(erro, "danger")
        else:
            flash(f"eSIM {novo['esim']} e pacote {nomePacote(novo['pacote'])} associados!", "success")
            return redirect(url_for('detalheCliente', id=id))
    return render_template('associar.html', cliente=cliente, pacotes=sistema.pacotes)


@app.route('/clientes/arvore')
def arvoreB():
    niveis = sistema.clientes.niveis()
    return render_template('arvore.html', stats=sistema.clientes.estatisticas(), niveis=niveis[:3],
                           ocultos=len(niveis) - 3 if len(niveis) > 3 else 0,
                           busca=sistema.clientes.ultimaBusca, insercao=sistema.clientes.ultimaInsercao)


@app.route('/rede')
def rede():
    algoritmo = request.args.get('algoritmo', '')
    origem = request.args.get('origem', '').upper()
    destino = request.args.get('destino', '').upper()
    resultado = sistema.executarAlgoritmo(algoritmo, origem, destino) if algoritmo else None
    return render_template('rede.html', mapa=sistema.mapaRede(resultado), resultado=resultado,
                           algoritmo=algoritmo, origem=origem, destino=destino,
                           vertices=[(v, sistema.nomePais(v)) for v in sistema.codigosRede()],
                           conexoes=sistema.conexoes(), nome=sistema.nomePais)


@app.route('/rede/conexoes', methods=['POST'])
def salvarConexao():
    origem = request.form.get('origem', '').upper()
    destino = request.form.get('destino', '').upper()
    latencia = numero(request.form.get('latencia'))
    if latencia is None:
        flash("Informe a latência em milissegundos (número inteiro).", "danger")
    else:
        erro = sistema.salvarConexao(origem, destino, latencia)
        flash(erro or f"Conexão {origem} ↔ {destino} salva com {latencia} ms.", "danger" if erro else "success")
    return redirect(url_for('rede'))


@app.route('/rede/reorganizar', methods=['POST'])
def reorganizarRede():
    sistema.reorganizarMapa()
    flash("Mapa reorganizado pelo igraph.", "success")
    return redirect(url_for('rede'))


@app.route('/rede/conexoes/remover', methods=['POST'])
def removerConexao():
    origem = request.form.get('origem', '').upper()
    destino = request.form.get('destino', '').upper()
    if sistema.removerConexao(origem, destino):
        flash(f"Conexão {origem} ↔ {destino} removida.", "success")
    else:
        flash("Conexão não encontrada.", "danger")
    return redirect(url_for('rede'))


@app.route('/consulta')
def consulta():
    idCliente = numero(request.args.get('cliente'))
    origem = request.args.get('origem', 'BR').upper()
    destino = request.args.get('destino', '').upper()
    resultado = None
    if request.args.get('cliente') and destino:
        if idCliente is None:
            flash("Informe o ID do cliente (número).", "danger")
        else:
            resultado = sistema.consultaIntegrada(idCliente, origem, destino)
    if idCliente is None and session.get("cliente_id") is not None:
        idCliente = session["cliente_id"]
    mapa = None
    if resultado and resultado["rota"]:
        caminho = resultado["rota"]["caminho"]
        mapa = sistema.mapaRede({"arestas": list(zip(caminho, caminho[1:])), "ordem": caminho,
                                 "origem": origem, "destino": destino})
    return render_template('consulta.html', resultado=resultado, mapa=mapa, idCliente=idCliente or "",
                           origem=origem, destino=destino,
                           paises=[(p["codigo"], p["pais"]) for p in sistema.paises.listar()])


if __name__ == '__main__':
    app.run(debug=True)
