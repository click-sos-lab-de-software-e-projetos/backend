import ast
from pathlib import Path

PASTA_TESTES = Path(__file__).parent
FUNCOES = (ast.FunctionDef, ast.AsyncFunctionDef)


def _funcoes_com_prefixo_test(pasta: Path) -> list[str]:
    encontradas = []
    for arquivo in sorted(pasta.rglob("*.py")):
        arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
        for no in ast.walk(arvore):
            if isinstance(no, FUNCOES) and no.name.startswith("test_"):
                encontradas.append(f"{arquivo.relative_to(pasta)}:{no.lineno} {no.name}")
    return encontradas


def arquivos_de_teste_nao_deve_conter_funcao_com_prefixo_test():
    encontradas = _funcoes_com_prefixo_test(PASTA_TESTES)
    assert not encontradas, (
        "O pytest só coleta *_deve_*; renomeie para "
        "<componente>_<ação>_deve_<resultado>: " + ", ".join(encontradas)
    )
