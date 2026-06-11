from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.database import SessionLocal
from app.models.usuario import Usuario
from app.schemas.cadastro import Cadastro
from app.schemas.login import Login
from app.models.pergunta import Pergunta
from app.models.anamnese import Anamnese
from app.models.resposta_usuario import RespostaUsuario
from app.schemas.anamnese import AnamneseSchema
from app.models.alternativa import Alternativa

from app.models.banca import Banca
from app.models.aposta import Aposta
from app.models.historico_banca import HistoricoBanca
from app.models.partida import Partida
from app.models.time import Time
from app.models.enums import (
    StatusBancaEnum,
    ResultadoApostaEnum,
    TipoMovimentacaoEnum,
)
from app.schemas.banca import CriarBanca, EditarBanca, MovimentarBanca
from app.schemas.aposta import CriarAposta, ResultadoAposta

from app.services.football_data_service import buscar_partidas
from app.services.importar_partidas_service import importar_partidas
from app.services.odds_service import buscar_odds
from app.services.recomendacao_service import recomendar

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TCC/dev: liberar geral. Em prod, restringir.
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def home():
    return {
        "mensagem": "API do TCC funcionando"
    }


@app.get("/partidas")
def partidas():
    return buscar_partidas()


@app.get("/importar")
def importar():
    return importar_partidas()


@app.post("/cadastro")
def cadastrar_usuario(dados: Cadastro):

    db = SessionLocal()

    usuario_existente = db.query(Usuario).filter(
        Usuario.email == dados.email
    ).first()

    if usuario_existente:
        raise HTTPException(
            status_code=400,
            detail="E-mail já cadastrado"
        )

    novo_usuario = Usuario(
        nome=dados.nome,
        email=dados.email,
        senha=dados.senha
    )

    db.add(novo_usuario)
    db.commit()
    db.refresh(novo_usuario)

    return {
        "id": novo_usuario.id,
        "nome": novo_usuario.nome,
        "email": novo_usuario.email,
        "mensagem": "Usuário cadastrado com sucesso"
    }


@app.post("/login")
def login(dados: Login):

    db = SessionLocal()

    usuario = db.query(Usuario).filter(
        Usuario.email == dados.email
    ).first()

    if not usuario:
        return {
            "sucesso": False,
            "mensagem": "Email ou senha inválidos"
        }

    if usuario.senha != dados.senha:
        return {
            "sucesso": False,
            "mensagem": "Email ou senha inválidos"
        }

    return {
        "sucesso": True,
        "mensagem": "Login realizado com sucesso",
        "usuario": {
            "id": usuario.id,
            "nome": usuario.nome,
            "email": usuario.email,
            "perfil_risco": (
                usuario.perfil_risco.value
                if usuario.perfil_risco
                else None
            )
        }
    }


@app.get("/perguntas")
def listar_perguntas():

    db = SessionLocal()

    perguntas = db.query(Pergunta).all()

    resultado = []

    for pergunta in perguntas:

        resultado.append({
            "id": pergunta.id,
            "texto": pergunta.texto,
            "alternativas": [
                {
                    "id": alternativa.id,
                    "texto": alternativa.texto
                }
                for alternativa in pergunta.alternativas
            ]
        })

    return resultado


@app.post("/anamnese")
def responder_anamnese(dados: AnamneseSchema):

    db = SessionLocal()

    anamnese = Anamnese(
        usuario_id=dados.usuario_id,
        perfil_calculado=None
    )

    db.add(anamnese)
    db.commit()
    db.refresh(anamnese)

    for resposta in dados.respostas:

        resposta_usuario = RespostaUsuario(
            anamnese_id=anamnese.id,
            pergunta_id=resposta.pergunta_id,
            alternativa_id=resposta.alternativa_id
        )

        db.add(resposta_usuario)

    db.commit()

    return {
        "mensagem": "Anamnese salva com sucesso",
        "anamnese_id": anamnese.id
    }


@app.get("/anamnese/resultado/{anamnese_id}")
def calcular_resultado_anamnese(anamnese_id: int):

    db = SessionLocal()

    respostas = db.query(RespostaUsuario).filter(
        RespostaUsuario.anamnese_id == anamnese_id
    ).all()

    total = 0

    for r in respostas:

        alternativa = db.query(Alternativa).filter(
            Alternativa.id == r.alternativa_id
        ).first()

        if alternativa:
            total += alternativa.peso

    if total <= 12:
        perfil = "conservador"
    elif total <= 20:
        perfil = "moderado"
    else:
        perfil = "agressivo"

    anamnese = db.query(Anamnese).filter(
        Anamnese.id == anamnese_id
    ).first()

    if not anamnese:
        raise HTTPException(status_code=404, detail="Anamnese não encontrada")

    anamnese.perfil_calculado = perfil

    db.commit()

    return {
        "anamnese_id": anamnese_id,
        "score_total": total,
        "perfil": perfil
    }


