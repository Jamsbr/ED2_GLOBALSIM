#Sem imports, porque os dados vêm do JSON pelo serviços.py
class Registro:
    def __init__(self, chave=None, elemento=None):
        self.Chave = chave
        self.Elemento = elemento


class Pagina:
    def __init__(self, ordem):
        self.n = 0
        self.r = [None for i in range(ordem)]
        self.p = [None for i in range(ordem + 1)]


def Pesquisa(x, Ap, info=None): # É uma busca recursiva.
    i = 1
    if Ap is None:
        return None

    while i < Ap.n and x.Chave > Ap.r[i - 1].Chave:
        i += 1
    if info is not None:
        info["paginas"] += 1
        info["comparacoes"] += i
        info["caminho"].append({"nivel": len(info["caminho"]), "chaves": [Ap.r[k].Chave for k in range(Ap.n)]})

    if x.Chave == Ap.r[i - 1].Chave:
        return Ap.r[i - 1]
    if x.Chave < Ap.r[i - 1].Chave:
        return Pesquisa(x, Ap.p[i - 1], info)
    return Pesquisa(x, Ap.p[i], info)


def _InsereNaPagina(Ap, Reg, ApDir):
    k = Ap.n
    NaoAchouPosicao = (k > 0)
    while NaoAchouPosicao:
        if Reg.Chave >= Ap.r[k - 1].Chave:
            NaoAchouPosicao = False
            break
        Ap.r[k] = Ap.r[k - 1]
        Ap.p[k + 1] = Ap.p[k]
        k -= 1
        if k < 1:
            NaoAchouPosicao = False

    Ap.r[k] = Reg
    Ap.p[k + 1] = ApDir
    Ap.n += 1

#Função auxiliar para descer, inserir e dividir.
def _Ins(Reg, Ap, Cresceu, RegRetorno, ApRetorno, Ordem, info=None): 
    i = 1
    if Ap is None:
        return True, Reg, None

    while i < Ap.n and Reg.Chave > Ap.r[i - 1].Chave:
        i += 1
    if info is not None:
        info["paginas"] += 1
        info["comparacoes"] += i

    if Reg.Chave < Ap.r[i - 1].Chave:
        i -= 1

    Cresceu, RegRetorno, ApRetorno = _Ins(Reg, Ap.p[i], Cresceu, RegRetorno, ApRetorno, Ordem, info)

    if not Cresceu:
        return Cresceu, RegRetorno, ApRetorno
    if Ap.n < Ordem:
        _InsereNaPagina(Ap, RegRetorno, ApRetorno)
        return False, RegRetorno, ApRetorno

    # overflow: a página é dividida e o registro do meio sobe
    if info is not None:
        info["divisoes"] += 1
    ApTemp = Pagina(Ordem)
    ApTemp.n = 0
    ApTemp.p[0] = None
    if i < (Ordem // 2) + 1:
        _InsereNaPagina(ApTemp, Ap.r[Ordem - 1], Ap.p[Ordem])
        Ap.n -= 1
        _InsereNaPagina(Ap, RegRetorno, ApRetorno)
    else:
        _InsereNaPagina(ApTemp, RegRetorno, ApRetorno)
    for J in range((Ordem // 2) + 2, Ordem + 1):
        _InsereNaPagina(ApTemp, Ap.r[J - 1], Ap.p[J])
    Ap.n = Ordem // 2
    ApTemp.p[0] = Ap.p[(Ordem // 2) + 1]
    RegRetorno = Ap.r[Ordem // 2]
    ApRetorno = ApTemp
    return Cresceu, RegRetorno, ApRetorno

#Insere um registro na árvore e trata o caso da raiz.
def _Insere(Reg, Ap, Ordem, info=None):
    Cresceu, RegRetorno, ApRetorno = _Ins(Reg, Ap, False, Registro(), Pagina(Ordem), Ordem, info)
    if Cresceu:  # a raiz dividiu: a árvore cresce em altura
        ApTemp = Pagina(Ordem)
        ApTemp.n = 1
        ApTemp.r[0] = RegRetorno
        ApTemp.p[1] = ApRetorno
        ApTemp.p[0] = Ap
        Ap = ApTemp
        if info is not None and ApTemp.p[0] is not None:
            info["raizDividiu"] = True
    return Ap


def Imprime(Ap):
    if Ap is not None:
        for i in range(Ap.n):
            yield from Imprime(Ap.p[i])
            yield Ap.r[i]
        yield from Imprime(Ap.p[Ap.n])


class ArvoreB:
    """Guarda a raiz e a instrumentação"""
    # Usada em:
    # app.py rota /clientes/arvore(arvoreB)
    # app.py rota /clientes/<id>(detalheCliente)
    # servicos.py buscaClietnes
    # servicos.py buscaIntegrada

    def __init__(self, ordem=4):
        self.ordem = ordem
        self.raiz = None
        self.tamanho = 0
        self.divisoes = 0
        self.ultimaBusca = {"chave": None, "encontrado": False, "paginas": 0, "comparacoes": 0, "caminho": []}
        self.ultimaInsercao = {"chave": None, "paginas": 0, "comparacoes": 0, "divisoes": 0, "raizDividiu": False}

    def _buscar(self, chave):
        info = {"paginas": 0, "comparacoes": 0, "caminho": []}
        return Pesquisa(Registro(chave), self.raiz, info), info

    def buscar(self, chave, registrar=True):
        reg, info = self._buscar(chave)
        if registrar:
            self.ultimaBusca = dict(info, chave=chave, encontrado=reg is not None)
        return reg.Elemento if reg else None

    def custoBusca(self, chave):
        reg, info = self._buscar(chave)
        return (reg.Elemento if reg else None), info["paginas"], info["comparacoes"]

    def atualizar(self, chave, valor):
        reg, _ = self._buscar(chave)
        if reg is None:
            return False
        reg.Elemento = valor
        return True

    def inserir(self, chave, valor):
        if self._buscar(chave)[0] is not None:
            return False
        info = {"chave": chave, "paginas": 0, "comparacoes": 0, "divisoes": 0, "raizDividiu": False}
        self.raiz = _Insere(Registro(chave, valor), self.raiz, self.ordem, info)
        self.tamanho += 1
        self.divisoes += info["divisoes"]
        self.ultimaInsercao = info
        return True

    def emOrdem(self):
        return Imprime(self.raiz)

    def maiorChave(self):
        Ap = self.raiz
        if Ap is None:
            return None
        while Ap.p[Ap.n] is not None:
            Ap = Ap.p[Ap.n]
        return Ap.r[Ap.n - 1].Chave

    def niveis(self):
        resultado = []
        atual = [self.raiz] if self.raiz else []
        while atual:
            resultado.append([[Ap.r[i].Chave for i in range(Ap.n)] for Ap in atual])
            atual = [Ap.p[i] for Ap in atual for i in range(Ap.n + 1) if Ap.p[i] is not None]
        return resultado

    def estatisticas(self):
        niveis = self.niveis()
        paginas = sum(len(n) for n in niveis)
        return {
            "ordem": self.ordem,
            "altura": len(niveis),
            "paginas": paginas,
            "chaves": self.tamanho,
            "divisoes": self.divisoes,
            "ocupacao": round(100 * self.tamanho / (paginas * self.ordem), 1) if paginas else 0,
            "paginasPorNivel": [len(n) for n in niveis],
        }
