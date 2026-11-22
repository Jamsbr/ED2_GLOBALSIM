from bisect import insort

from .tabela_hash import TabelaHash


class IndiceSecundario:
    """Índice secundário (diferencial): valor de um atributo -> lista ordenada de chaves primárias.

    É montado sobre a própria TabelaHash: a chave é o valor do atributo e o
    valor guardado é a lista de chaves primárias (IDs de clientes, códigos de
    países) que têm esse valor. Isso permite localizar registros por atributos
    que não são a chave da estrutura principal.
    """

    def __init__(self, campo):
        self.campo = campo
        self.tabela = TabelaHash()

    @staticmethod
    def _normalizar(valor):
        return str(valor).strip().lower()

    def adicionar(self, valor, chavePrimaria):
        chave = self._normalizar(valor)
        lista = self.tabela.buscar(chave)
        if lista is None:
            self.tabela.inserir(chave, [chavePrimaria])
        elif chavePrimaria not in lista:
            insort(lista, chavePrimaria)

    def remover(self, valor, chavePrimaria):
        chave = self._normalizar(valor)
        lista = self.tabela.buscar(chave)
        if lista is None or chavePrimaria not in lista:
            return
        lista.remove(chavePrimaria)
        if not lista:
            self.tabela.remover(chave)

    def buscar(self, valor):
        """Lista ordenada de chaves primárias (vazia se o valor não existe).
        Retorna (lista, comparações feitas na Tabela Hash)."""
        lista = self.tabela.buscar(self._normalizar(valor)) or []
        return list(lista), self.tabela.ultimaBusca["comparacoes"]

    @staticmethod
    def intersecar(a, b):
        """Interseção por intercalação de duas listas ordenadas.
        Retorna (resultado, comparações)."""
        i = j = comparacoes = 0
        resultado = []
        while i < len(a) and j < len(b):
            comparacoes += 1
            if a[i] == b[j]:
                resultado.append(a[i])
                i += 1
                j += 1
            elif a[i] < b[j]:
                i += 1
            else:
                j += 1
        return resultado, comparacoes

    def estatisticas(self):
        stats = self.tabela.estatisticas()
        stats["campo"] = self.campo
        stats["entradas"] = sum(len(lista) for _, lista in self.tabela.itens())
        stats["valoresDistintos"] = self.tabela.tamanho
        return stats
