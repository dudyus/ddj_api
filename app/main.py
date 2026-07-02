import os
import bcrypt
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from dotenv import load_dotenv

load_dotenv()

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
from app.schemas.usuario import EditarNome, EditarEmail, AlterarSenha, EditarFoto

from app.services.football_data_service import buscar_partidas
from app.services.importar_partidas_service import importar_partidas
from app.services.recomendacao_service import recomendar

# ── JWT ────────────────────────────────────────────────────────────────────────
JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-MUDE-EM-PRODUCAO")
JWT_ALGORITHM = "HS256"

_bearer = HTTPBearer()


def _criar_token(usuario_id: int) -> str:
    return jwt.encode({"sub": str(usuario_id)}, JWT_SECRET, algorithm=JWT_ALGORITHM)


def _get_usuario_logado(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> int:
    try:
        payload = jwt.decode(
            credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM]
        )
        return int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise HTTPException(status_code=401, detail="Token inválido ou expirado")


# ── Bcrypt ─────────────────────────────────────────────────────────────────────
def _hash_senha(senha: str) -> str:
    return bcrypt.hashpw(senha.encode(), bcrypt.gensalt()).decode()


def _verificar_senha(senha: str, hash_salvo: str) -> bool:
    """Verifica senha; migra plaintext → bcrypt automaticamente na primeira vez."""
    if hash_salvo.startswith("$2b$") or hash_salvo.startswith("$2a$"):
        return bcrypt.checkpw(senha.encode(), hash_salvo.encode())
    # Senha antiga em plaintext: compara e re-hasheia
    return hash_salvo == senha


def _verificar_e_migrar(db, usuario: Usuario, senha: str) -> bool:
    hash_salvo = usuario.senha
    if hash_salvo.startswith("$2b$") or hash_salvo.startswith("$2a$"):
        return bcrypt.checkpw(senha.encode(), hash_salvo.encode())
    if hash_salvo == senha:
        usuario.senha = _hash_senha(senha)
        db.commit()
        return True
    return False


# ── Rate limiter ───────────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)

# ── App ────────────────────────────────────────────────────────────────────────
app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS", "http://localhost:3000"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Helpers de autorização ─────────────────────────────────────────────────────
def _exigir_dono_usuario(usuario_id_path: int, usuario_logado: int) -> None:
    if usuario_id_path != usuario_logado:
        raise HTTPException(status_code=403, detail="Acesso negado")


def _exigir_dono_banca(banca: Banca, usuario_logado: int) -> None:
    if banca.usuario_id != usuario_logado:
        raise HTTPException(status_code=403, detail="Acesso negado")


def _exigir_dono_aposta(aposta: Aposta, usuario_logado: int) -> None:
    if aposta.usuario_id != usuario_logado:
        raise HTTPException(status_code=403, detail="Acesso negado")


def _exigir_dono_multipla(multipla: ApostaMultipla, usuario_logado: int) -> None:
    if multipla.usuario_id != usuario_logado:
        raise HTTPException(status_code=403, detail="Acesso negado")


# ── Serializers ────────────────────────────────────────────────────────────────
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