@app.get("/debug-anamnese")
def debug():
    db = SessionLocal()

    return [
        {"id": a.id, "usuario": a.usuario_id, "perfil": a.perfil_calculado}
        for a in db.query(Anamnese).all()
    ]


# =========================================================
# BANCA
# =========================================================

def _serializar_banca(banca: Banca) -> dict:
    return {
        "id": banca.id,
        "usuario_id": banca.usuario_id,
        "saldo_inicial": float(banca.saldo_inicial),
        "saldo_atual": float(banca.saldo_atual),
        "stop_loss": float(banca.stop_loss) if banca.stop_loss is not None else None,
        "meta_diaria": float(banca.meta_diaria) if banca.meta_diaria is not None else None,
        "status": banca.status.value if banca.status else None,
        "data_criacao": banca.data_criacao.isoformat() if banca.data_criacao else None,
        "data_fechamento": banca.data_fechamento.isoformat() if banca.data_fechamento else None,
    }


def _serializar_aposta(aposta: Aposta) -> dict:
    return {
        "id": aposta.id,
        "banca_id": aposta.banca_id,
        "partida_id": aposta.partida_id,
        "tipo_aposta": aposta.tipo_aposta,
        "odd": float(aposta.odd) if aposta.odd is not None else None,
        "valor": float(aposta.valor) if aposta.valor is not None else None,
        "lucro_prejuizo": float(aposta.lucro_prejuizo) if aposta.lucro_prejuizo is not None else None,
        "resultado": aposta.resultado.value if aposta.resultado else None,
        "data": aposta.data.isoformat() if aposta.data else None,
    }


def _status_banca(banca: Banca) -> dict:
    """Flags de meta/stop pra decidir se mostra modal no front."""
    saldo = float(banca.saldo_atual)
    meta = float(banca.meta_diaria) if banca.meta_diaria is not None else None
    stop = float(banca.stop_loss) if banca.stop_loss is not None else None
    return {
        "atingiu_meta": meta is not None and saldo >= meta,
        "atingiu_stop": stop is not None and saldo <= stop,
        "zerada": saldo <= 0,
    }


@app.get("/banca/ativa/{usuario_id}")
def banca_ativa(usuario_id: int):
    db = SessionLocal()

    banca = db.query(Banca).filter(
        Banca.usuario_id == usuario_id,
        Banca.status == StatusBancaEnum.ATIVA
    ).order_by(Banca.id.desc()).first()

    if not banca:
        return {"banca": None}

    apostas = db.query(Aposta).filter(
        Aposta.banca_id == banca.id
    ).order_by(Aposta.id.asc()).all()

    return {
        "banca": _serializar_banca(banca),
        "apostas": [_serializar_aposta(a) for a in apostas],
        "flags": _status_banca(banca),
    }


@app.post("/banca")
def criar_banca(dados: CriarBanca):
    db = SessionLocal()

    if dados.saldo_inicial <= 0:
        raise HTTPException(status_code=400, detail="Saldo inicial deve ser maior que 0")

    # fecha qualquer banca ativa anterior do usuário
    ativas = db.query(Banca).filter(
        Banca.usuario_id == dados.usuario_id,
        Banca.status == StatusBancaEnum.ATIVA
    ).all()
    for b in ativas:
        b.status = StatusBancaEnum.FECHADA
        b.data_fechamento = datetime.utcnow()

    banca = Banca(
        usuario_id=dados.usuario_id,
        saldo_inicial=dados.saldo_inicial,
        saldo_atual=dados.saldo_inicial,
        stop_loss=dados.stop_loss,
        meta_diaria=dados.meta_diaria,
        status=StatusBancaEnum.ATIVA,
    )
    db.add(banca)
    db.commit()
    db.refresh(banca)

    db.add(HistoricoBanca(
        usuario_id=dados.usuario_id,
        saldo=banca.saldo_atual,
        valor=dados.saldo_inicial,
        tipo_movimentacao=TipoMovimentacaoEnum.DEPOSITO,
    ))
    db.commit()

    return {"banca": _serializar_banca(banca), "flags": _status_banca(banca)}


