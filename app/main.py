from datetime import datetime
from typing import Optional

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
from app.models.aposta_multipla import ApostaMultipla, ItemApostaMultipla
from app.models.historico_banca import HistoricoBanca
from app.models.partida import Partida
from app.models.time import Time
from app.models.enums import (
    StatusBancaEnum,
    ResultadoApostaEnum,
    TipoMovimentacaoEnum,
    PerfilRiscoEnum,
)
from app.schemas.banca import CriarBanca, EditarBanca, MovimentarBanca
from app.schemas.aposta import CriarAposta, ResultadoAposta
from app.schemas.aposta_multipla import CriarApostaMultipla, ResultadoApostaMultipla
from app.schemas.usuario import EditarNome, EditarEmail, AlterarSenha

from app.services.football_data_service import buscar_partidas
from app.services.importar_partidas_service import importar_partidas
from app.services.recomendacao_service import recomendar

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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


@app.patch("/usuario/{usuario_id}/nome")
def editar_nome(usuario_id: int, dados: EditarNome):
    db = SessionLocal()
    usuario = db.get(Usuario, usuario_id)
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    novo = dados.novo_nome.strip()
    if not novo:
        raise HTTPException(status_code=400, detail="Nome não pode ser vazio")
    usuario.nome = novo
    db.commit()
    db.refresh(usuario)
    return {
        "id": usuario.id,
        "nome": usuario.nome,
        "email": usuario.email,
        "perfil_risco": usuario.perfil_risco.value if usuario.perfil_risco else None,
    }


@app.patch("/usuario/{usuario_id}/email")
def editar_email(usuario_id: int, dados: EditarEmail):
    db = SessionLocal()
    usuario = db.get(Usuario, usuario_id)
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    novo = dados.novo_email.strip().lower()
    if not novo:
        raise HTTPException(status_code=400, detail="Email não pode ser vazio")
    existente = db.query(Usuario).filter(
        Usuario.email == novo,
        Usuario.id != usuario_id
    ).first()
    if existente:
        raise HTTPException(status_code=400, detail="E-mail já está em uso")
    usuario.email = novo
    db.commit()
    db.refresh(usuario)
    return {
        "id": usuario.id,
        "nome": usuario.nome,
        "email": usuario.email,
        "perfil_risco": usuario.perfil_risco.value if usuario.perfil_risco else None,
    }


@app.patch("/usuario/{usuario_id}/senha")
def alterar_senha(usuario_id: int, dados: AlterarSenha):
    db = SessionLocal()
    usuario = db.get(Usuario, usuario_id)
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    if usuario.senha != dados.senha_atual:
        raise HTTPException(status_code=400, detail="Senha atual incorreta")
    nova = dados.nova_senha.strip()
    if len(nova) < 6:
        raise HTTPException(status_code=400, detail="Nova senha deve ter pelo menos 6 caracteres")
    usuario.senha = nova
    db.commit()
    return {"mensagem": "Senha alterada com sucesso"}


@app.delete("/usuario/{usuario_id}")
def deletar_usuario(usuario_id: int):
    db = SessionLocal()
    usuario = db.get(Usuario, usuario_id)
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    db.query(HistoricoBanca).filter(HistoricoBanca.usuario_id == usuario_id).delete()

    from app.models.aposta_multipla import ItemApostaMultipla as _Item, ApostaMultipla as _Multi
    multiplas_ids = [
        m.id for m in db.query(_Multi).filter(_Multi.usuario_id == usuario_id).all()
    ]
    if multiplas_ids:
        db.query(_Item).filter(_Item.multipla_id.in_(multiplas_ids)).delete()
    db.query(_Multi).filter(_Multi.usuario_id == usuario_id).delete()

    db.query(Aposta).filter(Aposta.usuario_id == usuario_id).delete()
    db.query(Banca).filter(Banca.usuario_id == usuario_id).delete()

    from app.models.resposta_usuario import RespostaUsuario as _Resp
    from app.models.anamnese import Anamnese as _Anam
    anamneses_ids = [
        a.id for a in db.query(_Anam).filter(_Anam.usuario_id == usuario_id).all()
    ]
    if anamneses_ids:
        db.query(_Resp).filter(_Resp.anamnese_id.in_(anamneses_ids)).delete()
    db.query(_Anam).filter(_Anam.usuario_id == usuario_id).delete()

    from app.models.recomendacao import Recomendacao as _Rec
    db.query(_Rec).filter(_Rec.usuario_id == usuario_id).delete()

    db.delete(usuario)
    db.commit()
    return {"mensagem": "Conta excluída com sucesso"}


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

    anamnese = db.query(Anamnese).filter(
        Anamnese.id == anamnese_id
    ).first()

    if not anamnese:
        raise HTTPException(status_code=404, detail="Anamnese não encontrada")

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

    if total <= 8:
        perfil = "conservador"
    elif total <= 11:
        perfil = "moderado"
    else:
        perfil = "agressivo"

    anamnese.perfil_calculado = perfil

    usuario = db.get(Usuario, anamnese.usuario_id)
    if usuario:
        usuario.perfil_risco = PerfilRiscoEnum(perfil.upper())

    db.commit()

    return {
        "anamnese_id": anamnese_id,
        "score_total": total,
        "perfil": perfil,
        "usuario": {
            "id": usuario.id,
            "nome": usuario.nome,
            "email": usuario.email,
            "perfil_risco": usuario.perfil_risco.value if usuario.perfil_risco else None,
        } if usuario else None,
    }