def _serializar_item(item: ItemApostaMultipla) -> dict:
    return {
        "id": item.id,
        "multipla_id": item.multipla_id,
        "partida_id": item.partida_id,
        "tipo_aposta": item.tipo_aposta,
        "odd": float(item.odd),
        "resultado": item.resultado.value if item.resultado else None,
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


def _derivar_resultado_multipla(itens: list[ItemApostaMultipla]) -> ResultadoApostaEnum:
    if any(i.resultado == ResultadoApostaEnum.PERDIDA for i in itens):
        return ResultadoApostaEnum.PERDIDA
    if itens and all(i.resultado == ResultadoApostaEnum.GANHA for i in itens):
        return ResultadoApostaEnum.GANHA
    return ResultadoApostaEnum.PENDENTE


def _liquidar_multipla(db, multipla: ApostaMultipla, banca: Banca, novo: ResultadoApostaEnum) -> None:
    if novo == multipla.resultado:
        return

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


def _perfil_risco_usuario(db, usuario_id: Optional[int]) -> Optional[str]:
    if usuario_id is None:
        return None
    usuario = db.get(Usuario, usuario_id)
    if usuario and usuario.perfil_risco:
        return usuario.perfil_risco.value
    return None


# ── Endpoints públicos ─────────────────────────────────────────────────────────
@app.get("/")
def home():
    return {"mensagem": "API do TCC funcionando"}


@app.get("/partidas")
def partidas():
    return buscar_partidas()


@app.get("/importar")
def importar():
    return importar_partidas()


@app.get("/perguntas")
def listar_perguntas():
    db = SessionLocal()
    perguntas = db.query(Pergunta).all()
    return [
        {
            "id": p.id,
            "texto": p.texto,
            "alternativas": [{"id": a.id, "texto": a.texto} for a in p.alternativas],
        }
        for p in perguntas
    ]


@app.get("/partidas/proximas")
def partidas_proximas(limite: int = 10, usuario_id: Optional[int] = None):
    db = SessionLocal()
    perfil_risco = _perfil_risco_usuario(db, usuario_id)
    partidas = (
        db.query(Partida)
        .filter(Partida.gols_casa.is_(None), Partida.data >= datetime.utcnow())
        .order_by(Partida.data.asc())
        .limit(limite)
        .all()
    )
    resultado = []
    for p in partidas:
        casa = db.get(Time, p.time_casa_id)
        fora = db.get(Time, p.time_fora_id)
        rec = recomendar(db, p, perfil_risco)
        resultado.append({
            **_serializar_partida(p, casa.nome if casa else "Casa", fora.nome if fora else "Fora"),
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
        "partida": _serializar_partida(p, casa.nome if casa else "Casa", fora.nome if fora else "Fora"),
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


# ── Autenticação ───────────────────────────────────────────────────────────────
@app.post("/cadastro")
def cadastrar_usuario(dados: Cadastro):
    db = SessionLocal()
    if db.query(Usuario).filter(Usuario.email == dados.email).first():
        raise HTTPException(status_code=400, detail="E-mail já cadastrado")

    novo_usuario = Usuario(
        nome=dados.nome,
        email=dados.email,
        senha=_hash_senha(dados.senha),
    )
    db.add(novo_usuario)
    db.commit()
    db.refresh(novo_usuario)

    token = _criar_token(novo_usuario.id)
    return {
        "id": novo_usuario.id,
        "nome": novo_usuario.nome,
        "email": novo_usuario.email,
        "token": token,
        "mensagem": "Usuário cadastrado com sucesso",
    }


@app.post("/login")
@limiter.limit("10/minute")
async def login(request: Request, dados: Login):
    db = SessionLocal()
    usuario = db.query(Usuario).filter(Usuario.email == dados.email).first()

    if not usuario or not _verificar_e_migrar(db, usuario, dados.senha):
        return {"sucesso": False, "mensagem": "Email ou senha inválidos"}

    token = _criar_token(usuario.id)
    return {
        "sucesso": True,
        "mensagem": "Login realizado com sucesso",
        "token": token,
        "usuario": {
            "id": usuario.id,
            "nome": usuario.nome,
            "email": usuario.email,
            "foto_perfil": usuario.foto_perfil,
            "perfil_risco": usuario.perfil_risco.value if usuario.perfil_risco else None,
        },
    }


# ── Usuário (protegido) ────────────────────────────────────────────────────────
@app.patch("/usuario/{usuario_id}/nome")
def editar_nome(
    usuario_id: int,
    dados: EditarNome,
    usuario_logado: int = Depends(_get_usuario_logado),
):
    _exigir_dono_usuario(usuario_id, usuario_logado)
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
        "foto_perfil": usuario.foto_perfil,
        "perfil_risco": usuario.perfil_risco.value if usuario.perfil_risco else None,
    }


@app.patch("/usuario/{usuario_id}/email")
def editar_email(
    usuario_id: int,
    dados: EditarEmail,
    usuario_logado: int = Depends(_get_usuario_logado),
):
    _exigir_dono_usuario(usuario_id, usuario_logado)
    db = SessionLocal()
    usuario = db.get(Usuario, usuario_id)
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    novo = dados.novo_email.strip().lower()
    if not novo:
        raise HTTPException(status_code=400, detail="Email não pode ser vazio")
    if db.query(Usuario).filter(Usuario.email == novo, Usuario.id != usuario_id).first():
        raise HTTPException(status_code=400, detail="E-mail já está em uso")
    usuario.email = novo
    db.commit()
    db.refresh(usuario)
    return {
        "id": usuario.id,
        "nome": usuario.nome,
        "email": usuario.email,
        "foto_perfil": usuario.foto_perfil,
        "perfil_risco": usuario.perfil_risco.value if usuario.perfil_risco else None,
    }


@app.patch("/usuario/{usuario_id}/foto")
def editar_foto(
    usuario_id: int,
    dados: EditarFoto,
    usuario_logado: int = Depends(_get_usuario_logado),
):
    _exigir_dono_usuario(usuario_id, usuario_logado)
    db = SessionLocal()
    usuario = db.get(Usuario, usuario_id)
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    if len(dados.foto_perfil) > 3_000_000:
        raise HTTPException(status_code=400, detail="Imagem muito grande")
    usuario.foto_perfil = dados.foto_perfil
    db.commit()
    db.refresh(usuario)
    return {
        "id": usuario.id,
        "nome": usuario.nome,
        "email": usuario.email,
        "foto_perfil": usuario.foto_perfil,
        "perfil_risco": usuario.perfil_risco.value if usuario.perfil_risco else None,
    }


@app.patch("/usuario/{usuario_id}/senha")
def alterar_senha(
    usuario_id: int,
    dados: AlterarSenha,
    usuario_logado: int = Depends(_get_usuario_logado),
):
    _exigir_dono_usuario(usuario_id, usuario_logado)
    db = SessionLocal()
    usuario = db.get(Usuario, usuario_id)
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    if not _verificar_e_migrar(db, usuario, dados.senha_atual):
        raise HTTPException(status_code=400, detail="Senha atual incorreta")
    nova = dados.nova_senha.strip()
    if len(nova) < 6:
        raise HTTPException(status_code=400, detail="Nova senha deve ter pelo menos 6 caracteres")
    usuario.senha = _hash_senha(nova)
    db.commit()
    return {"mensagem": "Senha alterada com sucesso"}


@app.delete("/usuario/{usuario_id}")
def deletar_usuario(
    usuario_id: int,
    usuario_logado: int = Depends(_get_usuario_logado),
):
    _exigir_dono_usuario(usuario_id, usuario_logado)
    db = SessionLocal()
    usuario = db.get(Usuario, usuario_id)
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    db.query(HistoricoBanca).filter(HistoricoBanca.usuario_id == usuario_id).delete()

    from app.models.aposta_multipla import ItemApostaMultipla as _Item, ApostaMultipla as _Multi
    multiplas_ids = [m.id for m in db.query(_Multi).filter(_Multi.usuario_id == usuario_id).all()]
    if multiplas_ids:
        db.query(_Item).filter(_Item.multipla_id.in_(multiplas_ids)).delete()
    db.query(_Multi).filter(_Multi.usuario_id == usuario_id).delete()
    db.query(Aposta).filter(Aposta.usuario_id == usuario_id).delete()
    db.query(Banca).filter(Banca.usuario_id == usuario_id).delete()

    from app.models.resposta_usuario import RespostaUsuario as _Resp
    from app.models.anamnese import Anamnese as _Anam
    anamneses_ids = [a.id for a in db.query(_Anam).filter(_Anam.usuario_id == usuario_id).all()]
    if anamneses_ids:
        db.query(_Resp).filter(_Resp.anamnese_id.in_(anamneses_ids)).delete()
    db.query(_Anam).filter(_Anam.usuario_id == usuario_id).delete()

    from app.models.recomendacao import Recomendacao as _Rec
    db.query(_Rec).filter(_Rec.usuario_id == usuario_id).delete()

    db.delete(usuario)
    db.commit()
    return {"mensagem": "Conta excluída com sucesso"}


# ── Anamnese (protegida) ───────────────────────────────────────────────────────
@app.post("/anamnese")
def responder_anamnese(
    dados: AnamneseSchema,
    usuario_logado: int = Depends(_get_usuario_logado),
):
    _exigir_dono_usuario(dados.usuario_id, usuario_logado)
    db = SessionLocal()
    anamnese = Anamnese(usuario_id=dados.usuario_id, perfil_calculado=None)
    db.add(anamnese)
    db.commit()
    db.refresh(anamnese)

    for resposta in dados.respostas:
        db.add(RespostaUsuario(
            anamnese_id=anamnese.id,
            pergunta_id=resposta.pergunta_id,
            alternativa_id=resposta.alternativa_id,
        ))
    db.commit()
    return {"mensagem": "Anamnese salva com sucesso", "anamnese_id": anamnese.id}


@app.get("/anamnese/resultado/{anamnese_id}")
def calcular_resultado_anamnese(
    anamnese_id: int,
    usuario_logado: int = Depends(_get_usuario_logado),
):
    db = SessionLocal()
    anamnese = db.query(Anamnese).filter(Anamnese.id == anamnese_id).first()
    if not anamnese:
        raise HTTPException(status_code=404, detail="Anamnese não encontrada")
    _exigir_dono_usuario(anamnese.usuario_id, usuario_logado)

    respostas = db.query(RespostaUsuario).filter(RespostaUsuario.anamnese_id == anamnese_id).all()
    total = 0
    for r in respostas:
        alt = db.query(Alternativa).filter(Alternativa.id == r.alternativa_id).first()
        if alt:
            total += alt.peso

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
            "foto_perfil": usuario.foto_perfil,
            "perfil_risco": usuario.perfil_risco.value if usuario.perfil_risco else None,
        } if usuario else None,
    }