@app.patch("/banca/{banca_id}")
def editar_banca(banca_id: int, dados: EditarBanca):
    db = SessionLocal()
    banca = db.get(Banca, banca_id)
    if not banca:
        raise HTTPException(status_code=404, detail="Banca não encontrada")

    if dados.meta_diaria is not None:
        banca.meta_diaria = dados.meta_diaria
    if dados.stop_loss is not None:
        banca.stop_loss = dados.stop_loss

    db.commit()
    db.refresh(banca)
    return {"banca": _serializar_banca(banca), "flags": _status_banca(banca)}


@app.post("/banca/{banca_id}/fechar")
def fechar_banca(banca_id: int):
    db = SessionLocal()
    banca = db.get(Banca, banca_id)
    if not banca:
        raise HTTPException(status_code=404, detail="Banca não encontrada")

    banca.status = StatusBancaEnum.FECHADA
    banca.data_fechamento = datetime.utcnow()
    db.commit()
    db.refresh(banca)
    return {"banca": _serializar_banca(banca)}


@app.get("/banca/historico/{usuario_id}")
def historico_bancas(usuario_id: int):
    db = SessionLocal()

    bancas = db.query(Banca).filter(
        Banca.usuario_id == usuario_id,
        Banca.status == StatusBancaEnum.FECHADA
    ).order_by(Banca.data_fechamento.desc().nullslast(), Banca.id.desc()).all()

    resultado = []
    for banca in bancas:
        apostas = db.query(Aposta).filter(
            Aposta.banca_id == banca.id
        ).order_by(Aposta.id.asc()).all()

        ganhas = sum(1 for a in apostas if a.resultado == ResultadoApostaEnum.GANHA)
        perdidas = sum(1 for a in apostas if a.resultado == ResultadoApostaEnum.PERDIDA)

        if float(banca.saldo_atual) >= float(banca.meta_diaria or 0) and banca.meta_diaria:
            resultado_final = "Green"
        elif banca.stop_loss is not None and float(banca.saldo_atual) <= float(banca.stop_loss):
            resultado_final = "Red"
        else:
            resultado_final = "Fechada"

        resultado.append({
            **_serializar_banca(banca),
            "resultado_final": resultado_final,
            "apostas_ganhas": ganhas,
            "apostas_perdidas": perdidas,
            "apostas": [_serializar_aposta(a) for a in apostas],
        })

    return {"historico": resultado}


# =========================================================
# APOSTA
# =========================================================

@app.post("/aposta")
def criar_aposta(dados: CriarAposta):
    db = SessionLocal()

    banca = db.get(Banca, dados.banca_id)
    if not banca:
        raise HTTPException(status_code=404, detail="Banca não encontrada")
    if banca.status != StatusBancaEnum.ATIVA:
        raise HTTPException(status_code=400, detail="Banca não está ativa")
    if dados.valor <= 0:
        raise HTTPException(status_code=400, detail="Valor da aposta inválido")
    if dados.valor > float(banca.saldo_atual):
        raise HTTPException(status_code=400, detail="Saldo insuficiente")

    aposta = Aposta(
        banca_id=dados.banca_id,
        usuario_id=dados.usuario_id,
        partida_id=dados.partida_id,
        tipo_aposta=dados.tipo_aposta,
        odd=dados.odd,
        valor=dados.valor,
        resultado=ResultadoApostaEnum.PENDENTE,
    )
    db.add(aposta)

    # reserva o valor da aposta da banca (entrada)
    banca.saldo_atual = float(banca.saldo_atual) - dados.valor

    db.commit()
    db.refresh(aposta)
    db.refresh(banca)

    db.add(HistoricoBanca(
        aposta_id=aposta.id,
        usuario_id=dados.usuario_id,
        saldo=banca.saldo_atual,
        valor=dados.valor,
        tipo_movimentacao=TipoMovimentacaoEnum.ENTRADA_APOSTA,
    ))
    db.commit()

    return {
        "aposta": _serializar_aposta(aposta),
        "banca": _serializar_banca(banca),
        "flags": _status_banca(banca),
    }


