from enum import Enum


class PerfilRiscoEnum(str, Enum):
    CONSERVADOR = "CONSERVADOR"
    MODERADO = "MODERADO"
    AGRESSIVO = "AGRESSIVO"


class TipoMovimentacaoEnum(str, Enum):
    DEPOSITO = "DEPOSITO"
    SAQUE = "SAQUE"
    ENTRADA_APOSTA = "ENTRADA_APOSTA"
    LUCRO = "LUCRO"
    PREJUIZO = "PREJUIZO"


class ResultadoApostaEnum(str, Enum):
    PENDENTE = "PENDENTE"
    GANHA = "GANHA"
    PERDIDA = "PERDIDA"
    CANCELADA = "CANCELADA"


class RiscoRecomendacaoEnum(str, Enum):
    BAIXO = "BAIXO"
    MEDIO = "MEDIO"
    ALTO = "ALTO"


class StatusBancaEnum(str, Enum):
    ATIVA = "ATIVA"
    FECHADA = "FECHADA"