# ── Banca (protegida) ──────────────────────────────────────────────────────────
@app.get("/banca/ativa/{usuario_id}")
def banca_ativa(
    usuario_id: int,
    usuario_logado: int = Depends(_get_usuario_logado),
):
    _exigir_dono_usuario(usuario_id, usuario_logado)
    db = SessionLocal()
    banca = (
        db.query(Banca)
        .filter(Banca.usuario_id == usuario_id, Banca.status == StatusBancaEnum.ATIVA)
        .order_by(Banca.id.desc())
        .first()
    )
    if not banca:
        return {"banca": None}

    apostas = db.query(Aposta).filter(Aposta.banca_id == banca.id).order_by(Aposta.id.asc()).all()
    multiplas = db.query(ApostaMultipla).filter(ApostaMultipla.banca_id == banca.id).order_by(ApostaMultipla.id.asc()).all()

    return {
        "banca": _serializar_banca(banca),
        "apostas": [_serializar_aposta(a) for a in apostas],
        "multiplas": [_serializar_multipla(m) for m in multiplas],
        "flags": _status_banca(banca),
    }


@app.post("/banca")
def criar_banca(
    dados: CriarBanca,
    usuario_logado: int = Depends(_get_usuario_logado),
):
    _exigir_dono_usuario(dados.usuario_id, usuario_logado)
    db = SessionLocal()
    if dados.saldo_inicial <= 0:
        raise HTTPException(status_code=400, detail="Saldo inicial deve ser maior que 0")

    for b in db.query(Banca).filter(Banca.usuario_id == dados.usuario_id, Banca.status == StatusBancaEnum.ATIVA).all():
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
def editar_banca(
    banca_id: int,
    dados: EditarBanca,
    usuario_logado: int = Depends(_get_usuario_logado),
):
    db = SessionLocal()
    banca = db.get(Banca, banca_id)
    if not banca:
        raise HTTPException(status_code=404, detail="Banca não encontrada")
    _exigir_dono_banca(banca, usuario_logado)

    if dados.meta_diaria is not None:
        banca.meta_diaria = dados.meta_diaria
    if dados.stop_loss is not None:
        banca.stop_loss = dados.stop_loss

    db.commit()
    db.refresh(banca)
    return {"banca": _serializar_banca(banca), "flags": _status_banca(banca)}


