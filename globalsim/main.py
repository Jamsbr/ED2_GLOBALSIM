from flask import Flask, render_template, request, redirect, url_for, flash
from arquivos.tabelaHash import TabelaHash
import json
import os

app = Flask(__name__)
app.secret_key = "segredo123"

DIRETORIO_ATUAL = os.path.dirname(os.path.abspath(__file__))
ARQUIVO_PAISES = os.path.join(DIRETORIO_ATUAL, "arquivos", "paises.json")

TABELA_PAISES = TabelaHash()


def carregarPaises():
    if os.path.exists(ARQUIVO_PAISES) and os.path.getsize(ARQUIVO_PAISES) > 0:
        with open(ARQUIVO_PAISES, "r", encoding="utf-8") as arquivoJson:
            for pais in json.load(arquivoJson):
                TABELA_PAISES.inserir(pais["codigo"], pais)


def salvarPaises():
    with open(ARQUIVO_PAISES, "w", encoding="utf-8") as arquivoJson:
        json.dump(TABELA_PAISES.listar(), arquivoJson, indent=4, ensure_ascii=False)


def lerFormulario():
    campos = ["codigo", "pais", "regiao", "operadora", "tecnologia"]
    pais = {c: request.form.get(c, "").strip() for c in campos}
    pais["codigo"] = pais["codigo"].upper()
    return pais


def formularioValido(pais):
    return all(pais.values()) and len(pais["codigo"]) == 2 and pais["codigo"].isalpha()


@app.route('/')
def principal():
    return render_template('index.html')


@app.route('/paises')
def listaPaises():
    return render_template('paises.html', paises=TABELA_PAISES.listar(),
                           stats=TABELA_PAISES.estatisticas(),
                           posicoes=TABELA_PAISES.posicoes)


@app.route('/paises/cadastrar', methods=['GET', 'POST'])
def cadastrarPais():
    if request.method == 'POST':
        pais = lerFormulario()
        if not formularioValido(pais):
            flash("Preencha todos os campos. O código deve ter 2 letras.", "danger")
            return render_template('formPais.html', pais=pais, novo=True)
        if TABELA_PAISES.buscar(pais["codigo"]):
            flash(f"O país {pais['codigo']} já está cadastrado!", "danger")
            return render_template('formPais.html', pais=pais, novo=True)
        TABELA_PAISES.inserir(pais["codigo"], pais)
        salvarPaises()
        flash(f"País {pais['codigo']} cadastrado com sucesso!", "success")
        return redirect(url_for('listaPaises'))
    return render_template('formPais.html', pais={}, novo=True)


@app.route('/paises/alterar/<codigo>', methods=['GET', 'POST'])
def alterarPais(codigo):
    pais = TABELA_PAISES.buscar(codigo)
    if not pais:
        flash(f"País {codigo} não encontrado!", "danger")
        return redirect(url_for('listaPaises'))
    if request.method == 'POST':
        novo = lerFormulario()
        novo["codigo"] = codigo  # a chave não muda
        if not formularioValido(novo):
            flash("Preencha todos os campos.", "danger")
            return render_template('formPais.html', pais=novo, novo=False)
        TABELA_PAISES.inserir(codigo, novo)
        salvarPaises()
        flash(f"País {codigo} atualizado com sucesso!", "success")
        return redirect(url_for('listaPaises'))
    return render_template('formPais.html', pais=pais, novo=False)


@app.route('/paises/remover/<codigo>', methods=['POST'])
def removerPais(codigo):
    if TABELA_PAISES.remover(codigo):
        salvarPaises()
        flash(f"País {codigo} removido com sucesso!", "success")
    else:
        flash(f"País {codigo} não encontrado!", "danger")
    return redirect(url_for('listaPaises'))


@app.route('/cobertura', methods=['GET', 'POST'])
def cobertura():
    if request.method == 'POST':
        codigo = request.form.get('codigo', '').strip().upper()
        pais = TABELA_PAISES.buscar(codigo)
        return render_template('cobertura.html', codigo=codigo, pais=pais,
                               busca=TABELA_PAISES.ultimaBusca)
    return render_template('cobertura.html')


carregarPaises()

if __name__ == '__main__':
    app.run(debug=True)
