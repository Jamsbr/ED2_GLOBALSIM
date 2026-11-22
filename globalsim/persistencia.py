"""Leitura e gravação dos arquivos JSON (os arquivos já vêm prontos na pasta arquivos/)."""
import json
import os

PASTA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "arquivos")
ARQUIVO_PAISES = os.path.join(PASTA, "paises.json")
ARQUIVO_CLIENTES = os.path.join(PASTA, "clientes.json")
ARQUIVO_PACOTES = os.path.join(PASTA, "pacotes.json")
ARQUIVO_REDE = os.path.join(PASTA, "rede.json")


def lerJson(caminho):
    with open(caminho, "r", encoding="utf-8") as arquivo:
        return json.load(arquivo)


def gravarJson(caminho, dados):
    with open(caminho, "w", encoding="utf-8") as arquivo:
        json.dump(dados, arquivo, indent=2, ensure_ascii=False)