@app.post("/banca/{banca_id}/depositar")
def depositar_banca(
    banca_id: int,
    dados: MovimentarBanca,
    usuario_logado: int = Depends(_get_usuario_logado),
):
    db = SessionLocal()
    banca = db.get(Banca, banca_id)
    if not banca:
        raise HTTPException(status_code=404, detail="Banca não encontrada")
    _exigir_dono_banca(banca, usuario_logado)
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
def sacar_banca(
    banca_id: int,
    dados: MovimentarBanca,
    usuario_logado: int = Depends(_get_usuario_logado),
):
    db = SessionLocal()
    banca = db.get(Banca, banca_id)
    if not banca:
        raise HTTPException(status_code=404, detail="Banca não encontrada")
    _exigir_dono_banca(banca, usuario_logado)
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
def fechar_banca(
    banca_id: int,
    usuario_logado: int = Depends(_get_usuario_logado),
):
    db = SessionLocal()
    banca = db.get(Banca, banca_id)
    if not banca:
        raise HTTPException(status_code=404, detail="Banca não encontrada")
    _exigir_dono_banca(banca, usuario_logado)

    banca.status = StatusBancaEnum.FECHADA
    banca.data_fechamento = datetime.utcnow()
    db.commit()
    db.refresh(banca)
    return {"banca": _serializar_banca(banca)}


