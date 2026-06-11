from app.database import SessionLocal
from app.models.pergunta import Pergunta
from app.models.alternativa import Alternativa

db = SessionLocal()

perguntas = [
    {
        "texto": "Com que frequência você aposta?",
        "alternativas": [
            "1 vez na semana",
            "3 a 4 vezes na semana",
            "Todos os dias"
        ]
    },
    {
        "texto": "Há quanto tempo você aposta?",
        "alternativas": [
            "Comecei agora",
            "Menos de 2 anos",
            "Mais de 2 anos"
        ]
    },
    {
        "texto": "Você costuma definir um limite de perda?",
        "alternativas": [
            "Sempre",
            "Nunca",
            "Às vezes"
        ]
    },
    {
        "texto": "Qual tipo de aposta você prefere?",
        "alternativas": [
            "Simples",
            "Múltiplas",
            "Ambas"
        ]
    },
    {
        "texto": "Qual seu principal objetivo ao apostar?",
        "alternativas": [
            "Diversão",
            "Renda extra",
            "Lucro constante"
        ]
    }
]

for pergunta_data in perguntas:

    pergunta = Pergunta(
        texto=pergunta_data["texto"]
    )

    db.add(pergunta)
    db.commit()
    db.refresh(pergunta)

    for indice, alternativa_texto in enumerate(
        pergunta_data["alternativas"],
        start=1
    ):

        alternativa = Alternativa(
            pergunta_id=pergunta.id,
            texto=alternativa_texto,
            peso=indice
        )

        db.add(alternativa)

    db.commit()

print("Perguntas cadastradas com sucesso!")