@app.get("/debug-anamnese")
def debug():
    db = SessionLocal()

    return [
        {"id": a.id, "usuario": a.usuario_id, "perfil": a.perfil_calculado}
        for a in db.query(Anamnese).all()
    ]


def _serializar_banca(banca: Banca) -> dict:
    ref = float(banca.saldo_referencia) if banca.saldo_referencia is not None else float(banca.saldo_inicial)
    return {
        "id": banca.id,
        "usuario_id": banca.usuario_id,
        "saldo_inicial": float(banca.saldo_inicial),
        "saldo_atual": float(banca.saldo_atual),
        "saldo_referencia": ref,
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
    ref = float(banca.saldo_referencia) if banca.saldo_referencia is not None else float(banca.saldo_inicial)
    perf = float(banca.saldo_atual) - ref
    ganho_alvo = float(banca.meta_diaria) if banca.meta_diaria is not None else None
    perda_limite = float(banca.stop_loss) if banca.stop_loss is not None else None
    return {
        "atingiu_meta": ganho_alvo is not None and perf >= ganho_alvo,
        "atingiu_stop": perda_limite is not None and perf <= -perda_limite,
        "zerada": float(banca.saldo_atual) <= 0,
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

    multiplas = db.query(ApostaMultipla).filter(
        ApostaMultipla.banca_id == banca.id
    ).order_by(ApostaMultipla.id.asc()).all()

    return {
        "banca": _serializar_banca(banca),
        "apostas": [_serializar_aposta(a) for a in apostas],
        "multiplas": [_serializar_multipla(m) for m in multiplas],
        "flags": _status_banca(banca),
    }


@app.post("/banca")
def criar_banca(dados: CriarBanca):
    db = SessionLocal()

    if dados.saldo_inicial <= 0:
        raise HTTPException(status_code=400, detail="Saldo inicial deve ser maior que 0")

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
        saldo_referencia=dados.saldo_inicial,
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


@app.post("/banca/{banca_id}/depositar")
def depositar_banca(banca_id: int, dados: MovimentarBanca):
    db = SessionLocal()
    banca = db.get(Banca, banca_id)
    if not banca:
        raise HTTPException(status_code=404, detail="Banca não encontrada")
    if banca.status != StatusBancaEnum.ATIVA:
        raise HTTPException(status_code=400, detail="Banca não está ativa")
    if dados.valor <= 0:
        raise HTTPException(status_code=400, detail="Valor deve ser maior que 0")

    banca.saldo_atual = float(banca.saldo_atual) + dados.valor
    banca.saldo_referencia = float(banca.saldo_atual)
    db.commit()
    db.refresh(banca)

    db.add(HistoricoBanca(
        banca_id=banca_id,
        usuario_id=banca.usuario_id,
        saldo=banca.saldo_atual,
        valor=dados.valor,
        tipo_movimentacao=TipoMovimentacaoEnum.DEPOSITO,
    ))
    db.commit()

    return {"banca": _serializar_banca(banca)}


@app.post("/banca/{banca_id}/sacar")
def sacar_banca(banca_id: int, dados: MovimentarBanca):
    db = SessionLocal()
    banca = db.get(Banca, banca_id)
    if not banca:
        raise HTTPException(status_code=404, detail="Banca não encontrada")
    if banca.status != StatusBancaEnum.ATIVA:
        raise HTTPException(status_code=400, detail="Banca não está ativa")
    if dados.valor <= 0:
        raise HTTPException(status_code=400, detail="Valor deve ser maior que 0")
    if dados.valor > float(banca.saldo_atual):
        raise HTTPException(status_code=400, detail="Saldo insuficiente para saque")

    banca.saldo_atual = float(banca.saldo_atual) - dados.valor
    banca.saldo_referencia = float(banca.saldo_atual)
    db.commit()
    db.refresh(banca)

    db.add(HistoricoBanca(
        banca_id=banca_id,
        usuario_id=banca.usuario_id,
        saldo=banca.saldo_atual,
        valor=dados.valor,
        tipo_movimentacao=TipoMovimentacaoEnum.SAQUE,
    ))
    db.commit()

    return {"banca": _serializar_banca(banca)}


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

        ref = float(banca.saldo_referencia) if banca.saldo_referencia is not None else float(banca.saldo_inicial)
        perf = float(banca.saldo_atual) - ref
        if banca.meta_diaria is not None and perf >= float(banca.meta_diaria):
            resultado_final = "Green"
        elif banca.stop_loss is not None and perf <= -float(banca.stop_loss):
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

    banca.saldo_atual = float(banca.saldo_atual) - dados.valor
    ref = float(banca.saldo_referencia) if banca.saldo_referencia is not None else float(banca.saldo_inicial)
    banca.saldo_referencia = ref - dados.valor

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

    ref = float(banca.saldo_referencia) if banca.saldo_referencia is not None else float(banca.saldo_inicial)
    if aposta.resultado == ResultadoApostaEnum.GANHA:
        banca.saldo_atual = float(banca.saldo_atual) - valor * odd
        banca.saldo_referencia = ref - valor
    elif aposta.resultado == ResultadoApostaEnum.PERDIDA:
        banca.saldo_referencia = ref - valor
    elif aposta.resultado == ResultadoApostaEnum.CANCELADA:
        banca.saldo_atual = float(banca.saldo_atual) - valor
        banca.saldo_referencia = ref - valor

    if novo == ResultadoApostaEnum.GANHA:
        retorno = valor * odd
        banca.saldo_atual = float(banca.saldo_atual) + retorno
        banca.saldo_referencia = float(banca.saldo_referencia) + valor
        aposta.lucro_prejuizo = retorno - valor
        mov = TipoMovimentacaoEnum.LUCRO
        mov_valor = retorno
    elif novo == ResultadoApostaEnum.PERDIDA:
        banca.saldo_referencia = float(banca.saldo_referencia) + valor
        aposta.lucro_prejuizo = -valor
        mov = TipoMovimentacaoEnum.PREJUIZO
        mov_valor = valor
    elif novo == ResultadoApostaEnum.CANCELADA:
        banca.saldo_atual = float(banca.saldo_atual) + valor
        banca.saldo_referencia = float(banca.saldo_referencia) + valor
        aposta.lucro_prejuizo = 0
        mov = TipoMovimentacaoEnum.DEPOSITO
        mov_valor = valor
    else:
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


def _serializar_item(item: ItemApostaMultipla) -> dict:
    return {
        "id": item.id,
        "multipla_id": item.multipla_id,
        "partida_id": item.partida_id,
        "tipo_aposta": item.tipo_aposta,
        "odd": float(item.odd),
    }


def _serializar_multipla(m: ApostaMultipla) -> dict:
    return {
        "id": m.id,
        "banca_id": m.banca_id,
        "usuario_id": m.usuario_id,
        "valor": float(m.valor),
        "odd_total": float(m.odd_total),
        "lucro_prejuizo": float(m.lucro_prejuizo) if m.lucro_prejuizo is not None else None,
        "resultado": m.resultado.value if m.resultado else None,
        "data": m.data.isoformat() if m.data else None,
        "itens": [_serializar_item(i) for i in m.itens],
    }


@app.post("/aposta-multipla")
def criar_aposta_multipla(dados: CriarApostaMultipla):
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
    if len(dados.itens) < 2:
        raise HTTPException(status_code=400, detail="Múltipla requer pelo menos 2 seleções")
    for item in dados.itens:
        if item.odd <= 1:
            raise HTTPException(status_code=400, detail=f"Odd inválida: {item.odd}")

    odd_total = 1.0
    for item in dados.itens:
        odd_total *= item.odd
    odd_total = round(odd_total, 2)

    multipla = ApostaMultipla(
        banca_id=dados.banca_id,
        usuario_id=dados.usuario_id,
        valor=dados.valor,
        odd_total=odd_total,
        resultado=ResultadoApostaEnum.PENDENTE,
    )
    db.add(multipla)
    db.flush()

    for item in dados.itens:
        db.add(ItemApostaMultipla(
            multipla_id=multipla.id,
            partida_id=item.partida_id,
            tipo_aposta=item.tipo_aposta,
            odd=item.odd,
        ))

    banca.saldo_atual = float(banca.saldo_atual) - dados.valor
    ref = float(banca.saldo_referencia) if banca.saldo_referencia is not None else float(banca.saldo_inicial)
    banca.saldo_referencia = ref - dados.valor

    db.commit()
    db.refresh(multipla)
    db.refresh(banca)

    db.add(HistoricoBanca(
        aposta_multipla_id=multipla.id,
        usuario_id=dados.usuario_id,
        saldo=banca.saldo_atual,
        valor=dados.valor,
        tipo_movimentacao=TipoMovimentacaoEnum.ENTRADA_APOSTA,
    ))
    db.commit()

    return {
        "multipla": _serializar_multipla(multipla),
        "banca": _serializar_banca(banca),
        "flags": _status_banca(banca),
    }


@app.delete("/aposta-multipla/{multipla_id}/item/{item_id}")
def remover_item_multipla(multipla_id: int, item_id: int):
    db = SessionLocal()

    multipla = db.get(ApostaMultipla, multipla_id)
    if not multipla:
        raise HTTPException(status_code=404, detail="Aposta múltipla não encontrada")
    if multipla.resultado != ResultadoApostaEnum.PENDENTE:
        raise HTTPException(status_code=400, detail="Só é possível remover itens de múltiplas pendentes")

    item = db.get(ItemApostaMultipla, item_id)
    if not item or item.multipla_id != multipla_id:
        raise HTTPException(status_code=404, detail="Item não encontrado nesta múltipla")

    db.delete(item)
    db.flush()

    db.refresh(multipla)
    banca = db.get(Banca, multipla.banca_id)

    if len(multipla.itens) == 0:
        multipla.resultado = ResultadoApostaEnum.CANCELADA
        multipla.lucro_prejuizo = 0
        banca.saldo_atual = float(banca.saldo_atual) + float(multipla.valor)
        banca.saldo_referencia = float(banca.saldo_referencia) + float(multipla.valor)
        db.commit()
        db.refresh(multipla)
        db.refresh(banca)
        db.add(HistoricoBanca(
            aposta_multipla_id=multipla.id,
            usuario_id=multipla.usuario_id,
            saldo=banca.saldo_atual,
            valor=multipla.valor,
            tipo_movimentacao=TipoMovimentacaoEnum.DEPOSITO,
        ))
        db.commit()
    else:
        nova_odd = 1.0
        for i in multipla.itens:
            nova_odd *= float(i.odd)
        multipla.odd_total = round(nova_odd, 2)
        db.commit()
        db.refresh(multipla)
        db.refresh(banca)

    return {
        "multipla": _serializar_multipla(multipla),
        "banca": _serializar_banca(banca),
        "flags": _status_banca(banca),
    }


@app.patch("/aposta-multipla/{multipla_id}/resultado")
def resultado_aposta_multipla(multipla_id: int, dados: ResultadoApostaMultipla):
    db = SessionLocal()

    multipla = db.get(ApostaMultipla, multipla_id)
    if not multipla:
        raise HTTPException(status_code=404, detail="Aposta múltipla não encontrada")

    banca = db.get(Banca, multipla.banca_id)
    if not banca:
        raise HTTPException(status_code=404, detail="Banca não encontrada")

    try:
        novo = ResultadoApostaEnum(dados.resultado.upper())
    except ValueError:
        raise HTTPException(status_code=400, detail="Resultado inválido")

    valor = float(multipla.valor)
    odd = float(multipla.odd_total)

    ref = float(banca.saldo_referencia) if banca.saldo_referencia is not None else float(banca.saldo_inicial)
    if multipla.resultado == ResultadoApostaEnum.GANHA:
        banca.saldo_atual = float(banca.saldo_atual) - valor * odd
        banca.saldo_referencia = ref - valor
    elif multipla.resultado == ResultadoApostaEnum.PERDIDA:
        banca.saldo_referencia = ref - valor
    elif multipla.resultado == ResultadoApostaEnum.CANCELADA:
        banca.saldo_atual = float(banca.saldo_atual) - valor
        banca.saldo_referencia = ref - valor

    if novo == ResultadoApostaEnum.GANHA:
        retorno = valor * odd
        banca.saldo_atual = float(banca.saldo_atual) + retorno
        banca.saldo_referencia = float(banca.saldo_referencia) + valor
        multipla.lucro_prejuizo = retorno - valor
        mov = TipoMovimentacaoEnum.LUCRO
        mov_valor = retorno
    elif novo == ResultadoApostaEnum.PERDIDA:
        banca.saldo_referencia = float(banca.saldo_referencia) + valor
        multipla.lucro_prejuizo = -valor
        mov = TipoMovimentacaoEnum.PREJUIZO
        mov_valor = valor
    elif novo == ResultadoApostaEnum.CANCELADA:
        banca.saldo_atual = float(banca.saldo_atual) + valor
        banca.saldo_referencia = float(banca.saldo_referencia) + valor
        multipla.lucro_prejuizo = 0
        mov = TipoMovimentacaoEnum.DEPOSITO
        mov_valor = valor
    else:
        multipla.lucro_prejuizo = None
        mov = None
        mov_valor = 0

    multipla.resultado = novo
    db.commit()
    db.refresh(multipla)
    db.refresh(banca)

    if mov is not None:
        db.add(HistoricoBanca(
            aposta_multipla_id=multipla.id,
            usuario_id=multipla.usuario_id,
            saldo=banca.saldo_atual,
            valor=mov_valor,
            tipo_movimentacao=mov,
        ))
        db.commit()

    return {
        "multipla": _serializar_multipla(multipla),
        "banca": _serializar_banca(banca),
        "flags": _status_banca(banca),
    }


@app.delete("/admin/limpar-dados")
def limpar_dados(usuario_id: Optional[int] = None):
    db = SessionLocal()

    if usuario_id is not None:
        bancas_ids = [b.id for b in db.query(Banca).filter(Banca.usuario_id == usuario_id).all()]
        apostas_ids = [a.id for a in db.query(Aposta).filter(Aposta.banca_id.in_(bancas_ids)).all()]
        multiplas_ids = [m.id for m in db.query(ApostaMultipla).filter(ApostaMultipla.banca_id.in_(bancas_ids)).all()]

        db.query(HistoricoBanca).filter(HistoricoBanca.usuario_id == usuario_id).delete(synchronize_session=False)
        db.query(ItemApostaMultipla).filter(ItemApostaMultipla.multipla_id.in_(multiplas_ids)).delete(synchronize_session=False)
        db.query(ApostaMultipla).filter(ApostaMultipla.banca_id.in_(bancas_ids)).delete(synchronize_session=False)
        db.query(Aposta).filter(Aposta.banca_id.in_(bancas_ids)).delete(synchronize_session=False)
        db.query(Banca).filter(Banca.usuario_id == usuario_id).delete(synchronize_session=False)
    else:
        db.query(HistoricoBanca).delete(synchronize_session=False)
        db.query(ItemApostaMultipla).delete(synchronize_session=False)
        db.query(ApostaMultipla).delete(synchronize_session=False)
        db.query(Aposta).delete(synchronize_session=False)
        db.query(Banca).delete(synchronize_session=False)

    db.commit()
    return {"mensagem": "Dados removidos com sucesso"}


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


def _perfil_risco_usuario(db, usuario_id: Optional[int]) -> Optional[str]:
    if usuario_id is None:
        return None
    usuario = db.get(Usuario, usuario_id)
    if usuario and usuario.perfil_risco:
        return usuario.perfil_risco.value
    return None


@app.get("/partidas/proximas")
def partidas_proximas(limite: int = 10, usuario_id: Optional[int] = None):
    db = SessionLocal()

    perfil_risco = _perfil_risco_usuario(db, usuario_id)

    partidas = db.query(Partida).filter(
        Partida.gols_casa.is_(None),
        Partida.data >= datetime.utcnow()
    ).order_by(Partida.data.asc()).limit(limite).all()

    resultado = []
    for p in partidas:
        casa = db.get(Time, p.time_casa_id)
        fora = db.get(Time, p.time_fora_id)
        rec = recomendar(db, p, perfil_risco)
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

    rec = recomendar(db, p)

    return {
        "partida": _serializar_partida(
            p,
            casa.nome if casa else "Casa",
            fora.nome if fora else "Fora",
        ),
        "odds": rec["odds"],
    }


@app.get("/partidas/{partida_id}/recomendacao")
def recomendacao_partida(partida_id: int, usuario_id: Optional[int] = None):
    db = SessionLocal()
    p = db.get(Partida, partida_id)
    if not p:
        raise HTTPException(status_code=404, detail="Partida não encontrada")

    perfil_risco = _perfil_risco_usuario(db, usuario_id)

    return recomendar(db, p, perfil_risco)