@app.get("/banca/historico/{usuario_id}")
def historico_bancas(
    usuario_id: int,
    usuario_logado: int = Depends(_get_usuario_logado),
):
    _exigir_dono_usuario(usuario_id, usuario_logado)
    db = SessionLocal()
    bancas = (
        db.query(Banca)
        .filter(Banca.usuario_id == usuario_id, Banca.status == StatusBancaEnum.FECHADA)
        .order_by(Banca.data_fechamento.desc().nullslast(), Banca.id.desc())
        .all()
    )

    resultado = []
    for banca in bancas:
        apostas = db.query(Aposta).filter(Aposta.banca_id == banca.id).order_by(Aposta.id.asc()).all()
        multiplas = db.query(ApostaMultipla).filter(ApostaMultipla.banca_id == banca.id).order_by(ApostaMultipla.id.asc()).all()

        ganhas = (
            sum(1 for a in apostas if a.resultado == ResultadoApostaEnum.GANHA)
            + sum(1 for m in multiplas if m.resultado == ResultadoApostaEnum.GANHA)
        )
        perdidas = (
            sum(1 for a in apostas if a.resultado == ResultadoApostaEnum.PERDIDA)
            + sum(1 for m in multiplas if m.resultado == ResultadoApostaEnum.PERDIDA)
        )

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
            "multiplas": [_serializar_multipla(m) for m in multiplas],
        })

    return {"historico": resultado}


# ── Apostas simples (protegidas) ───────────────────────────────────────────────
@app.post("/aposta")
def criar_aposta(
    dados: CriarAposta,
    usuario_logado: int = Depends(_get_usuario_logado),
):
    _exigir_dono_usuario(dados.usuario_id, usuario_logado)
    db = SessionLocal()
    banca = db.get(Banca, dados.banca_id)
    if not banca:
        raise HTTPException(status_code=404, detail="Banca não encontrada")
    _exigir_dono_banca(banca, usuario_logado)
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
    return {"aposta": _serializar_aposta(aposta), "banca": _serializar_banca(banca), "flags": _status_banca(banca)}


@app.patch("/aposta/{aposta_id}/resultado")
def resultado_aposta(
    aposta_id: int,
    dados: ResultadoAposta,
    usuario_logado: int = Depends(_get_usuario_logado),
):
    db = SessionLocal()
    aposta = db.get(Aposta, aposta_id)
    if not aposta:
        raise HTTPException(status_code=404, detail="Aposta não encontrada")
    _exigir_dono_aposta(aposta, usuario_logado)

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

    return {"aposta": _serializar_aposta(aposta), "banca": _serializar_banca(banca), "flags": _status_banca(banca)}