@app.patch("/aposta/{aposta_id}/resultado")
def resultado_aposta(aposta_id: int, dados: ResultadoAposta):
    db = SessionLocal()

    aposta = db.get(Aposta, aposta_id)
    if not aposta:
        raise HTTPException(status_code=404, detail="Aposta não encontrada")

    banca = db.get(Banca, aposta.banca_id)
    if not banca:
        raise HTTPException(status_code=404, detail="Banca não encontrada")

    try:
        novo = ResultadoApostaEnum(dados.resultado.upper())
    except ValueError:
        raise HTTPException(status_code=400, detail="Resultado inválido")

    valor = float(aposta.valor)
    odd = float(aposta.odd)

    # reverte efeito anterior (a entrada já foi descontada na criação;
    # GANHA/CANCELADA podem ter creditado retorno antes)
    if aposta.resultado == ResultadoApostaEnum.GANHA:
        banca.saldo_atual = float(banca.saldo_atual) - valor * odd
    elif aposta.resultado == ResultadoApostaEnum.CANCELADA:
        banca.saldo_atual = float(banca.saldo_atual) - valor

    # aplica novo resultado
    if novo == ResultadoApostaEnum.GANHA:
        retorno = valor * odd
        banca.saldo_atual = float(banca.saldo_atual) + retorno
        aposta.lucro_prejuizo = retorno - valor
        mov = TipoMovimentacaoEnum.LUCRO
        mov_valor = retorno
    elif novo == ResultadoApostaEnum.PERDIDA:
        aposta.lucro_prejuizo = -valor
        mov = TipoMovimentacaoEnum.PREJUIZO
        mov_valor = valor
    elif novo == ResultadoApostaEnum.CANCELADA:
        banca.saldo_atual = float(banca.saldo_atual) + valor
        aposta.lucro_prejuizo = 0
        mov = TipoMovimentacaoEnum.DEPOSITO
        mov_valor = valor
    else:  # PENDENTE
        aposta.lucro_prejuizo = None
        mov = None
        mov_valor = 0

    aposta.resultado = novo
    db.commit()
    db.refresh(aposta)
    db.refresh(banca)

    if mov is not None:
        db.add(HistoricoBanca(
            aposta_id=aposta.id,
            usuario_id=aposta.usuario_id,
            saldo=banca.saldo_atual,
            valor=mov_valor,
            tipo_movimentacao=mov,
        ))
        db.commit()

    return {
        "aposta": _serializar_aposta(aposta),
        "banca": _serializar_banca(banca),
        "flags": _status_banca(banca),
    }


# =========================================================
# ODDS + PARTIDAS PRÓXIMAS + RECOMENDAÇÃO
# =========================================================

def _serializar_partida(p: Partida, casa: str, fora: str) -> dict:
    return {
        "id": p.id,
        "time_casa": casa,
        "time_fora": fora,
        "data": p.data.isoformat() if p.data else None,
        "rodada": p.rodada,
        "gols_casa": p.gols_casa,
        "gols_fora": p.gols_fora,
    }


@app.get("/partidas/proximas")
def partidas_proximas(limite: int = 10):
    """Próximas partidas (ainda sem placar) com odds mock e melhor aposta."""
    db = SessionLocal()

    partidas = db.query(Partida).filter(
        Partida.gols_casa.is_(None),
        Partida.data >= datetime.utcnow()
    ).order_by(Partida.data.asc()).limit(limite).all()

    resultado = []
    for p in partidas:
        casa = db.get(Time, p.time_casa_id)
        fora = db.get(Time, p.time_fora_id)
        rec = recomendar(db, p)
        resultado.append({
            **_serializar_partida(
                p,
                casa.nome if casa else "Casa",
                fora.nome if fora else "Fora",
            ),
            "melhor_aposta": rec["melhor_aposta"],
            "risco": rec["risco"],
        })

    return {"partidas": resultado}


@app.get("/partidas/{partida_id}/odds")
def odds_partida(partida_id: int):
    db = SessionLocal()
    p = db.get(Partida, partida_id)
    if not p:
        raise HTTPException(status_code=404, detail="Partida não encontrada")

    casa = db.get(Time, p.time_casa_id)
    fora = db.get(Time, p.time_fora_id)

    return {
        "partida": _serializar_partida(
            p,
            casa.nome if casa else "Casa",
            fora.nome if fora else "Fora",
        ),
        "odds": buscar_odds(partida_id),
    }


@app.get("/partidas/{partida_id}/recomendacao")
def recomendacao_partida(partida_id: int):
    db = SessionLocal()
    p = db.get(Partida, partida_id)
    if not p:
        raise HTTPException(status_code=404, detail="Partida não encontrada")

    return recomendar(db, p)