# ── Apostas múltiplas (protegidas) ─────────────────────────────────────────────
@app.post("/aposta-multipla")
def criar_aposta_multipla(
    dados: CriarApostaMultipla,
    usuario_logado: int = Depends(_get_usuario_logado),
):
    _exigir_dono_usuario(dados.usuario_id, usuario_logado)
    db = SessionLocal()
    banca = db.get(Banca, dados.banca_id)
    if not banca:
        raise HTTPException(status_code=404, detail="Banca não encontrada")
    _exigir_dono_banca(banca, usuario_logado)
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
    return {"multipla": _serializar_multipla(multipla), "banca": _serializar_banca(banca), "flags": _status_banca(banca)}


@app.delete("/aposta-multipla/{multipla_id}/item/{item_id}")
def remover_item_multipla(
    multipla_id: int,
    item_id: int,
    usuario_logado: int = Depends(_get_usuario_logado),
):
    db = SessionLocal()
    multipla = db.get(ApostaMultipla, multipla_id)
    if not multipla:
        raise HTTPException(status_code=404, detail="Aposta múltipla não encontrada")
    _exigir_dono_multipla(multipla, usuario_logado)
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

    return {"multipla": _serializar_multipla(multipla), "banca": _serializar_banca(banca), "flags": _status_banca(banca)}


@app.patch("/aposta-multipla/{multipla_id}/resultado")
def resultado_aposta_multipla(
    multipla_id: int,
    dados: ResultadoApostaMultipla,
    usuario_logado: int = Depends(_get_usuario_logado),
):
    db = SessionLocal()
    multipla = db.get(ApostaMultipla, multipla_id)
    if not multipla:
        raise HTTPException(status_code=404, detail="Aposta múltipla não encontrada")
    _exigir_dono_multipla(multipla, usuario_logado)

    banca = db.get(Banca, multipla.banca_id)
    if not banca:
        raise HTTPException(status_code=404, detail="Banca não encontrada")

    try:
        novo = ResultadoApostaEnum(dados.resultado.upper())
    except ValueError:
        raise HTTPException(status_code=400, detail="Resultado inválido")
    if novo != ResultadoApostaEnum.CANCELADA:
        raise HTTPException(
            status_code=400,
            detail="Ganha/Perdida são definidos automaticamente pelo resultado das seleções",
        )
    if multipla.resultado != ResultadoApostaEnum.PENDENTE:
        raise HTTPException(status_code=400, detail="Só é possível cancelar múltiplas pendentes")

    _liquidar_multipla(db, multipla, banca, novo)
    db.refresh(multipla)
    db.refresh(banca)
    return {"multipla": _serializar_multipla(multipla), "banca": _serializar_banca(banca), "flags": _status_banca(banca)}


@app.patch("/aposta-multipla/{multipla_id}/item/{item_id}/resultado")
def resultado_item_multipla(
    multipla_id: int,
    item_id: int,
    dados: ResultadoApostaMultipla,
    usuario_logado: int = Depends(_get_usuario_logado),
):
    db = SessionLocal()
    multipla = db.get(ApostaMultipla, multipla_id)
    if not multipla:
        raise HTTPException(status_code=404, detail="Aposta múltipla não encontrada")
    _exigir_dono_multipla(multipla, usuario_logado)

    item = db.get(ItemApostaMultipla, item_id)
    if not item or item.multipla_id != multipla_id:
        raise HTTPException(status_code=404, detail="Item não encontrado nesta múltipla")

    banca = db.get(Banca, multipla.banca_id)
    if not banca:
        raise HTTPException(status_code=404, detail="Banca não encontrada")

    try:
        novo_item = ResultadoApostaEnum(dados.resultado.upper())
    except ValueError:
        raise HTTPException(status_code=400, detail="Resultado inválido")
    if novo_item == ResultadoApostaEnum.CANCELADA:
        raise HTTPException(status_code=400, detail="Para cancelar uma seleção, remova o item da múltipla")

    item.resultado = novo_item
    db.commit()
    db.refresh(multipla)

    novo_multipla = _derivar_resultado_multipla(multipla.itens)
    _liquidar_multipla(db, multipla, banca, novo_multipla)
    db.refresh(multipla)
    db.refresh(banca)
    return {"multipla": _serializar_multipla(multipla), "banca": _serializar_banca(banca), "flags": _status_banca(banca)}


# ── Helpers de serialização de partida ────────────────────────────────────────
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
